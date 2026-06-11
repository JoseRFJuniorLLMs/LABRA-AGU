"""
Biblioteca de Padrões de Fraude (o conhecimento pericial do agente).

Cada padrão é uma função pura `detect(graph) -> List[dict]` que opera sobre
o GRAFO DE CASO ACUMULADO (agent/graph.py), não sobre um documento isolado.
Isto é o que permite detectar fraude espalhada por várias fontes: a venda
de quotas da Junta + a procuração do cartório + as transferências do COAF
formam, juntas, a triangulação — mesmo que tenham chegado em dias e
documentos diferentes.

Cada achado traz:
  - `pattern`: nome canónico do padrão
  - `severidade`: BAIXA | MEDIA | ALTA | CRITICA
  - `envolvidos`: ids canónicos das entidades implicadas (alimenta o ACT-R)
  - `source_events`: ULIDs dos documentos que sustentam o achado (PROVENANCE)
  - `descricao` / `conclusao_juridica`: narrativa pericial

Novos padrões = nova entrada no catálogo. Nada mais muda no pipeline.
"""
from datetime import date, timedelta
from typing import Callable, Dict, List

from .graph import CaseGraph

# Limiar de comunicação COAF usado na deteção de fracionamento (smurfing).
LIMIAR_FRACIONAMENTO = 10_000.00
JANELA_VESPERA_DIAS = 30


def detect_triangulacao_offshore(g: CaseGraph) -> List[dict]:
    """Quotas vendidas a uma entidade que em seguida nomeia procurador com
    plenos poderes — o circuito clássico de blindagem patrimonial. As duas
    pernas podem vir de documentos/fontes diferentes."""
    out = []
    familiares = {(f["src"], f["dst"]) for f in g.rels("FAMILIAR")}
    for venda in g.rels("VENDEDOR_QUOTAS"):
        for proc in g.rels("PROCURADOR_COM_PODERES"):
            if proc["src"] == venda["dst"]:
                devedor, offshore, laranja = venda["src"], venda["dst"], proc["dst"]
                familiar = (devedor, laranja) in familiares
                events = set(venda["events"]) | set(proc["events"])
                if familiar:
                    for f in g.rels("FAMILIAR"):
                        if f["src"] == devedor and f["dst"] == laranja:
                            events |= f["events"]
                out.append({
                    "pattern": "triangulacao_offshore",
                    "severidade": "CRITICA" if familiar else "ALTA",
                    "envolvidos": [devedor, offshore, laranja],
                    "devedor_alvo": devedor,
                    "source_events": events,
                    "descricao": (
                        f"O devedor {devedor} transferiu quotas para {offshore}, "
                        f"que nomeou {laranja} como procurador com plenos poderes"
                        + (" — pessoa com vínculo familiar com o devedor." if familiar else ".")
                    ),
                    "conclusao_juridica": (
                        "Evidência robusta de esvaziamento patrimonial planejado "
                        "para frustrar a execução fiscal da União (triangulação "
                        "cíclica de quotas)."
                    ),
                })
    return out


def detect_fracionamento(g: CaseGraph) -> List[dict]:
    """Smurfing: três ou mais transferências do mesmo remetente, cada uma
    abaixo do limiar de comunicação obrigatória, somando valor relevante.
    Agora soma transações de TODOS os extratos acumulados, não de um só."""
    por_origem: Dict[str, List[dict]] = {}
    for t in g.transactions:
        if t["value"] < LIMIAR_FRACIONAMENTO:
            por_origem.setdefault(t["src"], []).append(t)
    out = []
    for origem, txs in por_origem.items():
        total = sum(t["value"] for t in txs)
        if len(txs) >= 3 and total >= LIMIAR_FRACIONAMENTO:
            destinos = sorted({t["dst"] for t in txs})
            events = set()
            for t in txs:
                events |= set(t["events"])
            out.append({
                "pattern": "fracionamento",
                "severidade": "ALTA",
                "envolvidos": [origem, *destinos],
                "devedor_alvo": origem,
                "source_events": events,
                "descricao": (
                    f"{origem} realizou {len(txs)} transferências individuais "
                    f"abaixo de R$ {LIMIAR_FRACIONAMENTO:,.2f}, somando "
                    f"R$ {total:,.2f} para {', '.join(destinos)}."
                ),
                "conclusao_juridica": (
                    "Padrão de fracionamento (estruturação/smurfing) compatível "
                    "com ocultação dolosa de movimentação financeira do radar COAF."
                ),
            })
    return out


