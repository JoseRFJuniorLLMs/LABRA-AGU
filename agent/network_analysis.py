"""
network_analysis — deteção de REDES entre casos (Fase 3).

Onde os detectores olham UM caso, este módulo olha o grafo GLOBAL e procura o
que liga vários casos: a mesma offshore, o mesmo laranja, o mesmo procurador a
servir muitos devedores — o FACILITADOR profissional por trás dos esquemas
(a "fábrica de laranjas"). Apanhar o facilitador vale mais do que apanhar um
devedor isolado.

Dois produtos, ambos sobre o `CaseGraph` consolidado (sem servidor):
  - facilitadores(): entidades não-devedoras a até N saltos de >=2 devedores
    distintos — o elo partilhado entre casos;
  - comunidades(): agrupa o grafo por *label propagation* (determinístico, sem
    dependências); comunidades com >=2 devedores são ANÉIS a investigar juntos.
"""
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Set

from .graph import CaseGraph

# Relações de "alienação" cujo ORIGEM é tipicamente um devedor (quem dissipa).
_ALIENACAO = ("VENDEDOR_QUOTAS", "DOACAO", "SUBORNO", "DESVIO_INSS",
              "CONVERTEU_CRIPTO")


class CrossCaseNetwork:
    def __init__(self, graph: CaseGraph, devedores: Optional[Set[str]] = None):
        self.g = graph
        self.adj = self._undirected()
        self.devedores = set(devedores) if devedores else self._infer_devedores()

    # ── topologia ──────────────────────────────────────────────────────
    def _undirected(self) -> Dict[str, Set[str]]:
        adj: Dict[str, Set[str]] = defaultdict(set)

        def link(s, d):
            if s != d:
                adj[s].add(d)
                adj[d].add(s)

        for lst in self.g.relations.values():
            for r in lst:
                link(r["src"], r["dst"])
        for t in self.g.transactions:
            link(t["src"], t["dst"])
        for tr in self.g.asset_transfers:
            link(tr["src"], tr["dst"])
        return adj

    def _infer_devedores(self) -> Set[str]:
        """Devedor = quem ALIENA (origem de venda/doação/transferência)."""
        devs: Set[str] = set()
        for rt in _ALIENACAO:
            for r in self.g.rels(rt):
                devs.add(r["src"])
        for t in self.g.transactions:
            devs.add(t["src"])
        return devs

    def _bfs(self, start: str, max_hops: int) -> Set[str]:
        seen, frontier = {start}, {start}
        for _ in range(max_hops):
            nxt: Set[str] = set()
            for n in frontier:
                nxt |= self.adj[n] - seen
            seen |= nxt
            frontier = nxt
            if not frontier:
                break
        return seen

    # ── facilitadores partilhados ──────────────────────────────────────
    def facilitadores(self, min_devedores: int = 2, max_hops: int = 2) -> List[dict]:
        """Entidades NÃO-devedoras alcançáveis (até max_hops) por >= min_devedores
        devedores distintos — offshore/laranja/procurador partilhado entre casos."""
        reach: Dict[str, Set[str]] = defaultdict(set)
        for dev in self.devedores:
            for n in self._bfs(dev, max_hops):
                if n != dev:
                    reach[n].add(dev)
        out = []
        for ent, devs in reach.items():
            if ent in self.devedores or len(devs) < min_devedores:
                continue
            out.append({
                "entidade": ent,
                "nome": self.g.entities.get(ent, ent),
                "kind": self.g.entity_kind.get(ent, ""),
                "n_devedores": len(devs),
                "devedores": sorted(devs),
                "grau": len(self.adj.get(ent, ())),
            })
        return sorted(out, key=lambda x: (x["n_devedores"], x["grau"]),
                      reverse=True)

    # ── comunidades (label propagation determinístico) ─────────────────
    def comunidades(self, max_iter: int = 30) -> List[dict]:
        if not self.adj:
            return []
        labels = {n: n for n in self.adj}
        nodes = sorted(self.adj)
        for _ in range(max_iter):
            changed = False
            for n in nodes:
                viz = self.adj[n]
                if not viz:
                    continue
                cnt = Counter(labels[m] for m in viz)
                # mais comum; desempate determinístico pelo menor label
                best = min(cnt, key=lambda lbl: (-cnt[lbl], lbl))
                if labels[n] != best:
                    labels[n] = best
                    changed = True
            if not changed:
                break
        grupos: Dict[str, Set[str]] = defaultdict(set)
        for n, lbl in labels.items():
            grupos[lbl].add(n)
        out = []
        for membros in grupos.values():
            devs = membros & self.devedores
            out.append({
                "membros": sorted(membros),
                "n_membros": len(membros),
                "devedores": sorted(devs),
                "n_devedores": len(devs),
                "anel": len(devs) >= 2,  # >=2 devedores juntos = anel
            })
        return sorted(out, key=lambda c: (c["n_devedores"], c["n_membros"]),
                      reverse=True)

    def aneis(self, min_devedores: int = 2) -> List[dict]:
        """Atalho: só as comunidades que são anéis (>= min_devedores)."""
        return [c for c in self.comunidades() if c["n_devedores"] >= min_devedores]
