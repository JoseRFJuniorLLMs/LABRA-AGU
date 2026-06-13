"""
orchestrator — ponto de entrada do orquestrador agêntico.

Integra o ForensicAgent (agent_loop.py) com o pipeline completo:

  1. Ingestão: documentos → grafo de caso (via Investigator / parser)
  2. Investigação agêntica: laço ReAct Planear→Agir→Refletir sobre o grafo
  3. Redação: peça com trace auditável, medidas e dispositivos legais

Cérebro: Gemma 4 LOCAL (LM Studio/Ollama/vLLM) ou planeador DETERMINÍSTICO.
LGPD: nada sai da máquina — CPF/sigilo só no servidor local.
Sem LLM disponível: modo offline/CI, 100% determinístico, sem diferença de saída.

Uso direto:
  python -m agent.orchestrator --devedor CPF_123 --texto "Relatório COAF..."
  python -m agent.orchestrator --devedor CPF_123 --arquivo processo.txt --out minuta.md
"""
import argparse
import json
import logging
import os
from typing import Optional

log = logging.getLogger(__name__)


# ── helpers de ingestão ────────────────────────────────────────────────────

def _ingerir_texto(investigator, texto: str, ref: str = "doc_inline") -> str:
    """Faz o parse do texto e ingere no grafo do Investigator. Retorna ref."""
    from .parser import parse_document
    doc = parse_document(texto, source_event_id=ref)
    investigator.ingest_only(doc)
    return ref


def _ingerir_arquivo(investigator, caminho: str, use_llm: bool = False) -> str:
    """Extrai texto do arquivo, (opcionalmente via LLM parser) e ingere."""
    from .reader import extract_text_from_file
    texto = extract_text_from_file(caminho)
    if not texto:
        raise ValueError(f"Nenhum texto extraído de: {caminho}")
    ref = os.path.basename(caminho)
    if use_llm:
        from .llm_parser import parse_document_llm
        from .parser import parse_document
        try:
            doc = parse_document_llm(texto, source_event_id=ref)
        except Exception as e:
            log.warning(f"Parser LLM falhou ({e}); usando determinístico.")
            doc = parse_document(texto, source_event_id=ref)
    else:
        from .parser import parse_document
        doc = parse_document(texto, source_event_id=ref)
    investigator.ingest_only(doc)
    return ref


# ── ponto de entrada principal ─────────────────────────────────────────────

def investigar(
    devedor: str,
    *,
    textos: Optional[list] = None,
    arquivos: Optional[list] = None,
    use_llm_parser: bool = False,
    use_llm_agent: bool = True,
    client=None,
    max_passos: int = 10,
    verbose: bool = False,
) -> dict:
    """
    Orquestra a investigação de ponta a ponta.

    Parâmetros
    ----------
    devedor : str
        CPF/CNPJ normalizado do alvo.
    textos : list[str], opcional
        Textos de documentos a ingerir no grafo antes da investigação.
    arquivos : list[str], opcional
        Caminhos de ficheiros (PDF/DOCX/TXT/…) a ingerir.
    use_llm_parser : bool
        Se True, tenta usar o parser LLM nos ficheiros.
    use_llm_agent : bool
        Se True (padrão), tenta usar Gemma 4 como planeador agêntico.
    client : HeraclitusClient, opcional
        Cliente gRPC para persistência auditável de cada passo no log.
    max_passos : int
        Limite de iterações do laço ReAct (defesa contra loops).
    verbose : bool
        Imprime cada passo do trace no stdout.

    Retorna
    -------
    dict com chaves:
        devedor, motor, trace, dossie, peca
    """
    from .entities import normalize_id
    from .investigator import Investigator
    from .agent_loop import ForensicAgent
    from .llm import LocalLLM

    dev = normalize_id(devedor)

    # 1. Construir grafo a partir dos documentos fornecidos
    investigator = Investigator()
    n_docs = 0
    for txt in (textos or []):
        _ingerir_texto(investigator, txt)
        n_docs += 1
    for arq in (arquivos or []):
        _ingerir_arquivo(investigator, arq, use_llm=use_llm_parser)
        n_docs += 1

    if n_docs == 0:
        log.warning("Nenhum documento ingerido — grafo vazio. "
                    "O agente rodará mas não encontrará padrões.")

    # Garante que o devedor está no grafo (mesmo que sem documentos)
    investigator.graph.entities.setdefault(dev, dev)

    # 2. Preparar o planeador LLM (Gemma 4 local, se disponível e desejado)
    llm = None
    if use_llm_agent:
        llm = LocalLLM()
        if not llm.available():
            log.info("LM Studio não responde → planeador determinístico.")
            llm = None
        else:
            log.info(f"Gemma 4 disponível em {llm.base} — usando como planeador.")

    # 3. Montar e rodar o agente forense
    agent = ForensicAgent(
        graph=investigator.graph,
        client=client,
        llm=llm,
        max_passos=max_passos,
    )
    resultado = agent.investigar(dev)

    # 4. Log do trace para o stdout (modo verbose)
    if verbose:
        _print_trace(resultado, dev)

    return {**resultado, "devedor": dev}


