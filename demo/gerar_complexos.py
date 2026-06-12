"""
Gerador de CASOS COMPLEXOS para a demo — esquemas que exercitam a Fase 2.

Cada caso é um superconjunto: a triangulação base (venda → procuração →
fracionamento → vínculo → véspera, que renderiza no grafo do painel) MAIS um
ou mais esquemas avançados declarados no documento de vínculos:

  - doação cruzada  : devedor doa a um intermediário que repassa ao laranja;
  - holding/usufruto: devedor é usufrutuário vitalício de uma empresa;
  - offshore cascata: devedor controla off2 que controla off3 (camadas).

Perfis (variam o conjunto de alertas, para o dashboard ter diversidade):
  completo · cascata · doacao_holding

Uso:
  python demo/gerar_complexos.py --n 6      # 6 casos complexos (limpa demo_data)
Depois:  python demo/run.py --keep          # ingere e mostra no painel

Dados fictícios com CPF/CNPJ de dígitos válidos. Os esquemas avançados são
detectados pelo asset_shield (já registado no catálogo do agente).
"""
import argparse
import os
import random
import sqlite3

from gerar_cenario import (fmt_cnpj, fmt_cpf, gerar_cnpj_valido,
                           gerar_cpf_valido)

PERFIS = ["completo", "cascata", "doacao_holding"]


def _ins(path, table, cols, rows):
    con = sqlite3.connect(path)
    con.execute(f"CREATE TABLE IF NOT EXISTS {table} "
                f"(id INTEGER PRIMARY KEY AUTOINCREMENT, {cols})")
    names = ",".join(c.split()[0] for c in cols.split(","))
    ph = ",".join("?" * len(rows[0]))
    con.executemany(f"INSERT INTO {table} ({names}) VALUES ({ph})", rows)
    con.commit()
    con.close()


def _limpa(data, entrada):
    for f in ("junta.db", "cartorio.db", "coaf.db"):
        p = os.path.join(data, f)
        if os.path.exists(p):
            os.remove(p)
    if os.path.isdir(entrada):
        for f in os.listdir(entrada):
            if f.endswith(".txt"):
                os.remove(os.path.join(entrada, f))


def gerar_caso(rng, data, entrada, idx, perfil):
    D = gerar_cpf_valido(rng)     # devedor
    L = gerar_cpf_valido(rng)     # laranja (cunhado)
    O1 = gerar_cnpj_valido(rng)   # offshore da triangulação

    # ── triangulação base (vai para os bancos SQL) ──
    cotas = rng.choice([72000, 85000, 95000, 110000, 130000])
    _ins(os.path.join(data, "junta.db"), "alteracoes",
         "socio TEXT, destino TEXT, data TEXT, cotas INTEGER",
         [(fmt_cpf(D), fmt_cnpj(O1), "2026-05-12", cotas)])
    _ins(os.path.join(data, "cartorio.db"), "procuracoes",
         "outorgante TEXT, procurador TEXT, data TEXT",
         [(fmt_cnpj(O1), L, "2026-05-13")])
    vals = rng.sample([9600, 9400, 9200, 9000, 8800, 8600], 3)
    _ins(os.path.join(data, "coaf.db"), "movimentacoes",
         "origem TEXT, destino TEXT, valor REAL, data TEXT",
         [(D, L, float(vals[0]), "2026-05-14"),
          (D, L, float(vals[1]), "2026-05-15"),
          (D, L, float(vals[2]), "2026-05-16")])

    # ── documento de vínculos (esquemas avançados, conforme o perfil) ──
    linhas = [
        "RELATÓRIO DE INVESTIGAÇÃO DE VÍNCULOS — LABRA / PGU-AGU.",
        f"Apurou-se que {L} é cunhado do devedor {D}, configurando interposição de pessoa.",
        "Consta ordem de bloqueio judicial (penhora) prevista para 05/06/2026.",
    ]
    esquemas = ["triangulação", "fracionamento", "véspera", "laranja"]
    if perfil in ("completo", "doacao_holding"):
        INT = gerar_cpf_valido(rng)
        linhas += [f"{D} doou um imóvel para {INT}.",
                   f"{INT} doou o mesmo imóvel para {L}."]
        esquemas.append("doação cruzada")
        H = gerar_cnpj_valido(rng)
        linhas.append(f"{D} é usufrutuário vitalício da empresa {H}.")
        esquemas.append("holding/usufruto")
    if perfil in ("completo", "cascata"):
        O2, O3 = gerar_cnpj_valido(rng), gerar_cnpj_valido(rng)
        linhas += [f"{D} controla a offshore {O2}.",
                   f"{O2} controla a offshore {O3}."]
        esquemas.append("offshore cascata")

    with open(os.path.join(entrada, f"complexo_{idx:02d}.txt"),
              "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")
    return D, perfil, esquemas


def main():
    ap = argparse.ArgumentParser(description="Gera casos complexos para a demo")
    ap.add_argument("--n", type=int, default=6, help="quantos casos complexos")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--keep", action="store_true",
                    help="não limpar demo_data antes (acrescenta aos existentes)")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    data = os.path.join(here, "demo_data")
    entrada = os.path.join(data, "entrada")
    os.makedirs(entrada, exist_ok=True)
    if not args.keep:
        _limpa(data, entrada)
    rng = random.Random(args.seed)

    print(f"A gerar {args.n} caso(s) complexo(s)...\n")
    for i in range(args.n):
        D, perfil, esquemas = gerar_caso(rng, data, entrada, i, PERFIS[i % len(PERFIS)])
        print(f"  Caso #{i+1} [{perfil}] devedor {fmt_cpf(D)} — "
              f"{len(esquemas)} esquemas: {', '.join(esquemas)}")
    print("\nFeito. Mostra no painel:\n  python demo/run.py --keep")


if __name__ == "__main__":
    main()
