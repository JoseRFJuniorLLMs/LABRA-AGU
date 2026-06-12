"""
Gerador do MEGA-CASO — um único esquema fictício com ~50 envolvidos, tudo
conectado, exercitando TODOS os padrões do agente + fraude do INSS.

100% fictício (CPF/CNPJ de dígitos válidos; nomes vêm de nomes.py no painel).
Usa tokens CPF/CNPJ nas frases canónicas, logo funciona com o parser
determinístico (sem precisar de LLM). Escreve as pernas SQL (junta/cartório/
COAF) e um documento denso com a teia de relações.

Padrões cobertos no devedor central:
  triangulação · fracionamento · véspera · laranja familiar · doação cruzada ·
  holding/usufruto · offshore em cascata · FRAUDE DO INSS (desvio de benefícios).

Uso:
  python demo/gerar_mega.py            # ACRESCENTA o mega-caso ao demo_data
  python demo/gerar_mega.py --seed 7   # reproduzível
Depois:  python demo/run.py --keep     # detecta e mostra (selecione o devedor central)
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


def main():
    ap = argparse.ArgumentParser(description="Gera o mega-caso (~50 envolvidos)")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    data = os.path.join(here, "demo_data")
    entrada = os.path.join(data, "entrada")
    os.makedirs(entrada, exist_ok=True)
    rng = random.Random(args.seed)
    cpf = lambda: fmt_cpf(gerar_cpf_valido(rng))      # noqa: E731
    cnpj = lambda: fmt_cnpj(gerar_cnpj_valido(rng))   # noqa: E731

    todos = set()

    def reg(*xs):
        for x in xs:
            todos.add(x)
        return xs if len(xs) > 1 else xs[0]

    L = ["RELATÓRIO INTEGRADO DE INVESTIGAÇÃO — MEGA-ESQUEMA — LABRA / PGU-AGU."]

    # ── núcleo (triangulação + fracionamento + véspera + laranja) ──
    D, O1, LAR = reg(cpf()), reg(cnpj()), reg(cpf())
    cotas = rng.choice([95000, 110000, 130000, 150000])
    _ins(os.path.join(data, "junta.db"), "alteracoes",
         "socio TEXT, destino TEXT, data TEXT, cotas INTEGER",
         [(D, O1, "2026-05-12", cotas)])
    _ins(os.path.join(data, "cartorio.db"), "procuracoes",
         "outorgante TEXT, procurador TEXT, data TEXT",
         [(O1, LAR, "2026-05-13")])
    vals = rng.sample([9100, 9200, 9300, 9400, 9500, 9600], 3)
    _ins(os.path.join(data, "coaf.db"), "movimentacoes",
         "origem TEXT, destino TEXT, valor REAL, data TEXT",
         [(D, LAR, float(vals[0]), "2026-05-14"),
          (D, LAR, float(vals[1]), "2026-05-15"),
          (D, LAR, float(vals[2]), "2026-05-16")])
    L.append(f"{LAR} é cunhado do devedor {D}, configurando interposição de pessoa.")
    L.append("Consta ordem de bloqueio judicial (penhora) prevista para 05/06/2026.")

    # ── doação cruzada ──
    I1 = reg(cpf())
    L.append(f"{D} doou um imóvel de alta liquidez para {I1}.")
    L.append(f"{I1} doou o mesmo imóvel para {LAR}.")

    # ── holding / usufruto ──
    H1 = reg(cnpj())
    L.append(f"{D} é usufrutuário vitalício e administrador da empresa {H1}.")

    # ── offshore em cascata ──
    O2, O3, O4 = reg(cnpj()), reg(cnpj()), reg(cnpj())
    L.append(f"{D} controla a offshore {O2}.")
    L.append(f"{O2} controla a offshore {O3}.")
    L.append(f"{O3} controla a offshore {O4}.")

    # ── família extra (interpostas pessoas) ──
    for k in ("irmão", "pai", "filho", "sogro", "genro"):
        f = reg(cpf())
        L.append(f"{f} é {k} do devedor {D}, com vínculos patrimoniais diretos.")

    # ── FRAUDE DO INSS: operador desvia benefícios para o devedor ──
    OP = reg(cpf())
    L.append(f"{OP} desviou benefícios previdenciários do INSS para {D}.")
    for _ in range(12):
        b = reg(cpf())
        L.append(f"{OP} controla o beneficiário fantasma {b} de aposentadorias do INSS.")

    # ── sócios ocultos ──
    for _ in range(5):
        s = reg(cpf())
        L.append(f"{D} controla o sócio oculto {s}.")

    # ── fundos interpostos (recebem aportes da holding) ──
    fundos = [reg(cnpj()) for _ in range(4)]
    for fu in fundos:
        L.append(f"{H1} transferiu {_brl(rng.randint(2, 9) * 1_000_000)} para {fu}.")

    # ── empresas de fachada (controladas pelos fundos) ──
    fachadas = [reg(cnpj()) for _ in range(3)]
    for i, e in enumerate(fachadas):
        L.append(f"{fundos[i % len(fundos)]} controla a empresa de fachada {e}.")

    # ── bancos (recebem créditos podres das fachadas) ──
    for i in range(2):
        bk = reg(cnpj())
        L.append(f"{fachadas[i % len(fachadas)]} transferiu "
                 f"{_brl(rng.randint(3, 12) * 1_000_000)} para {bk}.")

    # ── lobistas / operadores ──
    for _ in range(4):
        p = reg(cpf())
        L.append(f"{D} controla o operador de influência {p}.")

    # ── testas-de-ferro (recebem doações do laranja) ──
    for _ in range(4):
        t = reg(cpf())
        L.append(f"{LAR} doou bem imóvel para {t}.")

    # ── advogados de blindagem ──
    for _ in range(2):
        a = reg(cpf())
        L.append(f"{D} controla o escritório interposto {a}.")

    with open(os.path.join(entrada, "mega_caso.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    print(f"Mega-caso gerado: {len(todos)} envolvidos fictícios, tudo conectado "
          f"ao devedor central {D}.")
    print(f"  Padrões: triangulação · fracionamento · véspera · laranja · doação "
          f"cruzada · holding · cascata · FRAUDE INSS")
    print(f"  Documento: demo_data/entrada/mega_caso.txt  ({len(L)} linhas)")
    print("\nMostra no painel:\n  python demo/run.py --keep")


if __name__ == "__main__":
    main()
