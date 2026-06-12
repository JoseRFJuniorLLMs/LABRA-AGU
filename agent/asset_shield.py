"""
asset_shield — heurísticas avançadas de blindagem patrimonial (Fase 2).

Expande o catálogo do `patterns.py` para esquemas de alta performance que a
Procuradoria vê na prática. Mesmo contrato de `patterns.py`: cada detector é
`detect(graph: CaseGraph) -> List[dict]`, devolvendo achados com `pattern`,
`severidade`, `envolvidos`, `devedor_alvo`, `source_events` (ULIDs) e narrativa
jurídica — logo plugam diretamente no Investigator/daemon e na proveniência.

As relações que alimentam estes detectores (DOACAO, ADMINISTRA, CONTROLA) são
extraídas pelo `parser.py` (Fase 2). Heurísticas codificadas:

  - holding_usufruto   : controle de fato sem titularidade aparente
                         (usufruto/administração vitalícia de empresa);
  - doacao_cruzada     : doação em dois saltos para fechar no laranja familiar;
  - offshore_cascata   : camadas de controle indireto ocultando o beneficiário.
"""
from collections import defaultdict
from typing import Callable, Dict, List

from .graph import CaseGraph

# Arestas que representam "controle" (para a deteção de cascata). VENDEDOR_QUOTAS
# e PROCURADOR sozinhos formam a triangulação básica (já coberta); a cascata
# exige pelo menos uma aresta CONTROLA — camada de controle indireto.
_CONTROL_TYPES = ("CONTROLA", "VENDEDOR_QUOTAS", "PROCURADOR_COM_PODERES")


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


# Catálogo de blindagem — mesmo formato do patterns.PATTERNS.
SHIELD_PATTERNS: Dict[str, Callable[[CaseGraph], List[dict]]] = {
    "holding_usufruto": detect_holding_usufruto,
    "doacao_cruzada": detect_doacao_cruzada,
    "offshore_cascata": detect_offshore_cascata,
    "fraude_inss": detect_fraude_inss,
}
