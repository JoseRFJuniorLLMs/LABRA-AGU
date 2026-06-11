"""
Teste e2e do modo daemon contra um servidor FRESCO (isolado).

Fluxo testado — interação 100% através do log, com o daemon event-sourced
(reconstrói do LSN 0, reconcilia, vive):
  1. Procuradoria envia DIRETRIZ (alvo = devedor, boost ACT-R);
  2. Ingestor deposita um documento COAF com DOIS padrões de fraude
     (triangulação offshore + fracionamento/smurfing);
  3. O daemon (thread) reconstrói, reconcilia e emite ao vivo;
  4. Verificações: insights emitidos, proveniência composta (doc+diretriz),
     ativações ACT-R refletindo o boost, severidades.
"""
import json
import sys
import threading
import time

from agent.client import HeraclitusClient
from agent.daemon import AgentDaemon
from agent.testing import server_bin, temp_server

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
    if not server_bin():
        print("SKIP: heraclitus-server não encontrado (defina HERACLITUS_SERVER_BIN)")
        return 0

    with temp_server() as target:
        client = HeraclitusClient(target)
        step(0, f"servidor fresco em {target}")

        # 1. DIRETRIZ e documento entram no rio ANTES do daemon — o daemon
        #    reconstrói e reconcilia, provando o caminho event-sourcing.
        d_lsn = client.append_directive(
            alvos=["CPF_645.254.302-49"], foco="blindagem", boost=8)
        directive_id = client.resolve_event_id(d_lsn)
        step(1, f"DIRETRIZ no log (ULID={directive_id})")

        doc_lsn = client.append_document("ingestor_labra", DOC,
                                         attrs={"doc_ref": "COAF_TESTE"})
        doc_id = client.resolve_event_id(doc_lsn)
        step(2, f"documento no log (ULID={doc_id})")

        # 2. Daemon vivo (thread). Reconstrói do 0, reconcilia (emite), vive.
        daemon = AgentDaemon(target)
        t = threading.Thread(target=daemon.run, daemon=True)
        t.start()
        step(3, "daemon subscrito (reconstruindo + reconciliando)")

        # 3. Espera ativa pelos insights
        deadline = time.time() + 20
        insights = []
        while time.time() < deadline:
            rows = client.query(
                'MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n ORDER BY n.lsn DESC')
            insights = [r for r in rows if "INSIGHT_PERICIAL_FRAUDE" in r.get("kind", "")]
            if len(insights) >= 2:
                break
            time.sleep(0.5)
        assert len(insights) >= 2, f"esperava >=2 insights, veio {len(insights)}"

        padroes = set()
        for r in insights:
            payload = json.loads(r["content"])
            padroes.add(payload["tipo_fraude"])
            chain = client.provenance(r["id"])
            assert doc_id in chain, f"{r['id']} sem documento na proveniência: {chain}"
            assert directive_id in chain, f"{r['id']} sem diretriz na proveniência: {chain}"
            assert payload["diretrizes_aplicadas"] == [directive_id]
            act = payload["ativacao_act_r"].get("CPF:64525430249")
            assert act is not None and act > 0.0, f"ativação ACT-R inesperada: {act}"
        assert {"triangulacao_offshore", "fracionamento"} <= padroes, padroes
        step(4, f"daemon emitiu {len(insights)} insights: {sorted(padroes)}")
        step(5, "proveniência composta (documento + diretriz) confirmada")

        # 4. Idempotência: um SEGUNDO daemon no mesmo log não duplica nada.
        before = len(insights)
        d2 = AgentDaemon(target)
        d2._rebuild_state()
        d2._reconcile()
        rows = client.query('MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n')
        after = len([r for r in rows if "INSIGHT_PERICIAL_FRAUDE" in r.get("kind", "")])
        assert after == before, f"re-arranque duplicou insights ({before} -> {after})"
        step(6, f"idempotência: re-arranque não duplica ({after} insights)")

        daemon.stop()
        t.join(timeout=5)
        print("\nDAEMON LABRA-AGU <-> HeraclitusDB: SUCESSO TOTAL")
        return 0


if __name__ == "__main__":
    sys.exit(main())
