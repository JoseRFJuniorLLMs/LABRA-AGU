import json
import logging
import argparse
from agent.parser import parse_document
from agent.investigator import Investigator
from agent.client import HeraclitusClient
from agent.reader import extract_text_from_file

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')


def run_agent(file_path: str = None, target: str = "localhost:7474",
              tls: bool = False, use_llm: bool = False):
    logging.info("Iniciando Agente Pericial e Investigativo (LABRA-AGU)")

    try:
        client = HeraclitusClient(target, tls=tls)
    except Exception as e:
        logging.error(f"Erro ao inicializar gRPC client: {e}")
        return

    investigator = Investigator()
    if use_llm:
        from agent.llm_parser import parse_document_llm as _parse
    else:
        _parse = parse_document

    if file_path:
        logging.info(f"Extraindo texto do arquivo: {file_path}")
        document_text = extract_text_from_file(file_path)
        if not document_text:
            logging.error("Nenhum texto extraído do arquivo.")
            return
        doc_ref = file_path
    else:
        # Modo simulação local, caso não haja arquivo
        document_text = """
        Relatório COAF / Junta Comercial:
        O devedor CPF_645.254.302-49 transferiu quotas da empresa mãe para uma offshore
        CNPJ_OFFSHORE_01, que por sua vez nomeou o cunhado do devedor CPF_CUNHADO_001 como
        administrador com plenos poderes financeiros no dia 02/06/2026.
        """
        doc_ref = "CONTRATO_JUNTA_504"

    # 0. Cadeia de custódia: o documento-fonte vira evento imutável no log
    #    ANTES da análise. O insight apontará para o ULID real deste evento.
    source_event_id = None
    try:
        doc_lsn = client.append_document(
            "agente_pericial_labra_v1", document_text, attrs={"doc_ref": doc_ref}
        )
        source_event_id = client.resolve_event_id(doc_lsn)
        logging.info(f"Documento-fonte no log: LSN={doc_lsn} ULID={source_event_id}")
    except Exception as e:
        logging.warning(f"HeraclitusDB indisponível para custódia ({e}); modo offline.")

    logging.info("Processando documento desestruturado...")

    # 1. Parsing (Diretriz I) — source_event_id é o ULID REAL do log
    parsed_doc = _parse(document_text, source_event_id=source_event_id or doc_ref)

    # 2 e 3. Investigação e ACT-R (Diretrizes II e III) — catálogo completo
    insights = investigator.process_document(parsed_doc)

    if insights:
        for insight in insights:
            logging.info(
                f"ALERTA [{insight['payload']['severidade']}]: "
                f"{insight['payload']['tipo_fraude']}"
            )
            logging.info(f"Conclusão: {insight['payload']['conclusao_juridica']}")

            # 4. Gravação no Banco (Diretriz IV)
            try:
                lsn = client.append_insight(insight)
                insight_id = client.resolve_event_id(lsn)
                chain = client.provenance(insight_id)
                logging.info(f"Insight pericial salvo. LSN={lsn} ULID={insight_id}")
                logging.info(f"Cadeia de custódia (PROVENANCE): {chain}")
            except Exception as e:
                logging.warning(f"Não foi possível persistir no HeraclitusDB via gRPC (Servidor inativo?): {e}")
                logging.info("Payload gerado:")
                print(json.dumps(insight, indent=2, ensure_ascii=False))
    else:
        logging.info("Nenhuma anomalia detectada no documento.")


def run_daemon(target: str, tls: bool = False, use_llm: bool = False):
    """Modo contínuo: o agente vive subscrito ao log. Interação via
    `py directive.py` (ordens) e `py ingest.py` (documentos)."""
    from agent.daemon import AgentDaemon

    daemon = AgentDaemon(target, client=HeraclitusClient(target, tls=tls),
                         use_llm=use_llm)
    try:
        daemon.run()
    except KeyboardInterrupt:
        daemon.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente Investigativo LABRA-AGU")
    parser.add_argument("--file", type=str, help="Caminho do arquivo para processamento one-shot (PDF, DOCX, TXT, ZIP, MP3, MP4)", default=None)
    parser.add_argument("--daemon", action="store_true", help="Modo contínuo: subscreve o log e reage a documentos e DIRETRIZes")
    parser.add_argument("--target", type=str, help="Endereço gRPC do HeraclitusDB", default="localhost:7474")
    parser.add_argument("--tls", action="store_true", help="Conexão gRPC com TLS (produção)")
    parser.add_argument("--llm", action="store_true", help="Usar parser por LLM (requer ANTHROPIC_API_KEY); fallback determinístico")
    args = parser.parse_args()

    if args.daemon:
        run_daemon(args.target, tls=args.tls, use_llm=args.llm)
    else:
        run_agent(args.file, args.target, tls=args.tls, use_llm=args.llm)
