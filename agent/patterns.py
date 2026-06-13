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
from collections import defaultdict
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
    # Eventos-prova do vínculo familiar, indexados por (devedor, laranja).
    fam_events: Dict[tuple, set] = defaultdict(set)
    for f in g.rels("FAMILIAR"):
        fam_events[(f["src"], f["dst"])] |= set(f["events"])
    # Procurações indexadas pelo outorgante (src) — evita o produto cartesiano
    # venda × procuração (O(V·P) → O(V+P)).
    procs_by_src: Dict[str, List[dict]] = defaultdict(list)
    for proc in g.rels("PROCURADOR_COM_PODERES"):
        procs_by_src[proc["src"]].append(proc)

    for venda in g.rels("VENDEDOR_QUOTAS"):
        for proc in procs_by_src.get(venda["dst"], []):
            devedor, offshore, laranja = venda["src"], venda["dst"], proc["dst"]
            familiar = (devedor, laranja) in familiares
            events = set(venda["events"]) | set(proc["events"])
            if familiar:
                events |= fam_events.get((devedor, laranja), set())
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

    # Agrupa as suspeitas POR DEVEDOR (quem movimenta = src). Antes o detector
    # colapsava tudo num único achado atribuído a suspeitas[0][0] — logo, com
    # vários casos, só um devedor recebia o alerta. Agora cada devedor com
    # movimentação na véspera gera o seu próprio achado.
    por_devedor: Dict[str, list] = defaultdict(list)  # src -> [(dst, events)]
    def _check(d_str, src, dst, events):
        if not d_str:
            return
        try:
            dt = date.fromisoformat(d_str)
        except ValueError:
            return
        for m in marcos:
            if timedelta(0) <= (m - dt) <= timedelta(days=JANELA_VESPERA_DIAS):
                por_devedor[src].append((dst, set(events)))
                return

    for t in g.transactions:
        _check(t["date"], t["src"], t["dst"], t["events"])
    for venda in g.rels("VENDEDOR_QUOTAS"):
        _check(venda["date"], venda["src"], venda["dst"], venda["events"])

    if not por_devedor:
        return []
    out = []
    for devedor in sorted(por_devedor):
        movs = por_devedor[devedor]
        envolvidos = [devedor] + sorted({d for d, _ in movs})
        events = set(g.marcos_events())
        for _, evs in movs:
            events |= evs
        out.append({
            "pattern": "vespera_constricao",
            "severidade": "CRITICA",
            "envolvidos": envolvidos,
            "devedor_alvo": devedor,
            "source_events": events,
            "descricao": (
                f"{len(movs)} movimentação(ões) patrimonial(is) de {devedor} "
                f"realizada(s) até {JANELA_VESPERA_DIAS} dias antes de marco "
                f"judicial ({', '.join(marcos_raw)})."
            ),
            "conclusao_juridica": (
                "Fraude à execução (art. 792 CPC / art. 185 CTN): alienação ou "
                "oneração de bens na iminência de constrição judicial conhecida."
            ),
        })
    return out


def detect_suborno(g: CaseGraph) -> List[dict]:
    """Pagamento de propina/vantagem indevida a agente público (corrupção
    ativa). O pagador é, tipicamente, o mesmo devedor que blinda o patrimônio:
    o suborno e a triangulação fecham, juntos, o esquema de captura do agente
    público + esvaziamento patrimonial. Cada perna pode vir de fonte distinta."""
    out = []
    for s in g.rels("SUBORNO"):
        pagador, agente = s["src"], s["dst"]
        valor = s.get("value")
        out.append({
            "pattern": "suborno",
            "severidade": "CRITICA",
            "envolvidos": [pagador, agente],
            "devedor_alvo": pagador,
            "source_events": set(s["events"]),
            "descricao": (
                f"{pagador} pagou propina"
                + (f" de R$ {valor:,.2f}" if valor else "")
                + f" ao agente público {agente}"
                + (f" em {s['date']}" if s.get("date") else "") + "."
            ),
            "conclusao_juridica": (
                "Corrupção ativa (CP, art. 333) e ato de improbidade: "
                "vantagem indevida a agente público em contrapartida a "
                "favorecimento, com lesão ao erário e quebra da moralidade "
                "administrativa."
            ),
        })
    return out


