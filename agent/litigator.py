"""
litigator — gerador de minutas de peças processuais (Fase 2, passo 5).

Traduz a teoria do caso numa petição em Markdown (Fatos, Direito, Pedido
Cautelar) pronta para o peticionamento. Determinístico (templates), sem LLM no
caminho crítico.

REGRA DE OURO: toda afirmação de fato carrega a citação ao ULID/LSN da prova
de origem — `[Prova: ULID...]`. Um fato sem proveniência rastreável não entra
na peça (a filtragem é feita a montante, no theory_builder).
"""
from typing import List, Optional

from .legal_mapper import LegalMapper


def _provas(source_events) -> str:
    ulids = sorted(source_events or [])
    return "[Prova: " + "; ".join(ulids) + "]" if ulids else "[Prova: —]"


class Litigator:
    def __init__(self, mapper: Optional[LegalMapper] = None):
        self.mapper = mapper or LegalMapper()

    def minuta(self, *, devedor: str, achados: List[dict],
               devedor_nome: Optional[str] = None,
               causal: Optional[List[str]] = None,
               essenciais: Optional[List[str]] = None) -> str:
        alvo = devedor_nome or devedor
        patterns = [a.get("tipo_fraude") or a.get("pattern") for a in achados]
        legal = self.mapper.subsume([p for p in patterns if p])

        out: List[str] = []
        out.append(f"# Petição — Recuperação de Ativos — {alvo}")
        out.append("")
        out.append("**EXEQUENTE:** Advocacia-Geral da União (LABRA).  "
                   f"**EXECUTADO:** {alvo} (`{devedor}`).")
        out.append("")

        # I — DOS FATOS
        out.append("## I — DOS FATOS")
        out.append("")
        for i, a in enumerate(achados, 1):
            sev = a.get("severidade", "")
            score = a.get("evidence_score")
            sc = f" — força probatória {score:.2f}" if score is not None else ""
            desc = (a.get("descricao") or "").strip()
            out.append(f"{i}. ({sev}{sc}) {desc} {_provas(a.get('source_events'))}")
        out.append("")
        if causal:
            out.append("**Do nexo de causalidade** (sequência temporal por ULID):")
            for c in causal:
                out.append(f"- {c}")
            out.append("")
        if essenciais:
            out.append("**Provas essenciais** (sua subtração rompe o esquema de "
                       "ocultação — relevância máxima): "
                       + "; ".join(f"`{u}`" for u in essenciais) + ".")
            out.append("")

        # II — DO DIREITO
        out.append("## II — DO DIREITO")
        out.append("")
        for pattern, enquadramentos in legal["por_padrao"].items():
            for e in enquadramentos:
                ementa = f" — {e['ementa']}" if e.get("ementa") else ""
                out.append(f"- **{e['tipo']}** ({e['dispositivo']}){ementa}")
        out.append("")
        if legal["dispositivos"]:
            out.append("Dispositivos invocados: " +
                       ", ".join(legal["dispositivos"]) + ".")
            out.append("")

        # III — DO PEDIDO
        out.append("## III — DO PEDIDO (TUTELA CAUTELAR)")
        out.append("")
        out.append("Requer-se, com fundamento no *fumus boni iuris* (demonstrado "
                   "pelos fatos e provas supra) e no *periculum in mora* "
                   "(dissipação patrimonial em curso):")
        out.append("")
        out.append("a) a **indisponibilidade e o bloqueio** dos bens e ativos do "
                   f"executado `{devedor}` e das interpostas pessoas identificadas;")
        out.append("b) a **desconsideração da personalidade jurídica** das "
                   "estruturas empregadas na ocultação (CC, art. 50);")
        out.append("c) a declaração de **ineficácia/anulação** dos atos de "
                   "alienação e doação praticados em fraude (CPC, art. 792; "
                   "CC, arts. 158 e 159).")
        out.append("")
        out.append("> Cadeia de custódia: todos os fatos remetem por ULID aos "
                   "eventos imutáveis do log do HeraclitusDB, auditáveis e "
                   "consultáveis *AS OF* qualquer ponto do passado.")
        return "\n".join(out)
