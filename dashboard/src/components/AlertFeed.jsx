import React, { useState, useEffect } from 'react';
import { AlertTriangle, AlertOctagon, Bell, FileText, Clock, Link2, CheckCircle2 } from 'lucide-react';

const INITIAL_ALERTS = [
  {
    id: 'A1',
    title: 'Triangulação Societária — Offshore Confirmada',
    severity: 'critica',
    pattern: 'triangulacao_offshore',
    description: 'Quotas da Construtora Alfa transferidas ao cunhado do devedor (procurador com plenos poderes) 12 dias antes da penhora prevista.',
    actr: 0.98,
    timestamp: '2026-06-10 23:41:07',
    alvo: 'Carlos A. Menezes — CPF: 645.254.302-49',
    valor: 'R$ 2.400.000',
    fontes: ['Contrato Social — 2026-06-02.pdf', 'COAF Relatório 4421.pdf'],
    ulid_doc: '01J5X9KPMN4V7Z2AQWRT3EYCFH',
    ulid_diretriz: '01J5X8BKRV3T2M1PQEWND4SZGJ',
    new: true,
  },
  {
    id: 'A2',
    title: 'Fracionamento de Transferências (Smurfing)',
    severity: 'alta',
    pattern: 'fracionamento',
    description: '5 TEDs de R$ 9.800 realizados em 48h para contas distintas de familiares. Soma total: R$ 49.000 — abaixo do limiar COAF de R$ 50.000.',
    actr: 0.87,
    timestamp: '2026-06-10 18:22:33',
    alvo: 'Imobiliária Beta S.A. — CNPJ: 98.765.432/0001-11',
    valor: 'R$ 49.000',
    fontes: ['Extrato Bancário Mai-2026.csv'],
    ulid_doc: '01J5WRKHN7P4V1BMQXCE2TZYLA',
    ulid_diretriz: '01J5X8BKRV3T2M1PQEWND4SZGJ',
    new: true,
  },
  {
    id: 'A3',
    title: 'Dissipação Patrimonial — Véspera de Constrição',
    severity: 'critica',
    pattern: 'vespera_constricao',
    description: 'R$ 1,8M em bens imóveis transferidos nos 22 dias anteriores à citação judicial. Padrão de blindagem patrimonial ativado.',
    actr: 0.95,
    timestamp: '2026-06-09 09:14:51',
    alvo: 'Carlos A. Menezes — CPF: 645.254.302-49',
    valor: 'R$ 1.800.000',
    fontes: ['Cartório Registro Imóveis 2026.pdf', 'Citação Proc. 0014432-2026.pdf'],
    ulid_doc: '01J5VN2PHQX7R4KCMZTW8YAEBG',
    ulid_diretriz: null,
    new: false,
  },
  {
    id: 'A4',
    title: 'Interposta Pessoa — Laranja Familiar',
    severity: 'alta',
    pattern: 'laranja_familiar',
    description: 'Procuração com plenos poderes outorgada à cônjuge do devedor. Empresa registrada em nome dela movimenta 90% do patrimônio do casal.',
    actr: 0.81,
    timestamp: '2026-06-08 14:05:22',
    alvo: 'Rita F. Menezes — CPF: 732.891.004-11',
    valor: 'R$ 3.200.000',
    fontes: ['Procuração Pública 2025-0889.pdf'],
    ulid_doc: '01J5TM8GJNY2P6VBRXWD1KQCZA',
    ulid_diretriz: '01J5X8BKRV3T2M1PQEWND4SZGJ',
    new: false,
  },
  {
    id: 'A5',
    title: 'Criação de Estrutura Offshore',
    severity: 'media',
    pattern: 'triangulacao_offshore',
    description: 'Gamma Holdings Ltd constituída nas Ilhas Cayman 3 meses após início da investigação judicial. Diretor: Paulo R. Ferreira (cunhado).',
    actr: 0.75,
    timestamp: '2026-06-05 11:30:00',
    alvo: 'Paulo R. Ferreira — CPF: 019.234.567-88',
    valor: 'Indeterminado',
    fontes: ['Reg. BVI Gamma Holdings 2023.pdf'],
    ulid_doc: '01J5RK4FMHZ1Q9TCXNBV2YLWSE',
    ulid_diretriz: null,
    new: false,
  },
];

