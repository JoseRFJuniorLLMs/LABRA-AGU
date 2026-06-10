"""
Pipeline de Ingestão Universal — os "sentidos" do sistema LABRA.

Liga QUALQUER banco da AGU (Oracle, SQL Server, Postgres, MySQL, SQLite —
qualquer dialeto SQLAlchemy) e/ou uma pasta de depósito de ficheiros
(PDF, DOCX, CSV, TXT, ZIP, MP3, MP4) ao HeraclitusDB. Cada lote vira um
evento imutável no log; o agente daemon (main.py --daemon) faz a análise.

Separação de papéis: o pipeline INGERE (sem opinião), o agente INVESTIGA
(sem tocar nas fontes). Os dois conversam apenas através do rio.

Exemplos:
  # Sincronização incremental de uma tabela (qualquer banco):
  py pipeline.py --db "oracle+oracledb://user:pw@host/svc" \
      --table movimentacoes --incremental id \
      --template "{origem} transferiu R$ {valor} para {destino} em {data}"

  # Pasta vigiada (novos PDFs/áudios/vídeos entram no rio sozinhos):
  py pipeline.py --watch-dir ./entrada

  # Os dois juntos, em loop contínuo a cada 30s:
  py pipeline.py --db "sqlite:///agu.db" --table movs --incremental id \
      --watch-dir ./entrada --interval 30

  # Uma única passagem (cron/teste):
  py pipeline.py --db ... --table ... --incremental id --once
"""
import argparse
import hashlib
import json
import logging
import os
import time
from datetime import date, datetime

from agent.client import HeraclitusClient
from agent.reader import extract_text_from_file

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

STATE_PATH = "pipeline_state.json"


# ── estado (checkpoints idempotentes por fonte) ────────────────────────
def load_state() -> dict:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"sql": {}, "files": {}}


def save_state(state: dict):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


# ── formatação canónica (o parser do agente entende pt-BR) ────────────
def fmt(value):
    """Números viram moeda pt-BR; datas viram dd/mm/aaaa; resto, str."""
    if isinstance(value, float) or isinstance(value, int) and not isinstance(value, bool):
        s = f"{float(value):,.2f}"
        return s.replace(",", "@").replace(".", ",").replace("@", ".")
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, str):
        try:  # datas ISO vindas do banco
            return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
        except ValueError:
            return value
    return str(value)


def render_row(row: dict, template: str | None) -> str:
    if template:
        return template.format(**{k: fmt(v) for k, v in row.items()})
    # Sem template: linha legível e auditável (o parser pode não reagir,
    # mas o dado fica no rio com fidelidade total).
    return "; ".join(f"{k}={fmt(v)}" for k, v in row.items())


# ── conector SQL universal ─────────────────────────────────────────────
def sync_sql(client: HeraclitusClient, state: dict, db_url: str, table: str,
             incremental: str, template: str | None, batch_max: int = 500) -> int:
    try:
        import sqlalchemy
    except ImportError:
        raise SystemExit(
            "instale o conector universal: pip install sqlalchemy "
            "(+ driver do seu banco: oracledb, pyodbc, psycopg2, pymysql...)"
        )

    key = f"{db_url}::{table}"
    last = state["sql"].get(key)

    engine = sqlalchemy.create_engine(db_url)
    with engine.connect() as conn:
        col = sqlalchemy.column(incremental)
        tbl = sqlalchemy.table(table, col)
        q = sqlalchemy.select(sqlalchemy.text("*")).select_from(tbl).order_by(col)
        if last is not None:
            q = q.where(col > last)
        q = q.limit(batch_max)
        rows = [dict(r._mapping) for r in conn.execute(q)]

    if not rows:
        return 0

    # Um LOTE = um documento (padrões como fracionamento precisam de ver
    # as transações juntas, como num relatório COAF).
    lines = [render_row(r, template) for r in rows]
    body = (
        f"Extração automática — tabela {table} ({len(rows)} registros novos):\n"
        + "\n".join(f"Registro: {ln}." for ln in lines)
    )
    hi = max(r[incremental] for r in rows)
    lo = min(r[incremental] for r in rows)
    lsn = client.append_document(
        "pipeline_labra_sql",
        body,
        attrs={
            "source": "sql",
            "table": table,
            "incremental_col": incremental,
            "range": f"{lo}..{hi}",
            "db": db_url.split("://")[0],  # dialeto apenas; sem credenciais
        },
    )
    state["sql"][key] = hi if not hasattr(hi, "isoformat") else hi.isoformat()
    save_state(state)
    logging.info(f"SQL {table}[{lo}..{hi}] -> log (LSN={lsn}, {len(rows)} registros)")
    return len(rows)


# ── watcher de ficheiros (PDF/DOCX/CSV/TXT/ZIP/MP3/MP4) ───────────────
def sync_files(client: HeraclitusClient, state: dict, watch_dir: str) -> int:
    if not os.path.isdir(watch_dir):
        os.makedirs(watch_dir, exist_ok=True)
        return 0
    ingested = 0
    for name in sorted(os.listdir(watch_dir)):
        path = os.path.join(watch_dir, name)
        if not os.path.isfile(path):
            continue
        digest = _file_digest(path)
        if state["files"].get(digest):
            continue  # já ingerido (idempotente por conteúdo)
        try:
            text = extract_text_from_file(path)
        except Exception as e:
            logging.warning(f"falha ao extrair {name}: {e}")
            continue
        if not text or not text.strip():
            logging.warning(f"{name}: nenhum texto extraído; ignorado")
            state["files"][digest] = f"vazio:{name}"
            save_state(state)
            continue
        lsn = client.append_document(
            "pipeline_labra_files",
            text,
            attrs={"source": "file", "doc_ref": name, "sha256": digest},
        )
        state["files"][digest] = name
        save_state(state)
        ingested += 1
        logging.info(f"FICHEIRO {name} -> log (LSN={lsn}, sha256={digest[:12]}…)")
    return ingested


def _file_digest(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# ── loop principal ────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Pipeline de Ingestão Universal LABRA")
    ap.add_argument("--db", type=str, default=None, help="URL SQLAlchemy do banco-fonte")
    ap.add_argument("--table", type=str, default=None)
    ap.add_argument("--incremental", type=str, default="id",
                    help="Coluna incremental (id, rowversion, updated_at)")
    ap.add_argument("--template", type=str, default=None,
                    help="Frase canónica por linha, ex.: '{origem} transferiu R$ {valor} para {destino} em {data}'")
    ap.add_argument("--watch-dir", type=str, default=None, help="Pasta de depósito de ficheiros")
    ap.add_argument("--interval", type=int, default=30, help="Segundos entre ciclos")
    ap.add_argument("--once", action="store_true", help="Uma passagem e sai (cron)")
    ap.add_argument("--target", type=str, default="localhost:7474")
    args = ap.parse_args()

    if not args.db and not args.watch_dir:
        ap.error("forneça --db (com --table) e/ou --watch-dir")
    if args.db and not args.table:
        ap.error("--db exige --table")

    client = HeraclitusClient(args.target)
    state = load_state()
    logging.info("Pipeline de ingestão ativo. O agente daemon analisará o que entrar no rio.")

    while True:
        total = 0
        if args.db:
            total += sync_sql(client, state, args.db, args.table,
                              args.incremental, args.template)
        if args.watch_dir:
            total += sync_files(client, state, args.watch_dir)
        if args.once:
            logging.info(f"Passagem única concluída ({total} itens).")
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
