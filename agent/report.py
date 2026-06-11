"""
Gerador de Relatório Pericial (Diretriz V — "Rastreabilidade").

Traduz um insight do log numa narrativa jurídica conclusiva, com cadeia de
custódia verificável: lista os ULIDs dos documentos-fonte e das diretrizes,
as entidades envolvidas, as ativações ACT-R e a fundamentação legal.

Saída em Markdown (portável, convertível para PDF/DOCX). Não inventa nada —
todo conteúdo vem do insight e da sua proveniência no HeraclitusDB.
"""
import datetime
import json
from typing import Optional


def gerar_relatorio_md(insight_row: dict, provenance: list,
                       fontes: Optional[dict] = None) -> str:
    """
    insight_row: linha do MATCH (campos lsn, id, kind, content[JSON], ...).
    provenance: lista de ULIDs devolvida por PROVENANCE(insight_id).
    fontes: mapa opcional ULID -> linha do documento-fonte (para detalhar).
    """
    payload = json.loads(insight_row["content"])
    fontes = fontes or {}
    agora = datetime.datetime.now(datetime.timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    sev = payload.get("severidade", "—")
    tipo = payload.get("tipo_fraude", "—")
    envolvidos = payload.get("envolvidos", [])
    ativacoes = payload.get("ativacao_act_r", {})
    diretrizes = payload.get("diretrizes_aplicadas", [])

    out = []
    out.append("# RELATÓRIO PERICIAL — Indício de Blindagem Patrimonial")
    out.append("")
    out.append("> Documento gerado automaticamente pelo Agente Pericial LABRA-AGU.")
    out.append("> A cadeia de custódia é verificável no HeraclitusDB via `PROVENANCE`.")
    out.append("")
    out.append("## 1. Identificação")
    out.append("")
    out.append(f"- **Insight (ULID):** `{insight_row['id']}`")
    out.append(f"- **LSN no log:** {insight_row.get('lsn', '—')}")
    out.append(f"- **Tipo de fraude detectada:** {tipo}")
    out.append(f"- **Severidade:** **{sev}**")
    out.append(f"- **Devedor-alvo:** `{payload.get('devedor_alvo', '—')}`")
    out.append(f"- **Emitido em:** {agora}")
    out.append("")

    out.append("## 2. Descrição do Achado")
    out.append("")
    out.append(payload.get("descricao", "—"))
    out.append("")

    out.append("## 3. Entidades Envolvidas")
    out.append("")
    out.append("| Entidade (ID canónico) | Ativação ACT-R |")
    out.append("|---|---|")
    for e in envolvidos:
        out.append(f"| `{e}` | {ativacoes.get(e, '—')} |")
    out.append("")
    out.append("> A ativação ACT-R reflete a relevância sub-simbólica da entidade "
               "(recência + frequência de aparição na investigação). Valores "
               "elevados indicam centralidade no esquema fraudulento.")
    out.append("")

    out.append("## 4. Fundamentação Jurídica")
    out.append("")
    out.append(payload.get("conclusao_juridica", "—"))
    out.append("")

    out.append("## 5. Cadeia de Custódia (Proveniência Criptográfica)")
    out.append("")
    if provenance:
        out.append("Este achado é sustentado pelos seguintes eventos imutáveis "
                   "do log (cada um carimbado no tempo e protegido por hash):")
        out.append("")
        out.append("| ULID do evento-fonte | Tipo | Referência documental |")
        out.append("|---|---|---|")
        for ev in provenance:
            f = fontes.get(ev, {})
            ref = (f.get("attrs", {}) or {}).get("doc_ref") \
                or (f.get("attrs", {}) or {}).get("table") \
                or f.get("kind", "—")
            kind = f.get("kind", "—")
            out.append(f"| `{ev}` | {kind} | {ref} |")
        out.append("")
    else:
        out.append("_(Sem proveniência registada — verificar integridade.)_")
        out.append("")
    if diretrizes:
        out.append(f"**Diretrizes da Procuradoria aplicadas:** "
                   f"{', '.join('`'+d+'`' for d in diretrizes)}")
        out.append("")

    out.append("## 6. Verificação")
    out.append("")
    out.append("Para auditar este relatório de forma independente, consulte o "
               "HeraclitusDB:")
    out.append("")
    out.append("```")
    out.append(f'PROVENANCE ("{insight_row["id"]}")')
    out.append(f'MATCH (n) WHERE n.lsn = {insight_row.get("lsn", 0)} RETURN n')
    out.append("```")
    out.append("")
    out.append("---")
    out.append("*Panta rhei — a verdade não se edita. Este relatório nasce de "
               "eventos imutáveis e a sua origem é matematicamente verificável.*")
    return "\n".join(out)
