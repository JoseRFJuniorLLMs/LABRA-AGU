"""
Investigação contínua (Diretriz III — "O Cérebro").

O Investigator é um motor de padrões dirigível que opera sobre um GRAFO DE
CASO ACUMULADO (agent/graph.py), não documento a documento:

  - cada documento é fundido no grafo (resolução de entidades incluída);
  - os padrões correm sobre o grafo consolidado — fraude espalhada por
    várias fontes é finalmente visível;
  - achados são DEDUPLICADOS por assinatura (padrão + envolvidos), evitando
    alertas repetidos a cada novo documento que toca o mesmo esquema;
  - a memória ACT-R prioriza entidades recorrentes; DIRETRIZes da
    Procuradoria dão boost dirigido e entram na proveniência dos insights
    que influenciaram;
  - a proveniência de cada insight é COMPOSTA: todos os ULIDs dos
    documentos que sustentam o achado + os ULIDs das diretrizes aplicáveis.
"""
import datetime
from typing import Dict, List, Optional, Set, Tuple

from .act_r import ACTREngine
from .graph import CaseGraph
from .parser import ParsedDocument
from .patterns import PATTERNS


class Directive:
    """Uma ordem da Procuradoria, materializada de um evento DIRETRIZ."""

    def __init__(self, event_id: str, alvos: List[str], foco: str = "",
                 padroes: Optional[List[str]] = None, boost: int = 5):
        from .entities import normalize_id
        self.event_id = event_id          # ULID do evento DIRETRIZ no log
        self.alvos = [normalize_id(a) for a in (alvos or [])]
        self.foco = foco
        self.padroes = [p for p in (padroes or []) if p in PATTERNS]
        self.boost = boost

    def __repr__(self):
        return f"Directive({self.event_id}, alvos={self.alvos}, padroes={self.padroes})"


class Investigator:
    def __init__(self, decay_rate: float = 0.5):
        self.memory = ACTREngine(decay_rate=decay_rate)
        self.graph = CaseGraph()
        self.directives: List[Directive] = []
        # assinaturas (padrão, frozenset(envolvidos)) já emitidas — dedup
        self._emitted: Set[Tuple[str, frozenset]] = set()

    # ── Diretrizes ────────────────────────────────────────────────────
    def register_directive(self, directive: Directive):
        """Acolhe uma ordem: alvos ganham boost imediato de ativação."""
        self.directives.append(directive)
        for alvo in directive.alvos:
            self.memory.boost(alvo, directive.boost)

    def _active_patterns(self) -> List[str]:
        """Se alguma diretriz restringe padrões, a união delas manda;
        sem diretrizes restritivas, o catálogo inteiro é vigiado."""
        focados = [p for d in self.directives for p in d.padroes]
        return list(dict.fromkeys(focados)) if focados else list(PATTERNS)

    def _matching_directives(self, envolvidos: List[str], pattern: str) -> List[Directive]:
        """Diretrizes que influenciaram este achado (por alvo ou padrão)."""
        env = set(envolvidos)
        hits = []
        for d in self.directives:
            if any(a in env for a in d.alvos) or pattern in d.padroes:
                hits.append(d)
        return hits

    # ── Pipeline por documento ────────────────────────────────────────
    def process_document(self, doc: ParsedDocument) -> List[dict]:
        """
        Funde o documento no grafo de caso e reavalia o catálogo sobre o
        grafo consolidado. Devolve apenas insights NOVOS (deduplicados).
        """
        # 1. Acumula no grafo (resolve entidades) e regista acessos ACT-R
        touched = self.graph.ingest(doc)
        for cid in touched:
            self.memory.record_access(cid)

        # 2. Padrões sobre o grafo inteiro
        insights: List[dict] = []
        for name in self._active_patterns():
            for achado in PATTERNS[name](self.graph):
                sig = (achado["pattern"], frozenset(achado["envolvidos"]))
                if sig in self._emitted:
                    continue  # já alertado — não repetir
                self._emitted.add(sig)
                insights.append(self._build_insight(achado))
        return insights

    # compat: devolve um único insight ou None (usado em testes one-shot)
    def process_document_single(self, doc: ParsedDocument) -> Optional[dict]:
        found = self.process_document(doc)
        return found[0] if found else None

    def _build_insight(self, achado: dict) -> dict:
        envolvidos: List[str] = achado["envolvidos"]
        directives = self._matching_directives(envolvidos, achado["pattern"])

        # Ativações ACT-R reais (não números decorativos): o ranking que o
        # filtro sub-simbólico atribui a cada envolvido neste instante.
        ativacoes: Dict[str, float] = {
            e: round(self.memory.calculate_activation(e), 4) for e in envolvidos
        }

        payload = {
            "devedor_alvo": achado["devedor_alvo"],
            "tipo_fraude": achado["pattern"],
            "severidade": achado["severidade"],
            "descricao": achado["descricao"],
            "conclusao_juridica": achado["conclusao_juridica"],
            "envolvidos": envolvidos,
            "ativacao_act_r": ativacoes,
            "diretrizes_aplicadas": [d.event_id for d in directives],
        }

        # Proveniência COMPOSTA: todos os documentos que sustentam o achado
        # + as diretrizes que o dirigiram. Ordenada para determinismo.
        source_events = sorted(achado.get("source_events", set()))
        parents = source_events + [d.event_id for d in directives]

        return {
            "event_type": "INSIGHT_PERICIAL_FRAUDE",
            "timestamp_hlc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "agent_id": "agente_pericial_labra_v1",
            "parents": parents,
            "payload": payload,
        }
