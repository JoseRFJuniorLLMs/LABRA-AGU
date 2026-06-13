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
            "sogro", "sogra", "genro", "nora", "parente",
            "primo", "prima", "sobrinho", "sobrinha", "tio", "tia",
            "neto", "neta", "avô", "avo", "avó", "padrasto", "enteado")
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


class Asset(BaseModel):
    """Um BEM (imóvel, veículo, fazenda, conta, cripto…). O grafo deixa de ser
    só de pessoas: a blindagem é, no fundo, BENS a moverem-se."""
    id: str
    kind: str  # IMOVEL | VEICULO | FAZENDA | AERONAVE | CRIPTO | CONTA | BEM …
    valor_mercado: Optional[float] = None  # avaliação/valor de referência


class AssetTransfer(BaseModel):
    """Alienação de um bem entre pessoas (com o preço DECLARADO, que pode ser
    vil face ao valor de mercado)."""
    asset_id: str
    from_id: str
    to_id: str
    value: Optional[float] = None  # preço declarado da alienação
    date: Optional[str] = None


class EntityAttr(BaseModel):
    """Atributo de uma entidade (renda anual declarada, data de constituição…).
    Permite perguntas que o grafo de relações sozinho não responde — ex.: o
    patrimônio FECHA com a renda lícita declarada?"""
    id: str
    key: str            # renda_anual | data_constituicao | servidor_publico
    value_num: Optional[float] = None
    value_str: Optional[str] = None


class ParsedDocument(BaseModel):
    entities: List[Entity]
    relations: List[Relation]
    transactions: List[Transaction] = []
    marcos_judiciais: List[str] = []  # datas ISO de penhora/citação/bloqueio
    source_event_id: str
    assets: List[Asset] = []
    asset_transfers: List[AssetTransfer] = []
    entity_attrs: List[EntityAttr] = []
    # Sinal de confiança da extração (1.0 = alta). O parser determinístico é
    # frágil a redações fora dos gatilhos canónicos: quando há vários
    # identificadores mas poucos/nenhuns fatos, marca para REVISÃO HUMANA em
    # vez de produzir um grafo incompleto em silêncio.
    confidence: float = 1.0
    needs_review: bool = False
    # Sinal de confiança da extração (1.0 = alta). O parser determinístico é
    # frágil a redações fora dos gatilhos canónicos: quando há vários
    # identificadores mas poucos/nenhuns fatos, marca para REVISÃO HUMANA em
    # vez de produzir um grafo incompleto em silêncio.
    confidence: float = 1.0
    needs_review: bool = False


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

# ── Bens (ATIVOS) ──────────────────────────────────────────────────────
# Token de bem: tipo + sufixo (ex.: IMOVEL_MAT12345, FAZENDA_3, CRIPTO_WALLET).
# Distingue-se do _ID (que exige prefixo CPF/CNPJ ou cadeia de dígitos).
_BEM = (r"(?:IM[OÓ]VEL|VE[IÍ]CULO|VEICULO|FAZENDA|AERONAVE|EMBARCA[ÇC][AÃ]O|"
        r"EMBARCACAO|APARTAMENTO|TERRENO|CRIPTO|CONTA|BEM)[A-Za-z0-9_.\-/]*")
_BEM_RE = re.compile(_BEM, re.IGNORECASE)
# "<ID> vendeu/transferiu/alienou o <BEM> ... para <ID> ... por R$ <valor>"
_TRANSF_BEM_RE = re.compile(
    rf"({_ID})\s+(?:transferiu|vendeu|alienou|cedeu|doou|passou)\s+"
    rf"(?:o\s+|a\s+|os\s+|as\s+)?({_BEM})"
    rf"(?:(?!{_ID}).)*?\bpara\b\s+(?:a\s+|o\s+)?({_ID})"
    rf"(?:(?:(?!{_ID}).)*?\bR\$\s?([\d.]+,\d{{2}}))?",
    re.IGNORECASE | re.DOTALL,
)
# "<BEM> avaliado em / vale / valor de mercado R$ <valor>"
_AVALIACAO_RE = re.compile(
    rf"({_BEM})(?:(?!{_BEM}).)*?"
    rf"(?:avaliad[oa]|valor\s+de\s+mercado|vale)\b"
    rf"(?:(?!R\$).)*?R\$\s?([\d.]+,\d{{2}})",
    re.IGNORECASE | re.DOTALL,
)


