"""
DEMO LABRA-AGU — um comando, a história inteira.

Sobe um HeraclitusDB limpo (ou usa o serviço com --live), gera o cenário de
fraude multi-fonte, emite uma DIRETRIZ da Procuradoria (ACT-R), ingere os
quatro fontes pelo pipeline e mostra o agente FECHAR as fraudes ao vivo —
com a proveniência criptográfica de cada alerta.

Uso:
  python demo/run.py                 # servidor limpo próprio (determinístico)
  python demo/run.py --live          # contra o serviço Windows em 127.0.0.1:7474
  python demo/run.py --target host:porta
"""
import argparse
import json
import os
import sys
import threading
import time

# Saída em UTF-8 (acentos e símbolos) sem depender da code page do terminal.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pipeline
from agent.client import HeraclitusClient
from agent.daemon import AgentDaemon
from agent.testing import temp_server, server_bin

from gerar_cenario import construir  # noqa: E402  (após o sys.path)

SEV_ICON = {"CRITICA": "[CRÍTICA]", "ALTA": "[ALTA]",
            "MEDIA": "[MÉDIA]", "BAIXA": "[BAIXA]"}


def _sqlite_url(path: str) -> str:
    # sqlalchemy quer barras normais; em Windows vira sqlite:///C:/...
    return "sqlite:///" + os.path.abspath(path).replace(os.sep, "/")


def banner(txt):
    print("\n" + "=" * 72 + f"\n  {txt}\n" + "=" * 72)


