import React, { useState, useEffect } from 'react';
import { useBot } from '../context/BotContext';
import { botAPI, naukriAPI } from '../services/api';
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
  AlertCircle,
  Clock,
  Zap,
  Sparkles,
  CheckCircle2,
  DollarSign,
  Compass,
  Flame,
  Save,
  RotateCcw,
  Check
} from 'lucide-react';

const BOT_CONFIG_STORAGE_KEY = 'autoapply_bot_config';

const DEFAULT_BOT_CONFIG = {
  keywords: 'Full Stack Developer',
  location: 'Remote',
  experience: 3,
  maxApplications: 25,
  cooldown: 15,
  freshnessDays: 3,
  quickApplyOnly: true,
  minMatchScore: 60,
  matchGatingMode: 'observe',
  headless: false,
  dryRun: false,
  minSalary: '12',
  salaryCurrency: 'INR',
  allowedLocations: 'Remote, Bengaluru, Hyderabad, Pune',
  prohibitedLocations: '',
  strictSalary: false,
  strictLocation: false,
  platforms: {
    LinkedIn: true,
    Naukri: true,
    Indeed: true,
    Dindin: true,
  }
};

const getInitialBotConfig = () => {
  try {
    const raw = localStorage.getItem(BOT_CONFIG_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      return { 
        ...DEFAULT_BOT_CONFIG, 
        ...parsed, 
        platforms: { ...DEFAULT_BOT_CONFIG.platforms, ...(parsed.platforms || {}) } 
      };
    }
  } catch (err) {
    console.error('Error loading bot config from localStorage:', err);
  }
  return DEFAULT_BOT_CONFIG;
};

