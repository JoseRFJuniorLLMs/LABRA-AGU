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
import html as _html
import json
import os
import re
import sqlite3
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
from nomes import nome_de  # noqa: E402
from agent.entities import normalize_id  # noqa: E402
from agent.theory_builder import TheoryBuilder  # noqa: E402
from agent.graph_timeline import GraphTimeline  # noqa: E402

_EDGE_BASE = {"PROCURADOR_COM_PODERES": "procurador", "FAMILIAR": "cunhado",
              "DOACAO": "doou bem", "ADMINISTRA": "usufruto/admin",
              "CONTROLA": "controla", "DESVIO_INSS": "desvio INSS"}


def _br(dt):
    return f"{dt[8:10]}/{dt[5:7]}" if dt and len(dt) >= 10 else (dt or "")


def _subgraph(g, devedor, cotas_map):
    """Subgrafo do caso (componente conexo do devedor): nós + arestas reais +
    a linha do tempo (uma marca por documento/ULID, em ordem)."""
    from collections import defaultdict as _dd
    eds = []
    for rt, lst in g.relations.items():
        for r in lst:
            ev = min(r["events"]) if r["events"] else ""
            eds.append([r["src"], r["dst"], rt, r.get("value"), r.get("date"), ev])
    for t in g.transactions:
        ev = min(t["events"]) if t["events"] else ""
        eds.append([t["src"], t["dst"], "TRANSFERENCIA", t.get("value"), t.get("date"), ev])
    adj = _dd(set)
    for s, d, *_ in eds:
        adj[s].add(d); adj[d].add(s)
    comp, stack = set(), [devedor]
    while stack:
        n = stack.pop()
        if n in comp:
            continue
        comp.add(n); stack.extend(adj[n] - comp)
    eds = [e for e in eds if e[0] in comp and e[1] in comp]
    ulids = sorted({e[5] for e in eds if e[5]})
    ti = {u: i for i, u in enumerate(ulids)}
    nodes = [{"id": c, "label": nome_de(c) or g.entities.get(c, c),
              "id_fmt": _fmt_id(c), "kind": g.entity_kind.get(c, "")}
             for c in comp]
    edges = []
    for s, d, rt, val, dt, ev in eds:
        if rt == "VENDEDOR_QUOTAS":
            ct = cotas_map.get(s)
            lab = (f"vendeu {ct:,}".replace(",", ".") + " cotas") if ct else "vendeu quotas"
        elif rt == "TRANSFERENCIA":
            lab = ("R$ " + f"{val:,.0f}".replace(",", ".")) if val else "transferiu"
        else:
            lab = _EDGE_BASE.get(rt, rt.lower())
        if dt:  # acrescenta a data ao rótulo onde a relação a tem
            lab = lab + " · " + _br(dt)
        edges.append({"src": s, "dst": d, "kind": rt, "label": lab, "t": ti.get(ev, 0)})
    from collections import Counter as _Counter
    _FRASE = {"VENDEDOR_QUOTAS": "venda de quotas à offshore",
              "PROCURADOR_COM_PODERES": "procuração com plenos poderes ao laranja",
              "FAMILIAR": "vínculo familiar (cunhado)",
              "DOACAO": "doação a interposta pessoa",
              "ADMINISTRA": "usufruto / administração vitalícia",
              "CONTROLA": "controle em cascata",
              "DESVIO_INSS": "desvio de benefícios do INSS"}
    ticks = []
    for u in ulids:
        kinds = {e[2] for e in eds if e[5] == u}
        cnt = _Counter(e[2] for e in eds if e[5] == u)
        dt = next((e[4] for e in eds if e[5] == u and e[4]), "")
        lab = ("Venda de quotas" if "VENDEDOR_QUOTAS" in kinds else
               "Procuração" if "PROCURADOR_COM_PODERES" in kinds else
               "Fracionamento" if "TRANSFERENCIA" in kinds else "Documento (vínculos)")
        fr = []
        if cnt.get("TRANSFERENCIA"):
            fr.append(f"{cnt['TRANSFERENCIA']} transferências fracionadas")
        for k in ("VENDEDOR_QUOTAS", "PROCURADOR_COM_PODERES", "FAMILIAR",
                  "DOACAO", "ADMINISTRA", "CONTROLA"):
            if cnt.get(k):
                fr.append(_FRASE[k])
        ticks.append({"label": lab, "date": _br(dt),
                      "resumo": "; ".join(fr) if fr else lab})
    return nodes, edges, ticks