def run(target: str):
    here = os.path.dirname(os.path.abspath(__file__))
    client = HeraclitusClient(target)

    banner("1 · CENÁRIO — blindagem patrimonial fictícia, 4 fontes distintas")
    ids, paths = construir(base_dir=here)
    print(f"  Devedor   : {ids['devedor_fmt']}  (cru: {ids['devedor']})")
    print(f"  Laranja   : {ids['laranja']}  (cunhado do devedor)")
    print(f"  Offshore  : {ids['offshore_fmt']}")
    print("  Fontes    : junta.db · cartorio.db · coaf.db · entrada/vinculos.txt")

    banner("2 · DIRETRIZ DA PROCURADORIA — boost de atenção ACT-R no alvo")
    lsn_dir = client.append_directive(
        [f"CPF_{ids['devedor']}"], "offshores e dissipação patrimonial",
        [], 10, "procuradoria")
    print(f"  DIRETRIZ gravada no log imutável (LSN={lsn_dir}); boost=10 no devedor.")

    banner("3 · AGENTE VIVO — daemon subscrito ao rio (event sourcing)")
    daemon = AgentDaemon(target)
    t = threading.Thread(target=daemon.run, daemon=True)
    t.start()
    time.sleep(1.0)
    print("  Daemon reconstruiu o estado do log e está à escuta.")

    banner("4 · INGESTÃO MULTI-FONTE — 3 bancos SQL + 1 documento, num comando")
    sources = [
        {"type": "sql", "db": _sqlite_url(paths["junta"]), "table": "alteracoes",
         "incremental": "id",
         "template": "{socio} transferiu quotas da empresa para a offshore {destino} em {data}"},
        {"type": "sql", "db": _sqlite_url(paths["cartorio"]), "table": "procuracoes",
         "incremental": "id",
         "template": "A {outorgante} nomeou {procurador} com plenos poderes em {data}"},
        {"type": "sql", "db": _sqlite_url(paths["coaf"]), "table": "movimentacoes",
         "incremental": "id",
         "template": "{origem} transferiu R$ {valor} para {destino} em {data}"},
        {"type": "files", "watch_dir": paths["entrada"]},
    ]
    # estado de pipeline isolado para a demo (idempotência por fonte)
    pipeline.STATE_PATH = os.path.join(paths["data"], "pipeline_state.json")
    if os.path.exists(pipeline.STATE_PATH):
        os.remove(pipeline.STATE_PATH)
    n = pipeline.run_sources(client, sources, interval=0, once=True)
    print(f"  {n} itens ingeridos de 4 fontes. O agente vai correlacionar tudo.")

    banner("5 · O AGENTE FECHA AS FRAUDES — correlação cruzada + proveniência")
    alvo_canon = f"CPF:{ids['devedor']}"
    achados = {}
    deadline = time.time() + 25
    while time.time() < deadline:
        rows = client.query(
            'MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n')
        for r in rows:
            if "INSIGHT_PERICIAL_FRAUDE" not in r.get("kind", ""):
                continue
            p = json.loads(r["content"])
            achados[p["tipo_fraude"]] = (r["id"], p)
        if len(achados) >= 4:
            break
        time.sleep(0.5)

    if not achados:
        print("  ⚠ Nenhum insight ainda — verifique se o servidor está de pé.")
        daemon.stop(); t.join(timeout=5)
        return 1

    all_rows = {r["id"]: r for r in client.query("MATCH (n) RETURN n")}
    ordem = ["triangulacao_offshore", "vespera_constricao",
             "fracionamento", "laranja_familiar"]
    for nome in ordem + [k for k in achados if k not in ordem]:
        if nome not in achados:
            continue
        ev_id, p = achados[nome]
        sev = p.get("severidade", "?")
        print(f"\n  {SEV_ICON.get(sev, sev)} {nome.upper()}")
        print(f"     {p.get('descricao','').strip()}")
        # proveniência: de que fontes vem a prova deste alerta
        prov = client.provenance(ev_id)
        fontes = []
        for e in prov:
            row = all_rows.get(e, {})
            a = row.get("attrs", {})
            label = a.get("table") or a.get("source")
            if not label:
                label = "diretriz" if "DIRETRIZ" in row.get("kind", "") else "?"
            fontes.append(label)
        print(f"     ↳ proveniência (ULIDs reais): {len(prov)} evento(s) "
              f"de {sorted(set(fontes))}")

    banner("RESUMO")
    crit = [k for k, (_, p) in achados.items() if p.get("severidade") == "CRITICA"]
    print(f"  {len(achados)} fraudes detectadas; {len(crit)} CRÍTICAS: {', '.join(crit)}")
    print("  Cada alerta aponta criptograficamente (ULID) para os documentos-fonte.")
    print("  O CPF formatado da Junta e o cru do COAF/documento colapsaram num só nó.")
    print(f"  Tudo vive no log imutável do HeraclitusDB — auditável, AS OF qualquer ponto.")

    # ── Resultado VISUAL: relatório HTML auto-contido (abre no browser) ──
    alerts_view = []
    for nome in ordem + [k for k in achados if k not in ordem]:
        if nome not in achados:
            continue
        ev_id, p = achados[nome]
        prov = client.provenance(ev_id)
        fontes = []
        for e in prov:
            row = all_rows.get(e, {})
            a = row.get("attrs", {})
            label = a.get("table") or a.get("source")
            if not label:
                label = "diretriz" if "DIRETRIZ" in row.get("kind", "") else "log"
            fontes.append(label)
        alerts_view.append({
            "tipo": nome, "sev": p.get("severidade", "?"),
            "descricao": p.get("descricao", "").strip(),
            "conclusao": p.get("conclusao_juridica", ""),
            "fontes": sorted(set(fontes)), "n_prov": len(prov),
        })
    eventos = [
        {"data": "12/05/2026", "titulo": "Venda de quotas à offshore (Junta)", "tipo": "danger"},
        {"data": "13/05/2026", "titulo": "Procuração com plenos poderes ao cunhado (Cartório)", "tipo": "danger"},
        {"data": "14–16/05/2026", "titulo": "3 transferências fracionadas < R$ 10.000 (COAF)", "tipo": "warn"},
        {"data": "05/06/2026", "titulo": "Ordem de bloqueio judicial (penhora) prevista", "tipo": "danger"},
        {"data": "hoje", "titulo": "DIRETRIZ da Procuradoria + agente fecha as fraudes", "tipo": "info"},
    ]
    out_html = os.path.join(paths["data"], "relatorio_demo.html")
    try:
        import report_html
        import webbrowser
        full = report_html.gerar(ids, alerts_view, eventos, out_html)
        print(f"\n  📊 Relatório visual gerado: {full}")
        webbrowser.open(f"file:///{full.replace(os.sep, '/')}")
        print("  (aberto no browser)")
    except Exception as e:
        print(f"\n  (relatório HTML não gerado: {e})")

    daemon.stop()
    t.join(timeout=5)
    return 0


def main():
    ap = argparse.ArgumentParser(description="Demo LABRA-AGU (um comando)")
    ap.add_argument("--live", action="store_true",
                    help="usar o serviço Windows em 127.0.0.1:7474")
    ap.add_argument("--target", default=None, help="endereço host:porta")
    args = ap.parse_args()

    if args.target:
        return run(args.target)
    if args.live:
        return run("127.0.0.1:7474")
    # padrão: servidor limpo e isolado (determinístico, à prova de nervoso)
    if not server_bin():
        print("heraclitus-server não encontrado. Defina HERACLITUS_SERVER_BIN "
              "ou use --live com o serviço a correr.")
        return 1
    with temp_server() as target:
        return run(target)


if __name__ == "__main__":
    sys.exit(main())
