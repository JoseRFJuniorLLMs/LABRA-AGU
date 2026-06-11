"""
Consulta auditada (LGPD): toda LEITURA de dados pessoais é registada como
evento imutável no log (kind=ACESSO_LEITURA) — fica provado QUEM consultou
O QUÊ e POR QUÊ. A filosofia do projeto aplicada também ao acesso.

  py consulta.py --autor procurador.silva --motivo "Oficio 123" \
      'MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n'
"""
import argparse
import json
import logging

from agent.client import HeraclitusClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Consulta GQL auditada (LGPD)")
    ap.add_argument("gql", type=str, help="Consulta GQL")
    ap.add_argument("--autor", type=str, required=True, help="Quem consulta (identificação)")
    ap.add_argument("--motivo", type=str, default="", help="Justificativa do acesso")
    ap.add_argument("--tls", action="store_true")
    ap.add_argument("--target", type=str, default="localhost:7474")
    args = ap.parse_args()

    client = HeraclitusClient(args.target, tls=args.tls)
    rows = client.query_auditada(args.gql, autor=args.autor, motivo=args.motivo)
    logging.info(f"Acesso de '{args.autor}' registado no log (trilha LGPD).")
    print(json.dumps(rows, indent=2, ensure_ascii=False))
