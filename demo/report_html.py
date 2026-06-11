"""
Relatório visual auto-contido da demo — um único .html (sem dependências,
abre com duplo-clique) gerado a partir da deteção REAL do agente.

Identidade visual institucional (AGU / gov.br): azul-marinho sobre fundo
claro, cartões brancos. Mostra: cartões de alerta por severidade, o mapa de
relações (SVG), o rio de eventos (timeline) e a nota de cadeia de custódia.
"""
import html
import os

# Paleta institucional (gov.br / AGU)
AZUL = "#1351B4"
MARINHO = "#0C326F"
TINTA = "#1B2B40"
MUTED = "#5B6B7B"
BORDA = "#D8E0EA"
FUNDO = "#EEF2F7"
PAINEL = "#F7F9FC"

_SEV = {
    "CRITICA": ("#C0392B", "#FBE9E7", "CRÍTICA"),
    "ALTA": ("#B9770E", "#FCF3E3", "ALTA"),
    "MEDIA": ("#9A7D0A", "#FBF6E3", "MÉDIA"),
    "BAIXA": ("#2E7D32", "#E8F5E9", "BAIXA"),
}


def _esc(s):
    return html.escape(str(s))


def _node(cx, cy, titulo, sub, cor):
    return (
        f'<g>'
        f'<circle cx="{cx}" cy="{cy}" r="46" fill="#FFFFFF" stroke="{cor}" stroke-width="2.5"/>'
        f'<text x="{cx}" y="{cy-4}" text-anchor="middle" fill="{TINTA}" '
        f'font-size="13" font-weight="700">{_esc(titulo)}</text>'
        f'<text x="{cx}" y="{cy+14}" text-anchor="middle" fill="{MUTED}" '
        f'font-size="10">{_esc(sub)}</text>'
        f'</g>'
    )


def _edge(x1, y1, x2, y2, label, cor, texto, dy=-8):
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2 + dy
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{cor}" '
        f'stroke-width="2" marker-end="url(#arrow)"/>'
        f'<rect x="{mx-92}" y="{my-13}" width="184" height="20" rx="6" '
        f'fill="#FFFFFF" stroke="{cor}" stroke-width="1"/>'
        f'<text x="{mx}" y="{my+1}" text-anchor="middle" fill="{texto}" '
        f'font-size="10.5" font-weight="600">{_esc(label)}</text>'
    )


def _grafo_svg(ids):
    dev = (150, 200)
    off = (650, 95)
    lar = (650, 305)
    parts = [
        '<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="9" '
        'refY="3" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L9,3 L0,6 Z" fill="#94A3B8"/></marker></defs>',
        _edge(*dev, *off, "vendeu quotas · 12/05", "#C0392B", "#9B271B", dy=-14),
        _edge(*off, *lar, "procurador c/ plenos poderes · 13/05", "#C0392B", "#9B271B", dy=-14),
        _edge(*dev, *lar, "cunhado (familiar) + 3× fracionado", "#B9770E", "#8A5908", dy=40),
        _node(*dev, "DEVEDOR", "João Ribeiro", "#C0392B"),
        _node(*off, "OFFSHORE", "Atlantic Holdings", AZUL),
        _node(*lar, "LARANJA", "Carlos (cunhado)", "#B9770E"),
    ]
    return (f'<svg viewBox="0 0 800 400" width="100%" '
            f'style="max-width:840px">{"".join(parts)}</svg>')


def _card(a):
    cor, tint, rotulo = _SEV.get(a["sev"], ("#5B6B7B", "#EEF2F7", a["sev"]))
    fontes = " · ".join(_esc(f) for f in a["fontes"])
    return f"""
    <div class="card" style="border-left:4px solid {cor}">
      <div class="card-top">
        <span class="badge" style="background:{tint};color:{cor};border:1px solid {cor}">{rotulo}</span>
        <span class="tipo">{_esc(a['tipo'].replace('_',' ').upper())}</span>
      </div>
      <p class="desc">{_esc(a['descricao'])}</p>
      <p class="conc">{_esc(a.get('conclusao',''))}</p>
      <div class="prov">&#8627; proveniência: <b>{a['n_prov']}</b> evento(s) imutável(is) — {fontes}</div>
    </div>"""


def _timeline(eventos):
    out = []
    for e in eventos:
        cor = "#C0392B" if e["tipo"] == "danger" else (
            AZUL if e["tipo"] == "info" else "#B9770E")
        out.append(
            f'<div class="tl-item"><span class="tl-dot" style="background:{cor}"></span>'
            f'<span class="tl-date">{_esc(e["data"])}</span>'
            f'<span class="tl-title">{_esc(e["titulo"])}</span></div>')
    return "".join(out)


def gerar(ids, alerts, eventos, out_path):
    n_crit = sum(1 for a in alerts if a["sev"] == "CRITICA")
    cards = "".join(_card(a) for a in alerts)
    doc = f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LABRA-AGU · Relatório Pericial da Demo</title>
