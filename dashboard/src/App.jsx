import React, { useState } from 'react';
import { Activity, ShieldAlert, Cpu } from 'lucide-react';
import Timeline from './components/Timeline';
import CausalGraph from './components/CausalGraph';
import AlertPanel from './components/AlertPanel';

function App() {
  const [selectedEventId, setSelectedEventId] = useState('E4');

  // Mock data for the flow, pretending to hit HeraclitusDB REST
  const events = [
    { id: 'E1', date: '2022-01-15', title: 'Empresa Mãe criada', type: 'info', pos: 10 },
    { id: 'E2', date: '2023-06-20', title: 'Devedor torna-se sócio', type: 'info', pos: 35 },
    { id: 'E3', date: '2025-11-05', title: 'Offshore X constituída', type: 'info', pos: 60 },
    { id: 'E4', date: '2026-06-02', title: 'Alerta: Transferência de Quotas Suspeita', type: 'danger', pos: 85 }
  ];

  return (
    <div className="dashboard-container">
      <header>
        <div style={{display: 'flex', alignItems: 'center', gap: '12px'}}>
          <Activity size={28} color="var(--accent-cyan)" />
          <h1>Heraclitus Explorer</h1>
        </div>
        <div style={{display: 'flex', alignItems: 'center', gap: '16px', color: 'var(--text-muted)'}}>
          <span style={{display: 'flex', alignItems: 'center', gap: '6px'}}><Cpu size={18}/> Motor ACT-R: Online</span>
          <span style={{display: 'flex', alignItems: 'center', gap: '6px'}}><ShieldAlert size={18}/> Modo: Rastreamento Forense</span>
        </div>
      </header>

      <AlertPanel selectedEventId={selectedEventId} onSelectEvent={setSelectedEventId} />
      
      <CausalGraph selectedEventId={selectedEventId} />
      
      <Timeline events={events} selectedEventId={selectedEventId} onSelectEvent={setSelectedEventId} />
    </div>
  );
}

export default App;
