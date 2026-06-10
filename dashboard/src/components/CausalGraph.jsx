import React from 'react';
import { User, Briefcase, Globe } from 'lucide-react';

const CausalGraph = ({ selectedEventId }) => {
  // A simple simulated graph visualization for the UI
  // In a real app, we'd use D3.js or react-flow based on HeraclitusDB data
  
  return (
    <div className="glass-panel canvas-area">
      <h2 style={{ position: 'absolute', top: '20px', left: '20px', fontSize: '1.1rem', fontWeight: 600 }}>
        Geometria Causal (Manifold Visual)
      </h2>
      
      {/* Node: Devedor */}
      <div className="node" style={{ left: '15%', top: '40%' }}>
        <User size={24} color="var(--accent-cyan)" />
        <span className="node-label">Devedor<br/><small>CPF: 645...</small></span>
      </div>

      {/* Line Devedor -> Empresa */}
      <div className="line" style={{ left: '15%', top: '40%', width: '30%', transform: 'translate(30px, 30px) rotate(10deg)' }}></div>

      {/* Node: Empresa Mae */}
      <div className="node" style={{ left: '45%', top: '50%' }}>
        <Briefcase size={24} color="var(--text-main)" />
        <span className="node-label">Empresa Mãe<br/><small>CNPJ: 12.345...</small></span>
      </div>

      {/* Line Empresa -> Offshore */}
      <div className={`line ${selectedEventId === 'E4' ? 'danger' : ''}`} 
           style={{ 
             left: '45%', top: '50%', width: '30%', 
             transform: 'translate(30px, 30px) rotate(-20deg)',
             background: selectedEventId === 'E4' ? 'var(--accent-danger)' : 'var(--border-color)',
             boxShadow: selectedEventId === 'E4' ? '0 0 10px var(--accent-danger)' : 'none',
             height: selectedEventId === 'E4' ? '3px' : '2px'
           }}>
      </div>

      {/* Node: Offshore */}
      <div className={`node ${selectedEventId === 'E4' ? 'danger' : ''}`} style={{ left: '75%', top: '30%' }}>
        <Globe size={24} color={selectedEventId === 'E4' ? "var(--accent-danger)" : "var(--accent-purple)"} />
        <span className="node-label" style={{ color: selectedEventId === 'E4' ? "var(--accent-danger)" : "var(--text-muted)" }}>
          Offshore 01<br/><small>Cunhado Adm</small>
        </span>
      </div>
      
      <div style={{ position: 'absolute', bottom: '20px', right: '20px', fontSize: '0.8rem', color: 'var(--text-muted)', background: 'rgba(0,0,0,0.3)', padding: '8px', borderRadius: '6px' }}>
        Distância Hiperbólica (Devedor ↔ Offshore): <b>0.002</b> (Aproximados)
      </div>
    </div>
  );
};

export default CausalGraph;
