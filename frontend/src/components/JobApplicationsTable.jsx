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
  RefreshCw
} from 'lucide-react';

export const JobApplicationsTable = () => {
  const { jobs, refreshJobsAndStats } = useBot();
  const [searchTerm, setSearchTerm] = useState('');
  const [platformFilter, setPlatformFilter] = useState('ALL');
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [refreshing, setRefreshing] = useState(false);

  const handleRefresh = async () => {
    setRefreshing(true);
    await refreshJobsAndStats();
    setRefreshing(false);
  };

  const filteredJobs = jobs.filter((job) => {
    if (platformFilter !== 'ALL' && job.platform !== platformFilter) return false;
    if (statusFilter !== 'ALL') {
      if (statusFilter === 'SUCCESS' && !job.status?.includes('Success') && !job.status?.includes('Applied')) return false;
      if (statusFilter === 'FAILED' && !job.status?.includes('Failed')) return false;
      if (statusFilter === 'MANUAL' && !job.status?.includes('Manual')) return false;
    }
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      return (
        job.job_title?.toLowerCase().includes(q) ||
        job.company?.toLowerCase().includes(q) ||
        job.notes?.toLowerCase().includes(q)
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
          style={{ width: 'auto', minWidth: '140px', cursor: 'pointer' }}
        >
          <option value="ALL">All Statuses</option>
          <option value="SUCCESS">Success / Applied</option>
          <option value="MANUAL">Manual Review</option>
          <option value="FAILED">Failed</option>
        </select>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
          <thead>
            <tr style={{ background: 'rgba(15, 23, 42, 0.8)', borderBottom: '1px solid var(--border-color)' }}>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Timestamp</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Platform</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Job Title</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Company</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Status</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Notes</th>
              <th style={{ padding: '12px 16px', color: 'var(--text-secondary)', fontWeight: '600' }}>Link</th>
            </tr>
          </thead>
          <tbody>
            {filteredJobs.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  No application records found matching your filters.
                </td>
              </tr>
            ) : (
              filteredJobs.map((job, idx) => (
                <tr 
                  key={idx}
                  style={{
                    borderBottom: '1px solid rgba(255, 255, 255, 0.04)',
                    transition: 'background 0.15s ease'
                  }}
                  onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)'}
                  onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
                >
                  <td style={{ padding: '12px 16px', fontSize: '0.8rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                    {job.timestamp}
                  </td>
                  <td style={{ padding: '12px 16px' }}>
                    {getPlatformBadge(job.platform)}
                  </td>
                  <td style={{ padding: '12px 16px', fontWeight: '600', color: 'var(--text-primary)' }}>
                    {job.job_title}
                  </td>
                  <td style={{ padding: '12px 16px', color: 'var(--text-secondary)' }}>
                    {job.company}
                  </td>
                  <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                    {getStatusBadge(job.status)}
                  </td>
                  <td style={{ padding: '12px 16px', fontSize: '0.8rem', color: 'var(--text-muted)', maxWidth: '240px' }}>
                    {job.notes || '—'}
                  </td>
                  <td style={{ padding: '12px 16px', whiteSpace: 'nowrap' }}>
                    {job.job_url ? (
                      <a 
                        href={job.job_url} 
                        target="_blank" 
                        rel="noreferrer"
                        style={{ color: 'var(--primary)', display: 'inline-flex', alignItems: 'center', gap: '4px', textDecoration: 'none' }}
                      >
                        View <ExternalLink size={13} />
                      </a>
                    ) : '—'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
