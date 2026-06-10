import React from 'react';
import { AlertOctagon, FileText, Search } from 'lucide-react';

const AlertPanel = ({ selectedEventId, onSelectEvent }) => {
  const alerts = [
    {
      id: 'E4',
      title: 'Triangulação Societária',
      description: 'Transferência atípica de quotas detectada da Empresa Mãe para Offshore controlada pelo cunhado.',
      score: '0.98',
      type: 'danger'
    },
    {
      id: 'E3',
      title: 'Criação de Estrutura Offshore',
      description: 'Criação de entidade em paraíso fiscal coincide com pico de saques da Empresa Mãe.',
      score: '0.75',
      type: 'warning'
    }
  ];

  return (
    <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '20px' }}>
        <Search size={20} color="var(--accent-cyan)" />
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Descobertas Recentes</h2>
      </div>

      <div className="alerts-area">
        {alerts.map(alert => (
          <div 
            key={alert.id}
            onClick={() => onSelectEvent(alert.id)}
            style={{
              background: selectedEventId === alert.id ? 'rgba(239, 68, 68, 0.1)' : 'rgba(20, 26, 40, 0.8)',
              borderLeft: `4px solid ${alert.type === 'danger' ? 'var(--accent-danger)' : 'var(--accent-purple)'}`,
              padding: '16px',
              borderRadius: '8px',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              border: selectedEventId === alert.id ? '1px solid var(--accent-danger)' : '1px solid var(--border-color)'
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
              <h3 style={{ fontSize: '0.95rem', color: alert.type === 'danger' ? 'var(--accent-danger)' : 'var(--text-main)', margin: 0 }}>
                {alert.title}
              </h3>
              <span style={{ fontSize: '0.75rem', background: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                ACT-R: {alert.score}
              </span>
            </div>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
              {alert.description}
            </p>
            <div style={{ marginTop: '12px', display: 'flex', gap: '8px', alignItems: 'center', fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
              <FileText size={14} /> <span>1 Fonte Documental (PDF)</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default AlertPanel;
