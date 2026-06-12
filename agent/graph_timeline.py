"""
graph_timeline — estado do CaseGraph versionado por tempo (AS OF LSN).

Infraestrutura-base da Fase 2 (descoberta indutiva e litígio). Aproveita a
capacidade NATIVA do HeraclitusDB de ler o estado do log em qualquer ponto do
passado (`MATCH (n) AS OF LSN <n>`) para reconstruir o grafo de caso como ele
existia naquele instante — sem mutar nada, fiel ao event sourcing.

A reconstrução é DETERMINÍSTICA e reusa exatamente o mesmo caminho do daemon
(`parse_document` -> `CaseGraph.ingest`), de modo que `at_lsn(L)` é idêntico
ao grafo que o daemon teria depois de processar o evento de LSN L. Cada aresta
preserva os ULIDs de origem (proveniência), pré-requisito para os módulos de
nexo causal, contrafactual e litígio.

Uso típico:
    tl = GraphTimeline(client)
    g_agora = tl.at_lsn(tl.head())          # estado atual
    g_antes = tl.at_lsn(lsn_vespera)         # estado na véspera da penhora
    novidades = tl.diff(lsn_vespera, tl.head())   # o que mudou entretanto

Os outros módulos da Fase 2 consomem `at_lsn` para:
  - counterfactual.py : clonar o grafo AS OF e expurgar um ULID;
  - causal_chain.py   : ordenar eventos por LSN reconstruindo estados;
  - litigator.py      : citar o estado exato do patrimônio "na data X".
"""
import copy
from typing import Callable, Dict, List, Optional, Tuple

from .client import HeraclitusClient
from .graph import CaseGraph
from .parser import ParsedDocument, parse_document

# Apenas eventos-fonte (documentos) constroem o grafo. DIRETRIZ e os próprios
# INSIGHT são metadados/saída — nunca alteram a topologia patrimonial.
_SOURCE_KIND = "Observation"


