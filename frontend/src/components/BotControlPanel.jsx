import React, { useState, useEffect } from 'react';
import { useBot } from '../context/BotContext';
import { botAPI } from '../services/api';
import { 
  Play, 
  Pause, 
  Square, 
  Settings2, 
  Sliders, 
  ShieldCheck, 
  Search, 
  MapPin, 
  Briefcase,
  Eye, 
  EyeOff, 
  FileCheck,
  AlertCircle
} from 'lucide-react';

export const BotControlPanel = () => {
  const { status, profile, systemHealth, refreshStatus } = useBot();

  const [keywords, setKeywords] = useState('Full Stack Developer');
  const [location, setLocation] = useState('Remote');
  const [experience, setExperience] = useState(3);
  const [maxApplications, setMaxApplications] = useState(25);
  const [cooldown, setCooldown] = useState(15);
  const [headless, setHeadless] = useState(false);
  const [dryRun, setDryRun] = useState(false);

  // Sync with parsed profile experience if available
  useEffect(() => {
    if (profile?.years_of_experience) {
      setExperience(Math.round(profile.years_of_experience));
    }
  }, [profile]);

  const [platforms, setPlatforms] = useState({
    LinkedIn: true,
    Naukri: true,
    Indeed: true,
    Dindin: true,
  });

  const [loading, setLoading] = useState(false);

  const isRunning = status.state === 'Running';
  const isPaused = status.state === 'Paused';
  const isIdle = status.state === 'Idle' || status.state === 'Stopped';

  const handleTogglePlatform = (p) => {
    setPlatforms(prev => ({ ...prev, [p]: !prev[p] }));
  };

  const handleStart = async () => {
    if (!profile) {
      alert('Please upload a resume before starting the bot.');
      return;
    }

    const selectedPlatforms = Object.keys(platforms).filter(p => platforms[p]);
    if (selectedPlatforms.length === 0) {
      alert('Please select at least one platform to target.');
      return;
    }

    try {
      setLoading(true);
      const config = {
        keywords,
        location,
        experience_years: experience !== '' ? parseInt(experience, 10) : null,
        platforms: selectedPlatforms,
        max_applications: parseInt(maxApplications, 10),
        cooldown_seconds: parseFloat(cooldown),
        headless,
        dry_run: dryRun,
      };

      await botAPI.startBot(config);
      await refreshStatus();
    } catch (err) {
      alert('Failed to start bot: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const handlePause = async () => {
    try {
      setLoading(true);
      await botAPI.pauseBot();
      await refreshStatus();
    } catch (err) {
      alert('Failed to pause: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleResume = async () => {
    try {
      setLoading(true);
      await botAPI.resumeBot();
      await refreshStatus();
    } catch (err) {
      alert('Failed to resume: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    try {
      setLoading(true);
      await botAPI.stopBot();
      await refreshStatus();
    } catch (err) {
      alert('Failed to stop: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const creds = systemHealth?.credentials_configured || {};

  return (
    <div className="glass-card" style={{ padding: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            padding: '8px',
            borderRadius: 'var(--radius-md)',
            background: 'rgba(129, 140, 248, 0.15)',
            color: 'var(--secondary)'
          }}>
            <Sliders size={20} />
          </div>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '600' }}>Search & Bot Configuration</h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Configure job parameters, target platforms, and stealth options
            </p>
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
        {/* Keywords */}
        <div className="form-group">
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Search size={14} color="var(--primary)" /> Job Title / Keywords
          </label>
          <input 
            className="form-input" 
            placeholder="e.g. Full Stack Developer, Python"
            value={keywords} 
            onChange={(e) => setKeywords(e.target.value)}
            disabled={!isIdle}
          />
        </div>

        {/* Location */}
        <div className="form-group">
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <MapPin size={14} color="var(--primary)" /> Location
          </label>
          <input 
            className="form-input" 
            placeholder="e.g. Remote, New York, Bengaluru"
            value={location} 
            onChange={(e) => setLocation(e.target.value)}
            disabled={!isIdle}
          />
        </div>

        {/* Experience */}
        <div className="form-group">
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Briefcase size={14} color="var(--primary)" /> Experience (Years)
          </label>
          <input 
            type="number"
            min="0"
            max="30"
            step="1"
            className="form-input" 
            placeholder="e.g. 3"
            value={experience} 
            onChange={(e) => setExperience(e.target.value)}
            disabled={!isIdle}
          />
        </div>

        {/* Max Applications */}
        <div className="form-group">
          <label className="form-label">Max Applications</label>
          <input 
            type="number"
            min="1"
            max="100"
            className="form-input" 
            value={maxApplications} 
            onChange={(e) => setMaxApplications(e.target.value)}
            disabled={!isIdle}
          />
        </div>

        {/* Cooldown */}
        <div className="form-group">
          <label className="form-label">Cooldown Between Jobs (sec)</label>
          <input 
            type="number"
            min="5"
            max="120"
            className="form-input" 
            value={cooldown} 
            onChange={(e) => setCooldown(e.target.value)}
            disabled={!isIdle}
          />
        </div>
      </div>

      {/* Target Platforms Checkboxes */}
      <div style={{ marginTop: '16px', marginBottom: '20px' }}>
        <label className="form-label" style={{ display: 'block', marginBottom: '10px' }}>
          Target Job Platforms
        </label>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px' }}>
          {['LinkedIn', 'Naukri', 'Indeed', 'Dindin'].map((p) => {
            const hasCreds = creds[p];
            return (
              <div 
                key={p}
                onClick={() => isIdle && handleTogglePlatform(p)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '12px 14px',
                  borderRadius: 'var(--radius-md)',
                  background: platforms[p] ? 'rgba(56, 189, 248, 0.08)' : 'rgba(15, 23, 42, 0.5)',
                  border: `1px solid ${platforms[p] ? 'rgba(56, 189, 248, 0.35)' : 'var(--border-color)'}`,
                  cursor: isIdle ? 'pointer' : 'default',
                  transition: 'all 0.2s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <input 
                    type="checkbox"
                    checked={platforms[p]}
                    onChange={() => {}} // handled by parent div
                    disabled={!isIdle}
                    style={{ accentColor: 'var(--primary)', cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: '0.875rem', fontWeight: '600' }}>{p}</span>
                </div>

                <span style={{
                  fontSize: '0.68rem',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  background: hasCreds ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.15)',
                  color: hasCreds ? 'var(--success)' : 'var(--text-muted)'
                }}>
                  {hasCreds ? 'Ready' : 'No .env'}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Advanced Toggles (Headless & Dry Run) */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '20px',
        padding: '14px 16px',
        background: 'rgba(15, 23, 42, 0.4)',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-color)',
        marginBottom: '24px'
      }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: isIdle ? 'pointer' : 'default', fontSize: '0.8125rem' }}>
          <input 
            type="checkbox" 
            checked={headless} 
            onChange={(e) => setHeadless(e.target.checked)} 
            disabled={!isIdle}
            style={{ accentColor: 'var(--primary)' }}
          />
          <span><strong>Headless Mode</strong> (Runs silently in background)</span>
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: isIdle ? 'pointer' : 'default', fontSize: '0.8125rem' }}>
          <input 
            type="checkbox" 
            checked={dryRun} 
            onChange={(e) => setDryRun(e.target.checked)} 
            disabled={!isIdle}
            style={{ accentColor: 'var(--warning)' }}
          />
          <span><strong style={{ color: '#fbbf24' }}>Dry Run Mode</strong> (Fill forms but do NOT click final submit)</span>
        </label>
      </div>

      {/* Control Actions Bar */}
      <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
        {isIdle && (
          <button 
            onClick={handleStart} 
            disabled={loading || !profile}
            className="btn btn-primary"
            style={{ padding: '12px 28px', fontSize: '0.95rem' }}
          >
            <Play size={18} fill="currentColor" /> Start Auto-Apply Bot
          </button>
        )}

        {isRunning && (
          <>
            <button 
              onClick={handlePause} 
              disabled={loading}
              className="btn btn-warning"
              style={{ padding: '12px 24px' }}
            >
              <Pause size={18} fill="currentColor" /> Pause Bot
            </button>

            <button 
              onClick={handleStop} 
              disabled={loading}
              className="btn btn-danger"
              style={{ padding: '12px 24px' }}
            >
              <Square size={18} fill="currentColor" /> Stop Bot
            </button>
          </>
        )}

        {isPaused && (
          <>
            <button 
              onClick={handleResume} 
              disabled={loading}
              className="btn btn-success"
              style={{ padding: '12px 24px' }}
            >
              <Play size={18} fill="currentColor" /> Resume Execution
            </button>

            <button 
              onClick={handleStop} 
              disabled={loading}
              className="btn btn-danger"
              style={{ padding: '12px 24px' }}
            >
              <Square size={18} fill="currentColor" /> Stop Bot
            </button>
          </>
        )}
      </div>
    </div>
  );
};
