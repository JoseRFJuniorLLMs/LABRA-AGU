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


def run_teoria(target: str, devedor: str = None, tls: bool = False,
               out: str = None):
    """Sintetiza a TEORIA DO CASO a partir do log (Fase 2): corre os 10
    módulos sobre o estado atual e imprime a narrativa, a matriz de evidências
    e a minuta jurídica (com citação por ULID). `devedor` opcional — sem ele,
    escolhe o alvo principal."""
    from agent.entities import normalize_id
    from agent.theory_builder import TheoryBuilder

    client = HeraclitusClient(target, tls=tls)
    alvo = normalize_id(devedor) if devedor else None
    theory = TheoryBuilder(client).build(alvo)
    if theory is None:
        logging.info("Nenhuma fraude rastreável no log — sem teoria do caso. "
                     "(O daemon/pipeline já ingeriu documentos?)")
        return

    print("\n" + "=" * 72)
    print(f"  TEORIA DO CASO — {theory.devedor_nome}  ({theory.devedor})")
    print("=" * 72)
    print(f"\n{theory.narrativa}\n")
    print("--- Matriz de evidências (ordenada por força probatória) ---")
    for a in theory.matriz_evidencias:
        print(f"  [{a['severidade']:>7}] {a['pattern']:<22} "
              f"força {a['evidence_score']:.2f}  "
              f"({len(a['source_events'])} prova/s)")
    print(f"\nAnomalias indutivas: {len(theory.anomalias)}"
          + (f" (top: {theory.anomalias[0]['kind']})" if theory.anomalias else ""))
    rec = theory.reincidencia.get("atores_reincidentes") or {}
    if rec:
        print(f"Atores reincidentes (outros casos): {', '.join(rec)}")
    if theory.provas_essenciais:
        print(f"Provas essenciais (ULID): {', '.join(theory.provas_essenciais)}")

    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(theory.minuta)
        logging.info(f"Minuta gravada em {out}")
    else:
        print("\n" + "=" * 72 + "\n  MINUTA\n" + "=" * 72 + "\n")
        print(theory.minuta)


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
    parser.add_argument("--teoria", nargs="?", const="", default=None,
                        help="Gera a Teoria do Caso (minuta) a partir do log. Opcional: CPF/CNPJ do devedor; sem valor, escolhe o alvo principal")
    parser.add_argument("--out", type=str, default=None, help="Grava a minuta da Teoria do Caso num ficheiro .md")
    parser.add_argument("--target", type=str, help="Endereço gRPC do HeraclitusDB", default="localhost:7474")
    parser.add_argument("--tls", action="store_true", help="Conexão gRPC com TLS (produção)")
    parser.add_argument("--llm", action="store_true", help="Usar parser por LLM (requer ANTHROPIC_API_KEY); fallback determinístico")
    args = parser.parse_args()

    if args.teoria is not None:
        run_teoria(args.target, args.teoria or None, tls=args.tls, out=args.out)
    elif args.daemon:
        run_daemon(args.target, tls=args.tls, use_llm=args.llm)
    else:
        run_agent(args.file, args.target, tls=args.tls, use_llm=args.llm)