def _md_to_html(md: str) -> str:
    """Conversor Markdown→HTML mínimo (a minuta tem estrutura conhecida)."""
    def inline(s):
        s = _html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        s = re.sub(r"\*(.+?)\*", r"<i>\1</i>", s)
        return s
    out, in_list = [], False

    def close():
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False
    for ln in md.split("\n"):
        t = ln.strip()
        if not t:
            close()
            continue
        if t.startswith("### "):
            close(); out.append(f"<h5>{inline(t[4:])}</h5>")
        elif t.startswith("## "):
            close(); out.append(f"<h4>{inline(t[3:])}</h4>")
        elif t.startswith("# "):
            close(); out.append(f"<h3>{inline(t[2:])}</h3>")
        elif t.startswith("- "):
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append(f"<li>{inline(t[2:])}</li>")
        elif t.startswith("> "):
            close(); out.append(f"<blockquote>{inline(t[2:])}</blockquote>")
        else:
            close(); out.append(f"<p>{inline(t)}</p>")
    close()
    return "\n".join(out)

_SEVRANK = {"CRITICA": 2, "ALTA": 1, "MEDIA": 0, "BAIXA": -1}
_ORDEM = ["triangulacao_offshore", "vespera_constricao",
          "fracionamento", "laranja_familiar",
          "offshore_cascata", "doacao_cruzada", "holding_usufruto",
          "fraude_inss"]


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
        {"lsn": 0, "date": "início", "ev": "log vazio",
         "label": "log vazio — nenhum evento ainda",
         "nodes": [], "edges": [], "chips": []},
        {"lsn": 1, "date": "12/05/2026", "ev": "Venda de quotas",
         "label": "Venda de quotas à offshore (Junta Comercial)",
         "nodes": ["n_dev", "n_off"], "edges": ["e_venda"], "chips": []},
        {"lsn": 2, "date": "13/05/2026", "ev": "Procuração",
         "label": "Procuração com plenos poderes ao laranja (Cartório)",
         "nodes": N, "edges": ["e_venda", "e_proc"],
         "chips": [["Triangulação offshore", False]]},
        {"lsn": 3, "date": "14–16/05/2026", "ev": "Fracionamento",
         "label": "3 transferências fracionadas abaixo do limiar (COAF)",
         "nodes": N, "edges": ["e_venda", "e_proc", "e_frac"],
         "chips": [["Triangulação offshore", False],
                   ["Fracionamento", crit("fracionamento")]]},
        {"lsn": 4, "date": "documento", "ev": "Vínculo familiar",
         "label": "Vínculo familiar: laranja é cunhado do devedor",
         "nodes": N, "edges": ["e_venda", "e_proc", "e_frac", "e_fam"],
         "chips": [["Triangulação offshore", crit("triangulacao_offshore")],
                   ["Fracionamento", crit("fracionamento")],
                   ["Laranja familiar", crit("laranja_familiar")]]},
        {"lsn": 5, "date": "05/06/2026", "ev": "Penhora prevista",
         "label": "Ordem de bloqueio judicial (penhora) prevista",
         "nodes": N, "edges": ["e_venda", "e_proc", "e_frac", "e_fam"],
         "chips": [["Triangulação offshore", crit("triangulacao_offshore")],
                   ["Fracionamento", crit("fracionamento")],
                   ["Laranja familiar", crit("laranja_familiar")],
                   ["Véspera de constrição", crit("vespera_constricao")]]},
    ]