def _canon_bem(tok: str) -> str:
    """Id canónico do bem: maiúsculas, sem espaços, sem pontuação à direita."""
    return re.sub(r"[^0-9A-Za-z]+$", "", re.sub(r"\s+", "", tok.upper()))


def _bem_kind(tok: str) -> str:
    """Tipo do bem a partir do prefixo do token."""
    up = tok.upper()
    for k in ("IMOVEL", "IMÓVEL", "VEICULO", "VEÍCULO", "FAZENDA", "AERONAVE",
              "EMBARCACAO", "EMBARCAÇAO", "APARTAMENTO", "TERRENO", "CRIPTO",
              "CONTA"):
        if up.startswith(k):
            return k.replace("Ó", "O").replace("Í", "I").replace("Ç", "C").replace("Ã", "A")
    return "BEM"


# ── Cobertura ampliada (renda, contrato público, cripto, atributos,
#    passivos, judiciário) — a maioria reusa o dict de relações. ──────────
_FORO = r"(?:FORO|VARA|COMARCA|TRIBUNAL)[A-Za-z0-9_.\-/]*"
# "<ID> declara renda anual de R$ <valor>"
_RENDA_RE = re.compile(
    rf"({_ID})(?:(?!{_ID}).)*?\brenda\s+anual\b(?:(?!R\$).)*?R\$\s?([\d.]+,\d{{2}})",
    re.IGNORECASE | re.DOTALL)
# "<ID/CNPJ> foi constituída/aberta/fundada em <data>"
_CONSTIT_RE = re.compile(
    rf"({_ID})(?:(?!{_ID}).)*?\b(?:constitu[íi]da|aberta|fundada|criada)\s+em\s+"
    rf"(\d{{2}}/\d{{2}}/\d{{4}})",
    re.IGNORECASE | re.DOTALL)
# "<ID> e <ID> compartilham/têm o mesmo endereço|telefone|contador|conta"
_MESMO_ATRIB_RE = re.compile(
    rf"({_ID})\s+e\s+({_ID})(?:(?!{_ID}).)*?"
    rf"\b(?:compartilham|partilham|t[êe]m\s+o\s+mesmo|mesm[oa])\b"
    rf"(?:(?!{_ID}).)*?\b(endere[çc]o|telefone|contador|conta)\b",
    re.IGNORECASE | re.DOTALL)
# "<devedor> confessou dívida de R$ <valor> a/para <credor>"
_DIVIDA_RE = re.compile(
    rf"({_ID})(?:(?!{_ID}).)*?\bconfessou\s+d[íi]vida\b(?:(?!R\$).)*?"
    rf"R\$\s?([\d.]+,\d{{2}})(?:(?!{_ID}).)*?\b(?:a|para|ao|à)\b\s+({_ID})",
    re.IGNORECASE | re.DOTALL)
# "<reclamante> move reclamação trabalhista de R$ <valor> contra <empresa>"
_TRABALHISTA_RE = re.compile(
    rf"({_ID})(?:(?!{_ID}).)*?reclama[çc][ãa]o\s+trabalhista\b(?:(?!R\$).)*?"
    rf"R\$\s?([\d.]+,\d{{2}})(?:(?!{_ID}).)*?\bcontra\b\s+({_ID})",
    re.IGNORECASE | re.DOTALL)
# "<órgão> contratou <fornecedor> por R$ <valor>"
_CONTRATO_RE = re.compile(
    rf"({_ID})(?:(?!{_ID}).)*?\bcontratou\b(?:(?!{_ID}).)*?({_ID})"
    rf"(?:(?!{_ID}).)*?\bpor\s+R\$\s?([\d.]+,\d{{2}})",
    re.IGNORECASE | re.DOTALL)
