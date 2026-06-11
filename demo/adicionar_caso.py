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

    # JUNTA — venda de quotas (CPF do devedor FORMATADO).
    _ins(os.path.join(data, "junta.db"), "alteracoes",
         "socio TEXT, destino TEXT, data TEXT",
         [(fmt_cpf(dev), fmt_cnpj(off), "2026-05-12")])

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
    return {"devedor": dev, "devedor_fmt": fmt_cpf(dev),
            "laranja": lar, "offshore": fmt_cnpj(off)}


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
