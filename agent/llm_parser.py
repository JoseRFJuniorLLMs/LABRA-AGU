"""
Backend de parsing por LLM (opcional).

O parser determinístico (agent/parser.py) é robusto e auditável, mas dados
reais — PDFs de processos com OCR, contratos com redação livre, extratos de
bancos heterogéneos — raramente batem com gatilhos lexicais limpos. Este
módulo usa o Claude (SDK oficial da Anthropic) com saída estruturada para
extrair entidades, relações e transações de texto arbitrário, devolvendo o
MESMO schema Pydantic (`ParsedDocument`) — o resto do pipeline não muda.

Dois backends, selecionáveis por `LABRA_LLM_BACKEND`:

  - `anthropic` (default) — Claude via SDK oficial. `pip install anthropic`,
    `export ANTHROPIC_API_KEY=...`.
  - `local` — qualquer servidor OpenAI-compatible (LM Studio, Ollama, vLLM…),
    ideal para correr um modelo LOCAL (ex.: Gemma 4) sem que dados de processo
    saiam da máquina (LGPD). `pip install openai` e:
      export LABRA_LLM_BACKEND=local
      export LABRA_LLM_BASE_URL=http://localhost:1234/v1   # LM Studio
      export LABRA_LLM_MODEL=gemma-4-e4b
      export LABRA_LLM_API_KEY=local                        # token fictício

Qualquer falha (sem SDK, sem chave, servidor em baixo, recusa) degrada
graciosamente para o parser DETERMINÍSTICO — o agente nunca fica sem análise.
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

_BACKEND = os.environ.get("LABRA_LLM_BACKEND", "anthropic").lower()
_MODEL = os.environ.get(
    "LABRA_LLM_MODEL",
    "gemma-4-e4b" if _BACKEND == "local" else "claude-opus-4-8")
_BASE_URL = os.environ.get("LABRA_LLM_BASE_URL", "http://localhost:1234/v1")

_SYSTEM = """Você é um perito forense da Advocacia-Geral da União especializado \
em rastreamento de blindagem patrimonial. Extraia de documentos jurídicos \
(juntas comerciais, cartórios, COAF, extratos) APENAS fatos explícitos, sem \
inferir. Normalize identificadores como aparecem (CPF_xxx, CNPJ_xxx ou só os \
dígitos). Tipos de relação válidos:
  - VENDEDOR_QUOTAS: cessão/transferência de quotas;
  - PROCURADOR_COM_PODERES: procuração/administração com plenos poderes;
  - FAMILIAR: vínculo de parentesco;
  - DOACAO: doação ou transmissão gratuita de bem (X doou para Y);
  - ADMINISTRA: usufruto ou administração vitalícia de bem/empresa sem \
titularidade aparente (X é usufrutuário/administrador vitalício de Y);
  - CONTROLA: controle indireto em camadas / offshore em cascata (X controla Y).
Datas no formato ISO yyyy-mm-dd. Marcos judiciais = datas ISO de penhora, \
citação, bloqueio, arresto, indisponibilidade."""


# Schema que o LLM preenche (sem source_event_id — esse é do log, não do texto)
class _LLMEntity(BaseModel):
    id: str = Field(..., description="CPF_xxx, CNPJ_xxx ou dígitos")
    name: str = Field(..., description="Nome ou o próprio id se desconhecido")
    type: str = Field(..., description="PESSOA_FISICA ou PESSOA_JURIDICA")


class _LLMRelation(BaseModel):
    source_id: str
    target_id: str
    relation_type: str = Field(
        ..., description="VENDEDOR_QUOTAS | PROCURADOR_COM_PODERES | FAMILIAR | "
                         "DOACAO | ADMINISTRA | CONTROLA"
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
    """True se o backend selecionado tiver SDK e credenciais."""
    if _BACKEND == "local":
        try:
            import openai  # noqa: F401
            return True
        except ImportError:
            return False
    # anthropic
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


_USER_PROMPT = ("Extraia as entidades, relações, transações e marcos judiciais "
                "deste documento:\n\n")


def _to_parsed(ext: "_LLMExtraction", source_event_id: str) -> ParsedDocument:
    """Converte a extração do LLM no schema do pipeline. Confiança alta: a
    extração veio de um modelo, não dos gatilhos lexicais frágeis."""
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
        confidence=1.0,
        needs_review=False,
    )


def _parse_local(text: str, source_event_id: str) -> ParsedDocument:
    """Servidor OpenAI-compatible (LM Studio/Ollama/vLLM) com structured output."""
    from openai import OpenAI

    client = OpenAI(base_url=_BASE_URL,
                    api_key=os.environ.get("LABRA_LLM_API_KEY", "local"))
    resp = client.beta.chat.completions.parse(
        model=_MODEL,
        messages=[{"role": "system", "content": _SYSTEM},
                  {"role": "user", "content": _USER_PROMPT + text}],
        response_format=_LLMExtraction,
    )
    ext = resp.choices[0].message.parsed
    if ext is None:
        raise ValueError("resposta sem parsed (possível recusa)")
    return _to_parsed(ext, source_event_id)


def _parse_anthropic(text: str, source_event_id: str) -> ParsedDocument:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.parse(
        model=_MODEL,
        max_tokens=4096,
        system=_SYSTEM,
        messages=[{"role": "user", "content": _USER_PROMPT + text}],
        output_format=_LLMExtraction,
    )
    ext = resp.parsed_output
    if ext is None:
        raise ValueError("parsed_output vazio (possível recusa)")
    return _to_parsed(ext, source_event_id)


def parse_document_llm(text: str, source_event_id: str) -> ParsedDocument:
    """
    Extrai via LLM (backend `LABRA_LLM_BACKEND`: anthropic|local), com saída
    estruturada. Em QUALQUER falha cai para o parser determinístico — o agente
    nunca fica sem análise.
    """
    if not llm_available():
        return parse_deterministico(text, source_event_id)
    try:
        if _BACKEND == "local":
            return _parse_local(text, source_event_id)
        return _parse_anthropic(text, source_event_id)
    except Exception as e:  # noqa: BLE001 — degrada para o determinístico
        logging.warning(f"parser LLM ({_BACKEND}) falhou ({type(e).__name__}: "
                        f"{e}); usando parser determinístico")
        return parse_deterministico(text, source_event_id)
