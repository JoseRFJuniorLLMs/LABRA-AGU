"""
asset_shield — heurísticas avançadas de blindagem patrimonial (Fase 2).

Expande o catálogo do `patterns.py` para esquemas de alta performance que a
Procuradoria vê na prática. Mesmo contrato de `patterns.py`: cada detector é
`detect(graph: CaseGraph) -> List[dict]`, devolvendo achados com `pattern`,
`severidade`, `envolvidos`, `devedor_alvo`, `source_events` (ULIDs) e narrativa
jurídica — logo plugam diretamente no Investigator/daemon e na proveniência.

As relações que alimentam estes detectores (DOACAO, ADMINISTRA, CONTROLA) e os
BENS (ativos + alienações) são extraídos pelo `parser.py`. Heurísticas:

  - holding_usufruto    : controle de fato sem titularidade aparente
                          (usufruto/administração vitalícia de empresa);
  - doacao_cruzada      : doação em dois saltos para fechar no laranja familiar;
  - offshore_cascata    : camadas de controle indireto ocultando o beneficiário;
  - fraude_inss         : desvio de benefícios previdenciários para a rede;
  - bem_preco_vil       : alienação de bem por preço vil (venda simulada);
  - bem_a_interposto    : bem transferido a familiar / na véspera de constrição;
  - ubo_cadeia_profunda : controle indireto em >=3 saltos até o beneficiário final;
  - controle_circular   : participação cruzada circular que dissolve a titularidade.
"""
from collections import defaultdict
from datetime import date, timedelta
from typing import Callable, Dict, List

from .graph import CaseGraph

# Arestas que representam "controle" (para a deteção de cascata). VENDEDOR_QUOTAS
# e PROCURADOR sozinhos formam a triangulação básica (já coberta); a cascata
# exige pelo menos uma aresta CONTROLA — camada de controle indireto.
_CONTROL_TYPES = ("CONTROLA", "VENDEDOR_QUOTAS", "PROCURADOR_COM_PODERES")

_JANELA_VESPERA_DIAS = 30
_MAX_DEPTH = 6


def _control_adj(g: CaseGraph):
    """Adjacência de controle (com proveniência por aresta) para UBO/ciclos."""
    adj = defaultdict(list)
    for rt in _CONTROL_TYPES:
        for r in g.rels(rt):
            if r["src"] != r["dst"]:
                adj[r["src"]].append((r["dst"], rt, frozenset(r["events"])))
    return adj


def _marcos_datas(g: CaseGraph):
    out = []
    for m in g.marcos_datas():
        try:
            out.append(date.fromisoformat(m))
        except ValueError:
            pass
    return out


def _ownership_ids(g: CaseGraph) -> set:
    """Entidades que aparecem como titulares aparentes (alienaram quotas)."""
    return {r["src"] for r in g.rels("VENDEDOR_QUOTAS")}


def detect_holding_usufruto(g: CaseGraph) -> List[dict]:
    """Imóvel/empresa controlada pelo devedor via usufruto ou administração
    vitalícia, SEM quotas aparentes em seu nome — controle de fato que mantém
    o patrimônio sob o devedor enquanto o esconde da titularidade formal."""
    out = []
    titulares = _ownership_ids(g)
    for r in g.rels("ADMINISTRA"):
        controlador, alvo = r["src"], r["dst"]
        sem_quotas = controlador not in titulares
        out.append({
            "pattern": "holding_usufruto",
            "severidade": "CRITICA" if sem_quotas else "ALTA",
            "envolvidos": [controlador, alvo],
            "devedor_alvo": controlador,
            "source_events": set(r["events"]),
            "descricao": (
                f"{controlador} exerce controle de fato sobre {alvo} via "
                f"usufruto/administração vitalícia"
                + (" — sem deter quotas aparentes." if sem_quotas
                   else ", apesar da titularidade formal alterada.")
            ),
            "conclusao_juridica": (
                "Interposição real: poder de fato sobre o bem dissociado da "
                "titularidade formal, configurando blindagem patrimonial "
                "(art. 50 CC — confusão patrimonial / desconsideração)."
            ),
        })
    return out


