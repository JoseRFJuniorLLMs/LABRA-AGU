import json
from typing import List, Optional
from pydantic import BaseModel, Field

class Entity(BaseModel):
    id: str = Field(..., description="CPF ou CNPJ")
    name: str = Field(..., description="Nome da pessoa ou empresa")
    type: str = Field(..., description="'PESSOA_FISICA' ou 'PESSOA_JURIDICA'")

class Relation(BaseModel):
    source_id: str
    target_id: str
    relation_type: str = Field(..., description="'SOCIO', 'PROCURADOR', 'COMPRADOR', 'VENDEDOR'")
    value: Optional[float] = None
    date: Optional[str] = None

class ParsedDocument(BaseModel):
    entities: List[Entity]
    relations: List[Relation]
    source_event_id: str

def parse_document(text: str, source_event_id: str) -> ParsedDocument:
    """
    Mock de um parsing via LLM. 
    Na versão de produção, isso chamaria a API da OpenAI/Gemini com JSON mode.
    """
    # Exemplo simulado de extração baseado em regras simples para o protótipo
    # Para o devedor "CPF_645.254.302-49"
    if "transferiu quotas da empresa mãe para uma offshore" in text:
        return ParsedDocument(
            entities=[
                Entity(id="CPF_645.254.302-49", name="Devedor Principal", type="PESSOA_FISICA"),
                Entity(id="CNPJ_OFFSHORE_01", name="Offshore Blindagem Ltda", type="PESSOA_JURIDICA"),
                Entity(id="CPF_CUNHADO_001", name="Cunhado Laranja", type="PESSOA_FISICA")
            ],
            relations=[
                Relation(
                    source_id="CPF_645.254.302-49",
                    target_id="CNPJ_OFFSHORE_01",
                    relation_type="VENDEDOR_QUOTAS",
                    value=50000.0,
                    date="2026-06-01"
                ),
                Relation(
                    source_id="CNPJ_OFFSHORE_01",
                    target_id="CPF_CUNHADO_001",
                    relation_type="PROCURADOR_COM_PODERES",
                    date="2026-06-02"
                )
            ],
            source_event_id=source_event_id
        )
    
    # Retorno padrão vazio
    return ParsedDocument(entities=[], relations=[], source_event_id=source_event_id)
