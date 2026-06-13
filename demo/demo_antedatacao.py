"""
DEMO — cruzar BANCO + LOG DE MUDANÇAS (CDC) para achar antedatação.

Mostra o ponto que o estado atual do banco esconde: uma venda de quotas que
PARECE anterior à penhora (logo, legítima), mas cujo histórico de alterações
(o change-log / trilha de auditoria do sistema registral) revela ter sido
ANTEDATADA — a data foi editada DEPOIS da penhora para forjar anterioridade.

Duas fontes, e a fraude só aparece no CRUZAMENTO:
  • BANCO  (junta.db, SQL)         → a venda de quotas, hoje datada 01/05/2026.
  • LOG    (audit_junta.log, CDC)  → UPDATE em 10/06/2026: data 08/06→01/05;
                                      DELETE em 12/06/2026 (sumiço de prova);
                                      e a própria ordem de penhora (05/06/2026).

É 100% isolado: sobe um HeraclitusDB TEMPORÁRIO e usa um diretório temporário
— não mexe em demo_data/ nem no banco de produção. Uma cópia legível do log
fake fica em demo/exemplo_audit_junta.log para você abrir e inspecionar.

Uso:
  py demo/demo_antedatacao.py
"""
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)
sys.path.insert(0, _HERE)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pipeline  # noqa: E402
from agent.client import HeraclitusClient  # noqa: E402
from agent.daemon import AgentDaemon  # noqa: E402
from agent.testing import server_bin, temp_server  # noqa: E402
from gerar_cenario import (fmt_cnpj, fmt_cpf, gerar_cnpj_valido,  # noqa: E402
                           gerar_cpf_valido)
import random  # noqa: E402


def _log_fake(dev_fmt: str) -> str:
    """O change-log fake (CDC). Formato estruturado: uma linha por operação."""
    return (
        "# ============================================================\n"
        "# TRILHA DE AUDITORIA (CDC) — Sistema Registral / Junta Comercial\n"
        "# Export do change-log: NAO e o estado atual das tabelas, e o\n"
        "# HISTORICO de operacoes (quem mudou o que, e quando).\n"
        "# ============================================================\n"
        f"2026-05-02 09:12:44 INSERT alteracoes registro de {dev_fmt} "
        "campo=venda_quotas por=op_junta_03\n"
        f"Consta ordem de penhora em 05/06/2026 sobre os bens do executado "
        f"{dev_fmt}.\n"
        f"2026-06-10 14:32:11 UPDATE alteracoes registro de {dev_fmt} "
        "campo=data de=08/06/2026 para=01/05/2026 por=op_junta_47\n"
        f"2026-06-12 09:15:02 DELETE coaf registro de {dev_fmt} "
        "campo=movimentacao por=op_coaf_12\n"
    )


def banner(msg):
    print("\n" + "=" * 64 + f"\n  {msg}\n" + "=" * 64)


def main() -> int:
    if not server_bin():
        print("SKIP: heraclitus-server não encontrado (defina HERACLITUS_SERVER_BIN)")
        return 0

    rng = random.Random(7)
    dev = gerar_cpf_valido(rng)
    off = gerar_cnpj_valido(rng)
    dev_fmt = fmt_cpf(dev)

    tmp = tempfile.mkdtemp(prefix="labra_antedata_")
    watch = os.path.join(tmp, "entrada")
    os.makedirs(watch)

    # 1. BANCO (SQL) — a venda de quotas, hoje datada 01/05/2026 (parece limpa:
    #    35 dias ANTES da penhora, fora até da janela de véspera).
    junta = os.path.join(tmp, "junta.db")
    con = sqlite3.connect(junta)
    con.execute("CREATE TABLE alteracoes (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "socio TEXT, destino TEXT, data TEXT, cotas INTEGER)")
    con.execute("INSERT INTO alteracoes (socio, destino, data, cotas) "
                "VALUES (?,?,?,?)", (dev_fmt, fmt_cnpj(off), "2026-05-01", 95000))
    con.commit()
    con.close()

    # 2. LOG (CDC) — o change-log fake. Cópia visível em demo/ para inspeção.
    log_txt = _log_fake(dev_fmt)
    with open(os.path.join(watch, "audit_junta.log"), "w", encoding="utf-8") as f:
        f.write(log_txt)
    visivel = os.path.join(_HERE, "exemplo_audit_junta.log")
    with open(visivel, "w", encoding="utf-8") as f:
        f.write(log_txt)

    banner("CENÁRIO — banco diz uma coisa, o log conta a verdade")
    print(f"  Devedor (executado) : {dev_fmt}")
    print(f"  Offshore            : {fmt_cnpj(off)}")
    print("  BANCO junta.db      : venda de quotas datada 01/05/2026 (parece limpa)")
    print("  LOG  audit_junta.log: UPDATE 10/06 (data 08/06→01/05) + DELETE 12/06")
    print("  Penhora             : 05/06/2026  (do próprio log)")
    print(f"  Cópia do log fake   : {visivel}")

    with temp_server() as target:
        client = HeraclitusClient(target)
        pipeline.STATE_PATH = os.path.join(tmp, "pipeline_state.json")

        daemon = AgentDaemon(target)
        t = threading.Thread(target=daemon.run, daemon=True)
        t.start()
        time.sleep(1.0)

        banner("INGESTÃO — 1 banco SQL + 1 arquivo de log, num comando")
        sources = [
            {"type": "sql", "db": "sqlite:///" + junta.replace(os.sep, "/"),
             "table": "alteracoes", "incremental": "id",
             "template": "{socio} transferiu quotas da empresa para a offshore "
                         "{destino} em {data}"},
            {"type": "files", "watch_dir": watch},
        ]
        n = pipeline.run_sources(client, sources, interval=0, once=True)
        print(f"  {n} itens ingeridos (banco + log).")

        # espera o daemon consumir tudo
        deadline = time.time() + 40
        while time.time() < deadline:
            if daemon.metrics.get("processed_lsn", 0) >= client.snapshot():
                break
            time.sleep(0.2)
        time.sleep(0.5)

        banner("O AGENTE FECHA — fraude que SÓ o cruzamento revela")
        rows = [r for r in client.query(
            'MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n')
            if "INSIGHT_PERICIAL_FRAUDE" in r.get("kind", "")]
        all_rows = {r["id"]: r for r in client.query("MATCH (n) RETURN n")}
        achados = {}
        for r in rows:
            p = json.loads(r["content"])
            achados[p["tipo_fraude"]] = (r, p)

        for tp in ("antedatacao", "registro_apagado"):
            if tp not in achados:
                print(f"  ⚠ {tp} NÃO detectado.")
                continue
            r, p = achados[tp]
            # proveniência: de quais FONTES vieram os eventos que sustentam
            fontes = set()
            for ev in client.provenance(r["id"]):
                a = all_rows.get(ev, {}).get("attrs", {})
                fontes.add(a.get("table") or a.get("source") or "log")
            print(f"\n  ● [{p['severidade']}] {tp.upper()}")
            print(f"    {p['descricao']}")
            print(f"    └ fontes cruzadas: {sorted(fontes)}  "
                  f"({len(client.provenance(r['id']))} eventos por ULID)")

        daemon.stop()
        t.join(timeout=5)

    ok = "antedatacao" in achados and "registro_apagado" in achados
    print("\n" + ("✅ SUCESSO: banco + log cruzados → antedatação e DELETE achados."
                  if ok else "❌ Algo falhou — ver acima."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
