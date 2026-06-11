"""
Painel pericial da demo — UM único .html completo, interativo e orientado a
dados, gerado a partir da deteção REAL do agente.

Reflete TODOS os casos detectados (um seletor de casos quando há mais do que
um) e, por caso, uma linha do tempo lateral (reconstrução AS OF): arraste e o
grafo monta-se, os alertas escalam de ALTA para CRÍTICA. Inclui ainda os
cartões de alerta detalhados (conclusão jurídica + proveniência) e a cadeia de
custódia. Sem dependências externas — abre com duplo-clique.

Os dados (casos, alertas, severidades, proveniência) vêm embutidos da corrida;
adicione casos (adicionar_caso.py) e re-gere para o painel refleti-los.
"""
import json
import os

_CSS = """<style>
  *{box-sizing:border-box;}
  body{margin:0;background:#EEF2F7;color:#1B2B40;font-family:'Segoe UI',system-ui,sans-serif;line-height:1.5;}
  .topbar{background:#0C326F;color:#fff;display:flex;align-items:center;gap:12px;padding:14px 22px;}
  .logo{width:40px;height:40px;border-radius:10px;background:#fff;display:flex;align-items:center;justify-content:center;color:#0C326F;font-size:22px;}
  .accent{height:4px;background:#1351B4;}
  h1{font-size:1.2rem;margin:0;color:#fff;font-weight:600;}
  .sub{color:#c7d6ee;font-size:.82rem;}
  .pill{margin-left:auto;font-size:.72rem;color:#eaffea;border:1px solid #ffffff55;background:#ffffff1f;padding:5px 10px;border-radius:20px;}
  .wrap{max-width:1080px;margin:0 auto;padding:0 22px 60px;}
  h2{font-size:.95rem;color:#0C326F;margin:30px 0 14px;display:flex;gap:8px;align-items:center;}
  h2:before{content:'';width:4px;height:16px;background:#1351B4;border-radius:2px;}
  .summary{display:flex;gap:14px;flex-wrap:wrap;margin-top:22px;}
  .stat{background:#fff;border:1px solid #D8E0EA;border-radius:12px;padding:14px 18px;flex:1;min-width:140px;}
  .stat .n{font-size:1.7rem;font-weight:800;}
  .stat .l{color:#5B6B7B;font-size:.74rem;text-transform:uppercase;letter-spacing:.04em;}
  .cases-nav{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0 4px;}
  .cbtn{font-size:.78rem;padding:7px 12px;border-radius:8px;border:1px solid #D8E0EA;background:#fff;color:#1B2B40;cursor:pointer;}
  .cbtn.on{border:2px solid #1351B4;color:#0C326F;font-weight:600;}
  .asof{display:flex;align-items:center;gap:8px;margin-bottom:12px;font-size:.85rem;color:#5B6B7B;}
  .asof b{color:#0C326F;font-size:1rem;}
  .asof .desc{margin-left:auto;color:#1B2B40;}
  .stage{display:flex;gap:18px;}
  .panel{flex:1;background:#fff;border:1px solid #D8E0EA;border-radius:14px;padding:12px;box-shadow:0 1px 2px #0c326f0f;}
  .alerts-live{display:flex;flex-wrap:wrap;gap:7px;padding:10px 6px 4px;min-height:34px;}
  .chip{font-size:12px;font-weight:600;padding:4px 11px;border-radius:7px;}
  .scrubber{display:flex;gap:12px;}
  .scrubber input[type=range]{writing-mode:vertical-lr;width:30px;height:330px;accent-color:#1351B4;}
  .ticks{display:flex;flex-direction:column;justify-content:space-between;height:330px;font-size:12px;}
  .tick{display:flex;align-items:center;gap:8px;color:#5B6B7B;cursor:pointer;white-space:nowrap;}
  .tick .dot{width:9px;height:9px;border-radius:50%;background:#C3CEDC;flex:none;}
  .cards{display:grid;gap:14px;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));}
  .card{background:#fff;border:1px solid #D8E0EA;border-radius:12px;padding:16px 18px;box-shadow:0 1px 2px #0c326f0f;}
  .card-top{display:flex;align-items:center;gap:10px;margin-bottom:8px;}
  .badge{font-size:.68rem;font-weight:800;padding:3px 9px;border-radius:6px;letter-spacing:.04em;}
  .tipo{font-size:.82rem;font-weight:700;color:#1B2B40;}
  .desc{font-size:.85rem;margin:6px 0;}
  .conc{font-size:.78rem;color:#5B6B7B;font-style:italic;margin:6px 0;}
  .prov{font-size:.74rem;color:#1351B4;margin-top:10px;border-top:1px dashed #D8E0EA;padding-top:8px;}
  .note{margin-top:26px;background:#fff;border:1px solid #D8E0EA;border-left:4px solid #1351B4;border-radius:0 12px 12px 0;padding:16px 18px;font-size:.8rem;color:#1B2B40;}
  .note b{color:#0C326F;}
</style>"""