# ── formatação de saída ────────────────────────────────────────────────────

def _print_trace(resultado: dict, dev: str):
    motor = resultado.get("motor", "?")
    peca = resultado.get("peca", {})
    trace = resultado.get("trace", [])
    dossie = resultado.get("dossie", {})

    print()
    print("=" * 72)
    print(f"  INVESTIGACAO AGENTICA -- {dev}  [motor: {motor}]")
    print("=" * 72)
    print()

    print("-- TRACE DE RACIOCINIO " + "-" * 49)
    for passo in trace:
        print(f"  [{passo['passo']:>2}] {passo['acao']:<22}  -> {passo['obs']}")

    print()
    print("-- ACHADOS " + "-" * 61)
    for a in dossie.get("achados", []):
        sev = a.get("severidade", "?")
        pat = a.get("pattern", "?")
        env = ", ".join(a.get("envolvidos", []))
        print(f"  [{sev:>7}] {pat}  —  envolvidos: {env}")

    val = dossie.get("valor")
    if val is not None:
        val_br = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        print(f"\n  Valor estimado a recuperar: R$ {val_br}")

    redes = dossie.get("rede", [])
    if redes:
        print(f"  Facilitadores partilhados: {len(redes)}")

    print()
    print("-- PECA (MINUTA) " + "-" * 55)
    print(peca.get("texto", "(sem texto)"))
    print()
    print("-- DISPOSITIVOS LEGAIS " + "-" * 49)
    for d in peca.get("dispositivos", []):
        print(f"  * {d}")
    print("=" * 72)
    print()


def _json_seguro(obj):
    """Serializa dicts com sets (source_events) para JSON."""
    if isinstance(obj, set):
        return sorted(obj)
    raise TypeError(f"Não serializável: {type(obj)}")


# ── CLI ───────────────────────────────────────────────────────────────────

def _cli():
    p = argparse.ArgumentParser(
        description="Orquestrador agêntico LABRA-AGU — investigação forense completa.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Grafo vazio (apenas analisa com o que o agente extrai do próprio grafo):
  python -m agent.orchestrator --devedor CPF_12345678901

  # Com texto inline:
  python -m agent.orchestrator --devedor CPF_12345678901 \\
      --texto "O devedor transferiu quotas para offshore CNPJ_XYZ01..."

  # Com ficheiro + saída JSON:
  python -m agent.orchestrator --devedor CPF_12345678901 \\
      --arquivo processo.txt --out resultado.json

  # Forçar planeador determinístico (sem LLM, útil em CI):
  python -m agent.orchestrator --devedor CPF_12345678901 --no-llm
""",
    )
    p.add_argument("--devedor", required=True,
                   help="CPF/CNPJ do devedor alvo (ex.: CPF_12345678901)")
    p.add_argument("--texto", action="append", default=[],
                   help="Texto de documento a ingerir (pode repetir)")
    p.add_argument("--arquivo", action="append", default=[],
                   help="Caminho de ficheiro a ingerir (PDF/DOCX/TXT; pode repetir)")
    p.add_argument("--out", default=None,
                   help="Ficheiro de saída (.md ou .json). Omitir → stdout")
    p.add_argument("--no-llm", dest="no_llm", action="store_true",
                   help="Forçar planeador determinístico (não tenta LM Studio)")
    p.add_argument("--llm-parser", dest="llm_parser", action="store_true",
                   help="Usar parser LLM nos ficheiros (requer openai/anthropic SDK)")
    p.add_argument("--max-passos", type=int, default=10,
                   help="Máximo de iterações do laço ReAct (padrão: 10)")
    p.add_argument("--json", dest="fmt_json", action="store_true",
                   help="Saída em JSON (trace completo + peça)")
    p.add_argument("--target", default="localhost:7474",
                   help="Endereço gRPC do HeraclitusDB (padrão: localhost:7474)")
    p.add_argument("--tls", action="store_true",
                   help="Conexão gRPC com TLS")
    p.add_argument("-v", "--verbose", action="store_true",
                   help="Imprime trace detalhado no stdout")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    # cliente gRPC opcional (modo offline se não disponível)
    client = None
    try:
        from agent.client import HeraclitusClient
        client = HeraclitusClient(args.target, tls=args.tls)
    except Exception as e:
        log.warning(f"HeraclitusDB indisponível ({e}); modo offline.")

    resultado = investigar(
        devedor=args.devedor,
        textos=args.texto or None,
        arquivos=args.arquivo or None,
        use_llm_parser=args.llm_parser,
        use_llm_agent=not args.no_llm,
        client=client,
        max_passos=args.max_passos,
        verbose=args.verbose or not args.fmt_json,
    )

    if args.fmt_json:
        saida = json.dumps(resultado, indent=2, ensure_ascii=False,
                           default=_json_seguro)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(saida)
            log.info(f"Resultado JSON gravado em {args.out}")
        else:
            print(saida)
    elif args.out:
        texto_peca = resultado.get("peca", {}).get("texto", "")
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(texto_peca)
        log.info(f"Minuta gravada em {args.out}")


if __name__ == "__main__":
    _cli()
