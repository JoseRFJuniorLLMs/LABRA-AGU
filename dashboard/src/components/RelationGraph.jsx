import React, { useState, useRef } from 'react';
import { User, Briefcase, Globe, Building2, DollarSign } from 'lucide-react';

// Graph data: nodes and edges for the relation map
const GRAPH_NODES = [
  {
    id: 'n1', x: 50, y: 50,
    type: 'person', icon: User,
    label: 'Carlos A. Menezes', sublabel: 'CPF: 645.254.302-49',
    detail: { doc: 'CPF: 645.254.302-49', papel: 'Devedor Principal', risco: 'CRÍTICO' }
  },
  {
    id: 'n2', x: 25, y: 25,
    type: 'person', icon: User,
    label: 'Rita F. Menezes', sublabel: 'Esposa — CPF: 732.891.004-11',
    detail: { doc: 'CPF: 732.891.004-11', papel: 'Cônjuge / Laranja', risco: 'ALTO' }
  },
  {
    id: 'n3', x: 75, y: 25,
    type: 'person', icon: User,
    label: 'Paulo R. Ferreira', sublabel: 'Cunhado — CPF: 019.234.567-88',
    detail: { doc: 'CPF: 019.234.567-88', papel: 'Interposta Pessoa', risco: 'ALTO' }
  },
  {
    id: 'n4', x: 50, y: 75,
    type: 'company', icon: Briefcase,
    label: 'Construtora Alfa Ltda', sublabel: 'CNPJ: 12.345.678/0001-90',
    detail: { doc: 'CNPJ: 12.345.678/0001-90', papel: 'Empresa Principal', risco: 'ALTO' }
  },
  {
    id: 'n5', x: 20, y: 72,
    type: 'company', icon: Building2,
    label: 'Imobiliária Beta S.A.', sublabel: 'CNPJ: 98.765.432/0001-11',
    detail: { doc: 'CNPJ: 98.765.432/0001-11', papel: 'Empresa Laranja', risco: 'ALTO' }
  },
  {
    id: 'n6', x: 82, y: 62,
    type: 'offshore', icon: Globe,
    label: 'Gamma Holdings Ltd', sublabel: 'Ilhas Cayman / BVI',
    detail: { doc: 'Reg: BVI-2023-7742', papel: 'Offshore Controlada', risco: 'CRÍTICO' }
  },
  {
    id: 'n7', x: 82, y: 88,
    type: 'bank', icon: DollarSign,
    label: 'Conta BVI #7742', sublabel: 'R$ 4,2M detectados',
    detail: { doc: 'Bank: Cayman Nat.', papel: 'Destino Final', risco: 'CRÍTICO' }
  },
];

const GRAPH_EDGES = [
  { from: 'n1', to: 'n2', label: 'Cônjuge', color: 'var(--accent-cyan)', width: 2 },
  { from: 'n1', to: 'n3', label: 'Cunhado / Procurador', color: 'var(--accent-danger)', width: 2.5 },
  { from: 'n1', to: 'n4', label: 'Sócio Administrador', color: 'var(--accent-purple)', width: 2 },
  { from: 'n2', to: 'n5', label: 'Sócia 80%', color: 'var(--accent-warning)', width: 1.5 },
  { from: 'n4', to: 'n5', label: 'Transferência Quotas', color: 'var(--accent-danger)', width: 2.5 },
  { from: 'n3', to: 'n6', label: 'Plenos Poderes', color: 'var(--accent-danger)', width: 3 },
  { from: 'n5', to: 'n6', label: 'Aporte Irregular', color: 'var(--accent-danger)', width: 2 },
  { from: 'n6', to: 'n7', label: 'Transferência', color: 'var(--accent-warning)', width: 2 },
];

const NODE_COLORS = {
  person: 'var(--accent-cyan)',
  company: 'var(--accent-purple)',
  offshore: 'var(--accent-danger)',
  bank: 'var(--accent-warning)',
};

const NODE_LABELS = {
  person: 'Pessoa Física',
  company: 'Pessoa Jurídica',
  offshore: 'Offshore / Paraíso Fiscal',
  bank: 'Conta / Ativo',
};

function getNodePos(node, rect) {
  if (!rect) return { x: 0, y: 0 };
  return {
    x: (node.x / 100) * rect.width,
    y: (node.y / 100) * rect.height,
  };
}