const SEV_CONFIG = {
  critica: { label: 'CRÍTICA', icon: AlertOctagon, color: 'var(--accent-danger)' },
  alta:    { label: 'ALTA',    icon: AlertTriangle, color: 'var(--accent-warning)' },
  media:   { label: 'MÉDIA',   icon: Bell,          color: 'var(--accent-purple)' },
};

const AlertFeed = () => {
  const [alerts, setAlerts] = useState(INITIAL_ALERTS);
  const [selected, setSelected] = useState('A1');
  const [dismissed, setDismissed] = useState(new Set());

  const selectedAlert = alerts.find(a => a.id === selected);
  const visibleAlerts = alerts.filter(a => !dismissed.has(a.id));
  const newCount = visibleAlerts.filter(a => a.new).length;

  // Simulate a new alert coming in after 8 seconds
  useEffect(() => {
    const t = setTimeout(() => {
      setAlerts(prev => [
        {
          id: 'A6',
          title: 'Novo Relatório COAF Recebido',
          severity: 'alta',
          pattern: 'fracionamento',
          description: 'Relatório de Inteligência Financeira 5512/2026 aponta 7 operações suspeitas em conta de familiar não investigado.',
          actr: 0.79,
          timestamp: new Date().toLocaleString('pt-BR').replace(',', ''),
          alvo: 'Marco T. Ferreira — CPF: 556.712.038-90',
          valor: 'R$ 92.000',
          fontes: ['COAF RIF 5512-2026.pdf'],
          ulid_doc: '01J5ZNEWXMH7R4VCBQTPK2ALFG',
          ulid_diretriz: null,
          new: true,
        },
        ...prev,
      ]);
    }, 8000);
    return () => clearTimeout(t);
  }, []);

  return (
    <div className="alerts-view">
      {/* Left: Alert List */}
      <div className="glass-panel" style={{display:'flex',flexDirection:'column',gap:'0',padding:'0',overflow:'hidden'}}>
        <div className="panel-header" style={{padding:'16px 20px',margin:0}}>
          <AlertOctagon size={18} color="var(--accent-danger)" />
          <h2>Alertas de Fraude</h2>
          {newCount > 0 && (
            <span className="panel-count" style={{background:'rgba(239,68,68,0.15)',color:'var(--accent-danger)',border:'1px solid rgba(239,68,68,0.3)'}}>
              {newCount} novo{newCount > 1 ? 's' : ''}
            </span>
          )}
          <span className="panel-count" style={{marginLeft:'6px'}}>{visibleAlerts.length} total</span>
        </div>
        <div className="alerts-list" style={{padding:'0 16px 16px'}}>
          {visibleAlerts.map(alert => {
            const sev = SEV_CONFIG[alert.severity];
            const SevIcon = sev.icon;
            return (
              <div
                key={alert.id}
                id={`alert-card-${alert.id}`}
                className={`alert-card sev-${alert.severity} ${selected === alert.id ? 'selected' : ''}`}
                onClick={() => {
                  setSelected(alert.id);
                  setAlerts(prev => prev.map(a => a.id === alert.id ? { ...a, new: false } : a));
                }}
              >
                <div className="alert-card-top">
                  <div className="alert-title">
                    {alert.new && (
                      <span style={{
                        display:'inline-block',marginRight:'6px',
                        width:'7px',height:'7px',borderRadius:'50%',
                        background:'var(--accent-danger)',
                        boxShadow:'0 0 6px var(--accent-danger)',
                        verticalAlign:'middle',marginBottom:'1px'
                      }} />
                    )}
                    {alert.title}
                  </div>
                  <span className={`severity-badge sev-${alert.severity}`}>
                    {sev.label}
                  </span>
                </div>
                <p className="alert-desc">{alert.description}</p>
                <div className="alert-meta">
                  <span><Clock size={11} /> {alert.timestamp.split(' ')[0]}</span>
                  <span><FileText size={11} /> {alert.fontes.length} fonte{alert.fontes.length > 1 ? 's' : ''}</span>
                  <span style={{color: sev.color}}><SevIcon size={11} /> {alert.pattern}</span>
                </div>
                <div className="actr-bar">
                  <span className="actr-label">ACT-R</span>
                  <div className="actr-track">
                    <div className="actr-fill" style={{ width: `${alert.actr * 100}%` }} />
                  </div>
                  <span className="actr-score">{alert.actr.toFixed(2)}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Right: Detail Panel */}
      {selectedAlert ? (
        <div className="alert-detail">
          <div className="detail-section">
            <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:'10px',marginBottom:'10px'}}>
              <h3 style={{fontSize:'0.95rem',fontWeight:700,color:'var(--text-main)',lineHeight:'1.3'}}>
                {selectedAlert.title}
              </h3>
              <span className={`severity-badge sev-${selectedAlert.severity}`} style={{flexShrink:0}}>
                {SEV_CONFIG[selectedAlert.severity].label}
              </span>
            </div>
            <p style={{fontSize:'0.8rem',color:'var(--text-muted)',lineHeight:'1.6'}}>
              {selectedAlert.description}
            </p>
          </div>

          <div className="detail-section">
            <div className="detail-section-title">Dados do Evento</div>
            <div className="detail-row">
              <span>Alvo</span>
              <span className="val" style={{color:'var(--accent-cyan)',fontSize:'0.73rem'}}>{selectedAlert.alvo}</span>
            </div>
            <div className="detail-row">
              <span>Valor Envolvido</span>
              <span className="val" style={{color:'var(--accent-warning)'}}>{selectedAlert.valor}</span>
            </div>
            <div className="detail-row">
              <span>Padrão Detectado</span>
              <span className="val">{selectedAlert.pattern}</span>
            </div>
            <div className="detail-row">
              <span>Data/Hora</span>
              <span className="val">{selectedAlert.timestamp}</span>
            </div>
            <div className="detail-row">
              <span>Score ACT-R</span>
              <span className="val" style={{color:'var(--accent-cyan)'}}>{selectedAlert.actr.toFixed(4)}</span>
            </div>
          </div>

          <div className="detail-section">
            <div className="detail-section-title">Fontes Documentais</div>
            <div className="provenance-chain">
              {selectedAlert.fontes.map((f, i) => (
                <div key={i} className="provenance-item">
                  <FileText size={11} style={{flexShrink:0}} />
                  <span>{f}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="detail-section">
            <div className="detail-section-title">Cadeia de Custódia (ULIDs)</div>
            <div style={{display:'flex',flexDirection:'column',gap:'8px'}}>
              <div>
                <div style={{fontSize:'0.68rem',color:'var(--text-muted)',marginBottom:'4px'}}>
                  <Link2 size={10} style={{display:'inline',marginRight:'4px'}} />Documento Fonte
                </div>
                <div className="ulid-code">{selectedAlert.ulid_doc}</div>
              </div>
              {selectedAlert.ulid_diretriz ? (
                <div>
                  <div style={{fontSize:'0.68rem',color:'var(--text-muted)',marginBottom:'4px'}}>
                    <Link2 size={10} style={{display:'inline',marginRight:'4px'}} />Diretriz que Ativou
                  </div>
                  <div className="ulid-code">{selectedAlert.ulid_diretriz}</div>
                </div>
              ) : (
                <div style={{fontSize:'0.72rem',color:'var(--text-muted)',fontStyle:'italic'}}>
                  Detectado autonomamente (sem diretriz)
                </div>
              )}
            </div>
          </div>

          <div style={{display:'flex',flexDirection:'column',gap:'8px',marginTop:'auto'}}>
            <button id={`btn-relatorio-${selectedAlert.id}`} className="btn-action">
              <FileText size={14} /> Gerar Relatório Pericial
            </button>
            <button id={`btn-diretriz-${selectedAlert.id}`} className="btn-action">
              <CheckCircle2 size={14} /> Emitir Diretriz de Aprofundamento
            </button>
          </div>
        </div>
      ) : (
        <div className="glass-panel empty-state">
          <AlertOctagon size={32} color="var(--text-muted)" />
          <p>Selecione um alerta para ver os detalhes e a cadeia de custódia.</p>
        </div>
      )}
    </div>
  );
};

export default AlertFeed;
