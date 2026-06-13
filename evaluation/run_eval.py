"""
CLI da avaliação — imprime a tabela de precisão/recall/F1 por padrão e os
agregados. Corre offline:

  py evaluation/run_eval.py
  py evaluation/run_eval.py -v     # mostra também cada cenário (FP/FN)
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

from evaluation.harness import avaliar  # noqa: E402
from evaluation.scenarios import TODOS  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Avaliação dos detectores LABRA-AGU")
    ap.add_argument("-v", "--verbose", action="store_true",
                    help="mostra cada cenário (esperado vs detectado, FP/FN)")
    args = ap.parse_args()

    r = avaliar(TODOS)

    print("=" * 68)
    print(f"  AVALIAÇÃO DE DETECTORES — {r['n_cenarios']} cenários rotulados")
    print("=" * 68)
    print(f"  {'padrão':<24} {'prec':>6} {'recall':>7} {'F1':>6} "
          f"{'TP':>3} {'FP':>3} {'FN':>3}")
    print("  " + "-" * 60)
    for p, m in r["por_padrao"].items():
        print(f"  {p:<24} {m['precision']:>6.2f} {m['recall']:>7.2f} "
              f"{m['f1']:>6.2f} {m['tp']:>3} {m['fp']:>3} {m['fn']:>3}")
    print("  " + "-" * 60)
    mi = r["micro"]
    print(f"  {'MICRO (global)':<24} {mi['precision']:>6.2f} {mi['recall']:>7.2f} "
          f"{mi['f1']:>6.2f} {mi['tp']:>3} {mi['fp']:>3} {mi['fn']:>3}")
    print(f"  {'MACRO-F1 (média)':<24} {r['macro_f1']:>6.2f}")

    if args.verbose:
        print("\n  Cenários:")
        for d in r["detalhe"]:
            flag = "OK " if d["ok"] else "ERR"
            extra = ""
            if d["fp"]:
                extra += f"  FP={d['fp']}"
            if d["fn"]:
                extra += f"  FN={d['fn']}"
            print(f"   [{flag}] {d['nome']:<32} det={d['detectado']}{extra}")

    # código de saída: 0 se sem FP/FN (tudo certo), 1 caso contrário
    return 0 if (mi["fp"] == 0 and mi["fn"] == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
