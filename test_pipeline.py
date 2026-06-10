"""
Teste e2e do Pipeline de Ingestão Universal (requer heraclitus-server
em localhost:7474).

Simula a realidade da AGU:
  1. Um banco SQL legado (SQLite local, mas a URL podia ser Oracle/MSSQL)
     com 3 transferências fracionadas abaixo do limiar COAF;
  2. Uma pasta de depósito com um documento .txt de junta comercial
     (triangulação offshore);
  3. O pipeline sincroniza ambos para o HeraclitusDB (1 lote SQL = 1
     documento; 1 ficheiro = 1 documento), com checkpoints idempotentes;
  4. O agente daemon, subscrito ao rio, deteta as fraudes nas DUAS fontes
     sem saber de onde vieram — e a proveniência diz exatamente de onde.
"""
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import uuid

import pipeline
from agent.client import HeraclitusClient
from agent.daemon import AgentDaemon

TARGET = "localhost:7474"

TRIANGULACAO = """
Junta Comercial — alteração contratual:
O devedor CPF_111.222.333-44 transferiu quotas da empresa para a offshore
CNPJ_BLINDAGEM_09, que por sua vez nomeou a esposa do devedor CPF_ESPOSA_07
como administradora com plenos poderes no dia 05/06/2026.
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

    tmp = tempfile.mkdtemp(prefix="labra_pipe_")
    pipeline.STATE_PATH = os.path.join(tmp, "pipeline_state.json")

    # 1. Banco legado da AGU (qualquer URL SQLAlchemy serviria)
    db_path = os.path.join(tmp, "agu_legado.db")
    con = sqlite3.connect(db_path)
    con.execute("CREATE TABLE movs (id INTEGER PRIMARY KEY, origem TEXT, destino TEXT, valor REAL, data TEXT)")
    con.executemany(
        "INSERT INTO movs (origem, destino, valor, data) VALUES (?, ?, ?, ?)",
        [
            ("CPF_999.888.777-66", "CNPJ_CONCHA_03", 9500.0, "2026-06-01"),
            ("CPF_999.888.777-66", "CNPJ_CONCHA_03", 9800.0, "2026-06-02"),
            ("CPF_999.888.777-66", "CNPJ_CONCHA_03", 9700.0, "2026-06-03"),
        ],
    )
    con.commit()
    con.close()
    step(1, f"banco legado criado ({db_path})")

    # 2. Pasta de depósito com um documento
    watch = os.path.join(tmp, "entrada")
    os.makedirs(watch)
    with open(os.path.join(watch, "alteracao_contratual.txt"), "w", encoding="utf-8") as f:
        f.write(TRIANGULACAO)
    step(2, "pasta de depósito com 1 documento (.txt)")

    # 3. Daemon vivo a partir do head atual
    state_file = os.path.join(tmp, f"agent_state_{uuid.uuid4().hex[:6]}.json")
    daemon = AgentDaemon(TARGET, state_path=state_file)
    daemon._save_checkpoint(head - 1 if head > 0 else -1)
    t = threading.Thread(target=daemon.run, daemon=True)
    t.start()
    time.sleep(1.0)
    step(3, "agente daemon subscrito ao rio")

    # 4. Pipeline: uma passagem (SQL + ficheiros)
    pstate = pipeline.load_state()
    n_sql = pipeline.sync_sql(
        client, pstate, f"sqlite:///{db_path}", "movs", "id",
        template="{origem} transferiu R$ {valor} para {destino} em {data}",
    )
    n_files = pipeline.sync_files(client, pstate, watch)
    assert n_sql == 3 and n_files == 1, (n_sql, n_files)
    step(4, f"pipeline ingeriu {n_sql} registros SQL (1 lote) + {n_files} ficheiro")

    # Idempotência: segunda passagem não duplica nada
    assert pipeline.sync_sql(client, pipeline.load_state(), f"sqlite:///{db_path}",
                             "movs", "id", template="{origem} x {destino}") == 0
    assert pipeline.sync_files(client, pipeline.load_state(), watch) == 0
    step(5, "checkpoints idempotentes: segunda passagem = 0 ingestões")

    # 6. O daemon deve detetar fraudes nas DUAS fontes
    deadline = time.time() + 20
    achados = {}
    while time.time() < deadline:
        rows = client.query(
            'MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n ORDER BY n.lsn DESC'
        )
        achados = {}
        for r in rows:
            if "INSIGHT_PERICIAL_FRAUDE" not in r.get("kind", "") or r["lsn"] <= head:
                continue
            payload = json.loads(r["content"])
            achados[payload["tipo_fraude"]] = r
        if "fracionamento" in achados and "triangulacao_offshore" in achados:
            break
        time.sleep(0.5)
    assert "fracionamento" in achados, f"fracionamento não detetado: {sorted(achados)}"
    assert "triangulacao_offshore" in achados, f"triangulação não detetada: {sorted(achados)}"
    step(6, f"daemon detetou nas duas fontes: {sorted(achados)}")

    # 7. Proveniência aponta para a fonte certa (SQL vs ficheiro)
    fra_parents = client.provenance(achados["fracionamento"]["id"])
    tri_parents = client.provenance(achados["triangulacao_offshore"]["id"])
    by_id = {r["id"]: r for r in client.query(
        'MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n')}
    assert by_id[fra_parents[0]]["attrs"]["source"] == "sql"
    assert by_id[fra_parents[0]]["attrs"]["table"] == "movs"
    assert by_id[tri_parents[0]]["attrs"]["source"] == "file"
    assert "sha256" in by_id[tri_parents[0]]["attrs"]
    step(7, "proveniência distingue as fontes: sql/movs[1..3] e file+sha256")

    daemon.stop()
    t.join(timeout=5)
    step(8, f"daemon parado limpo ({daemon.insights_emitted} insights nesta corrida)")

    print("\nPIPELINE UNIVERSAL -> HERACLITUSDB -> AGENTE: SUCESSO TOTAL")
    return 0


if __name__ == "__main__":
    sys.exit(main())
