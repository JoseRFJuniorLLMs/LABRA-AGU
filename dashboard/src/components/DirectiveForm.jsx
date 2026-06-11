import React, { useState } from 'react';
import { Send, Loader, CheckCircle, Shield, FileText, Hash } from 'lucide-react';

const PATTERNS = [
  { id: 'triangulacao_offshore', label: 'Triangulação Offshore', desc: 'Quotas → procurador c/ plenos poderes' },
  { id: 'fracionamento', label: 'Fracionamento (Smurfing)', desc: '≥3 TED abaixo do limiar COAF' },
  { id: 'laranja_familiar', label: 'Interposta Pessoa (Laranja)', desc: 'Plenos poderes a familiar do devedor' },
  { id: 'vespera_constricao', label: 'Véspera de Constrição', desc: 'Dissipação 30 dias antes da penhora' },
];

const DirectiveForm = () => {
  const [form, setForm] = useState({
    alvos: '',
    foco: '',
    boost: 5,
    patterns: [],
    autor: '',
  });
  const [status, setStatus] = useState('idle'); // idle | loading | success | error
  const [submittedUlid, setSubmittedUlid] = useState('');

  const urgencyLabel = (v) => {
    if (v >= 9) return { text: 'Máxima — Emergência Patrimonial', cls: 'high' };
    if (v >= 7) return { text: 'Alta — Risco Iminente', cls: 'high' };
    if (v >= 4) return { text: 'Média — Investigação Ativa', cls: 'medium' };
    return { text: 'Baixa — Monitoramento Rotineiro', cls: '' };
  };

  const togglePattern = (id) => {
    setForm(f => ({
      ...f,
      patterns: f.patterns.includes(id)
        ? f.patterns.filter(p => p !== id)
        : [...f.patterns, id],
    }));
  };

  const generateFakeUlid = () => {
    const chars = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
    return Array.from({ length: 26 }, () => chars[Math.floor(Math.random() * chars.length)]).join('');
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!form.alvos.trim()) return;

    setStatus('loading');

    // Simulate API call to backend (directive.py via REST bridge)
    setTimeout(() => {
      const ulid = generateFakeUlid();
      setSubmittedUlid(ulid);
      setStatus('success');
      setTimeout(() => setStatus('idle'), 4000);
    }, 1800);
  };

  const alvosArray = form.alvos.split(',').map(s => s.trim()).filter(Boolean);
  const urgency = urgencyLabel(form.boost);

  return (
    <form onSubmit={handleSubmit} className="directive-view">

      {/* LEFT COLUMN */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

        {/* Identificação do Alvo */}
        <div className="form-card">
          <div>
            <div className="form-section-title">
              <span style={{display:'flex',alignItems:'center',gap:'6px'}}>
                <Hash size={12} /> Identificação do Alvo
              </span>
            </div>
            <div className="form-group" style={{marginTop:'12px'}}>
              <label className="form-label" htmlFor="alvos-input">
                CPF / CNPJ do Alvo
                <span style={{marginLeft:'auto',fontSize:'0.7rem',color:'var(--text-muted)'}}>
                  Separe múltiplos por vírgula
                </span>
              </label>
              <input
                id="alvos-input"
                className="form-input"
                type="text"
                placeholder="ex: 645.254.302-49, 12.345.678/0001-90"
                value={form.alvos}
                onChange={e => setForm(f => ({ ...f, alvos: e.target.value }))}
                required
              />
            </div>

            <div className="form-group" style={{marginTop:'12px'}}>
              <label className="form-label" htmlFor="autor-input">
                Identificação do Procurador
              </label>
              <input
                id="autor-input"
                className="form-input"
                type="text"
                placeholder="ex: Dr. Silva — Procuradoria Federal SP"
                value={form.autor}
                onChange={e => setForm(f => ({ ...f, autor: e.target.value }))}
              />
            </div>
          </div>
        </div>

        {/* Foco Investigativo */}
        <div className="form-card" style={{flex:1}}>
          <div>
            <div className="form-section-title">
              <span style={{display:'flex',alignItems:'center',gap:'6px'}}>
                <FileText size={12} /> Foco Investigativo
              </span>
            </div>
            <div className="form-group" style={{marginTop:'12px'}}>
              <label className="form-label" htmlFor="foco-input">
                Descreva o objetivo da investigação
              </label>
              <textarea
                id="foco-input"
                className="form-textarea"
                placeholder="ex: Ocultação de bens através de parentes e offshores em paraíso fiscal. Suspeita de dissipação patrimonial às vésperas da penhora judicial."
                value={form.foco}
                onChange={e => setForm(f => ({ ...f, foco: e.target.value }))}
                style={{minHeight:'100px'}}
              />
            </div>
          </div>
        </div>
      </div>

      {/* RIGHT COLUMN */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

        {/* Prioridade */}
        <div className="form-card">
          <div className="form-section-title">
            <span style={{display:'flex',alignItems:'center',gap:'6px'}}>
              <Shield size={12} /> Nível de Urgência (Boost ACT-R)
            </span>
          </div>
          <div className="slider-container" style={{marginTop:'12px'}}>
            <div className="slider-header">
              <div>
                <div style={{fontSize:'0.78rem',color:'var(--text-subtle)',marginBottom:'2px'}}>
                  {urgency.text}
                </div>
              </div>
              <div className={`slider-value ${urgency.cls}`}>{form.boost}</div>
            </div>
            <input
              id="boost-slider"
              type="range"
              min="1" max="10" step="1"
              value={form.boost}
              onChange={e => setForm(f => ({ ...f, boost: Number(e.target.value) }))}
            />
            <div className="slider-labels">
              <span>1 — Rotineiro</span>
              <span>5 — Padrão</span>
              <span>10 — Crítico</span>
            </div>
          </div>
        </div>

        {/* Padrões */}
        <div className="form-card">
          <div className="form-section-title">Focar em Padrões de Fraude</div>
          <div style={{fontSize:'0.74rem',color:'var(--text-muted)',marginBottom:'10px',marginTop:'4px'}}>
            Deixe em branco para verificar todos os padrões
          </div>
          <div className="patterns-grid">
            {PATTERNS.map(p => (
              <label
                key={p.id}
                className={`pattern-chip ${form.patterns.includes(p.id) ? 'selected' : ''}`}
                htmlFor={`pattern-${p.id}`}
              >
                <input
                  id={`pattern-${p.id}`}
                  type="checkbox"
                  checked={form.patterns.includes(p.id)}
                  onChange={() => togglePattern(p.id)}
                />
                <div className="pattern-chip-dot" />
                <div>
                  <div style={{fontWeight:500,lineHeight:'1.3'}}>{p.label}</div>
                  <div style={{fontSize:'0.68rem',opacity:0.7,marginTop:'1px'}}>{p.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Audit Preview */}
        <div className="form-card">
          <div className="form-section-title">Prévia da Ordem (Log Imutável)</div>
          <div className="audit-preview" style={{marginTop:'10px'}}>
            <div><span className="audit-key">tipo: </span><span className="audit-val">DIRETRIZ</span></div>
            <div><span className="audit-key">alvos: </span><span className="audit-val">[{alvosArray.join(', ') || '—'}]</span></div>
            <div><span className="audit-key">foco: </span><span className="audit-val">"{form.foco.slice(0,40) || '—'}{form.foco.length > 40 ? '…' : ''}"</span></div>
            <div><span className="audit-key">boost: </span><span className="audit-val">{form.boost}</span></div>
            <div><span className="audit-key">padrões: </span><span className="audit-val">[{form.patterns.length ? form.patterns.join(', ') : 'todos'}]</span></div>
            <div><span className="audit-key">autor: </span><span className="audit-val">"{form.autor || 'procuradoria'}"</span></div>
            {submittedUlid && status === 'success' && (
              <div style={{marginTop:'4px'}}>
                <span className="audit-key">ULID: </span>
                <span className="audit-ulid">{submittedUlid}</span>
                <span style={{marginLeft:'6px',color:'var(--accent-green)',fontSize:'0.68rem'}}>✓ Registado</span>
              </div>
            )}
          </div>
        </div>

        {/* Submit */}
        <button
          id="emitir-diretriz-btn"
          type="submit"
          className={`btn-primary ${status === 'loading' ? 'loading' : ''} ${status === 'success' ? 'success' : ''}`}
        >
          {status === 'loading' && <Loader size={18} style={{animation:'spin 1s linear infinite'}} />}
          {status === 'success' && <CheckCircle size={18} />}
          {status === 'idle' && <Send size={18} />}
          {status === 'loading' ? 'Registando no Rio Imutável…' :
           status === 'success' ? 'Diretriz Emitida com Sucesso!' :
           'Emitir Diretriz de Investigação'}
        </button>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </form>
  );
};

export default DirectiveForm;
