"""
Adiciona MAIS casos de fraude à demo — um comando, um caso novo inteiro.

Acrescenta (sem apagar o que já existe) uma triangulação completa aos bancos
da demo e um documento de vínculo na pasta vigiada, com CPF/CNPJ fictícios de
dígitos VÁLIDOS e nas colunas/frases EXATAS que o agente reconhece. Depois é
só re-ingerir (ver o tutorial) que o agente fecha o novo caso.

Uso:
  python demo/adicionar_caso.py                 # +1 caso
  python demo/adicionar_caso.py --n 3           # +3 casos
  python demo/adicionar_caso.py --seed 7        # reproduzível

Requer que os bancos já existam (corra antes `python demo/gerar_cenario.py`);
se não existirem, este script cria-os.
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


def adicionar_um(rng, data, entrada):
    dev = gerar_cpf_valido(rng)   # devedor
    lar = gerar_cpf_valido(rng)   # laranja (cunhado)
    off = gerar_cnpj_valido(rng)  # offshore
    agt = gerar_cpf_valido(rng)   # agente público subornado

    # JUNTA — venda de quotas (CPF do devedor FORMATADO).
    cotas = rng.choice([60000, 72000, 85000, 90000, 95000, 110000, 125000])
    _ins(os.path.join(data, "junta.db"), "alteracoes",
         "socio TEXT, destino TEXT, data TEXT, cotas INTEGER",
         [(fmt_cpf(dev), fmt_cnpj(off), "2026-05-12", cotas)])

    # CARTÓRIO — procuração com plenos poderes (offshore -> laranja).
    _ins(os.path.join(data, "cartorio.db"), "procuracoes",
         "outorgante TEXT, procurador TEXT, data TEXT",
         [(fmt_cnpj(off), lar, "2026-05-13")])

    # COAF — 3 transferências fracionadas, valores distintos < R$ 10.000.
    _ins(os.path.join(data, "coaf.db"), "movimentacoes",
         "origem TEXT, destino TEXT, valor REAL, data TEXT",
         [(dev, lar, 9300.00, "2026-05-14"),
          (dev, lar, 8800.00, "2026-05-15"),
          (dev, lar, 9100.00, "2026-05-16")])

    # DOCUMENTO — vínculo familiar (CPF cru) + marco judicial iminente.
    doc = (
        "RELATÓRIO DE INVESTIGAÇÃO DE VÍNCULOS — LABRA / PGU-AGU.\n"
        f"Apurou-se que {lar} é cunhado do devedor {dev}, configurando "
        "interposição de pessoa (laranja familiar).\n"
        "Consta ordem de bloqueio judicial (penhora) prevista para "
        "05/06/2026, de conhecimento prévio do alvo.\n"
    )
    with open(os.path.join(entrada, f"vinculos_{lar[-4:]}.txt"),
              "w", encoding="utf-8") as f:
        f.write(doc)

    # DOCUMENTO — corrupção ativa: propina do devedor a um agente público
    # (valor distinto por caso para não colidir na resolução de entidades).
    propina = rng.choice([120_000, 180_000, 250_000, 320_000, 450_000])
    # Formato brasileiro (250.000,00) — o que _VALUE_RE do parser reconhece.
    propina_br = f"{propina:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    doc_sub = (
        "RELATÓRIO COAF/CGU — INDÍCIO DE CORRUPÇÃO ATIVA.\n"
        f"Apurou-se que {dev} pagou propina de R$ {propina_br} ao agente "
        f"público {agt} em 20/05/2026, em contrapartida ao favorecimento na "
        "liberação de registros e à demora proposital na constrição dos bens.\n"
    )
    with open(os.path.join(entrada, f"suborno_{agt[-4:]}.txt"),
              "w", encoding="utf-8") as f:
        f.write(doc_sub)

    # LOG DE MUDANÇAS (CDC) — a data da venda (12/05) foi antedatada por UPDATE
    # em 10/06 (após a penhora de 05/06); e um registo COAF foi apagado em 12/06.
    dev_fmt = fmt_cpf(dev)
    audit = (
        "# TRILHA DE AUDITORIA (CDC) — Sistema Registral / Junta Comercial\n"
        f"2026-06-10 14:32:11 UPDATE alteracoes registro de {dev_fmt} "
        "campo=data de=08/06/2026 para=12/05/2026 por=op_junta_47\n"
        f"2026-06-12 09:15:02 DELETE coaf registro de {dev_fmt} "
        "campo=movimentacao por=op_coaf_12\n"
    )
    with open(os.path.join(entrada, f"auditoria_{dev[-4:]}.log"),
              "w", encoding="utf-8") as f:
        f.write(audit)
    return {"devedor": dev, "devedor_fmt": fmt_cpf(dev),
            "laranja": lar, "offshore": fmt_cnpj(off), "agente": agt}


def main():
    ap = argparse.ArgumentParser(description="Adiciona casos de fraude à demo")
    ap.add_argument("--n", type=int, default=1, help="quantos casos adicionar")
    ap.add_argument("--seed", type=int, default=None, help="semente reproduzível")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    data = os.path.join(here, "demo_data")
    entrada = os.path.join(data, "entrada")
    os.makedirs(entrada, exist_ok=True)
    rng = random.Random(args.seed)

    print(f"A adicionar {args.n} caso(s) de fraude aos bancos da demo...\n")
    for i in range(args.n):
        ids = adicionar_um(rng, data, entrada)
        print(f"  Caso #{i+1}: devedor {ids['devedor_fmt']} · "
              f"laranja {ids['laranja']} · offshore {ids['offshore']}")
    print("\nFeito. Agora re-ingira para o agente fechar os casos novos:")
    print("  python pipeline.py --config demo/sources.json --once")
    print("(com o daemon a correr: python main.py --daemon)")


if __name__ == "__main__":
    main()
