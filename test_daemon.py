"""
Teste e2e do modo daemon (requer heraclitus-server em localhost:7474).

Fluxo testado — interação 100% através do log:
  1. Daemon arranca subscrito ao rio (thread);
  2. Procuradoria envia DIRETRIZ (alvo = devedor, boost ACT-R);
  3. Ingestor deposita um documento COAF com DOIS padrões de fraude
     (triangulação offshore + fracionamento/smurfing);
  4. O daemon deteta os dois e grava insights com proveniência composta:
     parents = [ULID do documento, ULID da diretriz];
  5. Verificações: PROVENANCE, ativações ACT-R reais, severidades.
"""
import json
import sys
import threading
import time
import uuid

from agent.client import HeraclitusClient, is_ulid
from agent.daemon import AgentDaemon

TARGET = "localhost:7474"

DOC = """
Relatório COAF / Junta Comercial:
O devedor CPF_645.254.302-49 transferiu quotas da empresa mãe para uma offshore
CNPJ_OFFSHORE_01, que por sua vez nomeou o cunhado do devedor CPF_CUNHADO_001 como
administrador com plenos poderes financeiros no dia 02/06/2026.
Extrato bancário: CPF_645.254.302-49 transferiu R$ 9.500,00 para CNPJ_FACHADA_02 em 01/06/2026.
Extrato bancário: CPF_645.254.302-49 transferiu R$ 9.800,00 para CNPJ_FACHADA_02 em 02/06/2026.
Extrato bancário: CPF_645.254.302-49 transferiu R$ 9.700,00 para CNPJ_FACHADA_02 em 03/06/2026.
"""


def step(n, msg):
    print(f"[{n}] {msg}")


def main() -> int:
    client = HeraclitusClient(TARGET)
    try:
        head = client.snapshot()
    except Exception as e:
        print(f"FALHA: HeraclitusDB não acessível em {TARGET}: {e}")
        return 1
    step(0, f"conectado (head={head})")

    # 1. Daemon vivo (checkpoint isolado por execução do teste)
    state = f"agent_state_test_{uuid.uuid4().hex[:8]}.json"
    daemon = AgentDaemon(TARGET, state_path=state)
    daemon._save_checkpoint(head - 1 if head > 0 else -1)  # começa do head atual
    t = threading.Thread(target=daemon.run, daemon=True)
    t.start()
    time.sleep(1.0)
    step(1, "daemon subscrito ao log")

    # 2. DIRETRIZ via log
    d_lsn = client.append_directive(
        alvos=["CPF_645.254.302-49"],
        foco="blindagem patrimonial e fracionamento",
        boost=8,
    )
    directive_id = client.resolve_event_id(d_lsn)
    assert is_ulid(directive_id)
    step(2, f"DIRETRIZ enviada (ULID={directive_id})")

    # 3. Documento via ingestão
    doc_lsn = client.append_document("ingestor_labra", DOC, attrs={"doc_ref": "COAF_TESTE_DAEMON"})
    doc_id = client.resolve_event_id(doc_lsn)
    step(3, f"documento ingerido (ULID={doc_id})")

    # 4. Espera ativa pelos insights do daemon
    deadline = time.time() + 15
    insights = []
    while time.time() < deadline:
        rows = client.query(
            'MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n ORDER BY n.lsn DESC'
        )
        insights = [
            r for r in rows
            if "INSIGHT_PERICIAL_FRAUDE" in r.get("kind", "") and r["lsn"] > doc_lsn
        ]
        if len(insights) >= 2:
            break
        time.sleep(0.5)
    assert len(insights) >= 2, f"esperava >=2 insights do daemon, veio {len(insights)}"
    padroes = set()
    for r in insights:
        payload = json.loads(r["content"])
        padroes.add(payload["tipo_fraude"])
        # Proveniência composta: documento + diretriz
        chain = client.provenance(r["id"])
        assert doc_id in chain, f"insight {r['id']} sem o documento na proveniência: {chain}"
        assert directive_id in chain, f"insight {r['id']} sem a diretriz na proveniência: {chain}"
        # ACT-R real: ativação do devedor deve refletir o boost da diretriz
        act = payload["ativacao_act_r"].get("CPF_645.254.302-49")
        assert act is not None and act > 0.0, f"ativação ACT-R inesperada: {act}"
        assert payload["diretrizes_aplicadas"] == [directive_id]
    assert {"triangulacao_offshore", "fracionamento"} <= padroes, padroes
    step(4, f"daemon emitiu {len(insights)} insights: {sorted(padroes)}")
    step(5, "proveniência composta confirmada (documento + diretriz) em todos")

    daemon.stop()
    t.join(timeout=5)
    step(6, f"daemon parado limpo ({daemon.processed} eventos, {daemon.insights_emitted} insights)")

    print("\nDAEMON LABRA-AGU <-> HeraclitusDB: SUCESSO TOTAL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
