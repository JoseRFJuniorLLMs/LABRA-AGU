"""
anomaly_engine — descoberta INDUTIVA de fraude (Fase 2).

Onde o `patterns.py`/`asset_shield.py` são DEDUTIVOS (procuram esquemas
conhecidos), este motor é INDUTIVO: encontra o que destoa, mesmo sem padrão
catalogado. Opera sobre o `CaseGraph` já consolidado (nada de servidor) e
devolve `Anomaly` com score em [0,1], entidades envolvidas e a justificativa
estatística — pronto para o `evidence_scorer` ponderar e o `theory_builder`
incorporar.

Dois eixos:
  - estrutural (GAD): grau anómalo (z-score), concentração de entrada
    (coletor/laranja-hub) e pontos de articulação (a "ponte" que liga o
    devedor à offshore — remover o nó parte o esquema);
  - comportamental: valores fora da distribuição (z-score), estruturação
    sub-limiar (variância baixa logo abaixo de um teto) e movimentação na
    véspera de um marco judicial.
"""
import datetime
import statistics
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

from .graph import CaseGraph

JANELA_VESPERA_DIAS = 30


def _clamp(x: float) -> float:
    return round(max(0.0, min(1.0, x)), 3)


def _parse_date(s: Optional[str]) -> Optional[datetime.date]:
    if not s:
        return None
    try:
        return datetime.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


