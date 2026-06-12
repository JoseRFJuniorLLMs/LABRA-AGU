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

from .entities import normalize_id

# Identificadores reconhecidos. Os bancos da AGU guardam CPF/CNPJ como
# NÚMEROS (crus ou formatados), não como tokens "CPF_xxx"; documentos de
# protótipo usam o prefixo. Reconhecemos os dois mundos:
#   - tokens prefixados:  CPF_xxx / CNPJ_xxx (apelidos, protótipo)
#   - CPF formatado:      529.982.247-25
#   - CNPJ formatado:     11.222.333/0001-81
#   - números crus:       52998224725 (11) / 11222333000181 (14)
# A canonicalização e validação de dígitos ficam em entities.normalize_id.
_ID = (r"(?:(?:CPF|CNPJ)[A-Za-z0-9_.\-/]*"
       r"|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
       r"|\d{3}\.\d{3}\.\d{3}-\d{2}"
       r"|\d{14}|\d{11})")
_ID_RE = re.compile(_ID, re.IGNORECASE)
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
    # Decide pelo id canónico (reconhece CPF prefixado, formatado ou cru).
    return "PESSOA_FISICA" if normalize_id(token).upper().startswith("CPF") else "PESSOA_JURIDICA"


# Regexes dirigidas sobre o texto inteiro (frases partidas por \n ou por
# pontos dentro de CPFs tornam o split por sentenças inviável).
_VENDA_RE = re.compile(
    rf"({_ID})[^;]*?(?:transferiu|vendeu|cedeu)\s+(?:as\s+)?quotas.*?({_ID})",
    re.IGNORECASE | re.DOTALL,
)
# "que" é opcional: a nomeação pode vir no mesmo período ("..., que nomeou...")
# ou num documento separado ("A CNPJ_X nomeou CPF_Y ... poderes"). O outorgante
# é o id IMEDIATAMENTE antes de "nomeou/constituiu" (sem outro id no meio),
# senão o CPF do devedor seria capturado em vez da offshore.
_PROC_RE = re.compile(
    rf"({_ID})(?:(?!{_ID}).)*?(?:nomeou|constituiu)(.*?)({_ID})(.*?poderes)",
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
# Vínculo familiar AUTÓNOMO (documento sem procuração): "<laranja> é cunhado
# do devedor <devedor>". Essencial quando a família vem numa fonte separada
# das pernas societárias da triangulação.
_KINSHIP = "|".join(_FAMILIA)
_FAMILIA_RE = re.compile(
    rf"({_ID})\b[^.;]{{0,80}}?\b(?:{_KINSHIP})\b[^.;]{{0,40}}?devedor\s+({_ID})",
    re.IGNORECASE,
)

# Heurísticas avançadas de blindagem (Fase 2 — alimentam o asset_shield). Cada
# uma liga dois ids por um gatilho lexical, sem outro id no meio (precisão).
#   DOACAO     : "<X> doou ... para <Y>"                         (doação cruzada)
#   ADMINISTRA : "<X> ... usufrutuário/administrador vitalício ... <Y>"  (holding)
#   CONTROLA   : "<X> controla ... <Y>"                          (offshore cascata)
_DOACAO_RE = re.compile(
    rf"({_ID})(?:(?!{_ID}).)*?\b(?:doou|doaram|doa[çc][ãa]o)\b"
    rf"(?:(?!{_ID}).)*?\bpara\b\s+(?:a\s+|o\s+)?({_ID})",
    re.IGNORECASE | re.DOTALL,
)
_ADMIN_RE = re.compile(
    rf"({_ID})(?:(?!{_ID}).)*?\b(?:administrador[a]?\s+vital[íi]ci[oa]"
    rf"|usufrutu[áa]ri[oa]|usufruto)\b(?:(?!{_ID}).)*?({_ID})",
    re.IGNORECASE | re.DOTALL,
)
_CONTROLA_RE = re.compile(
    rf"({_ID})(?:(?!{_ID}).)*?\bcontrola\b(?:(?!{_ID}).)*?({_ID})",
    re.IGNORECASE | re.DOTALL,
)
# Fraude previdenciária: "<operador> desviou ... INSS ... para <destino>".
_INSS_RE = re.compile(
    rf"({_ID})(?:(?!{_ID}).)*?\bdesviou\b(?:(?!{_ID}).)*?\bINSS\b"
    rf"(?:(?!{_ID}).)*?\bpara\b\s+(?:a\s+|o\s+)?({_ID})",
    re.IGNORECASE | re.DOTALL,
)


def parse_document(text: str, source_event_id: str) -> ParsedDocument:
    """Extração determinística de entidades, relações e transações."""
    flat = re.sub(r"\s+", " ", text)  # quebras de linha não são fronteiras

    tokens = list(dict.fromkeys(_ID_RE.findall(flat)))  # ordem, sem duplicados
    entities = [Entity(id=t, name=t, type=_entity_type(t)) for t in tokens]
    relations: List[Relation] = []
    transactions: List[Transaction] = []

    cpf_tokens = [t for t in tokens if normalize_id(t).upper().startswith("CPF")]
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

    # Vínculo familiar declarado de forma autónoma (fonte separada)
    for m in _FAMILIA_RE.finditer(flat):
        relativo, dev = m.group(1), m.group(2)
        relations.append(Relation(
            source_id=dev, target_id=relativo, relation_type="FAMILIAR"))

    # Heurísticas avançadas de blindagem (Fase 2): doação, usufruto/administração
    # vitalícia e controle em cascata — populam o grafo para o asset_shield.
    # _trim apara pontuação à direita: a classe de _ID inclui '.' (CPF
    # formatado), logo um id no fim de frase engoliria o ponto final.
    def _trim(tok):
        return re.sub(r"[^0-9A-Za-z]+$", "", tok)
    for m in _DOACAO_RE.finditer(flat):
        relations.append(Relation(
            source_id=_trim(m.group(1)), target_id=_trim(m.group(2)),
            relation_type="DOACAO"))
    for m in _ADMIN_RE.finditer(flat):
        relations.append(Relation(
            source_id=_trim(m.group(1)), target_id=_trim(m.group(2)),
            relation_type="ADMINISTRA"))
    for m in _CONTROLA_RE.finditer(flat):
        relations.append(Relation(
            source_id=_trim(m.group(1)), target_id=_trim(m.group(2)),
            relation_type="CONTROLA"))
    for m in _INSS_RE.finditer(flat):
        relations.append(Relation(
            source_id=_trim(m.group(1)), target_id=_trim(m.group(2)),
            relation_type="DESVIO_INSS"))

    # Marcos judiciais (penhora, citação, bloqueio) com data próxima
    marcos = [_to_iso(m.group(2)) for m in _MARCO_RE.finditer(flat)]

    return ParsedDocument(
        entities=entities,
        relations=relations,
        transactions=transactions,
        marcos_judiciais=marcos,
        source_event_id=source_event_id,
    )