_HTML = """<body>
  <div class="topbar">
    <div class="logo">&#9878;</div>
    <div>
      <h1>LABRA — AGU · Painel Pericial</h1>
      <div class="sub">Laboratório de Recuperação de Ativos · Advocacia-Geral da União</div>
    </div>
    <span class="pill">&#9679; dados fictícios · LGPD-safe</span>
  </div>
  <div class="accent"></div>
  <div class="wrap">

  <div class="summary">
    <div class="stat"><div class="n" id="m_cases" style="color:#0C326F">0</div><div class="l">Casos detectados</div></div>
    <div class="stat"><div class="n" id="m_fraudes" style="color:#C0392B">0</div><div class="l">Fraudes</div></div>
    <div class="stat"><div class="n" id="m_criticas" style="color:#C0392B">0</div><div class="l">Severidade CRÍTICA</div></div>
    <div class="stat"><div class="n" style="color:#1351B4">4</div><div class="l">Fontes correlacionadas</div></div>
  </div>

  <div class="cases-nav" id="cases-nav"></div>

  <h2>Linha do Tempo — Reconstrução AS OF (arraste a barra)</h2>
  <div class="asof"><span>AS OF</span><b id="asof"></b><span class="desc" id="asof-desc"></span></div>
  <div class="stage">
    <div class="panel">
      <svg viewBox="0 0 480 330" width="100%" role="img" aria-label="Grafo da fraude que se monta ao longo do tempo">
        <defs><marker id="ah" markerWidth="9" markerHeight="9" refX="8" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#94A3B8"/></marker></defs>
        <line id="e_venda" x1="100" y1="165" x2="360" y2="75" stroke="#C0392B" stroke-width="2.2" marker-end="url(#ah)" opacity="0"/>
        <line id="e_proc" x1="360" y1="75" x2="360" y2="255" stroke="#C0392B" stroke-width="2.2" marker-end="url(#ah)" opacity="0"/>
        <line id="e_frac" x1="100" y1="165" x2="360" y2="255" stroke="#B9770E" stroke-width="2.2" marker-end="url(#ah)" opacity="0"/>
        <path id="e_fam" d="M108,185 Q235,310 348,268" stroke="#B9770E" stroke-width="2" fill="none" stroke-dasharray="5 4" opacity="0"/>
        <text id="l_venda" x="222" y="108" text-anchor="middle" font-size="11" fill="#9B271B" opacity="0">vendeu quotas</text>
        <text id="l_proc" x="378" y="170" font-size="11" fill="#9B271B" opacity="0">procurador</text>
        <text id="l_frac" x="186" y="240" font-size="11" fill="#8A5908" opacity="0">3&#215; fracionado</text>
        <text id="l_fam" x="232" y="305" text-anchor="middle" font-size="11" fill="#8A5908" opacity="0">cunhado (familiar)</text>
        <g id="n_dev" opacity="0.25"><circle cx="100" cy="165" r="40" fill="#fff" stroke="#C0392B" stroke-width="2.5"/><text x="100" y="160" text-anchor="middle" font-size="12" font-weight="700" fill="#1B2B40">DEVEDOR</text><text id="t_dev" x="100" y="176" text-anchor="middle" font-size="9.5" fill="#5B6B7B"></text></g>
        <g id="n_off" opacity="0.25"><circle cx="360" cy="75" r="40" fill="#fff" stroke="#1351B4" stroke-width="2.5"/><text x="360" y="70" text-anchor="middle" font-size="12" font-weight="700" fill="#1B2B40">OFFSHORE</text><text id="t_off" x="360" y="86" text-anchor="middle" font-size="9.5" fill="#5B6B7B"></text></g>
        <g id="n_lar" opacity="0.25"><circle cx="360" cy="255" r="40" fill="#fff" stroke="#B9770E" stroke-width="2.5"/><text x="360" y="250" text-anchor="middle" font-size="12" font-weight="700" fill="#1B2B40">LARANJA</text><text id="t_lar" x="360" y="266" text-anchor="middle" font-size="9.5" fill="#5B6B7B"></text></g>
      </svg>
      <div class="alerts-live" id="alerts-live"></div>
    </div>
    <div class="scrubber">
      <input id="scrub" type="range" min="0" max="5" step="1" value="0" aria-label="Linha do tempo"/>
      <div class="ticks" id="ticks"></div>
    </div>
  </div>

  <h2>Alertas de Fraude — Detalhe (do caso selecionado)</h2>
  <div class="cards" id="cards"></div>

  <div class="note">
    <b>Cadeia de custódia:</b> cada alerta aponta, por <b>ULID real</b>, para os eventos-fonte
    que o sustentam — e a própria DIRETRIZ da Procuradoria integra a proveniência. O CPF
    formatado da Junta e o cru do COAF/documento colapsam num <b>único nó</b> pela resolução de
    entidades. Tudo vive no log append-only do HeraclitusDB — imutável e consultável
    <b>AS OF</b> qualquer ponto do passado.
  </div>
  </div>"""