class AnomalyEngine:
    def __init__(self, graph: CaseGraph):
        self.graph = graph
        self._edges = self._directed_edges()

    # ── topologia ──────────────────────────────────────────────────────
    def _directed_edges(self) -> List[Tuple[str, str]]:
        """Todas as arestas dirigidas (relações + transações), achatadas."""
        edges: List[Tuple[str, str]] = []
        for lst in self.graph.relations.values():
            edges += [(r["src"], r["dst"]) for r in lst]
        edges += [(t["src"], t["dst"]) for t in self.graph.transactions]
        return edges

    def _undirected_adj(self) -> Dict[str, Set[str]]:
        adj: Dict[str, Set[str]] = defaultdict(set)
        for s, d in self._edges:
            if s == d:
                continue
            adj[s].add(d)
            adj[d].add(s)
        return adj

    # ── estrutural (GAD) ───────────────────────────────────────────────
    def detect_structural_anomalies(self) -> List[dict]:
        out: List[dict] = []
        adj = self._undirected_adj()
        if not adj:
            return out

        # 1. Grau anómalo (z-score sobre o grau não-dirigido)
        degs = {n: len(v) for n, v in adj.items()}
        vals = list(degs.values())
        mean = statistics.fmean(vals)
        std = statistics.pstdev(vals) if len(vals) > 1 else 0.0
        if std > 0:
            for n, d in degs.items():
                z = (d - mean) / std
                if z >= 1.5:
                    out.append({
                        "kind": "hub_grau",
                        "score": _clamp(0.5 + z / 6.0),
                        "entities": [n],
                        "justificativa": (
                            f"grau {d} é {z:.1f}σ acima da média ({mean:.1f}) — "
                            "concentração topológica atípica."),
                    })

        # 2. Concentração de entrada (coletor): muitos remetentes distintos
        fan_in: Dict[str, Set[str]] = defaultdict(set)
        for s, d in self._edges:
            if s != d:
                fan_in[d].add(s)
        for n, srcs in fan_in.items():
            if len(srcs) >= 3:
                out.append({
                    "kind": "coletor_fan_in",
                    "score": _clamp(len(srcs) / 5.0),
                    "entities": [n],
                    "justificativa": (
                        f"recebe de {len(srcs)} origens distintas — padrão de "
                        "coletor/contitular (possível laranja-hub)."),
                })

        # 3. Pontos de articulação (pontes): nó cuja remoção desconecta o grafo
        for n in self._articulation_points(adj):
            out.append({
                "kind": "ponte_articulacao",
                "score": 0.85,
                "entities": [n],
                "justificativa": (
                    "ponto de articulação: removê-lo parte o esquema em dois — "
                    "elo estrutural insubstituível da ocultação."),
            })
        return out

    def _articulation_points(self, adj: Dict[str, Set[str]]) -> List[str]:
        """Tarjan (DFS) — pontos de articulação de um grafo não-dirigido."""
        order: Dict[str, int] = {}
        low: Dict[str, int] = {}
        arts: Set[str] = set()
        timer = [0]

        def dfs(u: str, parent: Optional[str]):
            order[u] = low[u] = timer[0]
            timer[0] += 1
            children = 0
            for w in adj[u]:
                if w == parent:
                    continue
                if w not in order:
                    children += 1
                    dfs(w, u)
                    low[u] = min(low[u], low[w])
                    if parent is not None and low[w] >= order[u]:
                        arts.add(u)
                else:
                    low[u] = min(low[u], order[w])
            if parent is None and children > 1:
                arts.add(u)

        for node in list(adj):
            if node not in order:
                dfs(node, None)
        return sorted(arts)

    # ── comportamental ─────────────────────────────────────────────────
    def detect_behavioral_anomalies(self) -> List[dict]:
        out: List[dict] = []
        txs = self.graph.transactions
        if txs:
            out += self._value_outliers(txs)
            out += self._structuring(txs)
            out += self._pre_marco(txs)
        return out

    def _value_outliers(self, txs: List[dict]) -> List[dict]:
        vals = [t["value"] for t in txs if t.get("value") is not None]
        if len(vals) < 3:
            return []
        mean = statistics.fmean(vals)
        std = statistics.pstdev(vals)
        if std == 0:
            return []
        out = []
        for t in txs:
            v = t.get("value")
            if v is None:
                continue
            z = (v - mean) / std
            if z >= 2.0:
                out.append({
                    "kind": "valor_outlier",
                    "score": _clamp(z / 4.0),
                    "entities": [t["src"], t["dst"]],
                    "justificativa": (
                        f"transferência de {v:.2f} é {z:.1f}σ acima da média — "
                        "movimentação destoante do fluxo habitual."),
                })
        return out

    def _structuring(self, txs: List[dict]) -> List[dict]:
        """Estruturação: >=3 transferências do mesmo remetente, com variância
        baixa e todas logo abaixo de um teto redondo (assinatura de smurfing
        descoberta estatisticamente, sem regra de limiar fixa)."""
        por_origem: Dict[str, List[float]] = defaultdict(list)
        for t in txs:
            if t.get("value") is not None:
                por_origem[t["src"]].append(t["value"])
        out = []
        for origem, vs in por_origem.items():
            if len(vs) < 3:
                continue
            mean = statistics.fmean(vs)
            cv = (statistics.pstdev(vs) / mean) if mean else 1.0
            teto = 10_000.0 if max(vs) < 10_000 else 50_000.0
            sub_limiar = max(vs) < teto and (max(vs) / teto) > 0.5
            if cv < 0.25 and sub_limiar:
                out.append({
                    "kind": "estruturacao_sub_limiar",
                    "score": _clamp(0.9 - cv),
                    "entities": [origem],
                    "justificativa": (
                        f"{len(vs)} transferências de variância baixa (CV={cv:.2f}) "
                        f"logo abaixo de R$ {teto:,.0f} — estruturação para evadir "
                        "comunicação obrigatória."),
                })
        return out

    def _pre_marco(self, txs: List[dict]) -> List[dict]:
        marcos = [d for d in (_parse_date(m) for m in self.graph.marcos_datas()) if d]
        if not marcos:
            return []
        out = []
        for t in txs:
            dt = _parse_date(t.get("date"))
            if not dt:
                continue
            for m in marcos:
                delta = (m - dt).days
                if 0 <= delta <= JANELA_VESPERA_DIAS:
                    out.append({
                        "kind": "timing_vespera",
                        "score": _clamp(1.0 - delta / (2.0 * JANELA_VESPERA_DIAS)),
                        "entities": [t["src"], t["dst"]],
                        "justificativa": (
                            f"movimentação {delta} dia(s) antes de marco judicial "
                            f"({m.isoformat()}) — timing de dissipação na véspera."),
                    })
                    break
        return out

    # ── conveniência ───────────────────────────────────────────────────
    def detect_all(self) -> List[dict]:
        """Todas as anomalias, ordenadas por score decrescente."""
        anomalies = self.detect_structural_anomalies() + self.detect_behavioral_anomalies()
        return sorted(anomalies, key=lambda a: a["score"], reverse=True)
