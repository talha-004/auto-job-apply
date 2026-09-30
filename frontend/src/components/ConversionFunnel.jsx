import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  Award, 
  Send, 
  Calendar, 
  CheckCircle, 
  RefreshCw, 
  Clock, 
  BarChart3, 
  Filter,
  ArrowDown,
  Sparkles,
  Layers
} from 'lucide-react';
import { analyticsAPI, followupAPI } from '../services/api';
import './ConversionFunnel.css';

export function ConversionFunnel() {
  const [funnel, setFunnel] = useState(null);
  const [roi, setRoi] = useState([]);
  const [summary, setSummary] = useState(null);
  const [followups, setFollowups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [approvingId, setApprovingId] = useState(null);
  const [feedback, setFeedback] = useState(null);

  const loadAllAnalytics = async () => {
    setLoading(true);
    try {
      const [fData, roiData, sumData, followData] = await Promise.all([
        analyticsAPI.getFunnel().catch(() => null),
        analyticsAPI.getPlatformROI().catch(() => ({ platforms: [] })),
        analyticsAPI.getSummary().catch(() => null),
        followupAPI.getPending(5).catch(() => ({ followups: [] }))
      ]);

      if (fData) setFunnel(fData);
      if (roiData?.platforms) setRoi(roiData.platforms);
      if (sumData) setSummary(sumData);
      if (followData?.followups) setFollowups(followData.followups);
    } catch (err) {
      console.error('Failed to load conversion analytics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllAnalytics();
  }, []);

  const handleApproveFollowup = async (appId) => {
    setApprovingId(appId);
    try {
      await followupAPI.approve(appId);
      setFeedback({ msg: 'Follow-up email approved and dispatched successfully!', type: 'success' });
      setFollowups(prev => prev.filter(f => f.application_id !== appId));
    } catch (err) {
      setFeedback({ msg: 'Failed to approve follow-up: Daily cap reached or server error.', type: 'error' });
    } finally {
      setApprovingId(null);
      setTimeout(() => setFeedback(null), 4000);
    }
  };

  return (
    <div className="cf-container">
      {/* Header & Controls */}
      <div className="cf-header">
        <div className="cf-title-group">
          <h2 className="cf-title">
            <TrendingUp size={24} color="#38bdf8" />
            Conversion Funnel & Performance Analytics
          </h2>
          <p className="cf-subtitle">
            Real-time pipeline tracking, multi-platform ROI, and automated 5-day recruiter follow-up management.
          </p>
        </div>
        <button
          onClick={loadAllAnalytics}
          disabled={loading}
          className="cf-refresh-btn"
        >
          <RefreshCw size={15} className={loading ? 'cf-spin' : ''} />
          {loading ? 'Refreshing...' : 'Refresh Metrics'}
        </button>
      </div>

      {/* Toast Feedback */}
      {feedback && (
        <div className={`cf-toast ${feedback.type === 'success' ? 'cf-toast-success' : 'cf-toast-error'}`}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <CheckCircle size={16} />
            <span>{feedback.msg}</span>
          </div>
          <button onClick={() => setFeedback(null)} className="cf-toast-close">×</button>
        </div>
      )}

      {/* KPI Overview Cards */}
      <div className="cf-kpi-grid">
        {/* Card 1: Total Applications */}
        <div className="cf-kpi-card">
          <div className="cf-kpi-glow-bar" style={{ background: 'linear-gradient(90deg, #0284c7, #38bdf8)' }} />
          <div className="cf-kpi-header">
            <span>Total Applications</span>
            <div className="cf-kpi-icon-wrap" style={{ color: '#38bdf8' }}>
              <Send size={16} />
            </div>
          </div>
          <div className="cf-kpi-body">
            <span className="cf-kpi-val">{summary?.total_applications ?? 0}</span>
            <span className="cf-kpi-tag" style={{ color: '#38bdf8' }}>Submitted</span>
          </div>
        </div>

        {/* Card 2: Interviews Scheduled */}
        <div className="cf-kpi-card">
          <div className="cf-kpi-glow-bar" style={{ background: 'linear-gradient(90deg, #059669, #10b981)' }} />
          <div className="cf-kpi-header">
            <span>Interviews Scheduled</span>
            <div className="cf-kpi-icon-wrap" style={{ color: '#10b981' }}>
              <Calendar size={16} />
            </div>
          </div>
          <div className="cf-kpi-body">
            <span className="cf-kpi-val">{summary?.interviews_scheduled ?? 0}</span>
            <span className="cf-kpi-tag" style={{ color: '#10b981' }}>Callbacks</span>
          </div>
        </div>

        {/* Card 3: Interview Rate */}
        <div className="cf-kpi-card">
          <div className="cf-kpi-glow-bar" style={{ background: 'linear-gradient(90deg, #d97706, #f59e0b)' }} />
          <div className="cf-kpi-header">
            <span>Interview Rate</span>
            <div className="cf-kpi-icon-wrap" style={{ color: '#f59e0b' }}>
              <TrendingUp size={16} />
            </div>
          </div>
          <div className="cf-kpi-body">
            <span className="cf-kpi-val">{summary?.interview_rate_pct ?? 0}%</span>
            <span className="cf-kpi-tag" style={{ color: '#f59e0b' }}>Applied-to-Interview</span>
          </div>
        </div>

        {/* Card 4: Top Channel */}
        <div className="cf-kpi-card">
          <div className="cf-kpi-glow-bar" style={{ background: 'linear-gradient(90deg, #7c3aed, #a855f7)' }} />
          <div className="cf-kpi-header">
            <span>Top Performing Channel</span>
            <div className="cf-kpi-icon-wrap" style={{ color: '#a855f7' }}>
              <Award size={16} />
            </div>
          </div>
          <div className="cf-kpi-body">
            <span className="cf-kpi-val" style={{ fontSize: '1.4rem' }}>
              {summary?.top_performing_platform ?? 'N/A'}
            </span>
            <span className="cf-kpi-tag" style={{ color: '#a855f7' }}>Top Channel</span>
          </div>
        </div>
      </div>

      {/* Main Grid: Visual Funnel & Platform ROI */}
      <div className="cf-main-grid">
        {/* Stage-by-Stage Visual Funnel */}
        <div className="cf-funnel-card">
          <div>
            <h3 className="cf-section-title">
              <BarChart3 size={20} color="#38bdf8" />
              Stage-by-Stage Pipeline Funnel
            </h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
              Step-by-step conversion progression from initial job discovery to final offer receipt.
            </p>
          </div>

          <div className="cf-stages-list">
            {funnel?.stages && funnel.stages.length > 0 ? (
              funnel.stages.map((stage, idx) => {
                const fillWidth = Math.max(stage.count > 0 ? 5 : 0, stage.conversion_from_top_pct);
                return (
                  <div key={idx} className="cf-stage-item">
                    <div className="cf-stage-info">
                      <div className="cf-stage-name">
                        <span>{stage.stage}</span>
                      </div>
                      <div className="cf-stage-metrics">
                        <span className="cf-stage-count">{stage.count} {stage.count === 1 ? 'item' : 'items'}</span>
                        <span className="cf-stage-rate-pill">
                          {stage.conversion_from_previous_pct}% from prev
                        </span>
                      </div>
                    </div>
                    <div className="cf-track">
                      <div 
                        className="cf-fill"
                        style={{ width: `${fillWidth}%` }}
                      />
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="cf-empty-state">
                <Layers className="cf-empty-icon" />
                <span>No pipeline stages recorded yet. Launch application bot to begin populating funnel telemetry.</span>
              </div>
            )}
          </div>
        </div>

        {/* Platform ROI Cards */}
        <div className="cf-roi-card">
          <div>
            <h3 className="cf-section-title">
              <Filter size={19} color="#10b981" />
              Platform ROI Breakdown
            </h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
              Application throughput and callback rates across integrated job portals.
            </p>
          </div>

          <div className="cf-roi-list">
            {roi && roi.length > 0 ? (
              roi.map((p, idx) => (
                <div key={idx} className="cf-roi-item">
                  <div>
                    <div className="cf-platform-title">{p.platform}</div>
                    <div className="cf-platform-stats">
                      {p.applications_count} applied • {p.interviews_count} callbacks
                    </div>
                  </div>
                  <div className="cf-roi-badge">
                    <span className="cf-roi-pct">{p.conversion_rate_pct}%</span>
                    <span className="cf-roi-label">Conversion</span>
                  </div>
                </div>
              ))
            ) : (
              <div className="cf-empty-state">
                <Sparkles className="cf-empty-icon" />
                <span>No channel telemetry recorded yet.</span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Recruiter 5-Day Follow-Up Center */}
      <div className="cf-followup-card">
        <div className="cf-followup-header">
          <div>
            <h3 className="cf-section-title">
              <Clock size={20} color="#fbbf24" />
              Automated 5-Day Follow-Up Queue
            </h3>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
              Applications submitted $\ge$ 5 business days ago with no reply. Send polite 3-sentence check-in drafts to maximize interview response rates.
            </p>
          </div>
          <span className="cf-eligible-pill">
            {followups.length} Eligible
          </span>
        </div>

        {followups.length === 0 ? (
          <div className="cf-empty-state">
            <CheckCircle className="cf-empty-icon" />
            <span>No applications currently pending follow-up. All applications are under 5 days old or already checked in.</span>
          </div>
        ) : (
          <div className="cf-followups-grid">
            {followups.map((item, idx) => (
              <div key={idx} className="cf-followup-item">
                <div>
                  <div className="cf-followup-top">
                    <span className="cf-followup-title">{item.job_title}</span>
                    <span className="cf-followup-days">{item.days_elapsed}d ago</span>
                  </div>
                  <div className="cf-followup-company">{item.company}</div>
                  <div className="cf-followup-to">To: {item.recommended_recipient}</div>
                  <div className="cf-followup-preview">
                    {item.draft_body}
                  </div>
                </div>

                <div className="cf-followup-actions">
                  <button
                    onClick={() => handleApproveFollowup(item.application_id)}
                    disabled={approvingId === item.application_id}
                    className="cf-approve-btn"
                  >
                    <Send size={13} />
                    {approvingId === item.application_id ? 'Dispatching...' : 'Approve & Send Follow-Up'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default ConversionFunnel;
