import React, { useState, useEffect } from 'react';
import { 
  Clock, 
  Play, 
  Square, 
  RefreshCw, 
  Save, 
  CheckCircle, 
  AlertCircle, 
  Sun, 
  Activity, 
  ShieldCheck,
  Pause,
  Zap
} from 'lucide-react';
import { schedulerAPI } from '../services/api';

export function SchedulerSettings() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [feedback, setFeedback] = useState(null);

  // Config Form State
  const [morningHour, setMorningHour] = useState(9);
  const [morningMinute, setMorningMinute] = useState(0);
  const [refreshHours, setRefreshHours] = useState(6);
  const [dailyCap, setDailyCap] = useState(25);

  const showToast = (msg, type = 'success') => {
    setFeedback({ msg, type });
    setTimeout(() => setFeedback(null), 4000);
  };

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const data = await schedulerAPI.getStatus();
      setStatus(data);
      if (data.daily_stats) {
        setDailyCap(data.daily_stats.daily_cap || 25);
      }
    } catch (err) {
      showToast('Failed to load autonomous scheduler status', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const timer = setInterval(() => {
      schedulerAPI.getStatus().then(setStatus).catch(() => {});
    }, 10000);
    return () => clearInterval(timer);
  }, []);

  const handleStart = async () => {
    setActionLoading(true);
    try {
      const res = await schedulerAPI.start();
      showToast(res.message || 'Scheduler started successfully!', 'success');
      fetchStatus();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to start scheduler', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleStop = async () => {
    setActionLoading(true);
    try {
      const res = await schedulerAPI.stop();
      showToast(res.message || 'Scheduler stopped.', 'info');
      fetchStatus();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to stop scheduler', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSaveConfig = async (e) => {
    e.preventDefault();
    setActionLoading(true);
    try {
      const res = await schedulerAPI.updateConfig({
        morning_hunt_hour: parseInt(morningHour),
        morning_hunt_minute: parseInt(morningMinute),
        headline_refresh_interval_hours: parseInt(refreshHours),
        daily_application_cap: parseInt(dailyCap)
      });
      setStatus(res);
      showToast('Scheduler configuration updated and cron jobs rescheduled!', 'success');
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to update schedule config', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleToggleJob = async (jobId, currentEnabled) => {
    setActionLoading(true);
    try {
      await schedulerAPI.toggleJob(jobId, !currentEnabled);
      showToast(`Job ${jobId} ${!currentEnabled ? 'resumed' : 'paused'}.`, 'success');
      fetchStatus();
    } catch (err) {
      showToast('Failed to toggle job', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const handleTriggerNow = async (jobId) => {
    setActionLoading(true);
    try {
      await schedulerAPI.triggerJob(jobId);
      showToast(`Job '${jobId}' triggered immediately!`, 'success');
      fetchStatus();
    } catch (err) {
      showToast('Failed to trigger job', 'error');
    } finally {
      setActionLoading(false);
    }
  };

  const isRunning = status?.is_running ?? false;
  const appliedToday = status?.daily_stats?.applied_today ?? 0;
  const cap = status?.daily_stats?.daily_cap ?? dailyCap;
  const quotaPercent = Math.min(100, Math.round((appliedToday / (cap || 1)) * 100));

  return (
    <div className="glass-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Toast Feedback */}
      {feedback && (
        <div style={{
          padding: '12px 18px',
          borderRadius: 'var(--radius-md)',
          backgroundColor: feedback.type === 'error' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
          border: `1px solid ${feedback.type === 'error' ? 'var(--danger)' : 'var(--success)'}`,
          color: 'var(--text-primary)',
          fontSize: '0.9rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <span>{feedback.msg}</span>
          <button onClick={() => setFeedback(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>×</button>
        </div>
      )}

      {/* Header & Status Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', borderBottom: '1px solid var(--border-color)', paddingBottom: '16px' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Clock size={22} color="var(--primary)" />
            Autonomous Background Scheduler
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Fully automated daily morning hunts, profile freshness bumps, and persistent session health checks.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Running Status Badge */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            padding: '6px 14px',
            borderRadius: '9999px',
            background: isRunning ? 'rgba(16, 185, 129, 0.15)' : 'rgba(100, 116, 139, 0.15)',
            border: `1px solid ${isRunning ? 'rgba(16, 185, 129, 0.3)' : 'rgba(100, 116, 139, 0.3)'}`,
            color: isRunning ? 'var(--success)' : 'var(--text-muted)',
            fontSize: '0.85rem',
            fontWeight: 600
          }}>
            <span style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: isRunning ? 'var(--success)' : 'var(--text-muted)',
              boxShadow: isRunning ? '0 0 10px var(--success)' : 'none'
            }} />
            {isRunning ? 'SCHEDULER ACTIVE' : 'SCHEDULER STOPPED'}
          </div>

          {isRunning ? (
            <button
              onClick={handleStop}
              disabled={actionLoading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 16px',
                borderRadius: 'var(--radius-md)',
                background: 'rgba(239, 68, 68, 0.2)',
                border: '1px solid var(--danger)',
                color: 'var(--danger)',
                fontWeight: 600,
                fontSize: '0.85rem',
                cursor: 'pointer'
              }}
            >
              <Square size={14} />
              Stop Engine
            </button>
          ) : (
            <button
              onClick={handleStart}
              disabled={actionLoading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '8px 18px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--primary)',
                border: 'none',
                color: '#000',
                fontWeight: 600,
                fontSize: '0.85rem',
                cursor: 'pointer'
              }}
            >
              <Play size={14} />
              Start Engine
            </button>
          )}

          <button
            onClick={fetchStatus}
            disabled={loading}
            style={{
              background: 'transparent',
              border: '1px solid var(--border-color)',
              color: 'var(--text-secondary)',
              borderRadius: 'var(--radius-md)',
              padding: '8px 10px',
              cursor: 'pointer'
            }}
            title="Refresh Status"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* DAILY QUOTA PROGRESS BAR */}
      <div style={{
        background: 'var(--bg-input)',
        border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-md)',
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Activity size={18} color="var(--primary)" />
            <span style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              Daily Application Limit & Safety Quota
            </span>
          </div>
          <span style={{ fontSize: '0.85rem', color: quotaPercent >= 100 ? 'var(--danger)' : 'var(--text-secondary)' }}>
            <strong>{appliedToday}</strong> of <strong>{cap}</strong> submitted today ({quotaPercent}%)
          </span>
        </div>

        <div style={{
          width: '100%',
          height: '10px',
          background: 'rgba(255, 255, 255, 0.05)',
          borderRadius: '9999px',
          overflow: 'hidden'
        }}>
          <div style={{
            width: `${quotaPercent}%`,
            height: '100%',
            background: quotaPercent >= 100 ? 'var(--danger)' : quotaPercent > 75 ? 'var(--warning)' : 'var(--primary)',
            borderRadius: '9999px',
            transition: 'width 0.4s ease'
          }} />
        </div>

        {quotaPercent >= 100 && (
          <div style={{ fontSize: '0.8rem', color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <AlertCircle size={14} />
            Daily safety quota exhausted. The scheduler will automatically resume tomorrow morning to protect your accounts from portal rate limits.
          </div>
        )}
      </div>

      {/* SCHEDULED JOBS CARDS */}
      <div>
        <h3 style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '14px' }}>
          Registered Background Jobs ({status?.jobs?.length || 0})
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '16px' }}>
          {(status?.jobs || []).map((job) => (
            <div
              key={job.id}
              style={{
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)',
                padding: '18px 20px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <h4 style={{ fontSize: '0.95rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {job.id === 'morning_job_hunt' && <Sun size={16} color="var(--warning)" />}
                    {job.id === 'naukri_headline_refresh' && <Zap size={16} color="var(--primary)" />}
                    {job.id === 'session_health_check' && <ShieldCheck size={16} color="var(--success)" />}
                    {job.name}
                  </h4>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Trigger: {job.trigger}
                  </div>
                </div>

                <span style={{
                  padding: '2px 8px',
                  borderRadius: '4px',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  background: job.enabled ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                  color: job.enabled ? 'var(--success)' : 'var(--danger)',
                  border: `1px solid ${job.enabled ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`
                }}>
                  {job.enabled ? 'ACTIVE' : 'PAUSED'}
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                <div>
                  Next execution: <strong>{job.next_run_time ? new Date(job.next_run_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : 'None (Paused)'}</strong>
                </div>
                {job.last_run_time && (
                  <div>
                    Last run: {new Date(job.last_run_time).toLocaleTimeString()} ({job.last_run_status || 'OK'})
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', gap: '8px', marginTop: 'auto', paddingTop: '8px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                <button
                  onClick={() => handleToggleJob(job.id, job.enabled)}
                  disabled={actionLoading || !isRunning}
                  style={{
                    flex: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    padding: '6px 12px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    fontSize: '0.8rem',
                    cursor: isRunning ? 'pointer' : 'not-allowed'
                  }}
                >
                  {job.enabled ? <Pause size={13} /> : <Play size={13} />}
                  {job.enabled ? 'Pause' : 'Resume'}
                </button>

                <button
                  onClick={() => handleTriggerNow(job.id)}
                  disabled={actionLoading || !isRunning}
                  style={{
                    flex: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    padding: '6px 12px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'rgba(56, 189, 248, 0.15)',
                    border: '1px solid rgba(56, 189, 248, 0.3)',
                    color: 'var(--primary)',
                    fontSize: '0.8rem',
                    cursor: isRunning ? 'pointer' : 'not-allowed'
                  }}
                >
                  <Zap size={13} />
                  Run Now
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* SCHEDULE CONFIGURATION FORM */}
      <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '18px' }}>
        <h3 style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '14px' }}>
          Schedule & Quota Settings
        </h3>

        <form onSubmit={handleSaveConfig} style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '16px',
          alignItems: 'flex-end'
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Morning Hunt Time</label>
            <div style={{ display: 'flex', gap: '6px' }}>
              <select
                value={morningHour}
                onChange={(e) => setMorningHour(e.target.value)}
                style={{
                  flex: 1,
                  padding: '9px 10px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-input)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-primary)'
                }}
              >
                {Array.from({ length: 24 }).map((_, h) => (
                  <option key={h} value={h}>{String(h).padStart(2, '0')}:00</option>
                ))}
              </select>
              <select
                value={morningMinute}
                onChange={(e) => setMorningMinute(e.target.value)}
                style={{
                  flex: 1,
                  padding: '9px 10px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'var(--bg-input)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-primary)'
                }}
              >
                {[0, 15, 30, 45].map(m => (
                  <option key={m} value={m}>:{String(m).padStart(2, '0')}</option>
                ))}
              </select>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Headline Refresh Interval</label>
            <select
              value={refreshHours}
              onChange={(e) => setRefreshHours(e.target.value)}
              style={{
                padding: '9px 10px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="2">Every 2 Hours</option>
              <option value="4">Every 4 Hours</option>
              <option value="6">Every 6 Hours (Recommended)</option>
              <option value="8">Every 8 Hours</option>
              <option value="12">Every 12 Hours</option>
              <option value="24">Every 24 Hours</option>
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Daily Application Quota</label>
            <input
              type="number"
              min="1"
              max="200"
              value={dailyCap}
              onChange={(e) => setDailyCap(e.target.value)}
              style={{
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            />
          </div>

          <button
            type="submit"
            disabled={actionLoading}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              padding: '10px 18px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--primary)',
              border: 'none',
              color: '#000',
              fontWeight: 600,
              fontSize: '0.85rem',
              cursor: 'pointer',
              height: '38px'
            }}
          >
            <Save size={15} />
            Apply Settings
          </button>
        </form>
      </div>
    </div>
  );
}
