"""
theory_builder — o cérebro unificador (Fase 2, passo 5, orquestrador).

Recebe os eventos brutos do log do HeraclitusDB e sintetiza a TEORIA DO CASO,
chamando os outros nove módulos:

  graph_timeline   -> reconstrói o CaseGraph AS OF o estado atual;
  patterns + asset_shield -> deteta esquemas (dedutivo);
  anomaly_engine   -> desvios inéditos (indutivo);
  evidence_scorer  -> pondera cada achado pela qualidade da fonte (e descarta
                      o que não tem proveniência — "sem alucinações");
  causal_chain     -> nexo temporal por ULID;
  counterfactual   -> provas essenciais (cuja subtração rompe o esquema);
  case_memory      -> atores reincidentes de investigações anteriores;
  legal_mapper     -> subsunção à norma;
  litigator        -> minuta da peça com notas de rodapé por ULID.

Saída: `TheoryOfCase` (narrativa, alvos, matriz de evidências ordenada por
força probatória, anomalias, nexo, provas essenciais, reincidência e minuta).
"""
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from .anomaly_engine import AnomalyEngine
from .asset_shield import SHIELD_PATTERNS
from .case_memory import CaseMemory
from .causal_chain import CausalChainBuilder
from .counterfactual import CounterfactualEngine
from .evidence_scorer import EvidenceScorer
from .graph_timeline import GraphTimeline
from .legal_mapper import LegalMapper
from .litigator import Litigator
from .patterns import PATTERNS

_SEVW = {"CRITICA": 3, "ALTA": 2, "MEDIA": 1, "BAIXA": 0}


@dataclass
class TheoryOfCase:
    devedor: str
    devedor_nome: str
    narrativa: str
    alvos: List[str]
    matriz_evidencias: List[dict]
    anomalias: List[dict]
    nexo_causal: List[str]
    provas_essenciais: List[str]
    reincidencia: dict
    minuta: str

    def to_dict(self) -> dict:
        return asdict(self)


class TheoryBuilder:
    def __init__(self, client):
        self.client = client
        self.timeline = GraphTimeline(client)
        self.scorer = EvidenceScorer(client)
        self.mapper = LegalMapper()
        self.litigator = Litigator(self.mapper)
        self.memory = CaseMemory(client)

    def _detect(self, g) -> List[dict]:
        """Dedutivo (patterns + asset_shield), pontuado e filtrado por
        proveniência rastreável (sem alucinações)."""
        achados: List[dict] = []
        for fn in {**PATTERNS, **SHIELD_PATTERNS}.values():
            achados.extend(fn(g))
        for a in achados:
            evs = sorted(a.get("source_events", set()))
            a["source_events"] = evs
            a["evidence_score"] = self.scorer.score(evs)["score"]
        return [a for a in achados if a["evidence_score"] > 0]

    def _narrativa(self, nome, devedor, patterns, valor, reincidencia) -> str:
        partes = [f"O executado {nome} (`{devedor}`) articulou esquema de "
                  f"blindagem patrimonial detectado em {len(patterns)} frente(s): "
                  f"{', '.join(patterns)}."]
        if valor:
            partes.append(f"Identificada dissipação fracionada de {valor}.")
        rec = reincidencia.get("atores_reincidentes") or {}
        if rec:
            partes.append("Atores reincidentes de investigações anteriores: "
                          + ", ".join(f"`{k}`" for k in rec) + ".")
        partes.append("O nexo de causalidade e as provas essenciais demonstram o "
                      "consilium fraudis, com cadeia de custódia por ULID.")
        return " ".join(partes)

    def _detection(self, graph=None):
        """Grafo AS OF + achados agrupados por devedor (uma só passagem).
        `graph` opcional reusa um CaseGraph já reconstruído."""
        g = graph if graph is not None else self.timeline.at_lsn(self.timeline.head())
        por_dev = defaultdict(list)
        for a in self._detect(g):
            por_dev[a["devedor_alvo"]].append(a)
        return g, por_dev

    def _assemble(self, g, por_dev, anomalias, devedor) -> Optional[TheoryOfCase]:
        """Monta a TheoryOfCase de um devedor sobre um grafo já reconstruído."""
        case = sorted(por_dev.get(devedor, []),
                      key=lambda a: a["evidence_score"], reverse=True)
        if not case:
            return None
        causal = CausalChainBuilder(g).narrative(devedor)
        sink = next((a["envolvidos"][2] for a in case
                     if a["pattern"] == "triangulacao_offshore"
                     and len(a["envolvidos"]) >= 3), None)
        essenciais = (CounterfactualEngine(g).essential_ulids(devedor, sink)
                      if sink else [])
        alvos = sorted({e for a in case for e in a["envolvidos"]})
        reincidencia = self.memory.check_new_case(alvos, devedor=devedor)
        nome = g.entities.get(devedor, devedor)
        patterns = list(dict.fromkeys(a["pattern"] for a in case))
        valor = next((a.get("_valor") for a in case if a.get("_valor")), None)
        narrativa = self._narrativa(nome, devedor, patterns, valor, reincidencia)
        minuta = self.litigator.minuta(
            devedor=devedor, devedor_nome=nome, achados=case,
            causal=causal, essenciais=essenciais)
        return TheoryOfCase(
            devedor=devedor, devedor_nome=nome, narrativa=narrativa,
            alvos=alvos, matriz_evidencias=case, anomalias=anomalias,
            nexo_causal=causal, provas_essenciais=essenciais,
            reincidencia=reincidencia, minuta=minuta)

    def build(self, devedor: Optional[str] = None, graph=None) -> Optional[TheoryOfCase]:
        g, por_dev = self._detection(graph)
        if not por_dev:
            return None
        if devedor is None:  # alvo principal: mais achados, depois mais grave
            devedor = max(por_dev, key=lambda d: (
                len(por_dev[d]), sum(_SEVW.get(x["severidade"], 0) for x in por_dev[d])))
        anomalias = AnomalyEngine(g).detect_all()
        self.memory.load()
        return self._assemble(g, por_dev, anomalias, devedor)

    def build_all(self, graph=None) -> List[TheoryOfCase]:
        """Uma teoria por devedor — reusa um único grafo, detecção, cálculo de
        anomalias e carga de memória (O(grafo) + por-caso leve)."""
        g, por_dev = self._detection(graph)
        if not por_dev:
            return []
        anomalias = AnomalyEngine(g).detect_all()
        self.memory.load()
        return [t for t in (self._assemble(g, por_dev, anomalias, d)
                            for d in sorted(por_dev)) if t]
