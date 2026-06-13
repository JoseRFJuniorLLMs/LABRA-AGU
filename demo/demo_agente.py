"""
DEMO do AGENTE investigativo — investiga um devedor e rascunha a peça.

Mostra o ciclo agêntico de ponta a ponta sobre um caso real (offshore + laranja
+ fracionamento + suborno + antedatação): o agente reúne provas via ferramentas,
regista cada passo (trace auditável) e REDIGE a petição.

Cérebro: Gemma 4 LOCAL (LM Studio/Ollama) se o servidor estiver a correr; senão,
planeador DETERMINÍSTICO (corre offline, sem modelo). 100% em memória — não
precisa de servidor HeraclitusDB.

Uso:
  py demo/demo_agente.py
  (com Gemma:  inicie o LM Studio → Developer → carregue gemma-4-e4b → Start Server)
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent.agent_loop import ForensicAgent  # noqa: E402
from agent.graph import CaseGraph  # noqa: E402
from agent.llm import LocalLLM  # noqa: E402
from agent.parser import parse_document  # noqa: E402

# Um caso rico, partido em "fontes" (frases) como na realidade.
DOCS = [
    "CPF_DEV1 transferiu quotas para CNPJ_OFF1, que nomeou o cunhado CPF_LAR1 com plenos poderes.",
    "CPF_DEV1 transferiu R$ 9.000,00 para CPF_LAR1 em 01/02/2026.",
    "CPF_DEV1 transferiu R$ 9.300,00 para CPF_LAR1 em 02/02/2026.",
    "CPF_DEV1 transferiu R$ 8.700,00 para CPF_LAR1 em 03/02/2026.",
    "CPF_DEV1 pagou propina de R$ 100.000,00 ao agente público CPF_AG1 em 01/03/2026.",
    "Consta penhora em 05/06/2026. "
    "2026-06-10 14:32:11 UPDATE alteracoes registro de CPF_DEV1 "
    "campo=data de=08/06/2026 para=01/05/2026 por=op_junta_47",
]


def main():
    g = CaseGraph()
    for i, d in enumerate(DOCS):
        g.ingest(parse_document(d, f"EV{i}"))
    g.entities["CPF_DEV1"] = "João Ribeiro"

    llm = LocalLLM()
    on = llm.available()
    print("=" * 66)
    print("  AGENTE INVESTIGATIVO LABRA-AGU  ·  cérebro: "
          + ("Gemma 4 LOCAL (LM Studio)" if on else "DETERMINÍSTICO (LM Studio offline)"))
    if not on:
        print("  (para usar o Gemma: LM Studio → Developer → carregue o modelo "
              "→ Start Server em :1234)")
    print("=" * 66)

    agent = ForensicAgent(g, llm=llm)
    r = agent.investigar("CPF_DEV1")

    print("\n  PASSOS DO AGENTE (cadeia de raciocínio auditável):")
    for e in r["trace"]:
        print(f"   {e['passo']}. {e['acao']:<20} → {e['obs']}")

    d = r["dossie"]
    print(f"\n  DOSSIÊ: {len(d['achados'])} fraude(s) · "
          f"{len(d['essenciais'])} prova(s) essencial(is) · "
          f"valor R$ {(d['valor'] or 0):,.2f}")

    print("\n" + "-" * 66 + "\n  PEÇA RASCUNHADA (para revisão do procurador)\n" + "-" * 66)
    print(r["peca"]["texto"])
    print("\n✅ Agente concluiu (motor: " + r["motor"] + ").")
    return 0


if __name__ == "__main__":
    sys.exit(main())
