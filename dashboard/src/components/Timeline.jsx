import React from 'react';
import { History } from 'lucide-react';

const Timeline = ({ events, selectedEventId, onSelectEvent }) => {
  return (
    <div className="glass-panel timeline-area">
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
        <History size={20} color="var(--accent-cyan)" />
        <h2 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Rio de Eventos (Log Imutável)</h2>
      </div>
      
      <div className="timeline-track">
        {events.map(event => (
          <div 
            key={event.id}
            className={`timeline-event ${event.type} ${selectedEventId === event.id ? 'active' : ''}`}
            style={{ left: `${event.pos}%` }}
            onClick={() => onSelectEvent(event.id)}
          >
            <div className="timeline-tooltip">
              <strong style={{ color: event.type === 'danger' ? 'var(--accent-danger)' : 'var(--text-main)' }}>
                {event.date}
              </strong>
              <br/>
              {event.title}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Timeline;
