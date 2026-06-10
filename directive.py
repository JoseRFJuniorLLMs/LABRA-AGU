"""
Envia uma DIRETRIZ ao agente daemon — através do log, nunca por canal
lateral. A ordem vira evento imutável; o agente subscrito reage.

Exemplos:
  py directive.py --alvo CPF_645.254.302-49 --foco "transferencias para offshores"
  py directive.py --alvo CNPJ_OFFSHORE_01 --padrao fracionamento --padrao vespera_constricao --boost 8
"""
import argparse
import logging

from agent.client import HeraclitusClient
from agent.patterns import PATTERNS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Diretriz da Procuradoria para o agente LABRA")
    ap.add_argument("--alvo", action="append", default=[], help="CPF/CNPJ alvo (repetível)")
    ap.add_argument("--foco", type=str, default="", help="Descrição livre do foco investigativo")
    ap.add_argument("--padrao", action="append", default=[],
                    choices=sorted(PATTERNS), help="Restringir a padrões específicos (repetível)")
    ap.add_argument("--boost", type=int, default=5, help="Peso ACT-R dos alvos (default 5)")
    ap.add_argument("--autor", type=str, default="procuradoria", help="Identificação de quem ordena")
    ap.add_argument("--target", type=str, default="localhost:7474")
    args = ap.parse_args()

    client = HeraclitusClient(args.target)
    lsn = client.append_directive(args.alvo, args.foco, args.padrao, args.boost, args.autor)
    ulid = client.resolve_event_id(lsn)
    logging.info(f"DIRETRIZ registada no log: LSN={lsn} ULID={ulid}")
    logging.info("O agente daemon (se ativo) aplicará o boost e o foco imediatamente.")
