"""
case_memory — inteligência acumulada entre investigações (Fase 2, passo 4).

Impede que o agente analise o Caso B esquecendo que os mesmos laranjas e
offshores já operaram no Caso A. A persistência é o próprio log do
HeraclitusDB: cada insight já carrega `devedor_alvo` + `envolvidos` + tipo —
logo as "assinaturas de caso" reconstroem-se por replay (event sourcing), sem
um índice paralelo a manter coerente.

Decisão de engenharia: para RECORRÊNCIA (o mesmo CPF/CNPJ reaparecer) a
ferramenta certa é correspondência EXATA de identidade, não similaridade
vetorial. Logo:
  - recorrência  : interseção exata de entidades sobre os casos do log;
  - similaridade : Jaccard estrutural (entidades + padrões) entre casos.
A busca vetorial do HeraclitusDB fica como gancho para similaridade *semântica*
futura (esquemas parecidos mas com atores distintos) — `vector_hook`.

Uso no arranque do daemon:
    mem = CaseMemory(client).load()
    aviso = mem.check_new_case(entidades_do_caso, padroes, devedor=alvo)
    if aviso["alerta"]: ...  # atores reincidentes vindos de casos anteriores
"""
import json
from collections import defaultdict
from typing import Dict, List, Optional, Set


def _jaccard(a: Set[str], b: Set[str]) -> float:
    if not a and not b:
        return 0.0
    return round(len(a & b) / len(a | b), 3)


class CaseSignature:
    __slots__ = ("devedor", "entities", "patterns", "insights")

    def __init__(self, devedor: str):
        self.devedor = devedor
        self.entities: Set[str] = set()
        self.patterns: Set[str] = set()
        self.insights: int = 0

    def as_dict(self) -> dict:
        return {"devedor": self.devedor, "entities": sorted(self.entities),
                "patterns": sorted(self.patterns), "insights": self.insights}


class CaseMemory:
    def __init__(self, client):
        self.client = client
        self.cases: Dict[str, CaseSignature] = {}

    # ── carga a partir do log (assinaturas persistidas como insights) ──
    def load(self) -> "CaseMemory":
        self.cases.clear()
        rows = self.client.query(
            'MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n')
        for r in rows:
            if "INSIGHT_PERICIAL_FRAUDE" not in r.get("kind", ""):
                continue
            try:
                p = json.loads(r.get("content", "{}"))
            except (ValueError, TypeError):
                continue
            dev = p.get("devedor_alvo")
            if not dev:
                continue
            sig = self.cases.get(dev) or self.cases.setdefault(dev, CaseSignature(dev))
            sig.entities.update(p.get("envolvidos", []))
            sig.patterns.add(p.get("tipo_fraude", ""))
            sig.insights += 1
        return self

    # ── índice de atores ──────────────────────────────────────────────
    def _actor_cases(self) -> Dict[str, Set[str]]:
        """Entidade -> conjunto de casos (devedor_alvo) em que aparece."""
        appears: Dict[str, Set[str]] = defaultdict(set)
        for dev, sig in self.cases.items():
            for ent in sig.entities:
                appears[ent].add(dev)
        return appears

    def cross_case_actors(self) -> Dict[str, List[str]]:
        """Atores reincidentes: entidades presentes em >=2 casos distintos —
        os laranjas/offshores que circulam entre investigações."""
        return {ent: sorted(devs) for ent, devs in self._actor_cases().items()
                if len(devs) >= 2}

    def recurring_entities(self, entities, exclude_devedor: Optional[str] = None
                           ) -> Dict[str, List[str]]:
        """Para cada entidade do caso novo, em que OUTROS casos já apareceu."""
        appears = self._actor_cases()
        out: Dict[str, List[str]] = {}
        for ent in set(entities):
            prior = sorted(d for d in appears.get(ent, set()) if d != exclude_devedor)
            if prior:
                out[ent] = prior
        return out

    # ── similaridade estrutural (Jaccard) ─────────────────────────────
    def similar_cases(self, devedor: str, top: int = 5) -> List[dict]:
        target = self.cases.get(devedor)
        if not target:
            return []
        out = []
        for dev, sig in self.cases.items():
            if dev == devedor:
                continue
            je = _jaccard(target.entities, sig.entities)
            jp = _jaccard(target.patterns, sig.patterns)
            score = round(0.7 * je + 0.3 * jp, 3)
            if score > 0:
                out.append({
                    "devedor": dev,
                    "similaridade": score,
                    "entidades_comuns": sorted(target.entities & sig.entities),
                    "padroes_comuns": sorted(target.patterns & sig.patterns),
                })
        return sorted(out, key=lambda x: x["similaridade"], reverse=True)[:top]

    # ── verificação no arranque / caso novo ───────────────────────────
    def check_new_case(self, entities, patterns=None,
                       devedor: Optional[str] = None) -> dict:
        """Cruza um caso novo com a memória: atores reincidentes + casos
        estruturalmente parecidos. Chamado no arranque do daemon."""
        rec = self.recurring_entities(entities, exclude_devedor=devedor)
        similares = self.similar_cases(devedor) if devedor in self.cases else []
        return {
            "alerta": bool(rec),
            "atores_reincidentes": rec,
            "casos_similares": similares,
            "n_casos_memoria": len(self.cases),
        }

    def vector_hook(self, text: str, k: int = 5):
        """Gancho para similaridade SEMÂNTICA futura (esquemas parecidos com
        atores distintos), via o recall vetorial do HeraclitusDB. Recorrência
        de identidade NÃO usa isto — usa correspondência exata."""
        return self.client.recall(text, k)

    def stats(self) -> dict:
        return {
            "casos": len(self.cases),
            "atores_reincidentes": len(self.cross_case_actors()),
            "total_insights": sum(s.insights for s in self.cases.values()),
        }