# "<ID> converteu R$ <valor> em cripto ... repassou/enviou a/para <ID>" (1 só passo)
_CRIPTO_RE = re.compile(
    rf"({_ID})(?:(?!{_ID}).)*?\bconverteu\b(?:(?!R\$).)*?R\$\s?([\d.]+,\d{{2}})"
    rf"(?:(?!{_ID}).)*?\bcripto\w*\b"
    rf"(?:(?!{_ID}).)*?\b(?:repassou|enviou|transferiu|remeteu)\b"
    rf"(?:(?!{_ID}).)*?\b(?:a|para|ao|à)\b\s+(?:a\s+|o\s+)?({_ID})",
    re.IGNORECASE | re.DOTALL)
# "<advogado> obteve decisão/sentença/liminar favorável na <FORO>"
_DECISAO_RE = re.compile(
    rf"({_ID})(?:(?!{_ID}).)*?\b(?:decis[ãa]o|senten[çc]a|liminar)\s+favor[áa]vel\b"
    rf"(?:(?!{_FORO}).)*?({_FORO})",
    re.IGNORECASE | re.DOTALL)


def _atrib_rel(palavra: str) -> str:
    p = palavra.lower()
    if "endere" in p:
        return "MESMO_ENDERECO"
    if "telefone" in p:
        return "MESMO_TELEFONE"
    if "contador" in p:
        return "MESMO_CONTADOR"
    return "MESMA_CONTA"


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

    # _trim apara pontuação à direita: a classe de _ID inclui '.' (CPF
    # formatado), logo um id no fim de frase engoliria o ponto final.
    def _trim(tok):
        return re.sub(r"[^0-9A-Za-z]+$", "", tok)

    def _data_apos(m):
        """Data declarada na frase da relação (ex.: '... em 12/03/2024'),
        para a linha do tempo cronológica do painel."""
        ds = _DATE_RE.findall(flat[m.start():m.end() + 60])
        return _to_iso(ds[0]) if ds else None

    # Vínculo familiar declarado de forma autónoma (fonte separada)
    for m in _FAMILIA_RE.finditer(flat):
        relativo, dev = m.group(1), m.group(2)
        relations.append(Relation(
            source_id=dev, target_id=relativo, relation_type="FAMILIAR",
            date=_data_apos(m)))

    # Heurísticas avançadas de blindagem (Fase 2): doação, usufruto/administração
    # vitalícia, controle em cascata e desvio do INSS.
    for m in _DOACAO_RE.finditer(flat):
        relations.append(Relation(
            source_id=_trim(m.group(1)), target_id=_trim(m.group(2)),
            relation_type="DOACAO", date=_data_apos(m)))
    for m in _ADMIN_RE.finditer(flat):
        relations.append(Relation(
            source_id=_trim(m.group(1)), target_id=_trim(m.group(2)),
            relation_type="ADMINISTRA", date=_data_apos(m)))
    for m in _CONTROLA_RE.finditer(flat):
        relations.append(Relation(
            source_id=_trim(m.group(1)), target_id=_trim(m.group(2)),
            relation_type="CONTROLA", date=_data_apos(m)))
    for m in _INSS_RE.finditer(flat):
        relations.append(Relation(
            source_id=_trim(m.group(1)), target_id=_trim(m.group(2)),
            relation_type="DESVIO_INSS", date=_data_apos(m)))

    # Bens (ATIVOS): alienações e avaliações. O bem passa a ser um nó.
    assets: dict = {}
    asset_transfers: List[AssetTransfer] = []
    for m in _TRANSF_BEM_RE.finditer(flat):
        src, bem_tok, dst, val = m.group(1), m.group(2), m.group(3), m.group(4)
        bem = _canon_bem(bem_tok)
        assets.setdefault(bem, Asset(id=bem, kind=_bem_kind(bem_tok)))
        asset_transfers.append(AssetTransfer(
            asset_id=bem, from_id=_trim(src), to_id=_trim(dst),
            value=_to_float(val) if val else None, date=_data_apos(m)))
    for m in _AVALIACAO_RE.finditer(flat):
        bem = _canon_bem(m.group(1))
        a = assets.setdefault(bem, Asset(id=bem, kind=_bem_kind(m.group(1))))
        a.valor_mercado = _to_float(m.group(2))

    # Cobertura ampliada: atributos de entidade + relações novas.
    entity_attrs: List[EntityAttr] = []
    for m in _RENDA_RE.finditer(flat):
        entity_attrs.append(EntityAttr(id=_trim(m.group(1)), key="renda_anual",
                                       value_num=_to_float(m.group(2))))
    for m in _CONSTIT_RE.finditer(flat):
        entity_attrs.append(EntityAttr(id=_trim(m.group(1)),
                                       key="data_constituicao",
                                       value_str=_to_iso(m.group(2))))
    for m in _MESMO_ATRIB_RE.finditer(flat):
        relations.append(Relation(
            source_id=_trim(m.group(1)), target_id=_trim(m.group(2)),
            relation_type=_atrib_rel(m.group(3))))
    for m in _DIVIDA_RE.finditer(flat):  # credor (g3) tem crédito sobre devedor (g1)
        relations.append(Relation(
            source_id=_trim(m.group(3)), target_id=_trim(m.group(1)),
            relation_type="CREDOR_DIVIDA", value=_to_float(m.group(2)),
            date=_data_apos(m)))
    for m in _TRABALHISTA_RE.finditer(flat):  # reclamante (g1) vs empresa (g3)
        relations.append(Relation(
            source_id=_trim(m.group(1)), target_id=_trim(m.group(3)),
            relation_type="CREDOR_TRABALHISTA", value=_to_float(m.group(2)),
            date=_data_apos(m)))
    for m in _CONTRATO_RE.finditer(flat):  # órgão (g1) contrata fornecedor (g2)
        relations.append(Relation(
            source_id=_trim(m.group(1)), target_id=_trim(m.group(2)),
            relation_type="CONTRATOU_PUBLICO", value=_to_float(m.group(3)),
            date=_data_apos(m)))
    for m in _CRIPTO_RE.finditer(flat):  # origem (g1) → cripto → destino (g3)
        relations.append(Relation(
            source_id=_trim(m.group(1)), target_id=_trim(m.group(3)),
            relation_type="CONVERTEU_CRIPTO", value=_to_float(m.group(2))))
    for m in _DECISAO_RE.finditer(flat):  # advogado (g1) → foro (g2)
        relations.append(Relation(
            source_id=_trim(m.group(1)), target_id=_canon_bem(m.group(2)),
            relation_type="DECISAO_FAVORAVEL", date=_data_apos(m)))

    # Marcos judiciais (penhora, citação, bloqueio) com data próxima
    marcos = [_to_iso(m.group(2)) for m in _MARCO_RE.finditer(flat)]

    confidence, needs_review = _assess_confidence(
        flat, entities, relations, transactions)

    return ParsedDocument(
        entities=entities,
        relations=relations,
        transactions=transactions,
        marcos_judiciais=marcos,
        source_event_id=source_event_id,
        assets=list(assets.values()),
        asset_transfers=asset_transfers,
        entity_attrs=entity_attrs,
        confidence=confidence,
        needs_review=needs_review,
    )


def _assess_confidence(text, entities, relations, transactions):
    """Heurística de confiança da extração determinística. Vários
    identificadores presentes mas (quase) nenhum fato relacionado = forte
    indício de que a redação fugiu aos gatilhos canónicos → revisão humana
    (ou reprocessamento pelo parser LLM)."""
    n_ids = len(entities)
    n_fatos = len(relations) + len(transactions)
    if n_ids >= 2 and n_fatos == 0 and len(text) > 200:
        return 0.3, True
    if n_ids >= 3 and n_fatos < n_ids // 3:
        return 0.6, True
    return 1.0, False
