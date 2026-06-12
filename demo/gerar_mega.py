"""
Gerador do MEGA-CASO — um esquema fictício COMPLETO com ~100 envolvidos, tudo
conectado ao devedor central, cobrindo todos os padrões + fraude do INSS, e
todos os tipos de figura: offshore, laranja, empresa fantasma, holding,
advogados, contadores, empresários, funcionários públicos, fazendas, vizinhos,
irmãos, primos, tios, sobrinhos, fundos, bancos, lobistas, testas-de-ferro.

100% fictício (CPF/CNPJ de dígitos válidos; os nomes no painel vêm de nomes.py).
Usa tokens CPF/CNPJ nas frases canónicas → funciona no parser determinístico,
sem LLM.

Limpa o demo_data (mantém o teu complexo_06.txt) para haver UM caso rico e
limpo. Uso:
  python demo/gerar_mega.py
  python demo/run.py --keep      # abre o painel já no devedor central
"""
import argparse
import os
import random
import sqlite3

from gerar_cenario import (fmt_cnpj, fmt_cpf, gerar_cnpj_valido,
                           gerar_cpf_valido)


def _ins(path, table, cols, rows):
    con = sqlite3.connect(path)
    con.execute(f"CREATE TABLE IF NOT EXISTS {table} "
                f"(id INTEGER PRIMARY KEY AUTOINCREMENT, {cols})")
    names = ",".join(c.split()[0] for c in cols.split(","))
    ph = ",".join("?" * len(rows[0]))
    con.executemany(f"INSERT INTO {table} ({names}) VALUES ({ph})", rows)
    con.commit()
    con.close()


def _brl(n):
    return "R$ " + f"{n:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _clear(data, entrada):
    for f in ("junta.db", "cartorio.db", "coaf.db"):
        p = os.path.join(data, f)
        if os.path.exists(p):
            os.remove(p)
    if os.path.isdir(entrada):
        for f in os.listdir(entrada):
            if f.endswith(".txt") and f != "complexo_06.txt":
                os.remove(os.path.join(entrada, f))