export const BotControlPanel = () => {
  const { status, profile, systemHealth, refreshStatus } = useBot();

  const initialConfig = React.useMemo(() => getInitialBotConfig(), []);

  const [keywords, setKeywords] = useState(initialConfig.keywords);
  const [location, setLocation] = useState(initialConfig.location);
  const [experience, setExperience] = useState(initialConfig.experience);
  const [maxApplications, setMaxApplications] = useState(initialConfig.maxApplications);
  const [cooldown, setCooldown] = useState(initialConfig.cooldown);
  const [freshnessDays, setFreshnessDays] = useState(initialConfig.freshnessDays);
  const [quickApplyOnly, setQuickApplyOnly] = useState(initialConfig.quickApplyOnly);
  const [minMatchScore, setMinMatchScore] = useState(initialConfig.minMatchScore);
  const [matchGatingMode, setMatchGatingMode] = useState(initialConfig.matchGatingMode);
  const [headless, setHeadless] = useState(initialConfig.headless);
  const [dryRun, setDryRun] = useState(initialConfig.dryRun);

  // Compensation & Location Sanity Gating State
  const [minSalary, setMinSalary] = useState(initialConfig.minSalary);
  const [salaryCurrency, setSalaryCurrency] = useState(initialConfig.salaryCurrency);
  const [allowedLocations, setAllowedLocations] = useState(initialConfig.allowedLocations);
  const [prohibitedLocations, setProhibitedLocations] = useState(initialConfig.prohibitedLocations);
  const [strictSalary, setStrictSalary] = useState(initialConfig.strictSalary);
  const [strictLocation, setStrictLocation] = useState(initialConfig.strictLocation);

  const [platforms, setPlatforms] = useState(initialConfig.platforms);
  const [saveStatus, setSaveStatus] = useState(null); // null | 'saved' | 'reset'

  // Naukri Profile Headline & Booster State
  const [naukriHeadline, setNaukriHeadline] = useState('');
  const [updatingHeadline, setUpdatingHeadline] = useState(false);
  const [headlineMsg, setHeadlineMsg] = useState(null);
  const [boostingNaukri, setBoostingNaukri] = useState(false);
  const [boostMsg, setBoostMsg] = useState(null);

  // Auto-persist changes to localStorage whenever any parameter is modified
  useEffect(() => {
    const configToPersist = {
      keywords,
      location,
      experience,
      maxApplications,
      cooldown,
      freshnessDays,
      quickApplyOnly,
      minMatchScore,
      matchGatingMode,
      headless,
      dryRun,
      minSalary,
      salaryCurrency,
      allowedLocations,
      prohibitedLocations,
      strictSalary,
      strictLocation,
      platforms,
    };
    try {
      localStorage.setItem(BOT_CONFIG_STORAGE_KEY, JSON.stringify(configToPersist));
    } catch (err) {
      console.error('Failed to auto-save bot config to localStorage:', err);
    }
  }, [
    keywords, location, experience, maxApplications, cooldown, freshnessDays,
    quickApplyOnly, minMatchScore, matchGatingMode, headless, dryRun, minSalary,
    salaryCurrency, allowedLocations, prohibitedLocations, strictSalary, strictLocation, platforms
  ]);

  const handleSaveDefaultsManually = () => {
    const configToPersist = {
      keywords,
      location,
      experience,
      maxApplications,
      cooldown,
      freshnessDays,
      quickApplyOnly,
      minMatchScore,
      matchGatingMode,
      headless,
      dryRun,
      minSalary,
      salaryCurrency,
      allowedLocations,
      prohibitedLocations,
      strictSalary,
      strictLocation,
      platforms,
    };
    try {
      localStorage.setItem(BOT_CONFIG_STORAGE_KEY, JSON.stringify(configToPersist));
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (err) {
      console.error('Failed to save defaults:', err);
    }
  };

  const handleResetDefaults = () => {
    setKeywords(DEFAULT_BOT_CONFIG.keywords);
    setLocation(DEFAULT_BOT_CONFIG.location);
    setExperience(DEFAULT_BOT_CONFIG.experience);
    setMaxApplications(DEFAULT_BOT_CONFIG.maxApplications);
    setCooldown(DEFAULT_BOT_CONFIG.cooldown);
    setFreshnessDays(DEFAULT_BOT_CONFIG.freshnessDays);
    setQuickApplyOnly(DEFAULT_BOT_CONFIG.quickApplyOnly);
    setMinMatchScore(DEFAULT_BOT_CONFIG.minMatchScore);
    setMatchGatingMode(DEFAULT_BOT_CONFIG.matchGatingMode);
    setHeadless(DEFAULT_BOT_CONFIG.headless);
    setDryRun(DEFAULT_BOT_CONFIG.dryRun);
    setMinSalary(DEFAULT_BOT_CONFIG.minSalary);
    setSalaryCurrency(DEFAULT_BOT_CONFIG.salaryCurrency);
    setAllowedLocations(DEFAULT_BOT_CONFIG.allowedLocations);
    setProhibitedLocations(DEFAULT_BOT_CONFIG.prohibitedLocations);
    setStrictSalary(DEFAULT_BOT_CONFIG.strictSalary);
    setStrictLocation(DEFAULT_BOT_CONFIG.strictLocation);
    setPlatforms(DEFAULT_BOT_CONFIG.platforms);

    try {
      localStorage.setItem(BOT_CONFIG_STORAGE_KEY, JSON.stringify(DEFAULT_BOT_CONFIG));
      setSaveStatus('reset');
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (err) {
      // ignore
    }
  };

  // Sync with parsed profile experience and headline if available and not explicitly customized
  useEffect(() => {
    if (profile) {
      if (profile.years_of_experience && !localStorage.getItem(BOT_CONFIG_STORAGE_KEY)) {
        setExperience(Math.round(profile.years_of_experience));
      }
      if (profile.work_experience?.length > 0 && profile.skills?.length > 0) {
        const title = profile.work_experience[0].title || 'Software Engineer';
        const topSkills = profile.skills.slice(0, 4).join(' | ');
        setNaukriHeadline(`${title} | ${topSkills}`);
      } else if (profile.summary) {
        setNaukriHeadline(profile.summary.slice(0, 100));
      }
    }
  }, [profile]);

  const [loading, setLoading] = useState(false);
  const [preflightResult, setPreflightResult] = useState(null);
  const [checkingPreflight, setCheckingPreflight] = useState(false);

  const isRunning = status.state === 'Running';
  const isPaused = status.state === 'Paused';
  const isIdle = status.state === 'Idle' || status.state === 'Stopped';

  const handleTogglePlatform = (p) => {
    setPlatforms(prev => ({ ...prev, [p]: !prev[p] }));
  };

  const handleRunPreflight = async () => {
    const selectedPlatforms = Object.keys(platforms).filter(p => platforms[p]);
    setCheckingPreflight(true);
    try {
      const res = await botAPI.runPreflight({
        keywords,
        location,
        experience_years: experience ? parseInt(experience, 10) : null,
        platforms: selectedPlatforms,
        max_applications: parseInt(maxApplications, 10) || 25,
        cooldown_seconds: parseInt(cooldown, 10) || 15,
        freshness_days: freshnessDays,
        quick_apply_only: quickApplyOnly,
        min_match_score: parseInt(minMatchScore, 10) || 60,
        match_gating_mode: matchGatingMode,
        min_salary: minSalary ? parseFloat(minSalary) : null,
        salary_currency: salaryCurrency,
        allowed_locations: allowedLocations.split(',').map(s => s.trim()).filter(Boolean),
        prohibited_locations: prohibitedLocations.split(',').map(s => s.trim()).filter(Boolean),
        strict_salary_enforcement: strictSalary,
        strict_location_enforcement: strictLocation,
        headless,
        dry_run: dryRun,
      });
      setPreflightResult(res);
    } catch (err) {
      console.error('Preflight check failed:', err);
      setPreflightResult({
        overall: 'FAILED',
        passed: false,
        checks: {
          system: { status: 'error', message: err.response?.data?.detail || err.message }
        }
      });
    } finally {
      setCheckingPreflight(false);
    }
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
        freshness_days: freshnessDays !== '' ? parseInt(freshnessDays, 10) : null,
        quick_apply_only: quickApplyOnly,
        min_match_score: parseInt(minMatchScore, 10),
        match_gating_mode: matchGatingMode,
        min_salary: minSalary ? parseFloat(minSalary) : null,
        salary_currency: salaryCurrency,
        allowed_locations: allowedLocations.split(',').map(s => s.trim()).filter(Boolean),
        prohibited_locations: prohibitedLocations.split(',').map(s => s.trim()).filter(Boolean),
        strict_salary_enforcement: strictSalary,
        strict_location_enforcement: strictLocation,
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

  const handleBoostNaukri = async () => {
    setBoostingNaukri(true);
    setBoostMsg(null);
    try {
      const res = await naukriAPI.boostProfile(naukriHeadline || null, false);
      if (res.success) {
        setBoostMsg({
          type: 'success',
          text: `⚡ Active Today Badge Earned! Reach: ${res.result?.recruiter_reach_multiplier || '5.2x (Active Today Badge)'}`
        });
      } else {
        setBoostMsg({
          type: 'error',
          text: res.result?.reason || res.result?.error || 'Could not boost Naukri profile.'
        });
      }
    } catch (err) {
      setBoostMsg({
        type: 'error',
        text: err.response?.data?.detail || err.message
      });
    } finally {
      setBoostingNaukri(false);
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

  const handleUpdateHeadline = async () => {
    const trimmed = (naukriHeadline || '').trim();
    if (!trimmed || trimmed.length < 5 || trimmed.length > 250) {
      alert('Headline must be between 5 and 250 characters.');
      return;
    }

    try {
      setUpdatingHeadline(true);
      setHeadlineMsg(null);
      const res = await botAPI.updateNaukriHeadline(trimmed);
      setHeadlineMsg({ type: 'success', text: res.message || 'Naukri headline updated successfully!' });
    } catch (err) {
      setHeadlineMsg({ type: 'error', text: err.response?.data?.detail || err.message });
    } finally {
      setUpdatingHeadline(false);
    }
  };

  const creds = systemHealth?.credentials_configured || {};

  return (
    <div className="glass-card" style={{ padding: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
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
              Configure job parameters, freshness filters, and platform automation options
            </p>
          </div>
        </div>

        {/* Action Controls & Auto-Save Badge */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {saveStatus === 'saved' && (
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              fontSize: '0.78rem',
              color: '#34d399',
              background: 'rgba(16, 185, 129, 0.12)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              padding: '4px 10px',
              borderRadius: '9999px',
              animation: 'fadeIn 0.2s ease-in-out'
            }}>
              <Check size={13} /> Defaults Saved
            </span>
          )}

          {saveStatus === 'reset' && (
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '5px',
              fontSize: '0.78rem',
              color: '#38bdf8',
              background: 'rgba(56, 189, 248, 0.12)',
              border: '1px solid rgba(56, 189, 248, 0.3)',
              padding: '4px 10px',
              borderRadius: '9999px',
              animation: 'fadeIn 0.2s ease-in-out'
            }}>
              <RotateCcw size={13} /> Reset to Defaults
            </span>
          )}

          <button
            type="button"
            onClick={handleResetDefaults}
            disabled={!isIdle}
            title="Reset all search parameters to default recommendations"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-secondary)',
              fontSize: '0.8rem',
              fontWeight: 500,
              cursor: isIdle ? 'pointer' : 'default',
              transition: 'all 0.2s'
            }}
          >
            <RotateCcw size={13} />
            Reset
          </button>

          <button
            type="button"
            onClick={handleSaveDefaultsManually}
            disabled={!isIdle}
            title="Explicitly save current parameters as your persistent baseline"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              background: 'rgba(56, 189, 248, 0.15)',
              border: '1px solid rgba(56, 189, 248, 0.4)',
              borderRadius: 'var(--radius-sm)',
              color: '#38bdf8',
              fontSize: '0.8rem',
              fontWeight: 600,
              cursor: isIdle ? 'pointer' : 'default',
              transition: 'all 0.2s'
            }}
          >
            <Save size={13} />
            Save Defaults
          </button>
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

        {/* Job Freshness Filter */}
        <div className="form-group">
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Clock size={14} color="var(--primary)" /> Job Freshness
          </label>
          <select
            className="form-input"
            value={freshnessDays ?? ''}
            onChange={(e) => setFreshnessDays(e.target.value === '' ? null : parseInt(e.target.value, 10))}
            disabled={!isIdle}
            style={{ cursor: isIdle ? 'pointer' : 'default' }}
          >
            <option value="">Any Time</option>
            <option value="1">Last 24 Hours</option>
            <option value="3">Last 3 Days (Recommended)</option>
            <option value="7">Last 7 Days</option>
          </select>
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

        {/* Min Match Score */}
        <div className="form-group">
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Zap size={14} color="var(--primary)" /> Min Match Score (%)
          </label>
          <input 
            type="number"
            min="0"
            max="100"
            step="5"
            className="form-input" 
            value={minMatchScore} 
            onChange={(e) => setMinMatchScore(e.target.value)}
            disabled={!isIdle}
          />
        </div>

        {/* Match Gating Mode */}
        <div className="form-group">
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ShieldCheck size={14} color="var(--primary)" /> Match Gating Mode
          </label>
          <select
            className="form-input"
            value={matchGatingMode}
            onChange={(e) => setMatchGatingMode(e.target.value)}
            disabled={!isIdle}
            style={{ cursor: isIdle ? 'pointer' : 'default' }}
          >
            <option value="observe">Observe (Log & Persist, Don't Skip)</option>
            <option value="enforce">Enforce (Skip Jobs Below Min Score)</option>
          </select>
        </div>

        {/* Min Salary & Currency */}
        <div className="form-group">
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <DollarSign size={14} color="var(--primary)" /> Minimum Salary Floor
          </label>
          <div style={{ display: 'flex', gap: '8px' }}>
            <input 
              type="number"
              min="0"
              step="1"
              className="form-input" 
              placeholder="e.g. 12"
              value={minSalary} 
              onChange={(e) => setMinSalary(e.target.value)}
              disabled={!isIdle}
              style={{ flex: 1 }}
            />
            <select
              className="form-input"
              value={salaryCurrency}
              onChange={(e) => setSalaryCurrency(e.target.value)}
              disabled={!isIdle}
              style={{ width: '100px' }}
            >
              <option value="INR">LPA (₹)</option>
              <option value="USD">USD ($)</option>
              <option value="EUR">EUR (€)</option>
            </select>
          </div>
        </div>

        {/* Allowed Locations */}
        <div className="form-group">
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Compass size={14} color="var(--primary)" /> Allowed Cities
          </label>
          <input 
            className="form-input" 
            placeholder="e.g. Remote, Bengaluru, Hyderabad, Pune"
            value={allowedLocations} 
            onChange={(e) => setAllowedLocations(e.target.value)}
            disabled={!isIdle}
          />
        </div>

        {/* Prohibited Locations */}
        <div className="form-group">
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <AlertCircle size={14} color="#f87171" /> Prohibited Cities (Strict Exclusion)
          </label>
          <input 
            className="form-input" 
            placeholder="e.g. Kolkata, Chennai (Comma separated)"
            value={prohibitedLocations} 
            onChange={(e) => setProhibitedLocations(e.target.value)}
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
                    onChange={() => {}}
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

      {/* Advanced Toggles (Quick Apply, Headless & Dry Run) */}
      <div style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: '20px',
        padding: '14px 16px',
        background: 'rgba(15, 23, 42, 0.4)',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--border-color)',
        marginBottom: '20px'
      }}>
        {/* Quick Apply Only */}
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: isIdle ? 'pointer' : 'default', fontSize: '0.8125rem' }}>
          <input 
            type="checkbox" 
            checked={quickApplyOnly} 
            onChange={(e) => setQuickApplyOnly(e.target.checked)} 
            disabled={!isIdle}
            style={{ accentColor: 'var(--primary)' }}
          />
          <span><strong style={{ color: 'var(--primary)' }}>Quick Apply Only</strong> (Skip external ATS portals to prevent getting stuck)</span>
        </label>

        {/* Headless */}
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

        {/* Dry Run */}
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

        {/* Strict Salary Enforcement */}
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: isIdle ? 'pointer' : 'default', fontSize: '0.8125rem' }}>
          <input 
            type="checkbox" 
            checked={strictSalary} 
            onChange={(e) => setStrictSalary(e.target.checked)} 
            disabled={!isIdle}
            style={{ accentColor: 'var(--danger)' }}
          />
          <span><strong style={{ color: '#f87171' }}>Strict Salary Gate</strong> (Hard disqualify jobs below floor)</span>
        </label>

        {/* Strict Location Enforcement */}
        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: isIdle ? 'pointer' : 'default', fontSize: '0.8125rem' }}>
          <input 
            type="checkbox" 
            checked={strictLocation} 
            onChange={(e) => setStrictLocation(e.target.checked)} 
            disabled={!isIdle}
            style={{ accentColor: 'var(--danger)' }}
          />
          <span><strong style={{ color: '#f87171' }}>Strict Location Gate</strong> (Skip on-site roles outside allowed cities)</span>
        </label>
      </div>

      {/* Authenticated Naukri Profile Headline Management & Daily Booster */}
      <div style={{
        padding: '16px 18px',
        background: 'rgba(56, 189, 248, 0.05)',
        borderRadius: 'var(--radius-md)',
        border: '1px solid rgba(56, 189, 248, 0.2)',
        marginBottom: '24px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <label className="form-label" style={{ display: 'flex', alignItems: 'center', gap: '6px', margin: 0 }}>
            <Flame size={15} color="#10b981" /> Naukri Profile Visibility Booster & Headline
          </label>
          <span style={{ fontSize: '0.75rem', color: '#10b981', fontWeight: 600 }}>
            Active Today Rank Bumper
          </span>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          <input 
            className="form-input"
            style={{ flex: 1, minWidth: '240px' }}
            placeholder="e.g. Full Stack Developer | React | Node.js | MongoDB"
            value={naukriHeadline}
            onChange={(e) => setNaukriHeadline(e.target.value)}
            disabled={!isIdle || updatingHeadline || boostingNaukri}
          />
          <button
            type="button"
            className="btn btn-outline"
            onClick={handleUpdateHeadline}
            disabled={!isIdle || updatingHeadline || !naukriHeadline.trim()}
            style={{ whiteSpace: 'nowrap', padding: '10px 16px' }}
          >
            {updatingHeadline ? 'Saving...' : 'Save Headline'}
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleBoostNaukri}
            disabled={!isIdle || boostingNaukri}
            style={{ 
              whiteSpace: 'nowrap', 
              padding: '10px 18px',
              background: 'linear-gradient(135deg, #059669 0%, #10b981 100%)',
              border: 'none',
              boxShadow: '0 0 12px rgba(16, 185, 129, 0.4)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            <Zap size={15} fill="currentColor" />
            {boostingNaukri ? 'Boosting Profile...' : '⚡ Boost Profile Now (Active Today)'}
          </button>
        </div>
        {headlineMsg && (
          <div style={{
            marginTop: '8px',
            fontSize: '0.8rem',
            color: headlineMsg.type === 'success' ? 'var(--success)' : 'var(--danger)',
            display: 'flex',
            alignItems: 'center',
            gap: '6px'
          }}>
            {headlineMsg.type === 'success' ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
            {headlineMsg.text}
          </div>
        )}
        {boostMsg && (
          <div style={{
            marginTop: '8px',
            fontSize: '0.8rem',
            color: boostMsg.type === 'success' ? '#34d399' : '#f87171',
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontWeight: 600
          }}>
            {boostMsg.type === 'success' ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
            {boostMsg.text}
          </div>
        )}
      </div>

      {/* Control Actions Bar */}
      <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', alignItems: 'center' }}>
        {isIdle && (
          <>
            <button 
              onClick={handleStart} 
              disabled={loading || !profile}
              className="btn btn-primary"
              style={{ padding: '12px 28px', fontSize: '0.95rem' }}
            >
              <Play size={18} fill="currentColor" /> Start Auto-Apply Bot
            </button>

            <button
              type="button"
              onClick={handleRunPreflight}
              disabled={checkingPreflight}
              className="btn btn-outline"
              style={{ padding: '12px 20px', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <ShieldCheck size={18} color="var(--primary)" />
              {checkingPreflight ? 'Checking System...' : 'Run Pre-flight Check'}
            </button>
          </>
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

      {/* Pre-flight Validation Results Box */}
      {preflightResult && (
        <div style={{
          marginTop: '20px',
          padding: '16px 20px',
          borderRadius: 'var(--radius-md)',
          background: preflightResult.overall === 'PASSED' 
            ? 'rgba(16, 185, 129, 0.08)' 
            : preflightResult.overall === 'WARNINGS' 
            ? 'rgba(245, 158, 11, 0.08)' 
            : 'rgba(239, 68, 68, 0.08)',
          border: `1px solid ${
            preflightResult.overall === 'PASSED' 
              ? 'rgba(16, 185, 129, 0.3)' 
              : preflightResult.overall === 'WARNINGS' 
              ? 'rgba(245, 158, 11, 0.3)' 
              : 'rgba(239, 68, 68, 0.3)'
          }`
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ShieldCheck size={18} color={
                preflightResult.overall === 'PASSED' ? 'var(--success)' : preflightResult.overall === 'WARNINGS' ? 'var(--warning)' : 'var(--danger)'
              } />
              <strong style={{ fontSize: '0.95rem' }}>Pre-flight Validation Result:</strong>
              <span style={{
                padding: '2px 8px',
                borderRadius: '999px',
                fontSize: '0.75rem',
                fontWeight: '700',
                background: preflightResult.overall === 'PASSED' ? 'rgba(16, 185, 129, 0.2)' : preflightResult.overall === 'WARNINGS' ? 'rgba(245, 158, 11, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                color: preflightResult.overall === 'PASSED' ? 'var(--success)' : preflightResult.overall === 'WARNINGS' ? 'var(--warning)' : 'var(--danger)'
              }}>
                {preflightResult.overall}
              </span>
            </div>
            <button 
              type="button" 
              onClick={() => setPreflightResult(null)} 
              className="btn btn-outline" 
              style={{ padding: '4px 10px', fontSize: '0.75rem' }}
            >
              Dismiss
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '10px' }}>
            {preflightResult.checks?.profile && (
              <div style={{ fontSize: '0.8rem', padding: '8px 12px', borderRadius: '6px', background: 'rgba(255,255,255,0.03)' }}>
                <strong>Candidate Profile:</strong> {preflightResult.checks.profile.message}
              </div>
            )}
            {preflightResult.checks?.storage && (
              <div style={{ fontSize: '0.8rem', padding: '8px 12px', borderRadius: '6px', background: 'rgba(255,255,255,0.03)' }}>
                <strong>Storage:</strong> {preflightResult.checks.storage.message}
              </div>
            )}
            {preflightResult.checks?.llm && (
              <div style={{ fontSize: '0.8rem', padding: '8px 12px', borderRadius: '6px', background: 'rgba(255,255,255,0.03)' }}>
                <strong>LLM Engine:</strong> {preflightResult.checks.llm.message}
              </div>
            )}
            {preflightResult.checks?.platforms && Object.entries(preflightResult.checks.platforms).map(([plat, pInfo]) => (
              <div key={plat} style={{ fontSize: '0.8rem', padding: '8px 12px', borderRadius: '6px', background: 'rgba(255,255,255,0.03)' }}>
                <strong style={{ textTransform: 'capitalize' }}>{plat}:</strong> {pInfo.message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
