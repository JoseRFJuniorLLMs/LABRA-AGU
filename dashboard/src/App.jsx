import React, { useState } from 'react';
import {
  Activity, Shield, Send, Network, Bell, Cpu,
  Database, ChevronRight
} from 'lucide-react';
import DirectiveForm from './components/DirectiveForm';
import RelationGraph from './components/RelationGraph';
import AlertFeed from './components/AlertFeed';
import Timeline from './components/Timeline';
import AlertPanel from './components/AlertPanel';
import CausalGraph from './components/CausalGraph';

const TABS = [
  { id: 'alertas',   label: 'Alertas de Fraude',       icon: Bell,     badge: 2 },
  { id: 'mapa',      label: 'Mapa de Relações',         icon: Network,  badge: null },
  { id: 'diretriz',  label: 'Emitir Diretriz',          icon: Send,     badge: null },
  { id: 'explorer',  label: 'Heraclitus Explorer',      icon: Activity, badge: null },
];

const events = [
  { id: 'E1', date: '2022-01-15', title: 'Empresa Mãe criada', type: 'info', pos: 8 },
  { id: 'E2', date: '2023-06-20', title: 'Devedor torna-se sócio', type: 'info', pos: 28 },
  { id: 'E3', date: '2025-11-05', title: 'Offshore X constituída', type: 'info', pos: 55 },
  { id: 'E4', date: '2026-06-02', title: 'Alerta: Triangulação Societária', type: 'danger', pos: 80 },
  { id: 'E5', date: '2026-06-10', title: 'Diretriz #4421 Emitida', type: 'info', pos: 95 },
];

function App() {
  const [activeTab, setActiveTab] = useState('alertas');
  const [selectedEventId, setSelectedEventId] = useState('E4');

  return (
    <div className="app-shell">
      {/* Header */}
      <div>
        <header className="app-header">
          <div className="header-brand">
            <div className="header-logo-icon">
              <Shield size={18} color="white" />
            </div>
            <div>
              <h1>LABRA — AGU</h1>
              <div className="subtitle">Laboratório de Recuperação de Ativos · Sistema Pericial de IA</div>
            </div>
          </div>
          <div className="header-status">
            <div className="status-badge">
              <div className="status-dot" />
              Motor ACT-R Online
            </div>
            <div className="status-badge">
              <Database size={12} />
              HeraclitusDB · gRPC :7474
            </div>
            <div className="status-badge">
              <Cpu size={12} />
              Daemon Ativo
            </div>
          </div>
        </header>

        {/* Nav Tabs */}
        <nav className="nav-tabs">
          {TABS.map(tab => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                id={`tab-${tab.id}`}
                className={`nav-tab ${activeTab === tab.id ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.id)}
              >
                <Icon size={14} />
                {tab.label}
                {tab.badge && <span className="tab-badge">{tab.badge}</span>}
              </button>
            );
          })}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.72rem', color: 'var(--text-muted)', paddingRight: '4px' }}>
            <ChevronRight size={12} />
            {TABS.find(t => t.id === activeTab)?.label}
          </div>
        </nav>
      </div>

      {/* Main Content */}
      <div style={{ padding: '16px 20px 20px', overflow: 'hidden', height: '100%', display: 'flex', flexDirection: 'column' }}>

        {/* ALERTAS */}
        {activeTab === 'alertas' && (
          <AlertFeed />
        )}

        {/* MAPA DE RELAÇÕES */}
        {activeTab === 'mapa' && (
          <div className="glass-panel" style={{ flex: 1, overflow: 'hidden', padding: '0', position: 'relative' }}>
            <div style={{
              position: 'absolute', top: '16px', left: '20px', zIndex: 10,
              display: 'flex', alignItems: 'center', gap: '10px'
            }}>
              <Network size={18} color="var(--accent-cyan)" />
              <h2 style={{ fontSize: '0.95rem', fontWeight: 600 }}>Mapa de Relações — Grafo Causal</h2>
            </div>
            <div style={{ height: '100%', paddingTop: '52px' }}>
              <RelationGraph />
            </div>
          </div>
        )}

        {/* DIRETRIZ */}
        {activeTab === 'diretriz' && (
          <DirectiveForm />
        )}

        {/* HERACLITUS EXPLORER */}
        {activeTab === 'explorer' && (
          <div className="explorer-layout">
            <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
              <div className="panel-header">
                <Bell size={18} color="var(--accent-danger)" />
                <h2>Descobertas Recentes</h2>
              </div>
              <AlertPanel selectedEventId={selectedEventId} onSelectEvent={setSelectedEventId} />
            </div>

            <div className="glass-panel canvas-area">
              <h2>Geometria Causal (Manifold Visual)</h2>
              <CausalGraph selectedEventId={selectedEventId} />
            </div>

            <div className="glass-panel timeline-area">
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Activity size={18} color="var(--accent-cyan)" />
                <h2 style={{ fontSize: '0.95rem', fontWeight: 600 }}>Rio de Eventos (Log Imutável)</h2>
              </div>
              <div className="timeline-track">
                {events.map(event => (
                  <div
                    key={event.id}
                    className={`timeline-event ${event.type} ${selectedEventId === event.id ? 'active' : ''}`}
                    style={{ left: `${event.pos}%` }}
                    onClick={() => setSelectedEventId(event.id)}
                  >
                    <div className="timeline-tooltip">
                      <strong style={{ color: event.type === 'danger' ? 'var(--accent-danger)' : 'var(--text-main)' }}>
                        {event.date}
                      </strong>
                      <br />
                      {event.title}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
