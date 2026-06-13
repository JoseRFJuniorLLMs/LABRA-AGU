"""
coverage — vetores de fraude do contexto brasileiro que o catálogo base não vê.

Responde a três perguntas que o grafo de blindagem sozinho não responde:
  - o patrimônio FECHA com a renda lícita declarada? (enriquecimento ilícito)
  - o Estado foi capturado?  (contrato público direcionado; anomalia judiciária)
  - de onde veio / por onde passou o dinheiro? (cripto off-ramp; mula PIX)

Cada detector mantém o contrato `detect(graph) -> List[dict]` e pluga no mesmo
catálogo (investigator/daemon/theory_builder), com proveniência por ULID.

RESSALVA ÉTICA (detect_anomalia_judiciaria): o agente aponta ANOMALIA
ESTATÍSTICA que requer apuração — NUNCA "prova" de sentença comprada. Severidade
limitada, linguagem garantista, presunção de inocência e contraditório
assegurados. Não imputa ilícito a pessoa determinada.
"""
from collections import defaultdict
from datetime import date
from typing import Callable, Dict, List

from .graph import CaseGraph

_ATTR_RELS = ("MESMO_ENDERECO", "MESMO_TELEFONE", "MESMO_CONTADOR", "MESMA_CONTA")
_FATOR_ALERTA = 10      # patrimônio > 10x a renda anual = a investigar
_FATOR_CRITICO = 30     # patrimônio > 30x a renda anual = grave
_CONTRATO_JANELA_DIAS = 180   # fornecedor criado < 6 meses antes do contrato
_JUD_LIMIAR = 3         # nº de êxitos no mesmo foro para sinalizar anomalia
_MULA_K = 3             # fan-in e fan-out mínimos de uma conta de passagem


def _pares_vinculados(g: CaseGraph, *rtypes) -> set:
    """Pares (a,b) e (b,a) ligados por qualquer uma das relações dadas."""
    out = set()
    for rt in rtypes:
        for r in g.rels(rt):
            out.add((r["src"], r["dst"]))
            out.add((r["dst"], r["src"]))
    return out


# 1 ── Incompatibilidade renda × patrimônio (enriquecimento ilícito) ────
def detect_patrimonio_incompativel(g: CaseGraph) -> List[dict]:
    pat = defaultdict(float)
    pat_ev = defaultdict(set)
    for tr in g.asset_transfers:
        vm = (g.assets.get(tr["asset_id"], {}) or {}).get("valor_mercado") \
            or tr.get("value") or 0
        if vm:
            pat[tr["dst"]] += vm
            pat_ev[tr["dst"]] |= set(tr["events"])
    for t in g.transactions:
        if t.get("value"):
            pat[t["dst"]] += t["value"]
            pat_ev[t["dst"]] |= set(t["events"])

    out = []
    for cid, attrs in g.entity_attrs.items():
        renda = attrs.get("renda_anual")
        if not renda or renda <= 0:
            continue
        patrimonio = pat.get(cid, 0.0)
        if patrimonio <= _FATOR_ALERTA * renda:
            continue
        mult = patrimonio / renda
        out.append({
            "pattern": "patrimonio_incompativel",
            "severidade": "CRITICA" if mult >= _FATOR_CRITICO else "ALTA",
            "envolvidos": [cid],
            "devedor_alvo": cid,
            "source_events": pat_ev.get(cid, set()),
            "descricao": (
                f"{cid} adquiriu/movimentou patrimônio de R$ {patrimonio:,.2f} — "
                f"{mult:.0f}x a renda anual declarada (R$ {renda:,.2f})."),
            "conclusao_juridica": (
                "Evolução patrimonial a descoberto, incompatível com a renda "
                "lícita declarada — indício de enriquecimento ilícito (Lei "
                "8.429/92, art. 9º) e ocultação patrimonial; apurar a evolução "
                "no tempo e a origem dos recursos."),
        })
    return out


