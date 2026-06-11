"""
Backend de parsing por LLM (opcional).

O parser determinístico (agent/parser.py) é robusto e auditável, mas dados
reais — PDFs de processos com OCR, contratos com redação livre, extratos de
bancos heterogéneos — raramente batem com gatilhos lexicais limpos. Este
módulo usa o Claude (SDK oficial da Anthropic) com saída estruturada para
extrair entidades, relações e transações de texto arbitrário, devolvendo o
MESMO schema Pydantic (`ParsedDocument`) — o resto do pipeline não muda.

Ativação (opt-in, falha graciosamente para o determinístico):
  - `pip install anthropic`
  - `export ANTHROPIC_API_KEY=...`
  - `export LABRA_LLM_PARSER=1`  (ou passar use_llm=True)

Sem qualquer destes, o agente continua a usar o parser determinístico.
"""
import logging
import os
from typing import List, Optional

from pydantic import BaseModel, Field

from .parser import (
    Entity,
    ParsedDocument,
    Relation,
    Transaction,
    parse_document as parse_deterministico,
)

_MODEL = os.environ.get("LABRA_LLM_MODEL", "claude-opus-4-8")

_SYSTEM = """Você é um perito forense da Advocacia-Geral da União especializado \
em rastreamento de blindagem patrimonial. Extraia de documentos jurídicos \
(juntas comerciais, cartórios, COAF, extratos) APENAS fatos explícitos, sem \
inferir. Normalize identificadores como aparecem (CPF_xxx, CNPJ_xxx ou só os \
dígitos). Tipos de relação válidos: VENDEDOR_QUOTAS (cessão/transferência de \
quotas), PROCURADOR_COM_PODERES (procuração/administração com plenos poderes), \
FAMILIAR (vínculo de parentesco). Datas no formato ISO yyyy-mm-dd. Marcos \
judiciais = datas ISO de penhora, citação, bloqueio, arresto, indisponibilidade."""


# Schema que o LLM preenche (sem source_event_id — esse é do log, não do texto)
class _LLMEntity(BaseModel):
    id: str = Field(..., description="CPF_xxx, CNPJ_xxx ou dígitos")
    name: str = Field(..., description="Nome ou o próprio id se desconhecido")
    type: str = Field(..., description="PESSOA_FISICA ou PESSOA_JURIDICA")


class _LLMRelation(BaseModel):
    source_id: str
    target_id: str
    relation_type: str = Field(
        ..., description="VENDEDOR_QUOTAS | PROCURADOR_COM_PODERES | FAMILIAR"
    )
    value: Optional[float] = None
    date: Optional[str] = Field(None, description="ISO yyyy-mm-dd")


class _LLMTransaction(BaseModel):
    source_id: str
    target_id: str
    value: float
    date: Optional[str] = Field(None, description="ISO yyyy-mm-dd")


class _LLMExtraction(BaseModel):
    entities: List[_LLMEntity] = []
    relations: List[_LLMRelation] = []
    transactions: List[_LLMTransaction] = []
    marcos_judiciais: List[str] = Field(default_factory=list, description="datas ISO")


def llm_available() -> bool:
    """True se o SDK e a chave estiverem presentes."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def parse_document_llm(text: str, source_event_id: str) -> ParsedDocument:
    """
    Extrai via Claude (saída estruturada). Em qualquer falha, cai para o
    parser determinístico — o agente nunca fica sem análise.
    """
    if not llm_available():
        return parse_deterministico(text, source_event_id)

    try:
        import anthropic

        client = anthropic.Anthropic()
        resp = client.messages.parse(
            model=_MODEL,
            max_tokens=4096,
            system=_SYSTEM,
            messages=[{
                "role": "user",
                "content": f"Extraia as entidades, relações, transações e "
                           f"marcos judiciais deste documento:\n\n{text}",
            }],
            output_format=_LLMExtraction,
        )
        ext = resp.parsed_output
        if ext is None:
            raise ValueError("parsed_output vazio (possível recusa)")

        return ParsedDocument(
            entities=[Entity(id=e.id, name=e.name, type=e.type) for e in ext.entities],
            relations=[
                Relation(source_id=r.source_id, target_id=r.target_id,
                         relation_type=r.relation_type, value=r.value, date=r.date)
                for r in ext.relations
            ],
            transactions=[
                Transaction(source_id=t.source_id, target_id=t.target_id,
                            value=t.value, date=t.date)
                for t in ext.transactions
            ],
            marcos_judiciais=list(ext.marcos_judiciais),
            source_event_id=source_event_id,
        )
    except Exception as e:  # noqa: BLE001 — degrada para o determinístico
        logging.warning(f"parser LLM falhou ({type(e).__name__}: {e}); "
                        "usando parser determinístico")
        return parse_deterministico(text, source_event_id)