const RelationGraph = () => {
  const [hoveredNode, setHoveredNode] = useState(null);
  const [tooltip, setTooltip] = useState({ visible: false, x: 0, y: 0, node: null });
  const containerRef = useRef(null);

  const handleNodeEnter = (node, e) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setHoveredNode(node.id);
    setTooltip({ visible: true, x, y, node });
  };

  const handleNodeLeave = () => {
    setHoveredNode(null);
    setTooltip({ visible: false, x: 0, y: 0, node: null });
  };

  const containerRect = containerRef.current?.getBoundingClientRect();

  // Build edge coordinates
  const edgesWithCoords = GRAPH_EDGES.map(edge => {
    const fromNode = GRAPH_NODES.find(n => n.id === edge.from);
    const toNode = GRAPH_NODES.find(n => n.id === edge.to);
    if (!fromNode || !toNode || !containerRect) return null;
    const from = getNodePos(fromNode, { width: containerRect?.width || 600, height: containerRect?.height || 400 });
    const to = getNodePos(toNode, { width: containerRect?.width || 600, height: containerRect?.height || 400 });
    return { ...edge, x1: from.x, y1: from.y, x2: to.x, y2: to.y };
  }).filter(Boolean);

  return (
    <div className="relation-graph-container" ref={containerRef}>
      {/* SVG Edges */}
      <svg
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
        overflow="visible"
      >
        <defs>
          <marker id="arrow-danger" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 Z" fill="var(--accent-danger)" />
          </marker>
          <marker id="arrow-cyan" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 Z" fill="var(--accent-cyan)" />
          </marker>
          <marker id="arrow-purple" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 Z" fill="var(--accent-purple)" />
          </marker>
          <marker id="arrow-warning" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L0,6 L8,3 Z" fill="var(--accent-warning)" />
          </marker>
        </defs>
        {edgesWithCoords.map((edge, i) => {
          const markerId = edge.color.includes('danger') ? 'arrow-danger'
            : edge.color.includes('purple') ? 'arrow-purple'
            : edge.color.includes('warning') ? 'arrow-warning'
            : 'arrow-cyan';
          const isHighlighted = hoveredNode &&
            (GRAPH_EDGES.find((_, ei) => ei === i)?.from === hoveredNode ||
             GRAPH_EDGES.find((_, ei) => ei === i)?.to === hoveredNode);
          // Midpoint for label
          const mx = (edge.x1 + edge.x2) / 2;
          const my = (edge.y1 + edge.y2) / 2;
          return (
            <g key={i} opacity={hoveredNode && !isHighlighted ? 0.2 : 1} style={{transition:'opacity 0.3s'}}>
              <line
                className="graph-edge"
                x1={edge.x1} y1={edge.y1}
                x2={edge.x2} y2={edge.y2}
                stroke={edge.color}
                strokeWidth={isHighlighted ? edge.width + 1 : edge.width}
                strokeDasharray="5 4"
                markerEnd={`url(#${markerId})`}
                style={{animation:'dash-flow 3s linear infinite'}}
              />
              <text
                x={mx} y={my - 6}
                textAnchor="middle"
                fill="rgba(148, 163, 184, 0.7)"
                fontSize="9"
                style={{pointerEvents:'none'}}
              >
                {edge.label}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Nodes */}
      {GRAPH_NODES.map(node => {
        const pos = { x: node.x, y: node.y };
        const Icon = node.icon;
        const color = NODE_COLORS[node.type];
        const isHigh = node.detail?.risco === 'CRÍTICO';
        return (
          <div
            key={node.id}
            className="graph-node"
            style={{ left: `${pos.x}%`, top: `${pos.y}%` }}
            onMouseEnter={(e) => handleNodeEnter(node, e)}
            onMouseLeave={handleNodeLeave}
          >
            <div
              className={`node-circle type-${node.type} ${isHigh ? 'highlighted' : ''}`}
              style={{
                opacity: hoveredNode && hoveredNode !== node.id ? 0.5 : 1,
                transition: 'all 0.3s',
              }}
            >
              <Icon size={20} color={color} />
            </div>
            <div className="node-label-text">
              <strong>{node.label.split(' ').slice(0, 2).join(' ')}</strong>
              {node.sublabel.split(' ').slice(0,3).join(' ')}
            </div>
          </div>
        );
      })}

      {/* Tooltip */}
      {tooltip.visible && tooltip.node && (
        <div
          className="graph-tooltip"
          style={{
            left: Math.min(tooltip.x + 16, (containerRect?.width || 600) - 220),
            top: Math.min(tooltip.y - 10, (containerRect?.height || 400) - 160),
          }}
        >
          <div className="tooltip-title">{tooltip.node.label}</div>
          <div className="tooltip-row">
            <span>Documento</span>
            <span className="val">{tooltip.node.detail.doc}</span>
          </div>
          <div className="tooltip-row">
            <span>Papel</span>
            <span className="val">{tooltip.node.detail.papel}</span>
          </div>
          <div className="tooltip-row">
            <span>Risco</span>
            <span className="val" style={{
              color: tooltip.node.detail.risco === 'CRÍTICO' ? 'var(--accent-danger)' : 'var(--accent-warning)'
            }}>
              ● {tooltip.node.detail.risco}
            </span>
          </div>
          <div className="tooltip-row" style={{marginTop:'6px',paddingTop:'6px',borderTop:'1px solid var(--border-color)'}}>
            <span style={{fontSize:'0.68rem',color:'var(--accent-purple)'}}>Tipo</span>
            <span className="val" style={{fontSize:'0.7rem'}}>{NODE_LABELS[tooltip.node.type]}</span>
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="graph-legend">
        {Object.entries(NODE_LABELS).map(([type, label]) => (
          <div className="legend-item" key={type}>
            <div className="legend-dot" style={{ background: NODE_COLORS[type] }} />
            {label}
          </div>
        ))}
      </div>

      {/* Distância Hiperbólica */}
      <div style={{
        position: 'absolute', bottom: '16px', right: '16px',
        fontSize: '0.75rem', color: 'var(--text-muted)',
        background: 'rgba(0,0,0,0.5)', padding: '8px 12px',
        borderRadius: '8px', border: '1px solid var(--border-color)',
        backdropFilter: 'blur(8px)'
      }}>
        <div>Entidades mapeadas: <b style={{color:'var(--text-main)'}}>7</b></div>
        <div>Relações detectadas: <b style={{color:'var(--accent-danger)'}}>8</b></div>
        <div style={{marginTop:'3px',fontSize:'0.68rem',color:'var(--accent-cyan)'}}>
          Dist. Hiperbólica (Devedor ↔ Offshore): 0.002
        </div>
      </div>
    </div>
  );
};

export default RelationGraph;