def detect_doacao_cruzada(g: CaseGraph) -> List[dict]:
    """Doação em dois saltos: o devedor doa a um intermediário que, por sua
    vez, doa ao laranja final — quebrando o vínculo direto. Fecha CRÍTICA se o
    final (ou o intermediário) tem laço familiar com o devedor."""
    doacoes = g.rels("DOACAO")
    by_src: Dict[str, List[dict]] = defaultdict(list)
    for d in doacoes:
        by_src[d["src"]].append(d)
    familiares = {(f["src"], f["dst"]) for f in g.rels("FAMILIAR")}

    out = []
    for d1 in doacoes:
        devedor, intermediario = d1["src"], d1["dst"]
        for d2 in by_src.get(intermediario, []):
            final = d2["dst"]
            if final == devedor:
                continue
            fam = ((devedor, final) in familiares
                   or (devedor, intermediario) in familiares)
            events = set(d1["events"]) | set(d2["events"])
            if fam:
                for f in g.rels("FAMILIAR"):
                    if f["src"] == devedor and f["dst"] in (final, intermediario):
                        events |= set(f["events"])
            out.append({
                "pattern": "doacao_cruzada",
                "severidade": "CRITICA" if fam else "ALTA",
                "envolvidos": [devedor, intermediario, final],
                "devedor_alvo": devedor,
                "source_events": events,
                "descricao": (
                    f"{devedor} doou a {intermediario}, que repassou a {final}"
                    + (" — interposta pessoa com vínculo familiar." if fam else ".")
                ),
                "conclusao_juridica": (
                    "Doação cruzada para dissipar patrimônio por interposta "
                    "pessoa, frustrando a execução (art. 158 CC — fraude contra "
                    "credores; art. 792 CPC — fraude à execução)."
                ),
            })
    return out


def detect_offshore_cascata(g: CaseGraph) -> List[dict]:
    """Camadas de controle indireto (devedor → off1 → off2 …) que ocultam o
    beneficiário final real. Exige ao menos uma aresta CONTROLA na cadeia, para
    distinguir da triangulação básica (venda + procuração)."""
    adj: Dict[str, List[tuple]] = defaultdict(list)
    for rtype in _CONTROL_TYPES:
        for r in g.rels(rtype):
            adj[r["src"]].append((r["dst"], rtype, set(r["events"])))

    out = []
    for origem in list(adj):
        for meio, rt1, ev1 in adj[origem]:
            for fim, rt2, ev2 in adj.get(meio, []):
                if fim == origem or fim == meio:
                    continue
                if "CONTROLA" not in (rt1, rt2):
                    continue  # cadeia sem controle indireto = triangulação base
                out.append({
                    "pattern": "offshore_cascata",
                    "severidade": "ALTA",
                    "envolvidos": [origem, meio, fim],
                    "devedor_alvo": origem,
                    "source_events": ev1 | ev2,
                    "descricao": (
                        f"Controle em cascata {origem} → {meio} → {fim} "
                        f"({rt1.lower()} / {rt2.lower()}): beneficiário final "
                        "ocultado por camadas de controle indireto."
                    ),
                    "conclusao_juridica": (
                        "Estrutura multipartite (offshore/trust em cascata) para "
                        "ocultar o beneficiário efetivo — indício de ocultação "
                        "dolosa de patrimônio (Lei 9.613/98)."
                    ),
                })
    return out


def detect_fraude_inss(g: CaseGraph) -> List[dict]:
    """Desvio de benefícios previdenciários (INSS) para a rede do devedor —
    estelionato previdenciário/organização para fraudar a Previdência."""
    out = []
    for r in g.rels("DESVIO_INSS"):
        operador, destino = r["src"], r["dst"]
        out.append({
            "pattern": "fraude_inss",
            "severidade": "CRITICA",
            "envolvidos": [operador, destino],
            "devedor_alvo": destino,
            "source_events": set(r["events"]),
            "descricao": (
                f"{operador} desviou benefícios previdenciários do INSS para "
                f"{destino}, integrando-os ao esquema de blindagem."),
            "conclusao_juridica": (
                "Fraude previdenciária organizada: apropriação/desvio de "
                "benefícios do INSS (estelionato previdenciário, CP art. 171 "
                "§ 3º; Lei 8.213/91), com lesão ao erário."),
        })
    return out