_JS = """
  var el=function(id){return document.getElementById(id);};
  function sev(s){return s==='CRITICA'?['#C0392B','#FBE9E7','CRÍTICA']:s==='ALTA'?['#B9770E','#FCF3E3','ALTA']:['#5B6B7B','#EEF2F7',s];}
  el('m_cases').textContent=TOTALS.cases;
  el('m_fraudes').textContent=TOTALS.fraudes;
  el('m_criticas').textContent=TOTALS.criticas;
  var active=0, nav=el('cases-nav'), scrub=el('scrub'), ticks=el('ticks');
  if(CASES.length>1){
    CASES.forEach(function(c,i){
      var b=document.createElement('button'); b.className='cbtn';
      b.textContent='Caso '+(i+1)+' · '+c.dev;
      b.onclick=function(){active=i;renderCase();};
      nav.appendChild(b);
    });
  } else { nav.style.display='none'; }
  function card(a){
    var sc=sev(a.sev), d=document.createElement('div'); d.className='card';
    d.style.borderLeft='4px solid '+sc[0];
    d.innerHTML='<div class="card-top"><span class="badge" style="background:'+sc[1]+';color:'+sc[0]+';border:1px solid '+sc[0]+'">'+sc[2]+'</span><span class="tipo">'+a.tipo.replace(/_/g,' ').toUpperCase()+'</span></div>'
      +'<p class="desc">'+a.descricao+'</p><p class="conc">'+a.conclusao+'</p>'
      +'<div class="prov">&#8627; proveniência: <b>'+a.n_prov+'</b> evento(s) — '+a.fontes.join(' · ')+'</div>';
    return d;
  }
  var ALL_E=['e_venda','e_proc','e_frac','e_fam'], ALL_L=['l_venda','l_proc','l_frac','l_fam'], ALL_N=['n_dev','n_off','n_lar'];
  function op(id,v){var e=el(id); if(e) e.style.opacity=v;}
  function renderStep(){
    var c=CASES[active], s=+scrub.value, st=c.steps[s];
    el('asof').textContent='LSN '+st.lsn+' · '+st.date;
    el('asof-desc').textContent=st.label;
    ALL_N.forEach(function(id){op(id, st.nodes.indexOf(id)>=0?1:0.25);});
    ALL_E.forEach(function(id,i){var on=st.edges.indexOf(id)>=0; op(id,on?1:0); op(ALL_L[i],on?1:0);});
    var box=el('alerts-live'); box.innerHTML='';
    if(!st.chips.length){var e=document.createElement('span'); e.style.cssText='font-size:12px;color:#8a9aab'; e.textContent='sem alertas neste ponto do tempo'; box.appendChild(e);}
    st.chips.forEach(function(ch){
      var crit=ch[1], col=crit?'#C0392B':'#B9770E', bg=crit?'#FBE9E7':'#FCF3E3';
      var sp=document.createElement('span'); sp.className='chip'; sp.style.color=col; sp.style.background=bg; sp.style.border='1px solid '+col;
      sp.textContent=(crit?'CRÍTICA · ':'ALTA · ')+ch[0]; box.appendChild(sp);
    });
    Array.prototype.forEach.call(ticks.children,function(r){
      var on=+r.getAttribute('data-i')===s; r.style.color=on?'#0C326F':'#5B6B7B'; r.style.fontWeight=on?'600':'400';
      r.querySelector('.dot').style.background=on?'#1351B4':'#C3CEDC';
    });
  }
  function renderCase(){
    var c=CASES[active];
    el('t_dev').textContent=c.dev; el('t_off').textContent=c.off; el('t_lar').textContent=c.lar;
    var box=el('cards'); box.innerHTML=''; c.alerts.forEach(function(a){box.appendChild(card(a));});
    scrub.max=c.steps.length-1; scrub.value=c.steps.length-1;
    ticks.innerHTML='';
    c.steps.forEach(function(st,i){
      var r=document.createElement('div'); r.className='tick'; r.setAttribute('data-i',i);
      r.innerHTML='<span class="dot"></span><span>'+st.date+'</span>';
      r.onclick=function(){scrub.value=i;renderStep();};
      ticks.appendChild(r);
    });
    Array.prototype.forEach.call(nav.children,function(b,i){if(i===active)b.classList.add('on');else b.classList.remove('on');});
    renderStep();
  }
  scrub.addEventListener('input',renderStep);
  renderCase();
"""


def gerar(cases, totals, out_path):
    cases_js = json.dumps(cases, ensure_ascii=False)
    totals_js = json.dumps(totals, ensure_ascii=False)
    script = ("<script>(function(){var CASES=" + cases_js +
              ";var TOTALS=" + totals_js + ";" + _JS + "})();</script>")
    doc = ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width, initial-scale=1">'
           '<title>LABRA-AGU · Painel Pericial</title>' + _CSS + '</head>' +
           _HTML + script + '</body></html>')
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return os.path.abspath(out_path)
