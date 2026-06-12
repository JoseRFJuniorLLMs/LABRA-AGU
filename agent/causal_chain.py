"""
causal_chain — reconstrução do nexo de causalidade (Fase 2, passo 3).

Prova que uma ação FACILITOU outra (ex.: a venda de quotas viabilizou a
procuração que esvaziou o patrimônio). O tempo vem de graça do HeraclitusDB:
os ULIDs ordenam-se LEXICOGRAFICAMENTE por instante de criação, logo a ordem
causal é a ordem dos ULIDs — sem depender de datas declaradas no texto.

Modelo: cada aresta do CaseGraph (relação/transação) é um FATO com a sua
proveniência (ULIDs). Uma entidade que reaparece em fatos sucessivos é o fio
condutor da causalidade — a offshore que aparece na venda e depois na
procuração liga os dois atos. Encadeando, por entidade e em ordem temporal,
obtém-se um DAG de causas e efeitos.

Saída de `build_chain`: lista de `{'from_ulid', 'to_ulid', 'mechanism'}`
(+ 'entity' / 'date'), pronta para o litigator citar o encadeamento.
"""
from collections import defaultdict
from typing import Dict, List, Optional, Set

from .entities import normalize_id
from .graph import CaseGraph

_TX_KIND = "TRANSFERENCIA"


class CausalChainBuilder:
    def __init__(self, graph: CaseGraph):
        self.graph = graph

    # ── fatos (arestas com proveniência) ──────────────────────────────
    def _facts(self) -> List[dict]:
        facts: List[dict] = []
        for rtype, lst in self.graph.relations.items():
            for r in lst:
                if r["events"]:
                    facts.append({
                        "ulid": min(r["events"]), "src": r["src"],
                        "dst": r["dst"], "kind": rtype, "date": r["date"]})
        for t in self.graph.transactions:
            if t["events"]:
                facts.append({
                    "ulid": min(t["events"]), "src": t["src"],
                    "dst": t["dst"], "kind": _TX_KIND, "date": t["date"]})
        return facts

    def _component(self, target: str, facts: List[dict]) -> Set[str]:
        """Componente conexo (não-dirigido) que contém o alvo."""
        adj: Dict[str, Set[str]] = defaultdict(set)
        for f in facts:
            adj[f["src"]].add(f["dst"])
            adj[f["dst"]].add(f["src"])
        seen, stack = set(), [target]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(adj[n] - seen)
        return seen

    def _label(self, cid: str) -> str:
        return self.graph.entities.get(cid, cid)

    # ── construção do DAG causal ──────────────────────────────────────
    def build_chain(self, target_entity_id: str) -> List[dict]:
        target = normalize_id(target_entity_id)
        facts = self._facts()
        comp = self._component(target, facts)
        if target not in comp:
            return []
        facts = [f for f in facts if f["src"] in comp and f["dst"] in comp]

        # Para cada entidade, encadeia os fatos que a tocam em ordem temporal
        # (ULID). A entidade partilhada é o MECANISMO do nexo.
        by_entity: Dict[str, List[dict]] = defaultdict(list)
        for f in facts:
            by_entity[f["src"]].append(f)
            if f["dst"] != f["src"]:
                by_entity[f["dst"]].append(f)

        chain: List[dict] = []
        seen_links: Set[tuple] = set()
        for ent, fs in by_entity.items():
            # dedup de fatos idênticos e ordenação temporal por ULID
            uniq = {(f["ulid"], f["kind"], f["src"], f["dst"]): f for f in fs}
            ordered = sorted(uniq.values(), key=lambda x: x["ulid"])
            for a, b in zip(ordered, ordered[1:]):
                if a["ulid"] == b["ulid"]:
                    continue
                key = (a["ulid"], b["ulid"], ent)
                if key in seen_links:
                    continue
                seen_links.add(key)
                chain.append({
                    "from_ulid": a["ulid"],
                    "to_ulid": b["ulid"],
                    "mechanism": (f"{self._label(ent)}: {a['kind']} "
                                  f"viabilizou {b['kind']}"),
                    "entity": ent,
                    "date": b["date"],
                })
        return sorted(chain, key=lambda c: (c["from_ulid"], c["to_ulid"]))

    def narrative(self, target_entity_id: str) -> List[str]:
        """Encadeamento em frases (para a peça jurídica)."""
        return [f"{c['mechanism']} [Prova: {c['from_ulid']} → {c['to_ulid']}]"
                for c in self.build_chain(target_entity_id)]