# ── BENS (ativos) ──────────────────────────────────────────────────────
def detect_bem_preco_vil(g: CaseGraph) -> List[dict]:
    """Alienação de bem por preço MUITO abaixo do valor de mercado — venda
    simulada (subfaturamento) para tirar o bem do alcance da execução mantendo-o
    sob controle. Exige valor de mercado conhecido (avaliação)."""
    out = []
    for tr in g.asset_transfers:
        meta = g.assets.get(tr["asset_id"], {}) or {}
        vm, preco = meta.get("valor_mercado"), tr.get("value")
        if not vm or vm <= 0 or preco is None:
            continue
        ratio = preco / vm
        if ratio >= 0.5:
            continue  # dentro de uma faixa plausível de mercado
        out.append({
            "pattern": "bem_preco_vil",
            "severidade": "CRITICA" if ratio < 0.2 else "ALTA",
            "envolvidos": [tr["src"], tr["dst"]],
            "devedor_alvo": tr["src"],
            "source_events": set(tr["events"]),
            "descricao": (
                f"{tr['src']} alienou o bem {tr['asset_id']} "
                f"({meta.get('kind', 'BEM').lower()}) a {tr['dst']} por "
                f"R$ {preco:,.2f} — {ratio * 100:.0f}% do valor de mercado "
                f"(R$ {vm:,.2f})."),
            "conclusao_juridica": (
                "Venda a preço vil: negócio simulado para esvaziar o patrimônio "
                "(art. 167 CC — simulação; art. 158 CC — fraude contra credores; "
                "art. 792 CPC — fraude à execução)."),
        })
    return out


def detect_bem_a_interposto(g: CaseGraph) -> List[dict]:
    """Bem transferido a interposta pessoa: o adquirente é familiar do devedor
    e/ou a alienação ocorreu na véspera de marco judicial. Captura o laranja que
    NÃO aparece nas pernas societárias — só recebe o bem."""
    fam = {(f["src"], f["dst"]) for f in g.rels("FAMILIAR")}
    fam_events = defaultdict(set)
    for f in g.rels("FAMILIAR"):
        fam_events[(f["src"], f["dst"])] |= set(f["events"])
    marcos = _marcos_datas(g)
    out = []
    for tr in g.asset_transfers:
        dev, adq = tr["src"], tr["dst"]
        familiar = (dev, adq) in fam
        d = None
        try:
            d = date.fromisoformat(tr["date"]) if tr.get("date") else None
        except ValueError:
            d = None
        vespera = bool(d) and any(
            timedelta(0) <= (mk - d) <= timedelta(days=_JANELA_VESPERA_DIAS)
            for mk in marcos)
        flags = int(familiar) + int(vespera)
        if flags == 0:
            continue
        events = set(tr["events"])
        if familiar:
            events |= fam_events.get((dev, adq), set())
        if vespera:
            events |= set(g.marcos_events())
        motivos = []
        if familiar:
            motivos.append("o adquirente tem vínculo familiar com o devedor")
        if vespera:
            motivos.append("a alienação ocorreu na véspera de marco judicial")
        meta = g.assets.get(tr["asset_id"], {}) or {}
        out.append({
            "pattern": "bem_a_interposto",
            "severidade": "CRITICA" if flags >= 2 else "ALTA",
            "envolvidos": [dev, adq],
            "devedor_alvo": dev,
            "source_events": events,
            "descricao": (
                f"{dev} transferiu o bem {tr['asset_id']} "
                f"({meta.get('kind', 'BEM').lower()}) a {adq} — "
                + "; ".join(motivos) + "."),
            "conclusao_juridica": (
                "Transferência de bem a interposta pessoa para frustrar a "
                "execução (art. 50 CC — desconsideração; art. 158 CC; art. 792 "
                "CPC — fraude à execução; art. 185 CTN se em dívida ativa)."),
        })
    return out


