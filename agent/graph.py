"""
CaseGraph — o grafo de investigação acumulativo.

A fraude real espalha-se por MUITOS documentos e fontes: a venda de quotas
vem da Junta Comercial, a procuração do cartório, as transferências do
COAF. Analisar um documento de cada vez nunca veria a triangulação inteira.

O CaseGraph resolve isto: à medida que documentos chegam, as entidades,
relações e transações são *acumuladas* num grafo único (com proveniência
por aresta — cada fato lembra de qual evento/ULID veio). Os padrões de
fraude correm sobre o grafo consolidado, não sobre um texto isolado.

Coerente com event sourcing: o grafo é uma materialized view do log e é
reconstruível por replay (o daemon re-alimenta o grafo desde o checkpoint).
A resolução de entidades (entities.py) garante que o mesmo CPF, escrito de
formas diferentes em fontes diferentes, é um único nó.
"""
from collections import defaultdict
from typing import Dict, List, Set, Tuple

from .entities import entity_kind, normalize_id
from .parser import ParsedDocument


class CaseGraph:
    def __init__(self):
        # id canónico -> rótulo display (primeiro visto)
        self.entities: Dict[str, str] = {}
        self.entity_kind: Dict[str, str] = {}
        # arestas tipadas com proveniência: cada uma é
        # (src, dst, value, date, {event_ids})
        self.relations: Dict[str, List[dict]] = defaultdict(list)  # por tipo
        self.transactions: List[dict] = []
        # marco judicial -> conjunto de event_ids que o atestam
        self.marcos: Dict[str, Set[str]] = defaultdict(set)
        # contagem de aparições por entidade (sinal para ACT-R/relevância)
        self.mentions: Dict[str, int] = defaultdict(int)
        # BENS (ativos): o grafo deixa de ser só de pessoas. Cada bem é um nó
        # com tipo e valor de mercado; alienações ligam pessoas a um bem.
        self.assets: Dict[str, dict] = {}            # id -> {kind, valor_mercado, events}
        self.asset_transfers: List[dict] = []        # {asset_id, src, dst, value, date, events}
        # Atributos por entidade (renda anual, data de constituição, …) — base
        # para a compatibilidade renda×patrimônio e contrato direcionado.
        self.entity_attrs: Dict[str, dict] = defaultdict(dict)

    # ── ingestão ──────────────────────────────────────────────────────
    def ingest(self, doc: ParsedDocument) -> Set[str]:
        """Funde um documento no grafo. Devolve os ids canónicos tocados."""
        ev = doc.source_event_id
        touched: Set[str] = set()

        for e in doc.entities:
            cid = normalize_id(e.id)
            self.entities.setdefault(cid, e.name)
            self.entity_kind.setdefault(cid, entity_kind(cid))
            self.mentions[cid] += 1
            touched.add(cid)

        for r in doc.relations:
            src, dst = normalize_id(r.source_id), normalize_id(r.target_id)
            self._add_relation(r.relation_type, src, dst, r.value, r.date, ev)
            touched.update({src, dst})

        for t in doc.transactions:
            src, dst = normalize_id(t.source_id), normalize_id(t.target_id)
            self.transactions.append({
                "src": src, "dst": dst, "value": t.value,
                "date": t.date, "events": {ev},
            })
            touched.update({src, dst})

        for m in doc.marcos_judiciais:
            self.marcos[m].add(ev)

        for a in getattr(doc, "assets", []):
            meta = self.assets.setdefault(
                a.id, {"kind": a.kind, "valor_mercado": None, "events": set()})
            meta["events"].add(ev)
            if a.valor_mercado is not None:
                meta["valor_mercado"] = a.valor_mercado

        for tr in getattr(doc, "asset_transfers", []):
            src, dst = normalize_id(tr.from_id), normalize_id(tr.to_id)
            self.asset_transfers.append({
                "asset_id": tr.asset_id, "src": src, "dst": dst,
                "value": tr.value, "date": tr.date, "events": {ev},
            })
            self.mentions[src] += 1
            self.mentions[dst] += 1
            touched.update({src, dst})

        for ea in getattr(doc, "entity_attrs", []):
            cid = normalize_id(ea.id)
            val = ea.value_num if ea.value_num is not None else ea.value_str
            self.entity_attrs[cid][ea.key] = val
            touched.add(cid)

        return touched

    def _add_relation(self, rtype, src, dst, value, date, ev):
        for r in self.relations[rtype]:
            if r["src"] == src and r["dst"] == dst:
                r["events"].add(ev)
                if value is not None:
                    r["value"] = value
                if date is not None:
                    r["date"] = date
                return
        self.relations[rtype].append({
            "src": src, "dst": dst, "value": value, "date": date,
            "events": {ev},
        })

    # ── consultas usadas pelos padrões ────────────────────────────────
    def rels(self, rtype: str) -> List[dict]:
        return self.relations.get(rtype, [])

    def marcos_datas(self) -> List[str]:
        return list(self.marcos.keys())

    def marcos_events(self) -> Set[str]:
        out: Set[str] = set()
        for evs in self.marcos.values():
            out |= evs
        return out

    def events_for_entities(self, ids: Set[str]) -> Set[str]:
        """Todos os ULIDs de documentos que mencionam estas entidades."""
        evs: Set[str] = set()
        for rtype in self.relations:
            for r in self.relations[rtype]:
                if r["src"] in ids or r["dst"] in ids:
                    evs |= r["events"]
        for t in self.transactions:
            if t["src"] in ids or t["dst"] in ids:
                evs |= t["events"]
        return evs

    def stats(self) -> dict:
        return {
            "entities": len(self.entities),
            "relations": sum(len(v) for v in self.relations.values()),
            "transactions": len(self.transactions),
            "marcos": len(self.marcos),
            "assets": len(self.assets),
            "asset_transfers": len(self.asset_transfers),
        }
