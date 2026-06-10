"""
Parsing estruturado (Diretriz II — "As Mãos").

Extrai entidades, relações societárias e transações de texto desestruturado.
Esta versão usa regras determinísticas (regex + gatilhos lexicais) para o
protótipo; em produção, `parse_document` chamaria um LLM com JSON mode e o
mesmo schema Pydantic — o resto do pipeline não muda.
"""
import re
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

# Tokens de identificação usados nos documentos da União (formato livre dos
# sistemas de origem: CPF_xxx / CNPJ_xxx, com pontuação ou apelidos).
_ID_RE = re.compile(r"\b(?:CPF|CNPJ)[_A-Za-z0-9.\-/]*", re.IGNORECASE)
_VALUE_RE = re.compile(r"R\$\s?([\d.]+,\d{2})")
_DATE_RE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")

_FAMILIA = ("cunhado", "cunhada", "irmão", "irmao", "irmã", "irma",
            "esposa", "marido", "filho", "filha", "pai", "mãe", "mae",
            "sogro", "sogra", "genro", "nora", "parente")
_MARCO_JUDICIAL = ("penhora", "citação", "citacao", "bloqueio judicial",
                   "arresto", "indisponibilidade")


class Entity(BaseModel):
    id: str = Field(..., description="CPF ou CNPJ")
    name: str = Field(..., description="Nome da pessoa ou empresa")
    type: str = Field(..., description="'PESSOA_FISICA' ou 'PESSOA_JURIDICA'")


class Relation(BaseModel):
    source_id: str
    target_id: str
    relation_type: str = Field(
        ...,
        description="'VENDEDOR_QUOTAS', 'PROCURADOR_COM_PODERES', 'FAMILIAR', 'SOCIO'",
    )
    value: Optional[float] = None
    date: Optional[str] = None


class Transaction(BaseModel):
    source_id: str
    target_id: str
    value: float
    date: Optional[str] = None  # ISO yyyy-mm-dd


class ParsedDocument(BaseModel):
    entities: List[Entity]
    relations: List[Relation]
    transactions: List[Transaction] = []
    marcos_judiciais: List[str] = []  # datas ISO de penhora/citação/bloqueio
    source_event_id: str


def _to_iso(br_date: str) -> str:
    try:
        return datetime.strptime(br_date, "%d/%m/%Y").date().isoformat()
    except ValueError:
        return br_date


def _to_float(br_value: str) -> float:
    return float(br_value.replace(".", "").replace(",", "."))


def _entity_type(token: str) -> str:
    return "PESSOA_FISICA" if token.upper().startswith("CPF") else "PESSOA_JURIDICA"


# Regexes dirigidas sobre o texto inteiro (frases partidas por \n ou por
# pontos dentro de CPFs tornam o split por sentenças inviável).
_ID = r"(?:CPF|CNPJ)[A-Za-z0-9_.\-/]*"
_VENDA_RE = re.compile(
    rf"({_ID})[^;]*?(?:transferiu|vendeu|cedeu)\s+(?:as\s+)?quotas.*?({_ID})",
    re.IGNORECASE | re.DOTALL,
)
_PROC_RE = re.compile(
    rf"({_ID})\s*,?\s*que.*?(?:nomeou|constituiu)(.*?)({_ID})(.*?poderes)",
    re.IGNORECASE | re.DOTALL,
)
_TX_RE = re.compile(
    rf"({_ID})\s+(?:transferiu|depositou|remeteu|enviou(?:\s+pix)?)\s+"
    rf"R\$\s?([\d.]+,\d{{2}})\s+para\s+(?:a\s+|o\s+)?({_ID})"
    rf"(?:\s+em\s+(\d{{2}}/\d{{2}}/\d{{4}}))?",
    re.IGNORECASE,
)
_MARCO_RE = re.compile(
    r"(penhora|cita[çc][ãa]o|bloqueio\s+judicial|arresto|indisponibilidade)"
    r"\D{0,80}?(\d{2}/\d{2}/\d{4})",
    re.IGNORECASE | re.DOTALL,
)


def parse_document(text: str, source_event_id: str) -> ParsedDocument:
    """Extração determinística de entidades, relações e transações."""
    flat = re.sub(r"\s+", " ", text)  # quebras de linha não são fronteiras

    tokens = list(dict.fromkeys(_ID_RE.findall(flat)))  # ordem, sem duplicados
    entities = [Entity(id=t, name=t, type=_entity_type(t)) for t in tokens]
    relations: List[Relation] = []
    transactions: List[Transaction] = []

    cpf_tokens = [t for t in tokens if t.upper().startswith("CPF")]
    devedor = cpf_tokens[0] if cpf_tokens else None

    # Venda/cessão de quotas: "<id> transferiu quotas ... <id destino>"
    for m in _VENDA_RE.finditer(flat):
        src, target = m.group(1), m.group(2)
        window = flat[m.start():m.end() + 120]
        dates = _DATE_RE.findall(window)
        values = _VALUE_RE.findall(window)
        relations.append(Relation(
            source_id=src, target_id=target,
            relation_type="VENDEDOR_QUOTAS",
            value=_to_float(values[0]) if values else None,
            date=_to_iso(dates[0]) if dates else None,
        ))

    # Procuração/administração com plenos poderes:
    # "<entidade>, que ... nomeou ... <pessoa> ... poderes"
    for m in _PROC_RE.finditer(flat):
        grantor, middle, who, tail = m.group(1), m.group(2), m.group(3), m.group(4)
        window = (middle + tail).lower()
        dates = _DATE_RE.findall(flat[m.start():m.end() + 60])
        relations.append(Relation(
            source_id=grantor, target_id=who,
            relation_type="PROCURADOR_COM_PODERES",
            date=_to_iso(dates[0]) if dates else None,
        ))
        if devedor and any(f in window for f in _FAMILIA):
            relations.append(Relation(
                source_id=devedor, target_id=who, relation_type="FAMILIAR"
            ))

    # Transações financeiras (extratos COAF)
    for m in _TX_RE.finditer(flat):
        transactions.append(Transaction(
            source_id=m.group(1), target_id=m.group(3),
            value=_to_float(m.group(2)),
            date=_to_iso(m.group(4)) if m.group(4) else None,
        ))

    # Marcos judiciais (penhora, citação, bloqueio) com data próxima
    marcos = [_to_iso(m.group(2)) for m in _MARCO_RE.finditer(flat)]

    return ParsedDocument(
        entities=entities,
        relations=relations,
        transactions=transactions,
        marcos_judiciais=marcos,
        source_event_id=source_event_id,
    )