# ── Beneficiário final: cadeias profundas e controle circular ──────────
def detect_ubo_cadeia_profunda(g: CaseGraph) -> List[dict]:
    """Controle indireto em >=3 saltos até um beneficiário final (sink), ALÉM
    da cascata de 2 saltos. Cada camada extra afasta o controlador real do bem."""
    adj = _control_adj(g)
    out, seen = [], set()

    def dfs(start, node, path, events, depth):
        if depth >= _MAX_DEPTH:
            return
        for nxt, _rt, evs in adj.get(node, []):
            if nxt in path:
                continue  # ciclo → tratado em detect_controle_circular
            npath = path + [nxt]
            nevents = events | evs
            # cadeia profunda = >=3 saltos (>=4 nós) terminando num sink (UBO)
            if len(npath) >= 4 and not adj.get(nxt):
                key = (start, nxt)
                if key not in seen:
                    seen.add(key)
                    out.append({
                        "pattern": "ubo_cadeia_profunda",
                        "severidade": "CRITICA" if len(npath) >= 5 else "ALTA",
                        "envolvidos": list(dict.fromkeys(npath)),
                        "devedor_alvo": start,
                        "source_events": set(nevents),
                        "descricao": (
                            "Controle em cadeia profunda (" + " → ".join(npath)
                            + f"): {len(npath) - 1} camadas afastam o "
                            "beneficiário final real."),
                        "conclusao_juridica": (
                            "Estrutura multicamada para ocultar o beneficiário "
                            "efetivo — ocultação dolosa de patrimônio (Lei "
                            "9.613/98, art. 1º)."),
                    })
            dfs(start, nxt, npath, nevents, depth + 1)

    for origem in list(adj):
        dfs(origem, origem, [origem], frozenset(), 0)
    return out


def detect_controle_circular(g: CaseGraph) -> List[dict]:
    """Participação cruzada circular (A→B→…→A) que dissolve a titularidade real.
    Componentes fortemente conexos (Tarjan) de tamanho >=2 no grafo de controle."""
    adj = _control_adj(g)
    index, low, onstack, stack, idx, sccs = {}, {}, {}, [], [0], []

    def strong(v):
        index[v] = low[v] = idx[0]
        idx[0] += 1
        stack.append(v)
        onstack[v] = True
        for w, _rt, _evs in adj.get(v, []):
            if w not in index:
                strong(w)
                low[v] = min(low[v], low[w])
            elif onstack.get(w):
                low[v] = min(low[v], index[w])
        if low[v] == index[v]:
            comp = []
            while True:
                w = stack.pop()
                onstack[w] = False
                comp.append(w)
                if w == v:
                    break
            sccs.append(comp)

    for v in list(adj):
        if v not in index:
            strong(v)

    out = []
    for comp in sccs:
        if len(comp) < 2:
            continue
        nodes = set(comp)
        events = set()
        for u in comp:
            for w, _rt, evs in adj.get(u, []):
                if w in nodes:
                    events |= set(evs)
        out.append({
            "pattern": "controle_circular",
            "severidade": "CRITICA",
            "envolvidos": sorted(nodes),
            "devedor_alvo": sorted(nodes)[0],
            "source_events": events,
            "descricao": (
                "Controle circular (" + " ↔ ".join(sorted(nodes))
                + "): participação cruzada que dissolve a titularidade real."),
            "conclusao_juridica": (
                "Participação societária circular para ocultar o controlador "
                "final — abuso da personalidade (art. 50 CC) e ocultação "
                "dolosa de patrimônio (Lei 9.613/98)."),
        })
    return out


# Catálogo de blindagem — mesmo formato do patterns.PATTERNS.
SHIELD_PATTERNS: Dict[str, Callable[[CaseGraph], List[dict]]] = {
    "holding_usufruto": detect_holding_usufruto,
    "doacao_cruzada": detect_doacao_cruzada,
    "offshore_cascata": detect_offshore_cascata,
    "fraude_inss": detect_fraude_inss,
    "bem_preco_vil": detect_bem_preco_vil,
    "bem_a_interposto": detect_bem_a_interposto,
    "ubo_cadeia_profunda": detect_ubo_cadeia_profunda,
    "controle_circular": detect_controle_circular,
}
