"""
Teste unitário do passo 3 (Nexo e Força) — sem servidor.

  - causal_chain  : a offshore liga, no tempo, a venda à procuração (nexo);
  - counterfactual: a procuração é prova essencial quando é o único caminho,
    e torna-se corroborante quando há prova redundante (multi-evento);
  - evidence_scorer: pesos por qualidade da fonte e regra "sem alucinações"
    (ULID sem proveniência não pontua).
"""
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent.causal_chain import CausalChainBuilder
from agent.counterfactual import CounterfactualEngine
from agent.entities import normalize_id
from agent.evidence_scorer import EvidenceScorer, classify_source
from agent.graph import CaseGraph
from agent.parser import parse_document

DEV = "52998224725"
OFF = "CNPJ_11.222.333/0001-81"
LAR = "CPF_BENEFICIARIO_07"

VENDA = f"{DEV} transferiu quotas da empresa para a offshore {OFF} em 01/06/2026"
PROC = f"A {OFF} nomeou {LAR} com plenos poderes em 03/06/2026"
FAM = f"{LAR} é cunhado do devedor {DEV}"
TX = f"{DEV} transferiu R$ 9.500,00 para {LAR} em 14/05/2026"


def u(n):  # ULID-like ordenável (lexicográfico = temporal)
    return f"01HZZZ{n:020d}"


def _graph(items):
    g = CaseGraph()
    for text, ulid in items:
        g.ingest(parse_document(text, source_event_id=ulid))
    return g


def main() -> int:
    # ── causal_chain ──────────────────────────────────────────────────
    g = _graph([(VENDA, u(1)), (PROC, u(2)), (FAM, u(3)), (TX, u(4))])
    chain = CausalChainBuilder(g).build_chain(DEV)
    assert chain, "cadeia causal vazia"
    off = normalize_id(OFF)
    elo = [c for c in chain if c["from_ulid"] == u(1) and c["to_ulid"] == u(2)
           and c["entity"] == off]
    assert elo, "a offshore devia ligar a venda (u1) à procuração (u2)"
    print(f"[1] nexo causal: {len(chain)} elos; offshore liga venda→procuração")
    print(f"    mecanismo: {elo[0]['mechanism']}")

    # ── counterfactual ────────────────────────────────────────────────
    # Caminho único devedor→offshore→laranja: a procuração é essencial.
    gA = _graph([(VENDA, u(1)), (PROC, u(2))])
    cfA = CounterfactualEngine(gA)
    assert cfA.is_essential(u(2), DEV, LAR), "procuração devia ser essencial"
    assert cfA.is_essential(u(1), DEV, LAR), "venda devia ser essencial"
    print(f"[2] contrafactual: ULIDs essenciais = "
          f"{cfA.essential_ulids(DEV, LAR)}")

    # Com prova redundante da procuração (2º documento), o ULID deixa de ser
    # essencial — o caminho sobrevive sem ele.
    gB = _graph([(VENDA, u(1)), (PROC, u(2)), (PROC, u(50))])
    cfB = CounterfactualEngine(gB)
    assert not cfB.is_essential(u(2), DEV, LAR), \
        "com corroboração, a procuração não é essencial"
    print("[3] contrafactual: prova corroborada → procuração vira corroborante")

    # ── evidence_scorer ───────────────────────────────────────────────
    sm = {
        "u_coaf": {"source": "sql", "table": "movimentacoes"},
        "u_junta": {"source": "sql", "table": "alteracoes"},
        "u_file": {"source": "file", "doc_ref": "vinculos.txt"},
        "u_dep": {"source": "file", "doc_ref": "depoimento.txt"},
    }
    es = EvidenceScorer(source_map=sm)
    assert classify_source(sm["u_coaf"]) == "bancaria_oficial"
    assert es.weight_of("u_coaf") == 1.0
    assert es.weight_of("u_junta") == 0.9
    assert es.weight_of("u_file") == 0.6
    assert es.weight_of("u_dep") == 0.4
    assert es.weight_of("u_inexistente") is None, "sem proveniência não pontua"
    r = es.score(["u_coaf", "u_junta", "u_file", "u_inexistente"])
    esperado = round((1.0 + 0.9 + 0.6) / 3, 3)
    assert r["score"] == esperado, (r["score"], esperado)
    assert r["ignorados_sem_proveniencia"] == ["u_inexistente"]
    print(f"[4] força probatória: score={r['score']} "
          f"({r['n_provas']} provas; 1 ignorada sem ULID)")

    print("\nFASE 2 — NEXO E FORÇA (causal_chain + counterfactual + "
          "evidence_scorer): SUCESSO TOTAL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
