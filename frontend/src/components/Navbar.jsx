import React from 'react';
import { useBot } from '../context/BotContext';
import { Bot, Cpu, Sparkles, ShieldCheck, AlertCircle, ShieldAlert, Database, Clock, LayoutDashboard, TrendingUp } from 'lucide-react';

export const Navbar = ({ activeTab = 'dashboard', onSelectTab, interventionCount = 0 }) => {
  const { systemHealth, status } = useBot();

  const ollamaProvider = systemHealth?.llm?.providers?.ollama;
  const ollamaOnline = Boolean(
    ollamaProvider?.online ||
    systemHealth?.llm?.online ||
    (systemHealth?.llm?.unified_ready && systemHealth?.llm?.primary_provider === 'ollama')
  );
  const configuredModel =
    ollamaProvider?.configured_model ||
    systemHealth?.llm?.configured_model ||
    'qwen2.5-coder:7b';

  const navItems = [
    { id: 'dashboard', label: 'Bot Dashboard', icon: LayoutDashboard },
    { id: 'analytics', label: 'Funnel & Analytics', icon: TrendingUp },
    { id: 'interventions', label: 'Interventions', icon: ShieldAlert, badge: interventionCount },
    { id: 'vault', label: 'QA Vault', icon: Database },
    { id: 'scheduler', label: 'Scheduler', icon: Clock },
  ];

  return (
    <header style={{
      borderBottom: '1px solid var(--border-color)',
      background: 'rgba(10, 13, 20, 0.85)',
      backdropFilter: 'blur(12px)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      padding: '12px 28px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: '16px',
      flexWrap: 'wrap'
    }}>
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', cursor: 'pointer' }} onClick={() => onSelectTab && onSelectTab('dashboard')}>
        <div style={{
          width: '38px',
          height: '38px',
          borderRadius: '10px',
          background: 'linear-gradient(135deg, #0284c7 0%, #38bdf8 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          boxShadow: '0 0 16px rgba(56, 189, 248, 0.4)'
        }}>
          <Bot size={22} color="#ffffff" />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h1 style={{ fontSize: '1.2rem', fontWeight: '700', letterSpacing: '-0.02em' }}>
              AutoApply<span style={{ color: 'var(--primary)' }}>Jobs</span>
            </h1>
            <span style={{
              fontSize: '0.68rem',
              padding: '2px 8px',
              borderRadius: '999px',
              background: 'rgba(56, 189, 248, 0.15)',
              color: 'var(--primary)',
              fontWeight: '600'
            }}>
              AUTONOMOUS AI
            </span>
          </div>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
            Enterprise Agent with Local AI & Scheduler
          </p>
        </div>
      </div>

      {/* Navigation Tabs */}
      <nav style={{
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        background: 'var(--bg-input)',
        padding: '4px',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-color)'
      }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab && onSelectTab(item.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '6px 14px',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                background: isActive ? 'var(--primary-dark)' : 'transparent',
                color: isActive ? '#ffffff' : 'var(--text-secondary)',
                fontSize: '0.85rem',
                fontWeight: isActive ? 600 : 500,
                cursor: 'pointer',
                transition: 'all 0.15s ease',
                position: 'relative'
              }}
            >
              <Icon size={15} />
              <span>{item.label}</span>
              {Boolean(item.badge) && item.badge > 0 && (
                <span style={{
                  padding: '1px 6px',
                  borderRadius: '999px',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  background: 'var(--danger)',
                  color: '#fff',
                  marginLeft: '2px'
                }}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* System Status Indicators */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {/* Ollama Status */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          background: 'rgba(15, 23, 42, 0.6)',
          padding: '6px 12px',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-color)',
          fontSize: '0.8rem'
        }}>
          <Cpu size={15} color={ollamaOnline ? '#34d399' : '#f87171'} />
          <span style={{ color: 'var(--text-secondary)' }}>Ollama:</span>
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontWeight: '600',
            color: ollamaOnline ? '#34d399' : '#f87171'
          }}>
            {ollamaOnline ? configuredModel : 'Offline'}
          </span>
          <span style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            backgroundColor: ollamaOnline ? '#10b981' : '#ef4444',
            boxShadow: ollamaOnline ? '0 0 8px #10b981' : '0 0 8px #ef4444'
          }} className={ollamaOnline ? 'pulse' : ''} />
        </div>

        {/* Global Bot Status Badge */}
        <div className={`badge badge-${status.state.toLowerCase()}`}>
          <span style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            backgroundColor: 'currentColor'
          }} />
          {status.state}
        </div>
      </div>
    </header>
  );
};
