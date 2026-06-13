"""
recovery — quantificação do valor dissipado e FILA priorizada (Fase 3).

Transforma N alertas numa ORDEM de ataque. Por caso, estima o valor em risco
(o que o devedor dissipou) e combina-o com a severidade e a força probatória
num score de prioridade — o procurador sabe POR ONDE começar e QUANTO há a
recuperar, em vez de encarar 5.000 alertas "todos críticos".

Tudo sobre o `CaseGraph` (sem servidor). O valor é uma ESTIMATIVA defensável a
partir das provas (transferências, venda de quotas, bens a valor de mercado,
propina) — não um número mágico.
"""
import math
from typing import Dict, List, Optional

from .graph import CaseGraph

_SEV = {"CRITICA": 1.0, "ALTA": 0.7, "MEDIA": 0.4, "BAIXA": 0.2}

# Pesos do score de prioridade (somam 1.0): valor domina, mas severidade e
# força probatória corrigem (um valor enorme com prova fraca não é prioridade 1).
_W_VALOR, _W_SEV, _W_EVID = 0.5, 0.3, 0.2


def valor_dissipado(graph: CaseGraph, devedor: str) -> float:
    """Soma do valor que SAIU do devedor: transferências + venda de quotas +
    bens alienados (a valor de mercado quando há) + propina paga."""
    total = 0.0
    for t in graph.transactions:
        if t["src"] == devedor and t.get("value"):
            total += t["value"]
    for rt in ("VENDEDOR_QUOTAS", "SUBORNO", "CONVERTEU_CRIPTO",
               "CREDOR_DIVIDA"):
        for r in graph.rels(rt):
            # CREDOR_DIVIDA: o devedor é o ALVO (dst); os outros, a origem (src)
            alvo = r["dst"] if rt == "CREDOR_DIVIDA" else r["src"]
            if alvo == devedor and r.get("value"):
                total += r["value"]
    for tr in graph.asset_transfers:
        if tr["src"] == devedor:
            meta = graph.assets.get(tr["asset_id"], {})
            total += meta.get("valor_mercado") or tr.get("value") or 0.0
    return round(total, 2)


def _valor_norm(v: float) -> float:
    """Normaliza por ordem de grandeza (log10): ~0 a ~1 até ~R$ 1 bilhão,
    evitando que um único caso gigante esmague a escala."""
    return min(1.0, math.log10(max(0.0, v) + 1) / 9.0)


def score_prioridade(valor: float, severidade_max: str,
                     evidence_score: Optional[float]) -> float:
    ev = 0.6 if evidence_score is None else evidence_score
    sev = _SEV.get(severidade_max, 0.3)
    return round(_W_VALOR * _valor_norm(valor) + _W_SEV * sev + _W_EVID * ev, 4)


def priorizar(casos: List[dict]) -> List[dict]:
    """Ordena casos por prioridade. Cada caso: {devedor, valor, severidade_max,
    evidence_score?, n_fraudes?}. Anota score_prioridade e valor_norm."""
    out = []
    for c in casos:
        valor = c.get("valor") or 0.0
        score = score_prioridade(valor, c.get("severidade_max"),
                                 c.get("evidence_score"))
        out.append({**c, "score_prioridade": score,
                    "valor_norm": round(_valor_norm(valor), 3)})
    return sorted(out, key=lambda c: c["score_prioridade"], reverse=True)


def fila(graph: CaseGraph, casos_insights: Dict[str, dict]) -> List[dict]:
    """Conveniência: monta a fila priorizada a partir de um mapa
    devedor -> {severidade_max, evidence_score, n_fraudes}, calculando o valor
    dissipado de cada um direto do grafo."""
    casos = []
    for devedor, meta in casos_insights.items():
        casos.append({
            "devedor": devedor,
            "valor": valor_dissipado(graph, devedor),
            "severidade_max": meta.get("severidade_max"),
            "evidence_score": meta.get("evidence_score"),
            "n_fraudes": meta.get("n_fraudes"),
        })
    return priorizar(casos)