def detect_laranja_familiar(g: CaseGraph) -> List[dict]:
    """Procuração com plenos poderes outorgada a familiar do devedor —
    interposta pessoa (laranja) de primeiro grau."""
    fam_by_target: Dict[str, List[dict]] = {}
    for f in g.rels("FAMILIAR"):
        fam_by_target.setdefault(f["dst"], []).append(f)
    out = []
    for proc in g.rels("PROCURADOR_COM_PODERES"):
        fams = fam_by_target.get(proc["dst"], [])
        if fams:
            fam = fams[0]
            devedor = fam["src"]
            events = set(proc["events"]) | set(fam["events"])
            out.append({
                "pattern": "laranja_familiar",
                "severidade": "ALTA",
                "envolvidos": [devedor, proc["src"], proc["dst"]],
                "devedor_alvo": devedor,
                "source_events": events,
                "descricao": (
                    f"{proc['dst']}, com vínculo familiar com o devedor "
                    f"{devedor}, recebeu plenos poderes sobre {proc['src']}."
                ),
                "conclusao_juridica": (
                    "Indício de interposição de pessoa (testa-de-ferro familiar) "
                    "para manter controle de fato sobre patrimônio formalmente alienado."
                ),
            })
    return out


def detect_vespera_constricao(g: CaseGraph) -> List[dict]:
    """Dissipação patrimonial às vésperas de marco judicial (penhora,
    citação, bloqueio): movimentações nos N dias anteriores ao marco. O
    marco pode vir de um processo e a transação de um extrato distinto."""
    marcos_raw = g.marcos_datas()
    if not marcos_raw:
        return []
    marcos = []
    for m in marcos_raw:
        try:
            marcos.append(date.fromisoformat(m))
        except ValueError:
            continue
    if not marcos:
        return []

    suspeitas = []  # (src, dst, events)
    def _check(d_str, src, dst, events):
        if not d_str:
            return
        try:
            dt = date.fromisoformat(d_str)
        except ValueError:
            return
        for m in marcos:
            if timedelta(0) <= (m - dt) <= timedelta(days=JANELA_VESPERA_DIAS):
                suspeitas.append((src, dst, set(events)))
                return

    for t in g.transactions:
        _check(t["date"], t["src"], t["dst"], t["events"])
    for venda in g.rels("VENDEDOR_QUOTAS"):
        _check(venda["date"], venda["src"], venda["dst"], venda["events"])

    if not suspeitas:
        return []
    envolvidos = sorted({s for s, _, _ in suspeitas} | {d for _, d, _ in suspeitas})
    events = set(g.marcos_events())
    for _, _, evs in suspeitas:
        events |= evs
    return [{
        "pattern": "vespera_constricao",
        "severidade": "CRITICA",
        "envolvidos": envolvidos,
        "devedor_alvo": suspeitas[0][0],
        "source_events": events,
        "descricao": (
            f"{len(suspeitas)} movimentação(ões) patrimonial(is) realizadas "
            f"até {JANELA_VESPERA_DIAS} dias antes de marco judicial "
            f"({', '.join(marcos_raw)})."
        ),
        "conclusao_juridica": (
            "Fraude à execução (art. 792 CPC / art. 185 CTN): alienação ou "
            "oneração de bens na iminência de constrição judicial conhecida."
        ),
    }]


PATTERNS: Dict[str, Callable[[CaseGraph], List[dict]]] = {
    "triangulacao_offshore": detect_triangulacao_offshore,
    "fracionamento": detect_fracionamento,
    "laranja_familiar": detect_laranja_familiar,
    "vespera_constricao": detect_vespera_constricao,
}
