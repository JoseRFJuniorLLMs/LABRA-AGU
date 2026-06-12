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
  .case-bar{display:flex;align-items:center;gap:10px;margin:18px 0 4px;flex-wrap:wrap;}
  .case-lbl{font-size:.8rem;color:#5B6B7B;}
  .case-bar select{font-size:.85rem;padding:8px 12px;border-radius:8px;border:1px solid #D8E0EA;background:#fff;color:#1B2B40;min-width:340px;max-width:100%;cursor:pointer;}
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
  .tick .tk{display:flex;flex-direction:column;line-height:1.15;}
  .tick .td{font-weight:600;color:#1B2B40;}
  .tick .tev{font-size:10.5px;color:#5B6B7B;}
  .tick.on .td{color:#0C326F;}
  .ficha{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px;}
  .fe{background:#fff;border:1px solid #D8E0EA;border-radius:10px;padding:9px 13px;font-size:.82rem;}
  .fe .role{display:block;font-size:.66rem;color:#5B6B7B;text-transform:uppercase;letter-spacing:.04em;margin-bottom:2px;}
  .fe b{color:#0C326F;}
  .fe .id{color:#5B6B7B;font-variant-numeric:tabular-nums;}
  .fe.val b{color:#C0392B;}
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
  .teoria-bar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:4px 0 14px;}
  .llm-btn{font-size:.82rem;padding:8px 14px;border-radius:8px;border:1px solid #1351B4;background:#1351B4;color:#fff;cursor:pointer;}
  .llm-btn:hover{background:#0C326F;}
  .llm-hint{font-size:.74rem;color:#5B6B7B;}
  .matriz{display:flex;flex-direction:column;gap:7px;margin-bottom:16px;}
  .mrow{display:flex;align-items:center;gap:10px;font-size:.82rem;}
  .mrow .mt{width:210px;flex:none;}
  .mbar{flex:1;height:14px;background:#EEF2F7;border-radius:7px;overflow:hidden;border:1px solid #D8E0EA;}
  .mbar i{display:block;height:100%;border-radius:7px;}
  .mrow .msc{width:42px;text-align:right;font-variant-numeric:tabular-nums;color:#5B6B7B;}
  .minuta{background:#fff;border:1px solid #D8E0EA;border-radius:12px;padding:18px 22px;max-height:540px;overflow:auto;font-size:.85rem;line-height:1.6;}
  .minuta h3{font-size:1.05rem;color:#0C326F;margin:.2rem 0 .6rem;}
  .minuta h4{font-size:.95rem;color:#0C326F;border-bottom:1px solid #D8E0EA;padding-bottom:4px;margin:1.1rem 0 .5rem;}
  .minuta h5{font-size:.85rem;color:#1B2B40;margin:.8rem 0 .3rem;}
  .minuta code{background:#EEF2F7;padding:1px 5px;border-radius:4px;}
  .minuta blockquote{border-left:3px solid #1351B4;margin:.6rem 0;padding:6px 12px;background:#F7F9FC;color:#5B6B7B;font-size:.8rem;}
  .minuta ul{margin:.3rem 0 .6rem;padding-left:20px;} .minuta li{margin:3px 0;} .minuta p{margin:.4rem 0;}
  .netg{height:380px;background:#fff;border-radius:8px;}
  #tip{position:fixed;z-index:60;max-width:300px;background:#fff;border:1px solid #D8E0EA;border-left:3px solid #1351B4;border-radius:8px;padding:9px 12px;font-size:12px;color:#1B2B40;box-shadow:0 6px 18px #0c326f22;pointer-events:none;display:none;}
  #tip b{color:#0C326F;}
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

  <div class="case-bar" id="case-bar">
    <span class="case-lbl">Caso investigado</span>
    <select id="case-select"></select>
  </div>

  <h2>Ficha do Caso — quem é quem</h2>
  <div class="ficha" id="ficha"></div>

  <h2>Linha do Tempo — Reconstrução AS OF (arraste a barra)</h2>
  <div class="asof"><span>AS OF</span><b id="asof"></b><span class="desc" id="asof-desc"></span></div>
  <div class="stage">
    <div class="panel">
      <div id="g" class="netg" role="img" aria-label="Grafo de relações do caso (dinâmico, montado AS OF)"></div>
      <div class="alerts-live" id="alerts-live"></div>
    </div>
    <div class="scrubber">
      <input id="scrub" type="range" min="0" max="5" step="1" value="0" aria-label="Linha do tempo"/>
      <div class="ticks" id="ticks"></div>
    </div>
  </div>

  <h2>Alertas de Fraude — Detalhe (do caso selecionado)</h2>
  <div class="cards" id="cards"></div>

  <h2>Teoria do Caso — matriz de evidências e minuta</h2>
  <div class="teoria-bar">
    <button id="btn-llm" class="llm-btn">Reanalisar esquemas novos (LLM)</button>
    <span class="llm-hint" id="llm-hint">Copia o comando para reprocessar com Claude — doação cruzada, usufruto/holding e offshore em cascata — com fallback determinístico.</span>
  </div>
  <div class="matriz" id="matriz"></div>
  <div class="minuta" id="minuta"></div>

  <div class="note">
    <b>Cadeia de custódia:</b> cada alerta aponta, por <b>ULID real</b>, para os eventos-fonte
    que o sustentam — e a própria DIRETRIZ da Procuradoria integra a proveniência. O CPF
    formatado da Junta e o cru do COAF/documento colapsam num <b>único nó</b> pela resolução de
    entidades. Tudo vive no log append-only do HeraclitusDB — imutável e consultável
    <b>AS OF</b> qualquer ponto do passado.
  </div>
  </div>
  <div id="tip"></div>"""

_JS = """
  var el=function(id){return document.getElementById(id);};
  function esc(s){return (s==null?'':String(s)).replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c];});}
  function short(s,n){n=n||14; s=s||''; return s.length>n?s.slice(0,n-1)+'…':s;}
  function sev(s){return s==='CRITICA'?['#C0392B','#FBE9E7','CRÍTICA']:s==='ALTA'?['#B9770E','#FCF3E3','ALTA']:['#5B6B7B','#EEF2F7',s];}
  el('m_cases').textContent=TOTALS.cases; el('m_fraudes').textContent=TOTALS.fraudes; el('m_criticas').textContent=TOTALS.criticas;
  var active=0, sel=el('case-select'), scrub=el('scrub'), ticks=el('ticks'), gdiv=el('g'), net=null, nodesDS=null, edgesDS=null, appearT={};
  var tip=el('tip');
  function moveTip(ev){ var w=tip.offsetWidth||220; tip.style.left=Math.max(8,ev.clientX-w-16)+'px'; tip.style.top=Math.max(8,ev.clientY-12)+'px'; }
  function showTip(ev,html){ tip.innerHTML=html; tip.style.display='block'; moveTip(ev); }
  function hideTip(){ tip.style.display='none'; }
  if(CASES.length>1){
    CASES.forEach(function(c,i){ var o=document.createElement('option'); o.value=i;
      o.textContent='Caso '+(i+1)+' · '+c.dev_n+' ('+c.dev+') · '+c.alerts.length+' fraude(s)'; sel.appendChild(o); });
    sel.onchange=function(){active=+sel.value;renderCase();};
  } else { el('case-bar').style.display='none'; }
  function card(a){
    var sc=sev(a.sev), d=document.createElement('div'); d.className='card'; d.style.borderLeft='4px solid '+sc[0];
    d.innerHTML='<div class="card-top"><span class="badge" style="background:'+sc[1]+';color:'+sc[0]+';border:1px solid '+sc[0]+'">'+sc[2]+'</span><span class="tipo">'+a.tipo.replace(/_/g,' ').toUpperCase()+'</span></div>'
      +'<p class="desc">'+a.descricao+'</p><p class="conc">'+a.conclusao+'</p>'
      +'<div class="prov">&#8627; proveniência: <b>'+a.n_prov+'</b> evento(s) — '+a.fontes.join(' · ')+'</div>';
    return d;
  }
  function fe(role,nome,id,cls){ return '<div class="fe '+(cls||'')+'"><span class="role">'+role+'</span><b>'+nome+'</b>'+(id?' <span class="id">'+id+'</span>':'')+'</div>'; }

  // ── grafo dinâmico via vis-network (física, nós arrastáveis, sem sobreposição) ──
  function fcol(c,n){ return n.id===c.devedor_id?'#C0392B':((n.kind||'').indexOf('JURIDICA')>=0?'#1351B4':'#B9770E'); }
  function ecol(e){ return (e.kind==='VENDEDOR_QUOTAS'||e.kind==='PROCURADOR_COM_PODERES'||e.kind==='FAMILIAR')?'#C0392B':'#B9770E'; }
  function renderGraph(c){
    appearT={}; appearT[c.devedor_id]=0;
    c.edges.forEach(function(e){ [e.src,e.dst].forEach(function(id){ if(appearT[id]===undefined||e.t<appearT[id]) appearT[id]=e.t; }); });
    if(typeof vis==='undefined'){ gdiv.innerHTML='<div style="padding:24px;color:#8a9aab;font-size:12px">(vis-network não carregada — verifique demo/vendor/vis-network.min.js)</div>'; return; }
    nodesDS=new vis.DataSet(c.nodes.map(function(n){ var col=fcol(c,n);
      return {id:n.id, label:short(n.label,16)+'\\n'+n.id_fmt, shape:'dot', size:(n.id===c.devedor_id?20:14),
        color:{background:'#fff',border:col,highlight:{background:'#F7F9FC',border:col}}, borderWidth:2.6,
        font:{size:11,color:'#1B2B40'}}; }));
    edgesDS=new vis.DataSet(c.edges.map(function(e,i){ var col=ecol(e);
      return {id:i, from:e.src, to:e.dst, label:e.label, arrows:'to', color:{color:col,highlight:col},
        font:{size:10,color:col,strokeWidth:4,strokeColor:'#fff'}, smooth:{type:'dynamic'}, width:1.6}; }));
    if(net) net.destroy();
    net=new vis.Network(gdiv, {nodes:nodesDS, edges:edgesDS}, {
      physics:{barnesHut:{springLength:155,avoidOverlap:0.5}, stabilization:{iterations:240}},
      interaction:{hover:true, dragNodes:true, zoomView:true}, nodes:{shadow:false}, edges:{shadow:false}});
  }
  function renderReveal(){
    var c=CASES[active], p=+scrub.value;
    if(nodesDS) nodesDS.update(c.nodes.map(function(n){ var on=appearT[n.id]<=p, col=fcol(c,n);
      return {id:n.id, opacity:on?1:0.22, color:{background:'#fff',border:on?col:'#C3CEDC'}, font:{color:on?'#1B2B40':'#C3CEDC'}}; }));
    if(edgesDS) edgesDS.update(c.edges.map(function(e,i){ var on=e.t<=p, col=ecol(e);
      return {id:i, color:{color:on?col:'#E6ECF3'}, label:on?e.label:' ', font:{color:on?col:'#E6ECF3',strokeWidth:4,strokeColor:'#fff'}}; }));
    var n=(c.ticks||[]).length, tk=(c.ticks&&c.ticks[p])||{label:'',date:''};
    el('asof').textContent='passo '+(p+1)+'/'+n+(tk.date?' · '+tk.date:'');
    el('asof-desc').textContent=tk.label||'';
    Array.prototype.forEach.call(ticks.children,function(r){ var on=+r.getAttribute('data-i')===p;
      if(on)r.classList.add('on');else r.classList.remove('on'); r.querySelector('.dot').style.background=on?'#1351B4':'#C3CEDC'; });
  }
  function renderCase(){
    var c=CASES[active];
    el('ficha').innerHTML=fe('Devedor',c.dev_n,c.dev)+fe('Offshore',c.off_n,c.off)+fe('Laranja (cunhado)',c.lar_n,c.lar)+fe('Valor dissipado',c.valor,'','val');
    var box=el('cards'); box.innerHTML=''; c.alerts.forEach(function(a){box.appendChild(card(a));});
    var mz=el('matriz'); mz.innerHTML='';
    (c.matriz||[]).forEach(function(m){ var sc=sev(m.sev), pct=Math.round((m.score||0)*100);
      var row=document.createElement('div'); row.className='mrow';
      row.innerHTML='<span class="mt">'+m.tipo.replace(/_/g,' ')+'</span><span class="mbar"><i style="width:'+pct+'%;background:'+sc[0]+'"></i></span><span class="msc">'+(m.score!=null?m.score.toFixed(2):'—')+'</span>';
      mz.appendChild(row); });
    el('minuta').innerHTML=c.minuta_html||'<p style="color:#8a9aab">Sem minuta para este caso.</p>';
    renderGraph(c);
    ticks.innerHTML='';
    (c.ticks||[]).forEach(function(t,i){ var r=document.createElement('div'); r.className='tick'; r.setAttribute('data-i',i);
      r.innerHTML='<span class="dot"></span><span class="tk"><span class="td">'+esc(t.date||('#'+(i+1)))+'</span><span class="tev">'+esc(t.label)+'</span></span>';
      r.onclick=function(){scrub.value=i;renderReveal();};
      var html='<b>'+esc(t.date||('passo '+(i+1)))+' · '+esc(t.label)+'</b><div style="margin-top:3px;color:#5B6B7B">'+esc(t.resumo||'')+'</div>';
      r.onmouseenter=function(ev){showTip(ev,html);}; r.onmousemove=moveTip; r.onmouseleave=hideTip;
      ticks.appendChild(r); });
    scrub.max=Math.max(0,((c.ticks||[]).length)-1); scrub.value=scrub.max;
    sel.value=active; renderReveal();
  }
  scrub.addEventListener('input',renderReveal);
  var btn=el('btn-llm');
  if(btn) btn.onclick=function(){ var cmd='py main.py --daemon --llm';
    try{ if(navigator.clipboard) navigator.clipboard.writeText(cmd); }catch(e){}
    el('llm-hint').textContent='Comando copiado: '+cmd+'  (requer ANTHROPIC_API_KEY; extrai doação cruzada, usufruto e cascata via Claude; fallback determinístico).'; };
  renderCase();
"""


def gerar(cases, totals, out_path):
    cases_js = json.dumps(cases, ensure_ascii=False)
    totals_js = json.dumps(totals, ensure_ascii=False)
    # vis-network em bundle LOCAL (offline). O painel é gerado em
    # demo/demo_data/, logo a lib em demo/vendor/ fica em ../vendor/.
    vis = '<script src="../vendor/vis-network.min.js"></script>'
    script = (vis + "<script>(function(){var CASES=" + cases_js +
              ";var TOTALS=" + totals_js + ";" + _JS + "})();</script>")
    doc = ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
           '<meta name="viewport" content="width=device-width, initial-scale=1">'
           '<title>LABRA-AGU · Painel Pericial</title>' + _CSS + '</head>' +
           _HTML + script + '</body></html>')
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(doc)
    return os.path.abspath(out_path)