def _fmt_brl(num):
    return "R$ " + f"{num:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _frac_info(alerts):
    """Total fracionado (pt-BR) e nº de transferências, do texto do agente."""
    for a in alerts:
        if a["tipo"] == "fracionamento":
            mv = re.search(r"somando R\$ ([\d.,]+)", a["descricao"])
            mc = re.search(r"realizou (\d+)", a["descricao"])
            count = mc.group(1) if mc else "3"
            if mv:
                try:
                    return _fmt_brl(float(mv.group(1).replace(",", ""))), count
                except ValueError:
                    return "R$ " + mv.group(1), count
    return "—", None


def _cotas_map(junta_path):
    """devedor canónico -> nº de cotas vendidas (lido da Junta)."""
    m = {}
    try:
        con = sqlite3.connect(junta_path)
        try:
            rows = con.execute("SELECT socio, cotas FROM alteracoes").fetchall()
        except sqlite3.OperationalError:
            rows = [(s, None) for (s,) in con.execute("SELECT socio FROM alteracoes")]
        for socio, cotas in rows:
            m[normalize_id(socio)] = cotas
        con.close()
    except Exception:
        pass
    return m


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

    cotas_map = _cotas_map(paths["junta"])
    # CaseGraph reconstruído UMA vez (AS OF agora) — serve o grafo dinâmico do
    # painel e a Teoria do Caso (sem reconstruir duas vezes).
    g_full = None
    try:
        tl = GraphTimeline(client)
        g_full = tl.at_lsn(tl.head())
        teorias = {t.devedor: t for t in TheoryBuilder(client).build_all(graph=g_full)}
    except Exception as e:  # noqa: BLE001 — o painel não depende disto
        print(f"  (teoria do caso indisponível: {e})")
        teorias = {}
    cases = []
    for dev in sorted(cases_map):
        tipos = cases_map[dev]
        env = tipos.get("triangulacao_offshore", (None, {}))[1].get("envolvidos", [])
        dev_c = env[0] if len(env) > 0 else dev
        off_c = env[1] if len(env) > 1 else ""
        lar_c = env[2] if len(env) > 2 else ""
        dev_l, off_l, lar_l = _fmt_id(dev_c), _fmt_id(off_c) if off_c else "—", _fmt_id(lar_c) if lar_c else "—"
        dev_n, off_n, lar_n = nome_de(dev_c), nome_de(off_c), nome_de(lar_c)
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
        valor, count = _frac_info(alerts)
        cotas = cotas_map.get(dev_c)
        lbl_venda = (f"{cotas:,}".replace(",", ".") + " cotas") if cotas else "venda de quotas"
        lbl_frac = (f"{count}× {valor}") if valor != "—" else "fracionamento"
        teo = teorias.get(dev_c)
        minuta_html = _md_to_html(teo.minuta) if teo else ""
        matriz = ([{"tipo": a["pattern"], "sev": a["severidade"],
                    "score": a["evidence_score"]} for a in teo.matriz_evidencias]
                  if teo else [])
        if g_full is not None:
            g_nodes, g_edges, g_ticks = _subgraph(g_full, dev_c, cotas_map)
        else:
            g_nodes, g_edges, g_ticks = [], [], []
        cases.append({"dev": dev_l, "off": off_l, "lar": lar_l,
                      "dev_n": dev_n, "off_n": off_n, "lar_n": lar_n,
                      "valor": valor, "devedor_id": dev_c,
                      "nodes": g_nodes, "edges": g_edges, "ticks": g_ticks,
                      "minuta_html": minuta_html, "matriz": matriz,
                      "alerts": alerts})
        print(f"  Caso · {dev_n} ({dev_l}): {len(alerts)} fraude(s) "
              f"[{', '.join(a['tipo'] for a in alerts)}]")

    # Filtra casos-fragmento (1 alerta, sem triangulação) — são pernas de
    # cascata/doação que ganharam devedor_alvo próprio. Mantém os casos reais
    # (com ficha completa) e evita combos poluídos com entradas "—".
    ricos = [c for c in cases if len(c["alerts"]) >= 2]
    if ricos:
        cases = ricos

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
