import React, { useState } from 'react';
import { useBot } from '../context/BotContext';
import { jobsAPI } from '../services/api';
import { 
  FileSpreadsheet, 
  Download, 
  Search, 
  ExternalLink, 
  Filter, 
  CheckCircle, 
  AlertTriangle, 
  XCircle, 
  Clock,
  RefreshCw,
  Mail,
  Copy,
  User,
  Zap
} from 'lucide-react';

export const JobApplicationsTable = () => {
  const { jobs, refreshJobsAndStats } = useBot();
  const [searchTerm, setSearchTerm] = useState('');
  const [platformFilter, setPlatformFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [refreshing, setRefreshing] = useState(false);
  const [resolvingUrl, setResolvingUrl] = useState(null);

  const handleRefresh = async () => {
    setRefreshing(true);
    await refreshJobsAndStats();
    setRefreshing(false);
  };

  const handleResolve = async (jobUrl, action) => {
    setResolvingUrl(jobUrl);
    try {
      const res = await jobsAPI.resolveManualReview(jobUrl, action);
      if (res.success) {
        await refreshJobsAndStats();
      } else {
        alert(res.message || 'Action could not be completed.');
      }
    } catch (err) {
      alert(err.response?.data?.detail || err.message || 'Failed to resolve job.');
    } finally {
      setResolvingUrl(null);
    }
  };

  const manualReviewCount = jobs.filter(j => 
    String(j.status || '').toLowerCase().includes('manual') || 
    String(j.status || '').toLowerCase().includes('review')
  ).length;

  const filteredJobs = jobs.filter((job) => {
    if (platformFilter !== 'ALL' && job.platform !== platformFilter) return false;
    if (statusFilter !== 'ALL') {
      if (statusFilter === 'SUCCESS' && !job.status?.includes('Success') && !job.status?.includes('Applied')) return false;
      if (statusFilter === 'FAILED' && !job.status?.includes('Failed')) return false;
      if (statusFilter === 'MANUAL' && !job.status?.toLowerCase().includes('manual') && !job.status?.toLowerCase().includes('review')) return false;
    }
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      return (
        job.job_title?.toLowerCase().includes(q) ||
        job.company?.toLowerCase().includes(q) ||
        job.notes?.toLowerCase().includes(q) ||
        job.reason_code?.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const getStatusBadge = (status) => {
    const s = String(status || '');
    if (s.includes('Success') || s.includes('Applied') || s.includes('Dry Run')) {
      return (
        <span style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          background: 'rgba(16, 185, 129, 0.15)',
          color: '#34d399',
          border: '1px solid rgba(16, 185, 129, 0.3)',
          padding: '3px 8px',
          borderRadius: '999px',
          fontSize: '0.75rem',
          fontWeight: '600'
        }}>
          <CheckCircle size={12} /> {s}
        </span>
      );
    } else if (s.includes('Manual')) {
      return (
        <span style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          background: 'rgba(245, 158, 11, 0.15)',
          color: '#fbbf24',
          border: '1px solid rgba(245, 158, 11, 0.3)',
          padding: '3px 8px',
          borderRadius: '999px',
          fontSize: '0.75rem',
          fontWeight: '600'
        }}>
          <AlertTriangle size={12} /> Review Needed
        </span>
      );
    } else {
      return (
        <span style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          background: 'rgba(239, 68, 68, 0.15)',
          color: '#f87171',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          padding: '3px 8px',
          borderRadius: '999px',
          fontSize: '0.75rem',
          fontWeight: '600'
        }}>
          <XCircle size={12} /> {s || 'Failed'}
        </span>
      );
    }
  };

  const getPlatformBadge = (platform) => {
    let color = '#38bdf8';
    if (platform === 'LinkedIn') color = '#0ea5e9';
    if (platform === 'Naukri') color = '#3b82f6';
    if (platform === 'Indeed') color = '#6366f1';
    if (platform === 'Dindin') color = '#a855f7';

    return (
      <span style={{
        fontWeight: '600',
        fontSize: '0.8rem',
        color: color
      }}>
        {platform}
      </span>
    );
  };

  const getMatchBadge = (scoreStr) => {
    if (!scoreStr) return <span style={{ color: 'var(--text-muted)' }}>—</span>;
    const val = parseInt(String(scoreStr).replace('%', ''), 10);
    if (isNaN(val)) return <span style={{ color: 'var(--text-muted)' }}>—</span>;

    let color = '#94a3b8';
    let bg = 'rgba(148, 163, 184, 0.15)';
    if (val >= 80) {
      color = '#34d399';
      bg = 'rgba(16, 185, 129, 0.15)';
    } else if (val >= 60) {
      color = '#fbbf24';
      bg = 'rgba(245, 158, 11, 0.15)';
    } else {
      color = '#f87171';
      bg = 'rgba(239, 68, 68, 0.15)';
    }

    return (
      <span style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        background: bg,
        color: color,
        padding: '2px 7px',
        borderRadius: '999px',
        fontSize: '0.72rem',
        fontWeight: '700'
      }}>
        <Zap size={10} /> {val}%
      </span>
    );
  };

  return (
    <div className="glass-card" style={{ padding: '24px' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '14px',
        marginBottom: '20px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            padding: '8px',
            borderRadius: 'var(--radius-md)',
            background: 'rgba(56, 189, 248, 0.15)',
            color: 'var(--primary)'
          }}>
            <FileSpreadsheet size={20} />
          </div>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '600' }}>Application History & Excel Tracker</h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Logged to <code>job_applications.xlsx</code> automatically with duplicate prevention
            </p>
          </div>
        </div>

        {/* Actions (Export to Excel & Refresh) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button 
            onClick={handleRefresh} 
            className="btn btn-outline"
            style={{ padding: '8px 12px' }}
            title="Refresh Table"
          >
            <RefreshCw size={15} className={refreshing ? 'pulse' : ''} />
          </button>

          <a 
            href={jobsAPI.getExportUrl()} 
            download="job_applications.xlsx"
            className="btn btn-primary"
            style={{ padding: '8px 16px', textDecoration: 'none' }}
          >
            <Download size={16} /> Export to Excel (.xlsx)
          </a>
        </div>
      </div>

      {/* Filter Row */}
      <div style={{
        display: 'flex',
        gap: '12px',
        flexWrap: 'wrap',
        marginBottom: '16px',
        alignItems: 'center'
      }}>
        {/* Search */}
        <div style={{ flex: '1', minWidth: '220px', position: 'relative' }}>
          <Search size={16} color="var(--text-muted)" style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }} />
          <input 
            type="text" 
            placeholder="Search by title, company or note..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="form-input"
            style={{ paddingLeft: '36px' }}
          />
        </div>

        {/* Platform Filter */}
        <select 
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
          className="form-input"
          style={{ width: 'auto', minWidth: '140px', cursor: 'pointer' }}
        >
          <option value="ALL">All Platforms</option>
          <option value="LinkedIn">LinkedIn</option>
          <option value="Naukri">Naukri</option>
          <option value="Indeed">Indeed</option>
          <option value="Dindin">Dindin</option>
        </select>

        {/* Status Filter */}
        <select 
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="form-input"
          style={{ width: 'auto', minWidth: '170px', cursor: 'pointer' }}
        >
          <option value="ALL">All Statuses</option>
          <option value="MANUAL">⚠️ Manual Review Queue ({manualReviewCount})</option>
          <option value="SUCCESS">✅ Success / Applied</option>
          <option value="FAILED">❌ Failed</option>
        </select>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
          <thead>
            <tr style={{ background: 'rgba(15, 23, 42, 0.8)', borderBottom: '1px solid var(--border-color)' }}>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Timestamp</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Platform</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Job Title & Company</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Status</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Match</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Quality</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Priority</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Recruiter / Contact</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Reason / Notes</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Action / Link</th>
            </tr>
          </thead>
          <tbody>
            {filteredJobs.length === 0 ? (
              <tr>
                <td colSpan={10} style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No application records found matching your filters.
                </td>
              </tr>
            ) : (
              filteredJobs.map((job, idx) => {
                const isManual = String(job.status || '').toLowerCase().includes('manual') || 
                                 String(job.status || '').toLowerCase().includes('duplicate');
                const isResolvingThis = resolvingUrl === job.job_url;

                return (
                  <tr 
                    key={idx}
                    style={{
                      borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                      transition: 'background 0.15s ease',
                      background: isManual ? 'rgba(245, 158, 11, 0.03)' : 'transparent'
                    }}
                    onMouseOver={(e) => e.currentTarget.style.background = isManual ? 'rgba(245, 158, 11, 0.08)' : 'rgba(255, 255, 255, 0.03)'}
                    onMouseOut={(e) => e.currentTarget.style.background = isManual ? 'rgba(245, 158, 11, 0.03)' : 'transparent'}
                  >
                    <td style={{ padding: '12px 16px', fontSize: '0.8rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                      {job.timestamp}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      {getPlatformBadge(job.platform)}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      <div style={{ fontWeight: '600', color: 'var(--text-primary)' }}>{job.job_title}</div>
                      <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{job.company}</div>
                      {job.job_id && (
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{job.job_id}</div>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                      {getStatusBadge(job.status)}
                    </td>
                    <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                      {getMatchBadge(job.match_score)}
                    </td>
                    <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                      {job.job_quality_score ? (
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: '999px',
                          fontSize: '0.72rem',
                          fontWeight: '700',
                          background: job.job_quality_score >= 70 ? 'rgba(16, 185, 129, 0.15)' : 'rgba(148, 163, 184, 0.15)',
                          color: job.job_quality_score >= 70 ? '#34d399' : '#94a3b8'
                        }}>
                          ⭐ {job.job_quality_score}%
                        </span>
                      ) : '—'}
                    </td>
                    <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                      {job.priority_score ? (
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: '999px',
                          fontSize: '0.72rem',
                          fontWeight: '700',
                          background: job.priority_score >= 75 ? 'rgba(99, 102, 241, 0.2)' : 'rgba(148, 163, 184, 0.15)',
                          color: job.priority_score >= 75 ? '#818cf8' : '#94a3b8'
                        }}>
                          🔥 {job.priority_score}%
                        </span>
                      ) : '—'}
                    </td>
                    <td style={{ padding: '12px 16px' }}>
                      {job.hr_email ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                          {job.recruiter_name && (
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <User size={11} /> {job.recruiter_name}
                            </span>
                          )}
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <a 
                              href={`mailto:${job.hr_email}`} 
                              style={{ color: 'var(--primary)', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.8rem', fontWeight: '500' }}
                              title={`Send email to ${job.hr_email}`}
                            >
                              <Mail size={12} /> {job.hr_email}
                            </a>
                            <button
                              onClick={() => {
                                navigator.clipboard.writeText(job.hr_email);
                                alert(`Copied ${job.hr_email} to clipboard!`);
                              }}
                              title="Copy email to clipboard"
                              style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '2px', color: 'var(--text-muted)' }}
                            >
                              <Copy size={11} />
                            </button>
                          </div>
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td style={{ padding: '12px 16px', fontSize: '0.8rem', color: 'var(--text-muted)', maxWidth: '240px' }}>
                      {job.reason_code && (
                        <div style={{
                          display: 'inline-block',
                          marginBottom: '4px',
                          padding: '2px 6px',
                          borderRadius: '4px',
                          background: 'rgba(239, 68, 68, 0.15)',
                          color: '#f87171',
                          fontSize: '0.68rem',
                          fontWeight: '700'
                        }}>
                          {job.reason_code}
                        </div>
                      )}
                      <div>
                        {job.status_reason || job.skip_reason ? (
                          <span style={{ color: '#fbbf24' }}>{job.status_reason || job.skip_reason}</span>
                        ) : (
                          job.notes || '—'
                        )}
                      </div>
                    </td>
                    <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                      {isManual ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          <button
                            type="button"
                            onClick={() => handleResolve(job.job_url, 'apply_now')}
                            disabled={isResolvingThis}
                            className="btn btn-primary"
                            style={{ padding: '4px 10px', fontSize: '0.75rem', display: 'flex', alignItems: 'center', gap: '4px' }}
                            title="Execute complete safety pipeline to apply now"
                          >
                            <Zap size={12} /> {isResolvingThis ? 'Applying...' : 'Apply Now'}
                          </button>
                          <div style={{ display: 'flex', gap: '4px' }}>
                            <button
                              type="button"
                              onClick={() => handleResolve(job.job_url, 'mark_applied')}
                              disabled={isResolvingThis}
                              className="btn btn-outline"
                              style={{ padding: '3px 6px', fontSize: '0.7rem' }}
                              title="Mark as Applied"
                            >
                              ✓ Applied
                            </button>
                            <button
                              type="button"
                              onClick={() => handleResolve(job.job_url, 'dismiss')}
                              disabled={isResolvingThis}
                              className="btn btn-outline"
                              style={{ padding: '3px 6px', fontSize: '0.7rem', color: 'var(--danger)' }}
                              title="Dismiss from Review"
                            >
                              ✕ Dismiss
                            </button>
                          </div>
                        </div>
                      ) : (
                        job.job_url ? (
                          <a 
                            href={job.job_url} 
                            target="_blank" 
                            rel="noreferrer"
                            style={{ color: 'var(--primary)', display: 'inline-flex', alignItems: 'center', gap: '4px', textDecoration: 'none' }}
                          >
                            View <ExternalLink size={13} />
                          </a>
                        ) : '—'
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
