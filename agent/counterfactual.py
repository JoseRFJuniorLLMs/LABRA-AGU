"""
counterfactual — análise contrafactual de relevância probatória (Fase 2).

Responde: "se removermos o evento X, o caminho de ocultação ainda existe?"
Clona a topologia, expurga um ULID (e as arestas que SÓ ele sustenta) e
recalcula a conectividade entre o devedor e o beneficiário (offshore/laranja).
Se a remoção DESCONECTA — o esquema parte — aquele ULID é prova essencial
(relevância máxima). Se o caminho sobrevive por outras provas, o ULID é
redundante (relevância menor).

Coerente com a proveniência multi-evento do CaseGraph: uma aresta provada por
dois documentos só cai se ambos forem removidos — remover um não a apaga.

Isto formaliza o que o `anomaly_engine` aponta topologicamente (pontos de
articulação): o contrafactual fá-lo ao nível da PROVA (ULID), não do nó.
"""
from collections import defaultdict
from typing import Dict, List, Optional, Set

from .entities import normalize_id
from .graph import CaseGraph


class CounterfactualEngine:
    def __init__(self, graph: CaseGraph):
        self.graph = graph

    # ── topologia sob remoção de um ULID ──────────────────────────────
    def _adjacency(self, drop_ulid: Optional[str]) -> Dict[str, Set[str]]:
        """Grafo não-dirigido com as arestas que SOBREVIVEM à remoção de
        `drop_ulid` (uma aresta sobrevive se tem outra prova além dele)."""
        adj: Dict[str, Set[str]] = defaultdict(set)

        def keep(events: Set[str]) -> bool:
            return bool(events - ({drop_ulid} if drop_ulid else set()))

        def link(s, d):
            if s != d:
                adj[s].add(d)
                adj[d].add(s)

        for lst in self.graph.relations.values():
            for r in lst:
                if keep(r["events"]):
                    link(r["src"], r["dst"])
        for t in self.graph.transactions:
            if keep(t["events"]):
                link(t["src"], t["dst"])
        return adj

    @staticmethod
    def _connected(adj: Dict[str, Set[str]], a: str, b: str) -> bool:
        if a not in adj or b not in adj:
            return False
        seen, stack = set(), [a]
        while stack:
            n = stack.pop()
            if n == b:
                return True
            if n in seen:
                continue
            seen.add(n)
            stack.extend(adj[n] - seen)
        return b in seen

    def all_ulids(self) -> Set[str]:
        out: Set[str] = set()
        for lst in self.graph.relations.values():
            for r in lst:
                out |= set(r["events"])
        for t in self.graph.transactions:
            out |= set(t["events"])
        return out

    # ── relevância probatória ─────────────────────────────────────────
    def is_essential(self, ulid: str, source_id: str, sink_id: str) -> bool:
        """True se remover `ulid` desconecta o devedor do beneficiário."""
        s, k = normalize_id(source_id), normalize_id(sink_id)
        if not self._connected(self._adjacency(None), s, k):
            return False  # não há caminho a partir — nada a quebrar
        return not self._connected(self._adjacency(ulid), s, k)

    def rank_evidence(self, source_id: str, sink_id: str) -> List[dict]:
        """Relevância probatória de cada ULID para o caminho devedor→benef.
        1.0 = essencial (removê-lo parte o esquema); 0.3 = corroborante."""
        s, k = normalize_id(source_id), normalize_id(sink_id)
        connected = self._connected(self._adjacency(None), s, k)
        out = []
        for u in sorted(self.all_ulids()):
            essential = connected and not self._connected(self._adjacency(u), s, k)
            out.append({
                "ulid": u,
                "relevancia": 1.0 if essential else 0.3,
                "essencial": essential,
                "justificativa": (
                    "removê-lo desconecta o devedor do beneficiário — prova "
                    "insubstituível" if essential else
                    "o caminho de ocultação sobrevive por outras provas — "
                    "corroborante"),
            })
        return sorted(out, key=lambda x: x["relevancia"], reverse=True)

    def essential_ulids(self, source_id: str, sink_id: str) -> List[str]:
        return [r["ulid"] for r in self.rank_evidence(source_id, sink_id)
                if r["essencial"]]
