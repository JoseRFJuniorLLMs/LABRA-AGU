"""
evidence_scorer — força probatória por qualidade da fonte (Fase 2, passo 3).

Mitiga fragilidade probatória e alucinação: cada fato vale conforme a fonte
ORIGINAL que o sustenta (rastreada por ULID no log do HeraclitusDB). Sem
proveniência rastreável até um ULID válido, o fato não pontua (regra "sem
alucinações").

Matriz de pesos nativos (HOTO):
  - bancária/oficial (COAF, BACENJUD, extratos) ........ 1.0
  - registros públicos (Junta, Cartórios) .............. 0.9
  - documentos particulares (contratos gaveta, txt) .... 0.6
  - redes sociais / declarações testemunhais ........... 0.4

A fonte de cada ULID vem dos `attrs` do evento (source/table/doc_ref), que o
pipeline grava na ingestão. O score de uma tese é a média dos pesos das suas
provas.
"""
from typing import Callable, Dict, List, Optional

# Pesos por categoria (sobrescrevíveis no construtor).
DEFAULT_WEIGHTS: Dict[str, float] = {
    "bancaria_oficial": 1.0,
    "registro_publico": 0.9,
    "documento_particular": 0.6,
    "social_testemunhal": 0.4,
    "desconhecida": 0.5,
}

# Pistas lexicais nos attrs -> categoria.
_BANK = ("moviment", "comunic", "extrato", "bacen", "coaf", "bancar")
_REGISTRO = ("altera", "procurac", "procuração", "junta", "cartor", "registro")
_SOCIAL = ("rede", "social", "depoiment", "testemunh", "escuta")


def classify_source(attrs: dict) -> str:
    """Categoria da fonte a partir dos attrs do evento (source/table/doc_ref)."""
    src = (attrs.get("source") or "").lower()
    table = (attrs.get("table") or "").lower()
    ref = (attrs.get("doc_ref") or "").lower()
    blob = f"{src} {table} {ref}"
    if any(k in blob for k in _BANK):
        return "bancaria_oficial"
    if src == "sql" or any(k in table for k in _REGISTRO):
        return "registro_publico"
    if any(k in ref for k in _SOCIAL):
        return "social_testemunhal"
    if src == "file":
        return "documento_particular"
    return "desconhecida"


class EvidenceScorer:
    def __init__(self, client=None,
                 source_map: Optional[Dict[str, dict]] = None,
                 weights: Optional[Dict[str, float]] = None):
        """`client` resolve attrs por ULID a partir do log; em alternativa,
        `source_map` (ulid -> attrs) para uso offline/teste."""
        self.client = client
        self.source_map = source_map
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}
        self._index: Optional[Dict[str, dict]] = None

    def _attrs_of(self, ulid: str) -> Optional[dict]:
        if self.source_map is not None:
            return self.source_map.get(ulid)
        if self.client is None:
            return None
        if self._index is None:  # cache: um único MATCH e indexa por id
            self._index = {}
            for r in self.client.query("MATCH (n) RETURN n"):
                self._index[r.get("id")] = r.get("attrs", {})
        return self._index.get(ulid)

    def weight_of(self, ulid: str) -> Optional[float]:
        """Peso de uma prova; None se a proveniência não for rastreável."""
        attrs = self._attrs_of(ulid)
        if attrs is None:
            return None  # sem ULID válido no log -> não pontua
        return self.weights[classify_source(attrs)]

    def score(self, provenance_ulids: List[str]) -> dict:
        """Score probatório (média dos pesos das provas rastreáveis)."""
        pesos, fontes, ignorados = [], [], []
        for u in provenance_ulids:
            w = self.weight_of(u)
            if w is None:
                ignorados.append(u)
                continue
            pesos.append(w)
            fontes.append({"ulid": u, "categoria": classify_source(self._attrs_of(u)),
                           "peso": w})
        media = round(sum(pesos) / len(pesos), 3) if pesos else 0.0
        return {
            "score": media,
            "n_provas": len(pesos),
            "fontes": fontes,
            "ignorados_sem_proveniencia": ignorados,
        }

    def score_insight(self, insight: dict) -> dict:
        """Pontua um insight pericial pelos seus `parents` (ULIDs-fonte)."""
        parents = insight.get("parents") or insight.get("source_events") or []
        return self.score(list(parents))
