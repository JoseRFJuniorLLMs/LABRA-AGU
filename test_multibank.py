"""
Teste e2e: VÁRIOS BANCOS + DOCUMENTO em simultâneo, com correlação cruzada.

Prova a pergunta-chave: o agente trabalha com bancos e documentos ao mesmo
tempo? A triangulação é deliberadamente PARTIDA por três fontes distintas:

  - Banco JUNTA (SQL):     a venda de quotas (devedor -> offshore)
  - Banco CARTÓRIO (SQL):  a procuração (offshore -> laranja)
  - Documento (ficheiro):  o vínculo familiar (devedor ~ laranja)

Nenhuma fonte, sozinha, contém a fraude. Só o grafo de caso consolidado —
alimentado pelo pipeline multi-fonte e investigado pelo daemon — fecha a
triangulação CRÍTICA. A proveniência do insight aponta para as TRÊS fontes.
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

# CPF real (dígitos válidos) para exercitar a resolução de entidades: o
# banco grava com pontuação, o documento sem — têm de virar o MESMO nó.
DEVEDOR_PONT = "CPF_529.982.247-25"
DEVEDOR_NUM = "52998224725"
OFFSHORE = "CNPJ_11.222.333/0001-81"
LARANJA = "CPF_BENEFICIARIO_07"

DOC_FAMILIAR = f"""
Relatório de vínculos (COAF): apurou-se que {LARANJA} é cunhado do devedor
{DEVEDOR_NUM}, configurando interposição de pessoa.
"""


def step(n, msg):
    print(f"[{n}] {msg}")


def _mk_bank(path, table, cols, rows):
    con = sqlite3.connect(path)
    con.execute(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, {cols})")
    placeholders = ",".join("?" * (len(rows[0])))
    names = ",".join(c.split()[0] for c in cols.split(","))
    con.executemany(f"INSERT INTO {table} ({names}) VALUES ({placeholders})", rows)
    con.commit()
    con.close()


def main() -> int:
    if not server_bin():
        print("SKIP: heraclitus-server não encontrado (defina HERACLITUS_SERVER_BIN)")
        return 0

    with temp_server() as target:
        client = HeraclitusClient(target)
        tmp = tempfile.mkdtemp(prefix="labra_multi_")
        pipeline.STATE_PATH = os.path.join(tmp, "state.json")
        step(0, f"servidor fresco em {target}")

        # Banco 1 — JUNTA COMERCIAL: a venda de quotas (com pontuação no CPF).
        junta = os.path.join(tmp, "junta.db")
        _mk_bank(junta, "alteracoes", "socio TEXT, destino TEXT, data TEXT",
                 [(DEVEDOR_PONT, OFFSHORE, "2026-06-01")])

        # Banco 2 — CARTÓRIO: a procuração com plenos poderes.
        cartorio = os.path.join(tmp, "cartorio.db")
        _mk_bank(cartorio, "procuracoes", "outorgante TEXT, procurador TEXT, data TEXT",
                 [(OFFSHORE, LARANJA, "2026-06-03")])
        step(1, "dois bancos legados distintos (JUNTA + CARTÓRIO)")

        # Documento — o vínculo familiar (CPF sem pontuação: mesma pessoa).
        watch = os.path.join(tmp, "entrada")
        os.makedirs(watch)
        with open(os.path.join(watch, "vinculos.txt"), "w", encoding="utf-8") as f:
            f.write(DOC_FAMILIAR)
        step(2, "documento de vínculos (pasta vigiada)")

        # Daemon vivo
        daemon = AgentDaemon(target)
        t = threading.Thread(target=daemon.run, daemon=True)
        t.start()
        time.sleep(1.0)
        step(3, "agente daemon subscrito ao rio")

        # Pipeline MULTI-FONTE: os dois bancos + a pasta, num só comando.
        sources = [
            {"type": "sql", "db": f"sqlite:///{junta}", "table": "alteracoes",
             "incremental": "id",
             "template": "{socio} transferiu quotas da empresa para a offshore {destino} em {data}"},
            {"type": "sql", "db": f"sqlite:///{cartorio}", "table": "procuracoes",
             "incremental": "id",
             "template": "A {outorgante} nomeou {procurador} com plenos poderes em {data}"},
            {"type": "files", "watch_dir": watch},
        ]
        ingerido = pipeline.run_sources(client, sources, interval=0, once=True)
        assert ingerido == 3, f"esperava 3 itens ingeridos (2 bancos + 1 doc), veio {ingerido}"
        step(4, f"pipeline ingeriu de 3 fontes simultâneas ({ingerido} itens)")

        # O daemon tem de FECHAR a triangulação cruzando as três fontes.
        deadline = time.time() + 25
        tri = None
        while time.time() < deadline:
            rows = client.query(
                'MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n ORDER BY n.lsn DESC')
            for r in rows:
                if "INSIGHT_PERICIAL_FRAUDE" not in r.get("kind", ""):
                    continue
                p = json.loads(r["content"])
                if p["tipo_fraude"] == "triangulacao_offshore":
                    tri = r
                    break
            if tri:
                break
            time.sleep(0.5)
        assert tri, "triangulação cruzando bancos + documento NÃO foi detectada"
        payload = json.loads(tri["content"])
        step(5, f"triangulação detectada (severidade {payload['severidade']}) "
                "cruzando os três fontes")

        # Resolução de entidades: o CPF com e sem pontuação virou UM só nó,
        # senão a triangulação nunca fecharia entre o banco e o documento.
        assert "CPF:52998224725" in payload["envolvidos"], payload["envolvidos"]
        assert payload["severidade"] == "CRITICA", "vínculo familiar deve elevar a CRÍTICA"

        # Proveniência COMPOSTA: aponta para os 3 eventos-fonte distintos.
        prov = client.provenance(tri["id"])
        all_rows = {r["id"]: r for r in client.query("MATCH (n) RETURN n")}
        origens = set()
        for ev in prov:
            attrs = all_rows.get(ev, {}).get("attrs", {})
            origens.add(attrs.get("table") or attrs.get("source"))
        step(6, f"proveniência cruza as fontes: {sorted(o for o in origens if o)}")
        assert "alteracoes" in origens and "procuracoes" in origens, origens
        assert "file" in origens, origens

        daemon.stop()
        t.join(timeout=5)
        print("\nMULTI-BANCO + DOCUMENTO -> CORRELAÇÃO CRUZADA: SUCESSO TOTAL")
        return 0


if __name__ == "__main__":
    sys.exit(main())
