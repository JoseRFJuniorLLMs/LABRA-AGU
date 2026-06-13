"""
DEMO Fase 3 — redes entre casos, fila priorizada e feedback + ER fuzzy.

100% offline (sem servidor): monta um grafo com TRÊS devedores que partilham a
MESMA offshore e o MESMO laranja (uma "fábrica de laranjas") e demonstra:

  #1 redes entre casos  — acha o facilitador partilhado e o anel;
  #2 quantificação      — valor dissipado por caso + fila priorizada;
  #3a feedback          — re-pondera padrões pela precisão histórica;
  #3b ER fuzzy          — sugere entidades quase-idênticas para fusão.

Uso:  py demo/demo_fase3.py
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent.entity_resolution import FuzzyResolver  # noqa: E402
from agent.feedback import CONFIRMADO, FALSO, FeedbackStore  # noqa: E402
from agent.graph import CaseGraph  # noqa: E402
from agent.network_analysis import CrossCaseNetwork  # noqa: E402
from agent.parser import parse_document  # noqa: E402
from agent.recovery import fila  # noqa: E402


def banner(m):
    print("\n" + "=" * 66 + f"\n  {m}\n" + "=" * 66)


def _brl(v):
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# Cenário: 3 devedores, a MESMA offshore (CNPJ_GLOBAL) e o MESMO laranja
# (CPF_OPERADOR) — o facilitador profissional. Valores distintos por caso.
DOCS = [
    "CPF_DEV1 transferiu quotas para CNPJ_GLOBAL, que nomeou CPF_OPERADOR com plenos poderes. "
    "CPF_DEV1 transferiu R$ 4.000.000,00 para CNPJ_GLOBAL em 02/05/2026.",
    "CPF_DEV2 transferiu quotas para CNPJ_GLOBAL, que nomeou CPF_OPERADOR com plenos poderes. "
    "CPF_DEV2 transferiu R$ 250.000,00 para CNPJ_GLOBAL em 03/05/2026.",
    "CPF_DEV3 transferiu quotas para CNPJ_GLOBAL, que nomeou CPF_OPERADOR com plenos poderes. "
    "CPF_DEV3 transferiu R$ 18.000,00 para CNPJ_GLOBAL em 04/05/2026.",
]


def main():
    g = CaseGraph()
    for i, d in enumerate(DOCS):
        g.ingest(parse_document(d, f"EV{i}"))

    # #1 ── redes entre casos
    banner("#1 REDES ENTRE CASOS — o facilitador partilhado")
    net = CrossCaseNetwork(g)
    for f in net.facilitadores(min_devedores=2):
        print(f"  ● {f['entidade']} ({f['kind'] or 'entidade'}) serve "
              f"{f['n_devedores']} devedores: {', '.join(f['devedores'])}")
    aneis = net.aneis(min_devedores=2)
    print(f"  → {len(aneis)} anel(éis) detectado(s); o maior junta "
          f"{aneis[0]['n_devedores']} devedores num só esquema.")

    # #2 ── quantificação + fila priorizada
    banner("#2 QUANTIFICAÇÃO + FILA PRIORIZADA — por onde começar")
    insights = {
        "CPF_DEV1": {"severidade_max": "CRITICA", "evidence_score": 0.9, "n_fraudes": 2},
        "CPF_DEV2": {"severidade_max": "CRITICA", "evidence_score": 0.9, "n_fraudes": 2},
        "CPF_DEV3": {"severidade_max": "ALTA", "evidence_score": 0.6, "n_fraudes": 1},
    }
    for i, c in enumerate(fila(g, insights), 1):
        print(f"  {i}º  {c['devedor']:<10} {_brl(c['valor']):>20}  "
              f"[{c['severidade_max']:<7}]  prioridade={c['score_prioridade']}")

    # #3a ── feedback
    banner("#3a FEEDBACK — o sistema aprende com o veredicto")
    fb = FeedbackStore()
    for _ in range(4):
        fb.registar("fracionamento", FALSO)     # historicamente falso alarme
    fb.registar("triangulacao_offshore", CONFIRMADO)
    achados = [{"pattern": "fracionamento", "severidade": "ALTA"},
               {"pattern": "triangulacao_offshore", "severidade": "ALTA"}]
    for a in fb.reponderar(achados):
        print(f"  {a['pattern']:<24} confiança aprendida={a['confianca_aprendida']} "
              f"({a['amostras_feedback']} veredictos)")
    print("  → mesma severidade, mas a triangulação sobe: o fracionamento "
          "perdeu confiança por só dar falso alarme.")

    # #3b ── ER fuzzy
    banner("#3b RESOLUÇÃO DE ENTIDADES FUZZY — evasão por grafia")
    # Nomes reais nas entidades (em produção vêm das fontes). O operador aparece
    # numa fonte sem CPF, com o nome ligeiramente diferente — escaparia à
    # resolução exata, mas a fuzzy sugere o par para revisão.
    g.entities.update({
        "CPF_DEV1": "Ana Pereira", "CPF_DEV2": "Bruno Carvalho",
        "CPF_DEV3": "Célia Matos", "CPF_OPERADOR": "Carlos A. Menezes",
        "TMP_LANE": "Carlos Alberto Menezes",  # mesmo operador, fonte sem CPF
    })
    # limiar 0.80: o default (0.86) é conservador; "Carlos A." vs "Carlos
    # Alberto" pontua 0.82 no difflib (char-level) — captável sem falsar os
    # devedores, cujos nomes são bem distintos.
    for c in FuzzyResolver(g).candidatos(limiar_nome=0.80):
        print(f"  ? {c['nome_a']!r} ≈ {c['nome_b']!r}  "
              f"(sim={c['similaridade']}, {c['motivo']}) → revisão humana")

    print("\n✅ Fase 3 demonstrada: rede + valor + aprendizado + ER fuzzy.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
