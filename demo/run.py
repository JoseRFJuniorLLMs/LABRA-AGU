"""
DEMO LABRA-AGU — um comando, a história inteira.

Sobe um HeraclitusDB limpo (ou usa o serviço com --live), gera o cenário de
fraude multi-fonte, emite uma DIRETRIZ da Procuradoria (ACT-R), ingere as
fontes pelo pipeline e mostra o agente FECHAR as fraudes — com a proveniência
criptográfica de cada alerta. No fim, gera e abre um painel único interativo.

Uso:
  python demo/run.py                 # servidor limpo próprio (determinístico)
  python demo/run.py --keep          # NÃO regenera; usa os casos já em demo_data
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

_SEVRANK = {"CRITICA": 2, "ALTA": 1, "MEDIA": 0, "BAIXA": -1}
_ORDEM = ["triangulacao_offshore", "vespera_constricao",
          "fracionamento", "laranja_familiar"]


def _sqlite_url(path: str) -> str:
    return "sqlite:///" + os.path.abspath(path).replace(os.sep, "/")


def _paths(here):
    data = os.path.join(here, "demo_data")
    return {"data": data, "entrada": os.path.join(data, "entrada"),
            "junta": os.path.join(data, "junta.db"),
            "cartorio": os.path.join(data, "cartorio.db"),
            "coaf": os.path.join(data, "coaf.db")}


def _fmt_id(canon):
    """CPF:digits -> 000.000.000-00 ; CNPJ:digits -> 00.000.000/0000-00."""
    if canon.startswith("CPF:"):
        d = canon[4:]
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}" if len(d) == 11 else d
    if canon.startswith("CNPJ:"):
        d = canon[5:]
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else d
    return canon


def banner(txt):
    print("\n" + "=" * 72 + f"\n  {txt}\n" + "=" * 72)


def _steps_for(tipos):
    """A linha do tempo (6 passos) de um caso, com as severidades reais."""
    def crit(tp):
        return tp in tipos and tipos[tp][1].get("severidade") == "CRITICA"
    N = ["n_dev", "n_off", "n_lar"]
    return [
        {"lsn": 0, "date": "início", "label": "log vazio — nenhum evento ainda",
         "nodes": [], "edges": [], "chips": []},
        {"lsn": 1, "date": "12/05/2026", "label": "Venda de quotas à offshore (Junta)",
         "nodes": ["n_dev", "n_off"], "edges": ["e_venda"], "chips": []},
        {"lsn": 2, "date": "13/05/2026", "label": "Procuração com plenos poderes (Cartório)",
         "nodes": N, "edges": ["e_venda", "e_proc"],
         "chips": [["Triangulação offshore", False]]},
        {"lsn": 3, "date": "14–16/05/2026", "label": "3 transferências fracionadas (COAF)",
         "nodes": N, "edges": ["e_venda", "e_proc", "e_frac"],
         "chips": [["Triangulação offshore", False],
                   ["Fracionamento", crit("fracionamento")]]},
        {"lsn": 4, "date": "documento", "label": "Vínculo familiar: laranja é cunhado do devedor",
         "nodes": N, "edges": ["e_venda", "e_proc", "e_frac", "e_fam"],
         "chips": [["Triangulação offshore", crit("triangulacao_offshore")],
                   ["Fracionamento", crit("fracionamento")],
                   ["Laranja familiar", crit("laranja_familiar")]]},
        {"lsn": 5, "date": "05/06/2026", "label": "Ordem de bloqueio judicial (penhora) prevista",
         "nodes": N, "edges": ["e_venda", "e_proc", "e_frac", "e_fam"],
         "chips": [["Triangulação offshore", crit("triangulacao_offshore")],
                   ["Fracionamento", crit("fracionamento")],
                   ["Laranja familiar", crit("laranja_familiar")],
                   ["Véspera de constrição", crit("vespera_constricao")]]},
    ]


def run(target, keep=False):
    here = os.path.dirname(os.path.abspath(__file__))
    client = HeraclitusClient(target)
    paths = _paths(here)

    banner("1 · CENÁRIO — blindagem patrimonial fictícia, fontes multi-origem")
    if keep and os.path.exists(paths["junta"]):
        print("  Modo --keep: a usar os casos já existentes em demo_data/")
    else:
        ids, _ = construir(base_dir=here)
        print(f"  Caso base gerado · devedor {ids['devedor_fmt']} · laranja {ids['laranja']}")
    print("  Fontes: junta.db · cartorio.db · coaf.db · entrada/*.txt")

    banner("2 · DIRETRIZ DA PROCURADORIA — boost de atenção ACT-R")
    lsn_dir = client.append_directive(
        [], "offshores e dissipação patrimonial", [], 10, "procuradoria")
    print(f"  DIRETRIZ no log imutável (LSN={lsn_dir}); foco em offshores.")

    banner("3 · AGENTE VIVO — daemon subscrito ao rio (event sourcing)")
    daemon = AgentDaemon(target)
    t = threading.Thread(target=daemon.run, daemon=True)
    t.start()
    time.sleep(1.0)
    print("  Daemon reconstruiu o estado do log e está à escuta.")

    banner("4 · INGESTÃO MULTI-FONTE — bancos SQL + documentos, num comando")
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
    pipeline.STATE_PATH = os.path.join(paths["data"], "pipeline_state.json")
    if os.path.exists(pipeline.STATE_PATH):
        os.remove(pipeline.STATE_PATH)
    n = pipeline.run_sources(client, sources, interval=0, once=True)
    print(f"  {n} itens ingeridos. O agente vai correlacionar tudo.")

    banner("5 · O AGENTE FECHA AS FRAUDES — por caso, com proveniência")
    # Poll até o número de insights estabilizar.
    seen, stable, rows = -1, 0, []
    deadline = time.time() + 25
    while time.time() < deadline:
        rows = [r for r in client.query(
            'MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n')
            if "INSIGHT_PERICIAL_FRAUDE" in r.get("kind", "")]
        if len(rows) == seen:
            stable += 1
        else:
            stable, seen = 0, len(rows)
        if stable >= 3 and seen > 0:
            break
        time.sleep(0.5)
    if not rows:
        print("  ⚠ Nenhum insight — verifique o servidor.")
        daemon.stop(); t.join(timeout=5)
        return 1

    all_rows = {r["id"]: r for r in client.query("MATCH (n) RETURN n")}

    # Agrupa por caso (devedor_alvo); por tipo, guarda o insight MAIS severo.
    cases_map = {}
    for r in rows:
        p = json.loads(r["content"])
        dev, tp = p.get("devedor_alvo", "?"), p["tipo_fraude"]
        cur = cases_map.setdefault(dev, {}).get(tp)
        if cur is None or _SEVRANK.get(p.get("severidade"), 0) > _SEVRANK.get(cur[1].get("severidade"), 0):
            cases_map[dev][tp] = (r["id"], p)

    def fontes_de(ev_id):
        prov = client.provenance(ev_id)
        labs = []
        for e in prov:
            row = all_rows.get(e, {})
            a = row.get("attrs", {})
            lab = a.get("table") or a.get("source")
            if not lab:
                lab = "diretriz" if "DIRETRIZ" in row.get("kind", "") else "log"
            labs.append(lab)
        return sorted(set(labs)), len(prov)

    cases = []
    for dev in sorted(cases_map):
        tipos = cases_map[dev]
        env = tipos.get("triangulacao_offshore", (None, {}))[1].get("envolvidos", [])
        dev_l = _fmt_id(env[0]) if len(env) > 0 else _fmt_id(dev)
        off_l = _fmt_id(env[1]) if len(env) > 1 else "—"
        lar_l = _fmt_id(env[2]) if len(env) > 2 else "—"
        alerts = []
        for tp in _ORDEM:
            if tp not in tipos:
                continue
            ev_id, p = tipos[tp]
            fontes, nprov = fontes_de(ev_id)
            alerts.append({"tipo": tp, "sev": p.get("severidade", "?"),
                           "descricao": p.get("descricao", "").strip(),
                           "conclusao": p.get("conclusao_juridica", ""),
                           "fontes": fontes, "n_prov": nprov})
        cases.append({"dev": dev_l, "off": off_l, "lar": lar_l,
                      "alerts": alerts, "steps": _steps_for(tipos)})
        print(f"  Caso · devedor {dev_l}: {len(alerts)} fraude(s) "
              f"[{', '.join(a['tipo'] for a in alerts)}]")

    total_fraudes = sum(len(c["alerts"]) for c in cases)
    total_crit = sum(1 for c in cases for a in c["alerts"] if a["sev"] == "CRITICA")
    totals = {"cases": len(cases), "fraudes": total_fraudes, "criticas": total_crit}

    banner("RESUMO")
    print(f"  {len(cases)} caso(s) · {total_fraudes} fraude(s) · {total_crit} CRÍTICA(s)")
    print("  Cada alerta aponta por ULID aos documentos-fonte; CPF formatado e cru = 1 nó.")
    print("  Tudo vive no log imutável do HeraclitusDB — auditável, AS OF qualquer ponto.")

    out_html = os.path.join(paths["data"], "painel_demo.html")
    try:
        import report_html
        import webbrowser
        full = report_html.gerar(cases, totals, out_html)
        print(f"\n  📊 Painel único gerado: {full}")
        webbrowser.open(f"file:///{full.replace(os.sep, '/')}")
        print("  (aberto no browser — selecione o caso e arraste a barra de tempo)")
    except Exception as e:
        print(f"\n  (painel HTML não gerado: {e})")

    daemon.stop()
    t.join(timeout=5)
    return 0


def main():
    ap = argparse.ArgumentParser(description="Demo LABRA-AGU (um comando)")
    ap.add_argument("--live", action="store_true",
                    help="usar o serviço Windows em 127.0.0.1:7474")
    ap.add_argument("--target", default=None, help="endereço host:porta")
    ap.add_argument("--keep", action="store_true",
                    help="não regenerar; usar os casos já em demo_data (inclui adicionar_caso)")
    args = ap.parse_args()

    if args.target:
        return run(args.target, keep=args.keep)
    if args.live:
        return run("127.0.0.1:7474", keep=args.keep)
    if not server_bin():
        print("heraclitus-server não encontrado. Defina HERACLITUS_SERVER_BIN "
              "ou use --live com o serviço a correr.")
        return 1
    with temp_server() as target:
        return run(target, keep=args.keep)


if __name__ == "__main__":
    sys.exit(main())