# 2 ── Vínculo oculto por atributo compartilhado (link analysis) ────────
def detect_vinculo_por_atributo(g: CaseGraph) -> List[dict]:
    fluxo = _pares_vinculados(g, "CONTROLA", "VENDEDOR_QUOTAS",
                              "PROCURADOR_COM_PODERES")
    for t in g.transactions:
        fluxo.add((t["src"], t["dst"]))
    for tr in g.asset_transfers:
        fluxo.add((tr["src"], tr["dst"]))

    out = []
    for rt in _ATTR_RELS:
        for r in g.rels(rt):
            a, b = r["src"], r["dst"]
            opera = (a, b) in fluxo or (b, a) in fluxo
            atributo = rt.replace("MESMO_", "").replace("MESMA_", "").lower()
            out.append({
                "pattern": "vinculo_por_atributo",
                "severidade": "CRITICA" if opera else "ALTA",
                "envolvidos": [a, b],
                "devedor_alvo": a,
                "source_events": set(r["events"]),
                "descricao": (
                    f"{a} e {b} partilham o mesmo {atributo} — provável mesmo "
                    "controlador" + (" e há fluxo patrimonial entre eles."
                                     if opera else ".")),
                "conclusao_juridica": (
                    "Vínculo oculto por atributo compartilhado (endereço/"
                    "telefone/contador/conta) revela interposição e confusão "
                    "patrimonial (art. 50 CC — desconsideração)."),
            })
    return out


# 3 ── Passivo simulado / credor amigo (preterição do fisco) ────────────
def detect_passivo_simulado(g: CaseGraph) -> List[dict]:
    vinc = _pares_vinculados(g, "FAMILIAR", "CONTROLA", "VENDEDOR_QUOTAS",
                             "PROCURADOR_COM_PODERES", *_ATTR_RELS)
    out = []
    for rt in ("CREDOR_DIVIDA", "CREDOR_TRABALHISTA"):
        for r in g.rels(rt):
            credor, devedor = r["src"], r["dst"]
            if (credor, devedor) not in vinc:
                continue
            tipo = "trabalhista" if rt == "CREDOR_TRABALHISTA" else "confessada"
            out.append({
                "pattern": "passivo_simulado",
                "severidade": "CRITICA",
                "envolvidos": [credor, devedor],
                "devedor_alvo": devedor,
                "source_events": set(r["events"]),
                "descricao": (
                    f"Dívida {tipo} de {devedor} a {credor}, que tem vínculo "
                    "(familiar/societário/atributo) com o devedor — crédito "
                    "provavelmente simulado para preterir a Fazenda."),
                "conclusao_juridica": (
                    "Passivo simulado / credor amigo para furar a ordem de "
                    "preferência (art. 167 CC — simulação; fraude à execução). "
                    "Reclamação trabalhista combinada gera super-preferência em "
                    "lesão ao erário."),
            })
    return out


# 4 ── Contrato público direcionado / fornecedor de fachada ─────────────
def detect_contrato_direcionado(g: CaseGraph) -> List[dict]:
    orgaos_por_forn = defaultdict(set)
    for r in g.rels("CONTRATOU_PUBLICO"):
        orgaos_por_forn[r["dst"]].add(r["src"])

    out = []
    for r in g.rels("CONTRATOU_PUBLICO"):
        orgao, forn = r["src"], r["dst"]
        dc = g.entity_attrs.get(forn, {}).get("data_constituicao")
        criada_para = False
        if dc and r.get("date"):
            try:
                dias = (date.fromisoformat(r["date"]) - date.fromisoformat(dc)).days
                criada_para = -30 <= dias <= _CONTRATO_JANELA_DIAS
            except (ValueError, TypeError):
                pass
        mono = len(orgaos_por_forn.get(forn, set())) == 1
        if not (criada_para or mono):
            continue
        motivos = []
        if criada_para:
            motivos.append("fornecedor constituído às vésperas do contrato")
        if mono:
            motivos.append("fornecedor fatura com um único órgão")
        valor = f" (R$ {r['value']:,.2f})" if r.get("value") else ""
        out.append({
            "pattern": "contrato_direcionado",
            "severidade": "CRITICA" if criada_para else "ALTA",
            "envolvidos": [orgao, forn],
            "devedor_alvo": forn,
            "source_events": set(r["events"]),
            "descricao": (
                f"Contrato público de {orgao} a {forn}{valor} — "
                + "; ".join(motivos) + "."),
            "conclusao_juridica": (
                "Indício de direcionamento e fornecedor de fachada em "
                "contratação pública (Lei 14.133/21; Lei 8.429/92 — improbidade; "
                "frustração da licitação)."),
        })
    return out