class GraphTimeline:
    def __init__(self, client: HeraclitusClient,
                 parser: Optional[Callable[[str, str], ParsedDocument]] = None):
        self.client = client
        # Determinístico por defeito — a reconstrução histórica não pode
        # depender de um LLM não-reprodutível.
        self._parse = parser or parse_document

    # ── pontos do tempo ────────────────────────────────────────────────
    def head(self) -> int:
        """LSN do topo do log (o 'agora')."""
        return self.client.snapshot()

    def at_lsn(self, lsn: int) -> CaseGraph:
        """Reconstrói o CaseGraph AS OF a posição de log `lsn` — exatamente o
        `AS OF LSN` nativo do HeraclitusDB: inclui os eventos com LSN < `lsn`.
        Logo `at_lsn(head())` = estado atual; para incluir um evento concreto
        de LSN `e`, use `including(e)` (= `at_lsn(e + 1)`)."""
        rows = self.client.query(f"MATCH (n) AS OF LSN {int(lsn)} RETURN n")
        return self._materialize(rows)

    def including(self, event_lsn: int) -> CaseGraph:
        """Estado logo APÓS o evento de LSN `event_lsn` (conveniência)."""
        return self.at_lsn(int(event_lsn) + 1)

    def at_timestamp(self, ts) -> CaseGraph:
        """Reconstrói o grafo AS OF um instante (delega a resolução temporal
        ao HeraclitusDB via `AS OF TIMESTAMP`). `ts` no formato aceite pelo
        servidor (epoch ms ou ISO, conforme o build)."""
        try:
            rows = self.client.query(f"MATCH (n) AS OF TIMESTAMP {ts} RETURN n")
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                "AS OF TIMESTAMP não resolvido pelo servidor; use at_lsn(). "
                f"Detalhe: {e}")
        return self._materialize(rows)

    # ── replay determinístico ─────────────────────────────────────────
    def _materialize(self, rows: List[dict]) -> CaseGraph:
        """Funde os eventos-fonte (já limitados pela cláusula AS OF) num
        CaseGraph novo, por ordem de LSN. A ordem importa: valores/datas de
        uma aresta podem ser sobrescritos por um evento posterior."""
        g = CaseGraph()
        for r in sorted(rows, key=lambda x: x.get("lsn", 0)):
            if r.get("kind") != _SOURCE_KIND:
                continue
            text = r.get("content", "") or ""
            if not text.strip():
                continue
            try:
                doc = self._parse(text, source_event_id=r["id"])
                g.ingest(doc)
            except Exception:  # noqa: BLE001 — doc malformado não quebra a timeline
                continue
        return g

    # ── fatias e diferenças ───────────────────────────────────────────
    def frames(self, lsns: List[int]) -> List[Tuple[int, CaseGraph]]:
        """Vários estados do grafo, um por LSN pedido. Faz UM único replay
        do log e tira um snapshot (deep copy) em cada checkpoint — O(eventos),
        não O(eventos × frames)."""
        if not lsns:
            return []
        checkpoints = sorted(set(int(x) for x in lsns))
        rows = sorted(
            self.client.query("MATCH (n) RETURN n"),
            key=lambda x: x.get("lsn", 0))
        out: List[Tuple[int, CaseGraph]] = []
        g = CaseGraph()
        ci = 0
        for r in rows:
            lsn = r.get("lsn", 0)
            # Checkpoint na posição p inclui eventos com LSN < p; ao alcançar
            # um evento com LSN >= p, congela ANTES de o ingerir.
            while ci < len(checkpoints) and lsn >= checkpoints[ci]:
                out.append((checkpoints[ci], copy.deepcopy(g)))
                ci += 1
            if r.get("kind") == _SOURCE_KIND:
                text = r.get("content", "") or ""
                if text.strip():
                    try:
                        g.ingest(self._parse(text, source_event_id=r["id"]))
                    except Exception:  # noqa: BLE001
                        pass
        while ci < len(checkpoints):
            out.append((checkpoints[ci], copy.deepcopy(g)))
            ci += 1
        return out

    def diff(self, lsn_a: int, lsn_b: int) -> Dict[str, list]:
        """O que surgiu no grafo entre A e B (com A < B): entidades, relações,
        transações e marcos novos. Base visual do 'momento do esvaziamento'."""
        ga, gb = self.at_lsn(lsn_a), self.at_lsn(lsn_b)
        ent = [{"id": c, "nome": gb.entities[c], "kind": gb.entity_kind.get(c)}
               for c in gb.entities if c not in ga.entities]
        rels = []
        for rtype, lst in gb.relations.items():
            old = {(r["src"], r["dst"]) for r in ga.relations.get(rtype, [])}
            for r in lst:
                if (r["src"], r["dst"]) not in old:
                    rels.append({"type": rtype, "src": r["src"], "dst": r["dst"],
                                 "value": r["value"], "date": r["date"],
                                 "events": sorted(r["events"])})
        old_tx = {(t["src"], t["dst"], t["value"], t["date"])
                  for t in ga.transactions}
        txs = [{"src": t["src"], "dst": t["dst"], "value": t["value"],
                "date": t["date"], "events": sorted(t["events"])}
               for t in gb.transactions
               if (t["src"], t["dst"], t["value"], t["date"]) not in old_tx]
        marcos = [m for m in gb.marcos if m not in ga.marcos]
        return {"entities": ent, "relations": rels,
                "transactions": txs, "marcos": marcos}

    # ── serialização (para dashboard / litigator) ─────────────────────
    @staticmethod
    def snapshot_dict(graph: CaseGraph) -> dict:
        """Estado do grafo num dict JSON-serializável, com proveniência por
        aresta (ULIDs). Consumível pela visão 'AS OF' do painel e pelo
        litigator (notas de rodapé por ULID)."""
        return {
            "stats": graph.stats(),
            "entities": [{"id": c, "nome": n, "kind": graph.entity_kind.get(c)}
                         for c, n in graph.entities.items()],
            "relations": [
                {"type": rtype, "src": r["src"], "dst": r["dst"],
                 "value": r["value"], "date": r["date"],
                 "events": sorted(r["events"])}
                for rtype, lst in graph.relations.items() for r in lst],
            "transactions": [
                {"src": t["src"], "dst": t["dst"], "value": t["value"],
                 "date": t["date"], "events": sorted(t["events"])}
                for t in graph.transactions],
            "marcos": [{"data": m, "events": sorted(evs)}
                       for m, evs in graph.marcos.items()],
        }

    def frame_dict(self, lsn: int) -> dict:
        """Snapshot serializável do grafo AS OF `lsn` (com o próprio LSN)."""
        d = self.snapshot_dict(self.at_lsn(lsn))
        d["as_of_lsn"] = int(lsn)
        return d
