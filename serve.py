"""
serve.py — frontend WEB do agente investigativo (vê o LLM a trabalhar no HTML).

Sobe um servidor local (só biblioteca-padrão, sem dependências). Abre a página,
escreve/colhe um caso, clica "Investigar" e vês: os PASSOS do agente a aparecer
(cadeia de raciocínio), o dossiê e a PETIÇÃO redigida — pelo **Gemma 4 local**
se o LM Studio estiver ligado, senão pelo planeador determinístico.

  py serve.py            # abre em http://localhost:8770
  py serve.py --port 9000

Para o cérebro Gemma: LM Studio → aba Developer (</>) → carregar gemma-4-e4b →
Start Server (porta 1234). A página mostra o estado do Gemma no topo.
"""
import argparse
import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "demo"))  # nomes.py (rótulos)

from agent.llm import LocalLLM  # noqa: E402
from agent.orchestrator import _json_seguro, investigar  # noqa: E402

# Cache do grafo reconstruído do log de produção (caro: ~6s; reusa-se).
_LOG = {"graph": None}


def _client():
    from agent.client import HeraclitusClient
    return HeraclitusClient()  # 127.0.0.1:7474 (HERACLITUS_ADDR)


def _graph_log(force: bool = False):
    """Grafo COMPLETO reconstruído do log do HeraclitusDB (dados reais)."""
    if _LOG["graph"] is None or force:
        from agent.graph_timeline import GraphTimeline
        tl = GraphTimeline(_client())
        _LOG["graph"] = tl.at_lsn(tl.head())
    return _LOG["graph"]


def _devedores_log():
    """Devedores REAIS do log (a partir dos insights), com nome e nº de fraudes."""
    import json as _j
    from collections import defaultdict
    rows = [r for r in _client().query(
        'MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n')
        if "INSIGHT_PERICIAL_FRAUDE" in r.get("kind", "")]
    cont = defaultdict(set)
    for r in rows:
        try:
            p = _j.loads(r["content"])
        except Exception:
            continue
        cont[p.get("devedor_alvo", "?")].add(p.get("tipo_fraude"))
    try:
        from nomes import nome_de
    except Exception:
        def nome_de(_):
            return None
    out = [{"id": d, "nome": nome_de(d) or d, "n": len(f)} for d, f in cont.items()]
    return sorted(out, key=lambda x: -x["n"])


def _investigar_log(devedor: str, use_llm: bool = True) -> dict:
    """Investiga um devedor sobre os DADOS REAIS do log (não persiste o trace)."""
    from agent.agent_loop import ForensicAgent
    from agent.entities import normalize_id
    dev = normalize_id(devedor)
    llm = LocalLLM() if (use_llm and LocalLLM().available()) else None
    r = ForensicAgent(_graph_log(), client=None, llm=llm).investigar(dev)
    return {**r, "devedor": dev}

# CPF/CNPJ FICTÍCIOS mas com dígitos verificadores VÁLIDOS (o parser valida-os).
_CASO_EXEMPLO = (
    "158.813.998-03 transferiu quotas para 11.417.075/3645-57, que nomeou o cunhado 698.797.309-17 com plenos poderes.\n"
    "158.813.998-03 transferiu R$ 9.000,00 para 698.797.309-17 em 01/02/2026.\n"
    "158.813.998-03 transferiu R$ 9.300,00 para 698.797.309-17 em 02/02/2026.\n"
    "158.813.998-03 transferiu R$ 8.700,00 para 698.797.309-17 em 03/02/2026.\n"
    "158.813.998-03 pagou propina de R$ 100.000,00 ao agente público 568.151.884-18 em 01/03/2026.\n"
    "Consta penhora em 05/06/2026. 2026-06-10 14:32:11 UPDATE alteracoes "
    "registro de 158.813.998-03 campo=data de=08/06/2026 para=01/05/2026 por=op_junta_47"
)
_DEVEDOR_EXEMPLO = "158.813.998-03"