# 5 ── Off-ramp em criptoativos (quebra de rastreabilidade) ─────────────
def detect_offramp_cripto(g: CaseGraph) -> List[dict]:
    fam = {(f["src"], f["dst"]) for f in g.rels("FAMILIAR")}
    out = []
    for r in g.rels("CONVERTEU_CRIPTO"):
        src, dst = r["src"], r["dst"]
        familiar = (src, dst) in fam
        valor = r.get("value") or 0
        out.append({
            "pattern": "offramp_cripto",
            "severidade": "CRITICA" if familiar else "ALTA",
            "envolvidos": [src, dst],
            "devedor_alvo": src,
            "source_events": set(r["events"]),
            "descricao": (
                f"{src} converteu R$ {valor:,.2f} em criptoativos e repassou a "
                f"{dst}" + (" (interposta pessoa com vínculo familiar)"
                           if familiar else "") + " — off-ramp que quebra a "
                "rastreabilidade."),
            "conclusao_juridica": (
                "Uso de criptoativos para ocultar origem e titularidade do "
                "patrimônio (Lei 9.613/98, art. 1º — lavagem); quebra dolosa da "
                "cadeia de rastreabilidade."),
        })
    return out


# 6 ── Anomalia judiciária (SINAL, NÃO PROVA — salvaguardas embutidas) ──
def detect_anomalia_judiciaria(g: CaseGraph) -> List[dict]:
    # Cada decisão é um evento distinto no log (uma linha do DataJud); como o
    # grafo deduplica a relação (advogado, foro), o nº de decisões = nº de
    # eventos-prova acumulados nessa relação.
    por_par = defaultdict(set)
    for r in g.rels("DECISAO_FAVORAVEL"):
        por_par[(r["src"], r["dst"])] |= set(r["events"])

    out = []
    for (adv, foro), events in por_par.items():
        n = len(events)
        if n < _JUD_LIMIAR:
            continue
        out.append({
            "pattern": "anomalia_judiciaria",
            # Severidade limitada de propósito: é sinal a apurar, não imputação.
            "severidade": "ALTA" if n >= 2 * _JUD_LIMIAR else "MEDIA",
            "envolvidos": [adv, foro],
            "devedor_alvo": adv,
            "source_events": events,
            "descricao": (
                f"Concentração atípica: {adv} obteve {n} decisões favoráveis no "
                f"mesmo foro {foro} — anomalia estatística que REQUER APURAÇÃO."),
            "conclusao_juridica": (
                "SINAL ESTATÍSTICO, NÃO PROVA. Concentração anómala de êxito "
                "perante um mesmo foro merece apuração (aleatoriedade da "
                "distribuição, tempestividade, vínculos), assegurados o "
                "contraditório, a ampla defesa e a presunção de inocência. Não "
                "imputa, por si, qualquer ilícito a pessoa determinada."),
        })
    return out


# 7 ── Conta de passagem / mula financeira (redes PIX) ──────────────────
def detect_mula_financeira(g: CaseGraph) -> List[dict]:
    fan_in, fan_out, ev = defaultdict(set), defaultdict(set), defaultdict(set)
    for t in g.transactions:
        if t["src"] == t["dst"]:
            continue
        fan_in[t["dst"]].add(t["src"])
        fan_out[t["src"]].add(t["dst"])
        ev[t["dst"]] |= set(t["events"])
        ev[t["src"]] |= set(t["events"])

    out = []
    for n in set(fan_in) | set(fan_out):
        ins, outs = len(fan_in.get(n, ())), len(fan_out.get(n, ()))
        if ins >= _MULA_K and outs >= _MULA_K:
            out.append({
                "pattern": "mula_financeira",
                "severidade": "ALTA",
                "envolvidos": [n],
                "devedor_alvo": n,
                "source_events": ev.get(n, set()),
                "descricao": (
                    f"{n} recebe de {ins} origens e repassa a {outs} destinos — "
                    "padrão de conta de passagem/mula (típico de redes PIX)."),
                "conclusao_juridica": (
                    "Conta de passagem/mula no fracionamento e dispersão de "
                    "recursos (Lei 9.613/98); típica de redes de mulas e golpes "
                    "via PIX."),
            })
    return out


COVERAGE_PATTERNS: Dict[str, Callable[[CaseGraph], List[dict]]] = {
    "patrimonio_incompativel": detect_patrimonio_incompativel,
    "vinculo_por_atributo": detect_vinculo_por_atributo,
    "passivo_simulado": detect_passivo_simulado,
    "contrato_direcionado": detect_contrato_direcionado,
    "offramp_cripto": detect_offramp_cripto,
    "anomalia_judiciaria": detect_anomalia_judiciaria,
    "mula_financeira": detect_mula_financeira,
}
