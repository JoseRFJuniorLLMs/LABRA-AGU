"""
Teste e2e do Pipeline de Ingestão Universal contra um servidor FRESCO.

Simula a realidade da AGU:
  1. Um banco SQL legado (SQLite, mas a URL podia ser Oracle/MSSQL) com 3
     transferências fracionadas abaixo do limiar COAF;
  2. Uma pasta de depósito com um documento .txt (triangulação offshore);
  3. O pipeline sincroniza ambos para o HeraclitusDB com checkpoints
     idempotentes;
  4. O daemon, subscrito ao rio, deteta as fraudes nas DUAS fontes e a
     proveniência identifica exatamente a origem (sql/tabela vs ficheiro/hash).
"""
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time

import pipeline
from agent.client import HeraclitusClient
from agent.daemon import AgentDaemon
from agent.testing import server_bin, temp_server

TRIANGULACAO = """
Junta Comercial — alteração contratual:
O devedor CPF_111.444.777-35 transferiu quotas da empresa para a offshore
CNPJ_BLINDAGEM_09, que por sua vez nomeou a esposa do devedor CPF_ESPOSA_07
como administradora com plenos poderes no dia 05/06/2026.
"""


def step(n, msg):
    print(f"[{n}] {msg}")


def main() -> int:
    if not server_bin():
        print("SKIP: heraclitus-server não encontrado (defina HERACLITUS_SERVER_BIN)")
        return 0

    with temp_server() as target:
        client = HeraclitusClient(target)
        tmp = tempfile.mkdtemp(prefix="labra_pipe_")
        pipeline.STATE_PATH = os.path.join(tmp, "pipeline_state.json")
        step(0, f"servidor fresco em {target}")

        # 1. Banco legado
        db_path = os.path.join(tmp, "agu.db")
        con = sqlite3.connect(db_path)
        con.execute("CREATE TABLE movs (id INTEGER PRIMARY KEY, origem TEXT, "
                    "destino TEXT, valor REAL, data TEXT)")
        con.executemany(
            "INSERT INTO movs (origem, destino, valor, data) VALUES (?,?,?,?)",
            [("CPF_222.333.444-05", "CNPJ_CONCHA_03", 9500.0, "2026-06-01"),
             ("CPF_222.333.444-05", "CNPJ_CONCHA_03", 9800.0, "2026-06-02"),
             ("CPF_222.333.444-05", "CNPJ_CONCHA_03", 9700.0, "2026-06-03")])
        con.commit()
        con.close()
        step(1, "banco legado SQLite com fracionamento")

        # 2. Pasta de depósito
        watch = os.path.join(tmp, "entrada")
        os.makedirs(watch)
        with open(os.path.join(watch, "alteracao.txt"), "w", encoding="utf-8") as f:
            f.write(TRIANGULACAO)
        step(2, "pasta de depósito com 1 documento")

        # 3. Daemon vivo
        daemon = AgentDaemon(target)
        t = threading.Thread(target=daemon.run, daemon=True)
        t.start()
        time.sleep(1.0)
        step(3, "agente daemon subscrito ao rio")

        # 4. Pipeline: uma passagem (SQL + ficheiros)
        pstate = pipeline.load_state()
        n_sql = pipeline.sync_sql(
            client, pstate, f"sqlite:///{db_path}", "movs", "id",
            template="{origem} transferiu R$ {valor} para {destino} em {data}")
        n_files = pipeline.sync_files(client, pstate, watch)
        assert n_sql == 3 and n_files == 1, (n_sql, n_files)
        step(4, f"pipeline ingeriu {n_sql} registros SQL (1 lote) + {n_files} ficheiro")

        # Idempotência do pipeline
        assert pipeline.sync_sql(client, pipeline.load_state(),
                                 f"sqlite:///{db_path}", "movs", "id",
                                 template="{origem} {destino}") == 0
        assert pipeline.sync_files(client, pipeline.load_state(), watch) == 0
        step(5, "checkpoints idempotentes: segunda passagem = 0")

        # 5. O daemon deteta nas DUAS fontes
        deadline = time.time() + 25
        achados = {}
        while time.time() < deadline:
            rows = client.query(
                'MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n ORDER BY n.lsn DESC')
            achados = {}
            for r in rows:
                if "INSIGHT_PERICIAL_FRAUDE" not in r.get("kind", ""):
                    continue
                achados[json.loads(r["content"])["tipo_fraude"]] = r
            if "fracionamento" in achados and "triangulacao_offshore" in achados:
                break
            time.sleep(0.5)
        assert "fracionamento" in achados, f"fracionamento não detetado: {sorted(achados)}"
        assert "triangulacao_offshore" in achados, f"triangulação não detetada: {sorted(achados)}"
        step(6, f"daemon detetou nas duas fontes: {sorted(achados)}")

        # 6. Proveniência distingue as fontes
        all_rows = {r["id"]: r for r in client.query("MATCH (n) RETURN n")}
        fra_parents = client.provenance(achados["fracionamento"]["id"])
        tri_parents = client.provenance(achados["triangulacao_offshore"]["id"])
        fra_src = all_rows[fra_parents[0]]["attrs"]
        tri_src = all_rows[tri_parents[0]]["attrs"]
        assert fra_src.get("source") == "sql" and fra_src.get("table") == "movs"
        assert tri_src.get("source") == "file" and "sha256" in tri_src
        step(7, "proveniência distingue: sql/movs[1..3] e file+sha256")

        daemon.stop()
        t.join(timeout=5)
        print("\nPIPELINE UNIVERSAL -> HERACLITUSDB -> AGENTE: SUCESSO TOTAL")
        return 0


if __name__ == "__main__":
    sys.exit(main())
