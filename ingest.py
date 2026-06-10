"""
Ingestão pura: deposita um documento-fonte no rio (HeraclitusDB) como
evento imutável e termina. A ANÁLISE é trabalho do agente daemon, que
verá o evento chegar pelo Subscribe — separação limpa entre quem ingere
e quem investiga.

  py ingest.py --file extrato_banco_novo.pdf
  py ingest.py --texto "O devedor CPF_X transferiu R$ 9.000,00 ..."
"""
import argparse
import logging

from agent.client import HeraclitusClient
from agent.reader import extract_text_from_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ingestão de documento no HeraclitusDB")
    ap.add_argument("--file", type=str, default=None, help="PDF, DOCX, CSV, TXT, ZIP, MP3, MP4")
    ap.add_argument("--texto", type=str, default=None, help="Texto direto (alternativa a --file)")
    ap.add_argument("--ref", type=str, default="", help="Referência documental humana (nº processo etc.)")
    ap.add_argument("--target", type=str, default="localhost:7474")
    args = ap.parse_args()

    if not args.file and not args.texto:
        ap.error("forneça --file ou --texto")

    text = args.texto or extract_text_from_file(args.file)
    if not text or not text.strip():
        raise SystemExit("nenhum texto extraído")

    client = HeraclitusClient(args.target)
    lsn = client.append_document(
        "ingestor_labra", text, attrs={"doc_ref": args.ref or (args.file or "texto_direto")}
    )
    ulid = client.resolve_event_id(lsn)
    logging.info(f"Documento no log: LSN={lsn} ULID={ulid}")
    logging.info("O agente daemon analisará este evento automaticamente.")