_PAGE = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LABRA-AGU · Agente Investigativo</title><style>
*{box-sizing:border-box} body{margin:0;background:#EEF2F7;color:#1B2B40;font-family:'Segoe UI',system-ui,sans-serif;line-height:1.5}
.top{background:#0C326F;color:#fff;padding:14px 22px;display:flex;align-items:center;gap:12px}
.top h1{font-size:1.1rem;margin:0} .acc{height:4px;background:#1351B4}
.badge{margin-left:auto;font-size:.78rem;padding:5px 12px;border-radius:20px;border:1px solid #ffffff55}
.badge.on{background:#1f7a37;border-color:#2e9} .badge.off{background:#8a3a3a}
.wrap{max-width:1000px;margin:0 auto;padding:22px}
textarea{width:100%;min-height:150px;border:1px solid #D8E0EA;border-radius:10px;padding:12px;font-family:ui-monospace,monospace;font-size:13px}
.row{display:flex;gap:10px;align-items:center;margin:10px 0;flex-wrap:wrap}
input[type=text]{padding:9px 12px;border:1px solid #D8E0EA;border-radius:8px;font-size:14px;min-width:220px}
button{background:#1351B4;color:#fff;border:0;border-radius:8px;padding:10px 18px;font-size:14px;font-weight:600;cursor:pointer}
button:disabled{opacity:.5;cursor:wait}
h2{font-size:.95rem;color:#0C326F;margin:26px 0 12px;display:flex;gap:8px;align-items:center}
h2:before{content:'';width:4px;height:16px;background:#1351B4;border-radius:2px}
.step{background:#fff;border:1px solid #D8E0EA;border-left:4px solid #1351B4;border-radius:10px;padding:10px 14px;margin:7px 0;font-size:.88rem;opacity:0;transform:translateY(6px);transition:all .3s}
.step.in{opacity:1;transform:none} .step b{color:#0C326F} .step .o{color:#5B6B7B}
.peca{background:#fff;border:1px solid #D8E0EA;border-radius:12px;padding:18px 20px;white-space:pre-wrap;font-size:.9rem;line-height:1.6}
.kpi{display:flex;gap:12px;flex-wrap:wrap;margin:10px 0}
.kpi .c{background:#fff;border:1px solid #D8E0EA;border-radius:10px;padding:10px 16px}
.kpi .n{font-size:1.4rem;font-weight:800;color:#0C326F} .kpi .l{font-size:.72rem;color:#5B6B7B;text-transform:uppercase}
.motor{font-size:.78rem;color:#5B6B7B;margin-top:8px}
</style></head><body>
<div class="top"><div>⚖️</div><h1>LABRA-AGU · Agente Investigativo</h1>
<span id="gemma" class="badge">a verificar Gemma…</span></div><div class="acc"></div>
<div class="wrap">
  <h2>Investigar um caso REAL (log do HeraclitusDB)</h2>
  <div class="row">
    <select id="devlog"><option value="">a carregar devedores…</option></select>
    <button id="go" onclick="investigarLog()">▶ Investigar do log</button>
    <span id="status" class="motor"></span>
  </div>

  <details style="margin-top:18px">
    <summary style="cursor:pointer;color:#0C326F;font-weight:600">… ou colar um caso novo para teste (modo texto)</summary>
    <textarea id="texto" style="margin-top:10px">__EXEMPLO__</textarea>
    <div class="row">
      <input type="text" id="devedor" value="__DEVEXEMPLO__" placeholder="CPF/CNPJ que aparece no texto">
      <button onclick="investigar()">▶ Investigar (texto)</button>
    </div>
    <p class="motor">No modo texto o devedor tem de aparecer no texto colado (ex.: 158.813.998-03). Para casos reais usa o dropdown acima.</p>
  </details>
  <div id="out"></div>
</div>
<script>
async function refreshGemma(){
  try{ const r=await fetch('/health'); const j=await r.json();
    const b=document.getElementById('gemma');
    if(j.gemma){ b.textContent='● Gemma 4 LOCAL ligado'; b.className='badge on'; }
    else { b.textContent='● Gemma offline (determinístico)'; b.className='badge off'; }
  }catch(e){}
}
function esc(s){return (s==null?'':String(s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
function investigar(){ run({devedor:document.getElementById('devedor').value, texto:document.getElementById('texto').value}); }
function investigarLog(){ const s=document.getElementById('devlog'); if(!s.value){alert('Escolhe um devedor do log.');return;} run({fonte:'log', devedor:s.value}); }
async function loadDevedores(){
  const s=document.getElementById('devlog');
  try{ const r=await fetch('/devedores'); const j=await r.json();
    if(Array.isArray(j)&&j.length){ s.innerHTML=j.map(d=>'<option value="'+esc(d.id)+'">'+esc(d.nome)+' ('+esc(d.id)+') · '+d.n+' fraude(s)</option>').join(''); }
    else { s.innerHTML='<option value="">(log indisponível — HeraclitusDB ligado?)</option>'; }
  }catch(e){ s.innerHTML='<option value="">(log indisponível)</option>'; }
}
async function run(payload){
  const go=document.getElementById('go'), out=document.getElementById('out'), st=document.getElementById('status');
  go.disabled=true; st.textContent='a investigar… (do log + Gemma pode levar alguns segundos)'; out.innerHTML='';
  try{
    const r=await fetch('/investigar',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)});
    const j=await r.json();
    if(j.erro){ out.innerHTML='<p style="color:#b00">Erro: '+esc(j.erro)+'</p>'; return; }
    const d=j.dossie||{};
    let h='';
    if(!((d.achados||[]).length)){
      h+='<div style="background:#FCF3E3;border:1px solid #e0c98a;border-radius:10px;padding:12px 14px;margin:10px 0;color:#7a5b00">'
        +'⚠️ Nenhuma fraude para <b>'+esc(j.devedor||'')+'</b> nos dados investigados.<br>'
        +'No modo <b>texto</b>, o devedor tem de aparecer no texto colado. Para um caso real, escolhe no <b>dropdown do log</b> acima.</div>';
    }
    h+='<h2>Passos do agente (cadeia de raciocínio)</h2><div id="steps"></div>';
    h+='<h2>Dossiê</h2><div class="kpi">'
      +'<div class="c"><div class="n">'+(d.achados||[]).length+'</div><div class="l">Fraudes</div></div>'
      +'<div class="c"><div class="n">'+(d.essenciais||[]).length+'</div><div class="l">Provas essenciais</div></div>'
      +'<div class="c"><div class="n">R$ '+((d.valor||0).toLocaleString("pt-BR"))+'</div><div class="l">Valor a recuperar</div></div>'
      +'</div>';
    h+='<h2>Peça rascunhada (revisão do procurador)</h2><div class="peca">'+esc((j.peca||{}).texto||'')+'</div>';
    h+='<div class="motor">motor: <b>'+esc(j.motor||'?')+'</b></div>';
    out.innerHTML=h;
    // anima os passos a aparecer
    const steps=j.trace||[]; const box=document.getElementById('steps');
    steps.forEach((e,i)=>{ const el=document.createElement('div'); el.className='step';
      el.innerHTML='<b>'+(e.passo)+'. '+esc(e.acao)+'</b> <span class="o">→ '+esc(e.obs)+'</span>';
      box.appendChild(el); setTimeout(()=>el.classList.add('in'), 120*i+50); });
    st.textContent='';
  }catch(e){ out.innerHTML='<p style="color:#b00">Falha: '+esc(e.message)+'</p>'; }
  finally{ go.disabled=false; }
}
refreshGemma(); setInterval(refreshGemma, 5000); loadDevedores();
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):  # silencia o log ruidoso por request
        pass

    def do_GET(self):
        if self.path.startswith("/health"):
            self._send(200, json.dumps({"gemma": LocalLLM().available()}))
        elif self.path.startswith("/devedores"):
            try:
                self._send(200, json.dumps(_devedores_log(), ensure_ascii=False))
            except Exception as e:  # noqa: BLE001 — HeraclitusDB pode estar em baixo
                self._send(200, json.dumps({"erro": f"{type(e).__name__}: {e}"}))
        elif self.path == "/" or self.path.startswith("/index"):
            self._send(200, _PAGE.replace("__EXEMPLO__", _CASO_EXEMPLO)
                       .replace("__DEVEXEMPLO__", _DEVEDOR_EXEMPLO),
                       "text/html; charset=utf-8")
        else:
            self._send(404, json.dumps({"erro": "rota desconhecida"}))

    def do_POST(self):
        if not self.path.startswith("/investigar"):
            self._send(404, json.dumps({"erro": "rota desconhecida"}))
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            devedor = (body.get("devedor") or "").strip()
            fonte = body.get("fonte") or "texto"
            if not devedor:
                self._send(400, json.dumps({"erro": "informe o devedor"}))
                return
            if fonte == "log":
                r = _investigar_log(devedor)  # dados REAIS do HeraclitusDB
            else:
                texto = body.get("texto") or ""
                r = investigar(devedor, textos=[texto] if texto.strip() else None,
                               use_llm_agent=True)
            self._send(200, json.dumps(r, default=_json_seguro, ensure_ascii=False))
        except Exception as e:  # noqa: BLE001 — devolve o erro à página
            self._send(500, json.dumps({"erro": f"{type(e).__name__}: {e}"}))


def main():
    ap = argparse.ArgumentParser(description="Frontend web do agente LABRA-AGU")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--no-open", action="store_true", help="não abrir o browser")
    args = ap.parse_args()
    url = f"http://127.0.0.1:{args.port}"
    print(f"LABRA-AGU · agente web em {url}  (Ctrl+C para parar)")
    print("  Gemma: " + ("LIGADO" if LocalLLM().available()
                          else "offline — inicie o Start Server no LM Studio"))
    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
