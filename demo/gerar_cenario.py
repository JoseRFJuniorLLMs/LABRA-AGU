"""
Gerador do cenário pericial da DEMO — dados 100% fictícios e juridicamente
seguros (LGPD), mas com CPF/CNPJ de dígitos verificadores VÁLIDOS (o
agente valida-os em agent/entities.py).

A narrativa é uma triangulação de blindagem patrimonial PARTIDA por quatro
fontes — nenhuma sozinha contém a fraude; só o grafo de caso consolidado a
fecha:

  Junta Comercial (SQL)  : devedor vende quotas para a offshore
  Cartório (SQL)         : a offshore nomeia o cunhado como procurador
  COAF (SQL)             : 3 transferências fracionadas (smurfing)
  Documento (pasta)      : o vínculo familiar + a véspera da penhora

As frases (templates SQL e o texto do documento) seguem EXATAMENTE o que o
parser determinístico do agente reconhece, de modo que os quatro padrões
disparam: triangulacao_offshore (CRÍTICA), laranja_familiar (ALTA),
fracionamento (ALTA) e vespera_constricao (CRÍTICA).

Usa apenas a biblioteca-padrão.
"""
import os
import random
import sqlite3
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ── geração de identificadores válidos (dígitos verificadores corretos) ──

def _dv_cpf(digits):
    s = sum(d * (len(digits) + 1 - i) for i, d in enumerate(digits))
    r = s % 11
    return 0 if r < 2 else 11 - r


def gerar_cpf_valido(rng):
    d = [rng.randint(0, 9) for _ in range(9)]
    d.append(_dv_cpf(d))
    d.append(_dv_cpf(d))
    return "".join(map(str, d))


def gerar_cnpj_valido(rng):
    d = [rng.randint(0, 9) for _ in range(12)]
    for pesos in ([5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2],
                  [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]):
        s = sum(x * p for x, p in zip(d, pesos))
        r = s % 11
        d.append(0 if r < 2 else 11 - r)
    return "".join(map(str, d))


def fmt_cpf(n):
    return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"


def fmt_cnpj(n):
    return f"{n[:2]}.{n[2:5]}.{n[5:8]}/{n[8:12]}-{n[12:]}"


def _mk_bank(path, table, cols, rows):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY AUTOINCREMENT, {cols})")
    names = ",".join(c.split()[0] for c in cols.split(","))
    ph = ",".join("?" * len(rows[0]))
    con.executemany(f"INSERT INTO {table} ({names}) VALUES ({ph})", rows)
    con.commit()
    con.close()


def construir(base_dir=None, seed=42):
    """Cria os bancos e o documento da demo. Devolve os ids gerados e os
    caminhos. `seed` fixo torna a demo reproduzível entre ensaios."""
    rng = random.Random(seed)
    here = base_dir or os.path.dirname(os.path.abspath(__file__))
    data = os.path.join(here, "demo_data")
    entrada = os.path.join(data, "entrada")
    os.makedirs(entrada, exist_ok=True)

    # Identidades fictícias com dígitos válidos.
    cpf_devedor = gerar_cpf_valido(rng)   # João Ribeiro (executado fiscal)
    cpf_laranja = gerar_cpf_valido(rng)   # Carlos Silva (cunhado / laranja)
    cnpj_offshore = gerar_cnpj_valido(rng)  # Atlantic Holdings Inc

    # ── JUNTA COMERCIAL: venda de quotas (CPF do devedor FORMATADO) ──
    # O CPF vai formatado aqui e CRU no documento → a resolução de entidades
    # tem de colapsá-los no mesmo nó (CPF:<digitos>).
    _mk_bank(
        os.path.join(data, "junta.db"), "alteracoes",
        "socio TEXT, destino TEXT, data TEXT",
        [(fmt_cpf(cpf_devedor), fmt_cnpj(cnpj_offshore), "2026-05-12")],
    )

    # ── CARTÓRIO: procuração com plenos poderes (offshore → laranja) ──
    _mk_bank(
        os.path.join(data, "cartorio.db"), "procuracoes",
        "outorgante TEXT, procurador TEXT, data TEXT",
        [(fmt_cnpj(cnpj_offshore), cpf_laranja, "2026-05-13")],
    )

    # ── COAF: 3 transferências fracionadas, valores DISTINTOS < R$ 10.000 ──
    # (valores distintos evitam qualquer dedup colapsar transações iguais)
    _mk_bank(
        os.path.join(data, "coaf.db"), "movimentacoes",
        "origem TEXT, destino TEXT, valor REAL, data TEXT",
        [
            (cpf_devedor, cpf_laranja, 9500.00, "2026-05-14"),
            (cpf_devedor, cpf_laranja, 8700.00, "2026-05-15"),
            (cpf_devedor, cpf_laranja, 9200.00, "2026-05-16"),
        ],
    )

    # ── DOCUMENTO: vínculo familiar + marco judicial iminente ──
    # Frase do vínculo no formato que _FAMILIA_RE reconhece:
    #   "<laranja> ... cunhado ... devedor <devedor>"
    # Marco no formato que _MARCO_RE reconhece: palavra-gatilho + data.
    doc = (
        "RELATÓRIO DE INVESTIGAÇÃO DE VÍNCULOS — LABRA / PGU-AGU.\n"
        f"Apurou-se que {cpf_laranja} é cunhado do devedor {cpf_devedor}, "
        "configurando interposição de pessoa (laranja familiar).\n"
        "Consta ordem de bloqueio judicial (penhora) prevista para "
        "05/06/2026, de conhecimento prévio do alvo.\n"
    )
    with open(os.path.join(entrada, "vinculos.txt"), "w", encoding="utf-8") as f:
        f.write(doc)

    ids = {
        "devedor": cpf_devedor,
        "devedor_fmt": fmt_cpf(cpf_devedor),
        "laranja": cpf_laranja,
        "offshore": cnpj_offshore,
        "offshore_fmt": fmt_cnpj(cnpj_offshore),
    }
    paths = {
        "data": data, "entrada": entrada,
        "junta": os.path.join(data, "junta.db"),
        "cartorio": os.path.join(data, "cartorio.db"),
        "coaf": os.path.join(data, "coaf.db"),
    }
    return ids, paths


if __name__ == "__main__":
    ids, paths = construir()
    print("=== CENÁRIO PERICIAL GERADO (dados fictícios, dígitos válidos) ===")
    print(f"  Devedor  (João Ribeiro) : {ids['devedor_fmt']}  [cru: {ids['devedor']}]")
    print(f"  Laranja  (Carlos, cunhado): {ids['laranja']}")
    print(f"  Offshore (Atlantic Holdings): {ids['offshore_fmt']}")
    print(f"\n  Bancos + documento em: {paths['data']}")
    # Comando de diretriz pronto a copiar (alvo = devedor).
    cmd = (f"python directive.py --alvo CPF_{ids['devedor']} "
           f"--foco \"offshores e dissipacao patrimonial\" --boost 10")
    cmd_path = os.path.join(paths["data"], "diretriz_pronta.txt")
    with open(cmd_path, "w", encoding="utf-8") as f:
        f.write(cmd + "\n")
    print(f"\n  Diretriz pronta (copy-paste em {cmd_path}):\n    {cmd}")
