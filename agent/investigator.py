"""
Investigação contínua (Diretriz III — "O Cérebro").

O Investigator é um motor de padrões dirigível:
  - percorre o catálogo de padrões de fraude (agent/patterns.py);
  - mantém memória ACT-R entre documentos (entidades recorrentes sobem);
  - aceita DIRETRIZES da Procuradoria (alvos com boost de ativação, foco
    em padrões específicos) — cada diretriz é um evento do log, e o seu
    ULID entra na proveniência dos insights que ela influenciou.
"""
import datetime
from typing import Dict, List, Optional

from .act_r import ACTREngine
from .parser import ParsedDocument
from .patterns import PATTERNS


class Directive:
    """Uma ordem da Procuradoria, materializada de um evento DIRETRIZ."""

    def __init__(self, event_id: str, alvos: List[str], foco: str = "",
                 padroes: Optional[List[str]] = None, boost: int = 5):
        self.event_id = event_id          # ULID do evento DIRETRIZ no log
        self.alvos = alvos or []
        self.foco = foco
        self.padroes = [p for p in (padroes or []) if p in PATTERNS]
        self.boost = boost

    def __repr__(self):
        return f"Directive({self.event_id}, alvos={self.alvos}, padroes={self.padroes})"


class Investigator:
    def __init__(self, decay_rate: float = 0.5):
        self.memory = ACTREngine(decay_rate=decay_rate)
        self.directives: List[Directive] = []

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
        hits = []
        for d in self.directives:
            alvo_hit = any(a in envolvidos for a in d.alvos)
            padrao_hit = pattern in d.padroes
            if alvo_hit or padrao_hit:
                hits.append(d)
        return hits

    # ── Pipeline por documento ────────────────────────────────────────
    def process_document(self, doc: ParsedDocument) -> List[dict]:
        """
        Analisa um documento estruturado contra o catálogo (ou o foco das
        diretrizes ativas) e devolve a lista de insights periciais.
        """
        # 1. Memória: toda entidade vista é um acesso ACT-R
        for entity in doc.entities:
            self.memory.record_access(entity.id)

        # 2. Padrões
        insights: List[dict] = []
        for name in self._active_patterns():
            achado = PATTERNS[name](doc)
            if achado:
                insights.append(self._build_insight(doc, achado))
        return insights

    # compat: API antiga devolvia um único insight ou None
    def process_document_single(self, doc: ParsedDocument) -> Optional[dict]:
        found = self.process_document(doc)
        return found[0] if found else None

    def _build_insight(self, doc: ParsedDocument, achado: dict) -> dict:
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

        # Proveniência: documento-fonte + diretrizes que dirigiram o achado.
        parents = [doc.source_event_id] + [d.event_id for d in directives]

        return {
            "event_type": "INSIGHT_PERICIAL_FRAUDE",
            "timestamp_hlc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "agent_id": "agente_pericial_labra_v1",
            "parents": parents,
            "payload": payload,
        }