def _marcos_dates(g: CaseGraph) -> List[date]:
    out = []
    for m in g.marcos_datas():
        try:
            out.append(date.fromisoformat(m))
        except ValueError:
            continue
    return out


def detect_antedatacao(g: CaseGraph) -> List[dict]:
    """Antedatação fraudulenta: o histórico (CDC/trilha do banco) mostra que a
    DATA de um registo foi ALTERADA para ANTES de um marco judicial, mas a
    própria alteração foi feita DEPOIS do marco. O estado atual do banco parece
    limpo (venda "antiga"); só cruzando o registo do banco com o log de
    mudanças a fraude aparece — esvaziamento patrimonial disfarçado de negócio
    anterior à execução."""
    marcos = _marcos_dates(g)
    if not marcos:
        return []
    out = []
    for a in g.alteracoes:
        if a.get("operacao") != "UPDATE" or "data" not in (a.get("campo") or ""):
            continue
        try:
            d_new = date.fromisoformat(a["para"])
            t_chg = date.fromisoformat(a["em"])
        except (ValueError, TypeError):
            continue
        for m in marcos:
            # data nova é anterior/igual ao marco, mas a edição foi feita depois
            if d_new <= m <= t_chg:
                ent = a["entidade"]
                events = set(a["events"]) | set(g.marcos_events())
                # liga ao registo DO BANCO que foi antedatado (mesma entidade)
                for v in g.rels("VENDEDOR_QUOTAS"):
                    if v["src"] == ent:
                        events |= set(v["events"])
                de_txt = f" (era {a.get('de')})" if a.get("de") else ""
                out.append({
                    "pattern": "antedatacao",
                    "severidade": "CRITICA",
                    "envolvidos": [ent],
                    "devedor_alvo": ent,
                    "source_events": events,
                    "descricao": (
                        f"Registro de {ent} teve a data alterada para "
                        f"{a['para']}{de_txt} em {a['em']} — DEPOIS do marco "
                        f"judicial de {m.isoformat()}. Antedatação para simular "
                        f"negócio anterior à execução."
                    ),
                    "conclusao_juridica": (
                        "Fraude à execução com adulteração de registro (CPC, "
                        "art. 792; CP, arts. 297/299 — falsidade documental): a "
                        "data foi retroagida após a constrição para forjar "
                        "anterioridade do ato."
                    ),
                })
                break
    return out


def detect_registro_apagado(g: CaseGraph) -> List[dict]:
    """Destruição de prova: registo APAGADO (DELETE no log) em data igual ou
    posterior a um marco judicial — sumiço deliberado de movimentação do radar
    depois de a execução ser conhecida."""
    marcos = _marcos_dates(g)
    if not marcos:
        return []
    out = []
    for a in g.alteracoes:
        if a.get("operacao") != "DELETE":
            continue
        try:
            t_chg = date.fromisoformat(a["em"])
        except (ValueError, TypeError):
            continue
        for m in marcos:
            if t_chg >= m:
                ent = a["entidade"]
                events = set(a["events"]) | set(g.marcos_events())
                tab = a.get("tabela") or "registro"
                out.append({
                    "pattern": "registro_apagado",
                    "severidade": "CRITICA",
                    "envolvidos": [ent],
                    "devedor_alvo": ent,
                    "source_events": events,
                    "descricao": (
                        f"Registro de {ent} na fonte '{tab}' foi APAGADO em "
                        f"{a['em']} — em/após o marco judicial de "
                        f"{m.isoformat()}. Destruição de prova."
                    ),
                    "conclusao_juridica": (
                        "Fraude processual e supressão de documento (CP, art. "
                        "305): eliminação de registro após o conhecimento da "
                        "execução, para subtrair movimentação ao rastreamento."
                    ),
                })
                break
    return out


PATTERNS: Dict[str, Callable[[CaseGraph], List[dict]]] = {
    "triangulacao_offshore": detect_triangulacao_offshore,
    "fracionamento": detect_fracionamento,
    "laranja_familiar": detect_laranja_familiar,
    "vespera_constricao": detect_vespera_constricao,
    "suborno": detect_suborno,
    "antedatacao": detect_antedatacao,
    "registro_apagado": detect_registro_apagado,
}
