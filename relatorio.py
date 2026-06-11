"""
Gera o relatório pericial em Markdown de um insight (por ULID), com a
cadeia de custódia resolvida a partir do HeraclitusDB.

  py relatorio.py --insight 01KTS... --out relatorio.md
  py relatorio.py --ultimos 5            # lista os insights recentes
"""
import argparse
import logging

from agent.client import HeraclitusClient
from agent.report import gerar_relatorio_md

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _por_id(client, rows, insight_id):
    for r in rows:
        if r["id"] == insight_id:
            return r
    raise SystemExit(f"insight {insight_id} não encontrado")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Relatório pericial LABRA")
    ap.add_argument("--insight", type=str, help="ULID do insight")
    ap.add_argument("--out", type=str, default=None, help="Ficheiro de saída (.md)")
    ap.add_argument("--ultimos", type=int, default=0, help="Listar N insights recentes")
    ap.add_argument("--tls", action="store_true")
    ap.add_argument("--target", type=str, default="localhost:7474")
    args = ap.parse_args()

    client = HeraclitusClient(args.target, tls=args.tls)
    rows = client.query(
        'MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n ORDER BY n.lsn DESC'
    )
    insights = [r for r in rows if "INSIGHT_PERICIAL_FRAUDE" in r.get("kind", "")]

    if args.ultimos:
        for r in insights[: args.ultimos]:
            import json
            p = json.loads(r["content"])
            print(f"{r['id']}  LSN={r['lsn']:>4}  [{p.get('severidade')}] "
                  f"{p.get('tipo_fraude')}  alvo={p.get('devedor_alvo')}")
        raise SystemExit(0)

    if not args.insight:
        ap.error("forneça --insight <ULID> ou --ultimos N")

    insight = _por_id(client, insights, args.insight)
    prov = client.provenance(args.insight)
    # Resolve os documentos-fonte para detalhar a custódia
    all_rows = client.query("MATCH (n) RETURN n")
    fontes = {r["id"]: r for r in all_rows if r["id"] in set(prov)}

    md = gerar_relatorio_md(insight, prov, fontes)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        logging.info(f"Relatório gravado em {args.out}")
    else:
        print(md)
