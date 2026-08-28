import React from 'react';
import { useBot } from '../context/BotContext';
import { botAPI } from '../services/api';
import { 
  CheckCircle2, 
  Clock, 
  AlertTriangle, 
  Send, 
  Layers, 
  ShieldAlert, 
  Play, 
  Zap 
} from 'lucide-react';

export const StatusIndicator = () => {
  const { status, stats, refreshStatus } = useBot();

  const handleResumeAfterCaptcha = async () => {
    try {
      await botAPI.resumeBot();
      await refreshStatus();
    } catch (e) {
      console.error('Error resuming bot:', e);
    }
  };

  const progressPercent = status.total_target > 0 
    ? Math.min(Math.round((status.applied_count / status.total_target) * 100), 100)
    : 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* CAPTCHA / 2FA Action Banner */}
      {status.is_paused_for_captcha && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.2) 0%, rgba(217, 119, 6, 0.3) 100%)',
          border: '1px solid #f59e0b',
          borderRadius: 'var(--radius-lg)',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: '0 0 24px rgba(245, 158, 11, 0.25)',
          animation: 'pulse-dot 2.5s infinite ease-in-out'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div style={{
              width: '42px',
              height: '42px',
              borderRadius: '10px',
              background: '#f59e0b',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center'
            }}>
              <ShieldAlert size={24} color="#000000" />
            </div>
            <div>
              <h4 style={{ color: '#fbbf24', fontSize: '1rem', fontWeight: '700' }}>
                Manual User Action Required
              </h4>
              <p style={{ fontSize: '0.875rem', color: '#fef3c7', marginTop: '2px' }}>
                {status.captcha_message || 'A CAPTCHA or 2FA challenge was detected. Solve it in your browser window, then click Resume.'}
              </p>
            </div>
          </div>
          <button 
            onClick={handleResumeAfterCaptcha}
            className="btn btn-warning"
            style={{ fontWeight: '700', padding: '10px 22px' }}
          >
            <Play size={16} fill="currentColor" />
            Resume Bot Now
          </button>
        </div>
      )}

      {/* Metrics Row */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '16px'
      }}>
        {/* Total Applications Card */}
        <div className="glass-card" style={{ padding: '18px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: '500' }}>
                Total Tracked Applications
              </span>
              <h3 style={{ fontSize: '1.8rem', fontWeight: '700', marginTop: '4px' }}>
                {stats.total_applications}
              </h3>
            </div>
            <div style={{
              padding: '10px',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(56, 189, 248, 0.12)',
              color: 'var(--primary)'
            }}>
              <Send size={20} />
            </div>
          </div>
        </div>

        {/* Successful Applications Card */}
        <div className="glass-card" style={{ padding: '18px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: '500' }}>
                Submitted Successfully
              </span>
              <h3 style={{ fontSize: '1.8rem', fontWeight: '700', marginTop: '4px', color: 'var(--success)' }}>
                {stats.success_count}
              </h3>
            </div>
            <div style={{
              padding: '10px',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(16, 185, 129, 0.12)',
              color: 'var(--success)'
            }}>
              <CheckCircle2 size={20} />
            </div>
          </div>
        </div>

        {/* Manual Review Needed */}
        <div className="glass-card" style={{ padding: '18px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: '500' }}>
                Manual Review Needed
              </span>
              <h3 style={{ fontSize: '1.8rem', fontWeight: '700', marginTop: '4px', color: 'var(--warning)' }}>
                {stats.manual_review_count}
              </h3>
            </div>
            <div style={{
              padding: '10px',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(245, 158, 11, 0.12)',
              color: 'var(--warning)'
            }}>
              <AlertTriangle size={20} />
            </div>
          </div>
        </div>

        {/* Current Active Session Progress */}
        <div className="glass-card" style={{ padding: '18px 20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: '500' }}>
                Active Session Progress
              </span>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginTop: '4px' }}>
                <h3 style={{ fontSize: '1.8rem', fontWeight: '700' }}>
                  {status.applied_count}
                </h3>
                <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>
                  / {status.total_target || 0} Target
                </span>
              </div>
            </div>
            <div style={{
              padding: '10px',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(129, 140, 248, 0.12)',
              color: 'var(--secondary)'
            }}>
              <Zap size={20} />
            </div>
          </div>

          {/* Progress bar */}
          <div style={{
            width: '100%',
            height: '6px',
            background: 'rgba(255, 255, 255, 0.08)',
            borderRadius: '999px',
            marginTop: '12px',
            overflow: 'hidden'
          }}>
            <div style={{
              width: `${progressPercent}%`,
              height: '100%',
              background: 'linear-gradient(90deg, #38bdf8 0%, #10b981 100%)',
              transition: 'width 0.4s ease'
            }} />
          </div>
        </div>
      </div>
    </div>
  );
};