def main():
    ap = argparse.ArgumentParser(description="Mega-caso completo (~100 envolvidos)")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--keep", action="store_true", help="não limpar demo_data")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    data = os.path.join(here, "demo_data")
    entrada = os.path.join(data, "entrada")
    os.makedirs(entrada, exist_ok=True)
    if not args.keep:
        _clear(data, entrada)
    rng = random.Random(args.seed)
    cpf = lambda: fmt_cpf(gerar_cpf_valido(rng))      # noqa: E731
    cnpj = lambda: fmt_cnpj(gerar_cnpj_valido(rng))   # noqa: E731

    todos = set()

    def reg(x):
        todos.add(x)
        return x

    L = ["RELATÓRIO INTEGRADO DE INVESTIGAÇÃO — MEGA-ESQUEMA — LABRA / PGU-AGU."]

    # Relógio do esquema: cada relação ganha uma data, avançando 2023 → 2026,
    # para a linha do tempo do painel ser uma cronologia fina (não 4 passos).
    import datetime
    _cur = [datetime.date(2023, 1, 9)]

    def dt():
        _cur[0] += datetime.timedelta(days=rng.randint(4, 15))
        return _cur[0].strftime("%d/%m/%Y")

    def addr(frase):
        """Acrescenta a relação ao documento, datada (… em DD/MM/AAAA)."""
        L.append(frase.rstrip(".") + f", em {dt()}.")

    def pessoas(n, frase):
        out = []
        for _ in range(n):
            i = reg(cpf())
            out.append(i)
            addr(frase.format(i))
        return out

    def empresas(n, frase):
        out = []
        for _ in range(n):
            i = reg(cnpj())
            out.append(i)
            addr(frase.format(i))
        return out

    big = lambda: _brl(rng.randint(2, 14) * 1_000_000)  # noqa: E731

    # ── núcleo (triangulação + fracionamento + véspera + laranja) ──
    D, O1, LAR = reg(cpf()), reg(cnpj()), reg(cpf())
    _ins(os.path.join(data, "junta.db"), "alteracoes",
         "socio TEXT, destino TEXT, data TEXT, cotas INTEGER",
         [(D, O1, "2026-05-12", rng.choice([95000, 130000, 180000]))])
    _ins(os.path.join(data, "cartorio.db"), "procuracoes",
         "outorgante TEXT, procurador TEXT, data TEXT", [(O1, LAR, "2026-05-13")])
    vals = rng.sample([9100, 9200, 9300, 9400, 9500, 9600], 3)
    _ins(os.path.join(data, "coaf.db"), "movimentacoes",
         "origem TEXT, destino TEXT, valor REAL, data TEXT",
         [(D, LAR, float(vals[0]), "2026-05-14"),
          (D, LAR, float(vals[1]), "2026-05-15"),
          (D, LAR, float(vals[2]), "2026-05-16")])
    L.append(f"{LAR} é cunhado do devedor {D}, configurando interposição de pessoa.")
    L.append("Consta ordem de bloqueio judicial (penhora) prevista para 05/06/2026.")

    # ── família (interpostas pessoas) ──
    fam = [("irmão",), ("irmão",), ("primo",), ("primo",), ("primo",),
           ("sobrinho",), ("sobrinho",), ("tio",), ("tio",), ("pai",),
           ("filho",), ("sogro",), ("genro",)]
    for (k,) in fam:
        i = reg(cpf())
        L.append(f"{i} é {k} do devedor {D}, com vínculos patrimoniais diretos.")

    # ── doação cruzada ──
    I1 = reg(cpf())
    L.append(f"{D} doou um imóvel de alta liquidez para {I1}.")
    L.append(f"{I1} doou o mesmo imóvel para {LAR}.")

    # ── holding / usufruto (2) ──
    H1, H2 = reg(cnpj()), reg(cnpj())
    L.append(f"{D} é usufrutuário vitalício e administrador da holding {H1}.")
    L.append(f"{D} é usufrutuário vitalício da holding rural {H2}.")

    # ── offshore em cascata (D → O2 → O3 → O4 → O5) ──
    O2, O3, O4, O5 = reg(cnpj()), reg(cnpj()), reg(cnpj()), reg(cnpj())
    L.append(f"{D} controla a offshore {O2}.")
    L.append(f"{O2} controla a offshore {O3}.")
    L.append(f"{O3} controla a offshore {O4}.")
    L.append(f"{O4} controla a offshore {O5}.")

    # ── empresas de fachada (controladas pela holding) ──
    fachadas = empresas(8, f"{H1} controla a empresa de fachada {{}}.")

    # ── FRAUDE DO INSS (operador + beneficiários fantasma) ──
    OP = reg(cpf())
    L.append(f"{OP} desviou benefícios previdenciários do INSS para {D}.")
    pessoas(20, f"{OP} controla o beneficiário fantasma {{}} de aposentadorias do INSS.")

    # ── advogados de blindagem ──
    pessoas(6, f"{D} controla o advogado interposto {{}}.")
    # ── contadores ──
    pessoas(5, f"{D} controla o contador {{}} responsável pela contabilidade paralela.")
    # ── empresários / sócios ocultos ──
    pessoas(8, f"{D} controla o sócio empresário oculto {{}}.")
    # ── fazendas (ativos rurais interpostos) ──
    empresas(6, f"{D} controla a fazenda {{}} registrada em terceiro.")
    # ── vizinhos usados como laranjas ──
    pessoas(5, f"{D} controla o vizinho-laranja {{}}.")
    # ── lobistas / operadores de influência ──
    pessoas(4, f"{D} controla o operador de influência {{}}.")
    # ── testas-de-ferro (recebem doações do laranja) ──
    pessoas(4, f"{LAR} doou bem imóvel para {{}}.")

    # ── fundos interpostos (recebem aportes da holding) ──
    for _ in range(5):
        fu = reg(cnpj())
        L.append(f"{H1} transferiu {big()} para {fu}, fundo interposto.")
    # ── funcionários públicos (propina via holding) ──
    for _ in range(6):
        fp = reg(cpf())
        L.append(f"{H2} transferiu {big()} para {fp}, agente público beneficiado.")
    # ── bancos (recebem créditos podres das fachadas) ──
    for i in range(3):
        bk = reg(cnpj())
        L.append(f"{fachadas[i % len(fachadas)]} transferiu {big()} para {bk}, banco recebedor.")

    with open(os.path.join(entrada, "mega_caso.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    print(f"Mega-caso COMPLETO gerado: {len(todos)} envolvidos fictícios, "
          f"tudo conectado ao devedor central {D}.")
    print("  Tipos: offshore · laranja · empresa fantasma · holding · INSS · "
          "advogados · contadores · empresários · funcionários públicos · "
          "fazendas · vizinhos · família (irmãos/primos/tios/sobrinhos) · "
          "fundos · bancos · lobistas · testas-de-ferro.")
    print(f"  Documento: demo_data/entrada/mega_caso.txt  ({len(L)} linhas)")
    print("\nMostra no painel:\n  python demo/run.py --keep")


if __name__ == "__main__":
    main()
