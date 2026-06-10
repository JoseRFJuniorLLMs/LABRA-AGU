import time
import json
import logging
import argparse
from agent.parser import parse_document
from agent.investigator import Investigator
from agent.client import HeraclitusClient
from agent.reader import extract_text_from_file

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def run_agent(file_path: str = None):
    logging.info("Iniciando Agente Pericial e Investigativo (LABRA-AGU)")
    
    try:
        client = HeraclitusClient('localhost:7474')
    except Exception as e:
        logging.error(f"Erro ao inicializar gRPC client: {e}")
        return

    investigator = Investigator()

    logging.info("Agente conectado. Aguardando eventos do HeraclitusDB...")

    if file_path:
        logging.info(f"Extraindo texto do arquivo: {file_path}")
        document_text = extract_text_from_file(file_path)
        if not document_text:
            logging.error("Nenhum texto extraído do arquivo.")
            return
    else:
        # Modo simulação local, caso não haja arquivo
        document_text = """
        Relatório COAF / Junta Comercial:
        O devedor CPF_645.254.302-49 transferiu quotas da empresa mãe para uma offshore 
        CNPJ_OFFSHORE_01, que por sua vez nomeou o cunhado do devedor CPF_CUNHADO_001 como 
        administrador com plenos poderes financeiros no dia 02/06/2026.
        """
    
    logging.info("Processando documento desestruturado...")
    
    # 1. Parsing (Diretriz I)
    parsed_doc = parse_document(document_text, source_event_id="01JX_CONTRATO_JUNTA_504")
    
    # 2 e 3. Investigação e ACT-R (Diretrizes II e III)
    insight = investigator.process_document(parsed_doc)
    
    if insight:
        logging.info(f"ALERTA FRAUDE DETECTADA: {insight['payload']['tipo_fraude']}")
        logging.info(f"Conclusão: {insight['payload']['conclusao_juridica']}")
        
        # 4. Gravação no Banco (Diretriz IV)
        try:
            lsn = client.append_insight(insight)
            logging.info(f"Insight pericial salvo no HeraclitusDB com sucesso. LSN: {lsn}")
        except Exception as e:
            logging.warning(f"Não foi possível persistir no HeraclitusDB via gRPC (Servidor inativo?): {e}")
            logging.info("Payload gerado:")
            print(json.dumps(insight, indent=2, ensure_ascii=False))
    else:
        logging.info("Nenhuma anomalia detectada no documento.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agente Investigativo LABRA-AGU")
    parser.add_argument("--file", type=str, help="Caminho do arquivo para processamento (PDF, DOCX, TXT, ZIP, MP3, MP4)", default=None)
    args = parser.parse_args()
    
    run_agent(args.file)
