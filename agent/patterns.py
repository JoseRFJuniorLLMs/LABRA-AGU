"""
Biblioteca de Padrões de Fraude (o conhecimento pericial do agente).

Cada padrão é uma função pura `detect(doc) -> Optional[dict]` registada no
catálogo PATTERNS. O Investigator percorre o catálogo (ou o subconjunto
pedido por uma DIRETRIZ) e, para cada deteção, produz um achado com:
  - `pattern`: nome canónico do padrão
  - `severidade`: BAIXA | MEDIA | ALTA | CRITICA
  - `envolvidos`: ids das entidades implicadas (alimenta o ACT-R)
  - `descricao` / `conclusao_juridica`: narrativa pericial

Novos padrões = nova entrada no catálogo. Nada mais muda no pipeline.
"""
from datetime import date, timedelta
from typing import Callable, Dict, List, Optional

from .parser import ParsedDocument

# Limiar de comunicação COAF usado na deteção de fracionamento (smurfing).
LIMIAR_FRACIONAMENTO = 10_000.00
JANELA_VESPERA_DIAS = 30


def _rels(doc: ParsedDocument, kind: str):
    return [r for r in doc.relations if r.relation_type == kind]


def detect_triangulacao_offshore(doc: ParsedDocument) -> Optional[dict]:
    """Quotas vendidas a uma entidade que em seguida nomeia procurador com
    plenos poderes — o circuito clássico de blindagem patrimonial."""
    for venda in _rels(doc, "VENDEDOR_QUOTAS"):
        for proc in _rels(doc, "PROCURADOR_COM_PODERES"):
            if proc.source_id == venda.target_id:
                familiar = any(
                    f.target_id == proc.target_id for f in _rels(doc, "FAMILIAR")
                )
                return {
                    "pattern": "triangulacao_offshore",
                    "severidade": "CRITICA" if familiar else "ALTA",
                    "envolvidos": [venda.source_id, venda.target_id, proc.target_id],
                    "devedor_alvo": venda.source_id,
                    "descricao": (
                        f"O devedor {venda.source_id} transferiu quotas para "
                        f"{venda.target_id}, que nomeou {proc.target_id} como "
                        "procurador com plenos poderes"
                        + (" — pessoa com vínculo familiar com o devedor." if familiar else ".")
                    ),
                    "conclusao_juridica": (
                        "Evidência robusta de esvaziamento patrimonial planejado "
                        "para frustrar a execução fiscal da União (triangulação "
                        "cíclica de quotas)."
                    ),
                }
    return None


def detect_fracionamento(doc: ParsedDocument) -> Optional[dict]:
    """Smurfing: três ou mais transferências do mesmo remetente, cada uma
    abaixo do limiar de comunicação obrigatória, somando valor relevante."""
    por_origem: Dict[str, List] = {}
    for t in doc.transactions:
        if t.value < LIMIAR_FRACIONAMENTO:
            por_origem.setdefault(t.source_id, []).append(t)
    for origem, txs in por_origem.items():
        total = sum(t.value for t in txs)
        if len(txs) >= 3 and total >= LIMIAR_FRACIONAMENTO:
            destinos = sorted({t.target_id for t in txs})
            return {
                "pattern": "fracionamento",
                "severidade": "ALTA",
                "envolvidos": [origem, *destinos],
                "devedor_alvo": origem,
                "descricao": (
                    f"{origem} realizou {len(txs)} transferências individuais "
                    f"abaixo de R$ {LIMIAR_FRACIONAMENTO:,.2f}, somando "
                    f"R$ {total:,.2f} para {', '.join(destinos)}."
                ),
                "conclusao_juridica": (
                    "Padrão de fracionamento (estruturação/smurfing) compatível "
                    "com ocultação dolosa de movimentação financeira do radar COAF."
                ),
            }
    return None


def detect_laranja_familiar(doc: ParsedDocument) -> Optional[dict]:
    """Procuração com plenos poderes outorgada a familiar do devedor —
    interposta pessoa (laranja) de primeiro grau."""
    familiares = {f.target_id for f in _rels(doc, "FAMILIAR")}
    for proc in _rels(doc, "PROCURADOR_COM_PODERES"):
        if proc.target_id in familiares:
            devedor = next(
                (f.source_id for f in _rels(doc, "FAMILIAR")
                 if f.target_id == proc.target_id),
                proc.source_id,
            )
            return {
                "pattern": "laranja_familiar",
                "severidade": "ALTA",
                "envolvidos": [devedor, proc.source_id, proc.target_id],
                "devedor_alvo": devedor,
                "descricao": (
                    f"{proc.target_id}, com vínculo familiar com o devedor "
                    f"{devedor}, recebeu plenos poderes sobre {proc.source_id}."
                ),
                "conclusao_juridica": (
                    "Indício de interposição de pessoa (testa-de-ferro familiar) "
                    "para manter controle de fato sobre patrimônio formalmente alienado."
                ),
            }
    return None


def detect_vespera_constricao(doc: ParsedDocument) -> Optional[dict]:
    """Dissipação patrimonial às vésperas de marco judicial (penhora,
    citação, bloqueio): transações nos N dias anteriores ao marco."""
    if not doc.marcos_judiciais:
        return None
    try:
        marcos = [date.fromisoformat(m) for m in doc.marcos_judiciais]
    except ValueError:
        return None
    suspeitas = []
    for t in doc.transactions:
        if not t.date:
            continue
        try:
            td = date.fromisoformat(t.date)
        except ValueError:
            continue
        for m in marcos:
            if timedelta(0) <= (m - td) <= timedelta(days=JANELA_VESPERA_DIAS):
                suspeitas.append(t)
                break
    # Relações de venda de quotas datadas também contam como dissipação
    for venda in _rels(doc, "VENDEDOR_QUOTAS"):
        if venda.date:
            try:
                vd = date.fromisoformat(venda.date)
            except ValueError:
                continue
            for m in marcos:
                if timedelta(0) <= (m - vd) <= timedelta(days=JANELA_VESPERA_DIAS):
                    suspeitas.append(venda)
                    break
    if not suspeitas:
        return None
    envolvidos = sorted({s.source_id for s in suspeitas} | {s.target_id for s in suspeitas})
    return {
        "pattern": "vespera_constricao",
        "severidade": "CRITICA",
        "envolvidos": envolvidos,
        "devedor_alvo": suspeitas[0].source_id,
        "descricao": (
            f"{len(suspeitas)} movimentação(ões) patrimonial(is) realizadas "
            f"até {JANELA_VESPERA_DIAS} dias antes de marco judicial "
            f"({', '.join(doc.marcos_judiciais)})."
        ),
        "conclusao_juridica": (
            "Fraude à execução (art. 792 CPC / art. 185 CTN): alienação ou "
            "oneração de bens na iminência de constrição judicial conhecida."
        ),
    }


PATTERNS: Dict[str, Callable[[ParsedDocument], Optional[dict]]] = {
    "triangulacao_offshore": detect_triangulacao_offshore,
    "fracionamento": detect_fracionamento,
    "laranja_familiar": detect_laranja_familiar,
    "vespera_constricao": detect_vespera_constricao,
}