<style>
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:{FUNDO}; color:{TINTA};
    font-family:'Segoe UI',system-ui,sans-serif; line-height:1.5; }}
  .topbar {{ background:{MARINHO}; color:#fff; }}
  .accent {{ height:4px; background:{AZUL}; }}
  .wrap {{ max-width:1080px; margin:0 auto; padding:0 22px 60px; }}
  header {{ display:flex; align-items:center; gap:14px; padding:18px 22px; max-width:1080px;
    margin:0 auto; }}
  .logo {{ width:42px;height:42px;border-radius:10px;background:#fff;
    display:flex;align-items:center;justify-content:center;font-size:22px;color:{MARINHO}; }}
  h1 {{ font-size:1.2rem; margin:0; color:#fff; font-weight:600; }}
  .sub {{ color:#c7d6ee; font-size:.82rem; }}
  .pill {{ margin-left:auto; font-size:.72rem; color:#eaffea; border:1px solid #ffffff55;
    background:#ffffff1f; padding:5px 10px; border-radius:20px; }}
  h2 {{ font-size:.95rem; color:{MARINHO}; margin:30px 0 14px; display:flex; gap:8px; align-items:center; }}
  h2:before {{ content:''; width:4px; height:16px; background:{AZUL}; border-radius:2px; }}
  .summary {{ display:flex; gap:14px; flex-wrap:wrap; margin-top:22px; }}
  .stat {{ background:#fff; border:1px solid {BORDA}; border-radius:12px; padding:14px 18px; flex:1; min-width:150px; }}
  .stat .n {{ font-size:1.7rem; font-weight:800; }}
  .stat .l {{ color:{MUTED}; font-size:.74rem; text-transform:uppercase; letter-spacing:.04em; }}
  .cards {{ display:grid; gap:14px; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)); }}
  .card {{ background:#fff; border:1px solid {BORDA}; border-radius:12px; padding:16px 18px;
    box-shadow:0 1px 2px #0c326f0f; }}
  .card-top {{ display:flex; align-items:center; gap:10px; margin-bottom:8px; }}
  .badge {{ font-size:.68rem; font-weight:800; padding:3px 9px; border-radius:6px; letter-spacing:.04em; }}
  .tipo {{ font-size:.82rem; font-weight:700; color:{TINTA}; }}
  .desc {{ font-size:.85rem; margin:6px 0; }}
  .conc {{ font-size:.78rem; color:{MUTED}; font-style:italic; margin:6px 0; }}
  .prov {{ font-size:.74rem; color:{AZUL}; margin-top:10px; border-top:1px dashed {BORDA}; padding-top:8px; }}
  .panel {{ background:{PAINEL}; border:1px solid {BORDA}; border-radius:14px; padding:20px; text-align:center; }}
  .tl-item {{ display:flex; align-items:center; gap:12px; padding:8px 0; border-bottom:1px solid {BORDA}; font-size:.82rem; }}
  .tl-dot {{ width:10px;height:10px;border-radius:50%;flex:none; }}
  .tl-date {{ color:{MUTED}; width:108px; flex:none; font-variant-numeric:tabular-nums; }}
  .note {{ margin-top:26px; background:#fff; border:1px solid {BORDA}; border-left:4px solid {AZUL};
    border-radius:0 12px 12px 0; padding:16px 18px; font-size:.8rem; color:{TINTA}; }}
  .note b {{ color:{MARINHO}; }}
</style></head>
<body>
  <div class="topbar">
    <header>
      <div class="logo">&#9878;</div>
      <div>
        <h1>LABRA — AGU · Relatório Pericial</h1>
        <div class="sub">Laboratório de Recuperação de Ativos · Advocacia-Geral da União</div>
      </div>
      <span class="pill">&#9679; dados fictícios · LGPD-safe</span>
    </header>
  </div>
  <div class="accent"></div>
  <div class="wrap">

  <div class="summary">
    <div class="stat"><div class="n" style="color:#C0392B">{len(alerts)}</div><div class="l">Fraudes detectadas</div></div>
    <div class="stat"><div class="n" style="color:#C0392B">{n_crit}</div><div class="l">Severidade CRÍTICA</div></div>
    <div class="stat"><div class="n" style="color:{AZUL}">4</div><div class="l">Fontes correlacionadas</div></div>
    <div class="stat"><div class="n" style="color:#B9770E">1</div><div class="l">Nó (CPF resolvido)</div></div>
  </div>

  <h2>Alertas de Fraude</h2>
  <div class="cards">{cards}</div>

  <h2>Mapa de Relações — Grafo Causal</h2>
  <div class="panel">{_grafo_svg(ids)}</div>

  <h2>Rio de Eventos — Log Imutável</h2>
  <div class="panel" style="text-align:left">{_timeline(eventos)}</div>

  <div class="note">
    <b>Cadeia de custódia:</b> cada alerta aponta, por <b>ULID real</b>, para os eventos-fonte
    que o sustentam — e a própria DIRETRIZ da Procuradoria integra a proveniência. O CPF
    formatado da Junta ({_esc(ids['devedor_fmt'])}) e o cru do COAF/documento ({_esc(ids['devedor'])})
    colapsaram num <b>único nó</b> pela resolução de entidades. Tudo vive no log append-only do
    HeraclitusDB — imutável e consultável <b>AS OF</b> qualquer ponto do passado.
  </div>
  </div>
</body></html>"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return os.path.abspath(out_path)
