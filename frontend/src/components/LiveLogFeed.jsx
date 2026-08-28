import React, { useState, useRef, useEffect } from 'react';
import { useBot } from '../context/BotContext';
import { 
  Terminal, 
  Trash2, 
  ArrowDownCircle, 
  Filter, 
  CheckCircle2, 
  AlertTriangle, 
  XCircle, 
  Info 
} from 'lucide-react';

export const LiveLogFeed = () => {
  const { logs } = useBot();
  const [filterLevel, setFilterLevel] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const logEndRef = useRef(null);

  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const filteredLogs = logs.filter((log) => {
    if (filterLevel !== 'ALL' && log.level !== filterLevel) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      return (
        log.message.toLowerCase().includes(q) ||
        (log.platform && log.platform.toLowerCase().includes(q))
      );
    }
    return true;
  });

  const getLevelColor = (level) => {
    switch (level) {
      case 'SUCCESS': return '#34d399';
      case 'WARNING': return '#fbbf24';
      case 'ERROR': return '#f87171';
      case 'ACTION': return '#38bdf8';
      default: return '#94a3b8';
    }
  };

  return (
    <div className="glass-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', height: '480px' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            padding: '8px',
            borderRadius: 'var(--radius-md)',
            background: 'rgba(16, 185, 129, 0.15)',
            color: 'var(--success)'
          }}>
            <Terminal size={20} />
          </div>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '600' }}>Live Action Logs</h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Real-time browser activity & LLM decision streaming
            </p>
          </div>
        </div>

        {/* Filter Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <input 
            type="text" 
            placeholder="Filter logs..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{
              padding: '6px 12px',
              fontSize: '0.75rem',
              background: 'var(--bg-input)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              outline: 'none'
            }}
          />

          <select 
            value={filterLevel}
            onChange={(e) => setFilterLevel(e.target.value)}
            style={{
              padding: '6px 10px',
              fontSize: '0.75rem',
              background: 'var(--bg-input)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-primary)',
              outline: 'none',
              cursor: 'pointer'
            }}
          >
            <option value="ALL">All Levels</option>
            <option value="INFO">Info</option>
            <option value="ACTION">Action</option>
            <option value="SUCCESS">Success</option>
            <option value="WARNING">Warning</option>
            <option value="ERROR">Error</option>
          </select>

          <button 
            onClick={() => setAutoScroll(!autoScroll)}
            className="btn btn-outline"
            style={{
              padding: '6px 10px',
              fontSize: '0.75rem',
              color: autoScroll ? 'var(--primary)' : 'var(--text-muted)'
            }}
            title={autoScroll ? 'Auto-scroll enabled' : 'Auto-scroll disabled'}
          >
            <ArrowDownCircle size={14} />
          </button>
        </div>
      </div>

      {/* Terminal Output */}
      <div style={{
        flex: 1,
        background: '#05070a',
        borderRadius: 'var(--radius-md)',
        border: '1px solid rgba(255, 255, 255, 0.05)',
        padding: '14px',
        overflowY: 'auto',
        fontFamily: 'var(--font-mono)',
        fontSize: '0.8125rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px'
      }}>
        {filteredLogs.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', textAlign: 'center', marginTop: '40px' }}>
            No logs to display yet. Start the bot or perform an action.
          </div>
        ) : (
          filteredLogs.map((log, idx) => (
            <div 
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '8px',
                lineHeight: '1.4',
                color: '#e2e8f0',
                wordBreak: 'break-word'
              }}
            >
              <span style={{ color: '#64748b', fontSize: '0.75rem', flexShrink: 0 }}>
                [{log.timestamp}]
              </span>

              {log.platform && (
                <span style={{
                  color: 'var(--primary)',
                  fontSize: '0.75rem',
                  fontWeight: '600',
                  flexShrink: 0
                }}>
                  [{log.platform}]
                </span>
              )}

              <span style={{
                color: getLevelColor(log.level),
                fontWeight: '600',
                fontSize: '0.75rem',
                flexShrink: 0
              }}>
                {log.level}:
              </span>

              <span style={{ color: log.level === 'SUCCESS' ? '#34d399' : log.level === 'ERROR' ? '#f87171' : '#f1f5f9' }}>
                {log.message}
              </span>
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  );
};
