import React, { useState, useEffect } from 'react';
import { 
  Database, 
  Save, 
  RefreshCw, 
  Plus, 
  Trash2, 
  CheckCircle, 
  Briefcase, 
  MapPin, 
  DollarSign, 
  ShieldCheck, 
  Clock,
  HelpCircle
} from 'lucide-react';
import { vaultAPI } from '../services/api';

export function QAVaultEditor() {
  const [vault, setVault] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState(null);

  // New Custom QA pair input state
  const [newQuestion, setNewQuestion] = useState('');
  const [newAnswer, setNewAnswer] = useState('');

  const showToast = (msg, type = 'success') => {
    setFeedback({ msg, type });
    setTimeout(() => setFeedback(null), 4000);
  };

  const loadVault = async () => {
    setLoading(true);
    try {
      const res = await vaultAPI.getVault();
      if (res.success && res.vault) {
        setVault(res.vault);
      }
    } catch (err) {
      showToast('Failed to load candidate QA Vault. Ensure a resume profile exists.', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVault();
  }, []);

  const handleChange = (field, value) => {
    setVault(prev => ({
      ...prev,
      [field]: value
    }));
  };

  const handleCustomQaChange = (q, newAns) => {
    setVault(prev => ({
      ...prev,
      custom_qa: {
        ...prev.custom_qa,
        [q]: newAns
      }
    }));
  };

  const handleRemoveCustomQa = (q) => {
    setVault(prev => {
      const nextCustom = { ...prev.custom_qa };
      delete nextCustom[q];
      return {
        ...prev,
        custom_qa: nextCustom
      };
    });
  };

  const handleAddCustomQa = (e) => {
    e.preventDefault();
    if (!newQuestion.trim() || !newAnswer.trim()) return;

    setVault(prev => ({
      ...prev,
      custom_qa: {
        ...(prev.custom_qa || {}),
        [newQuestion.trim()]: newAnswer.trim()
      }
    }));
    setNewQuestion('');
    setNewAnswer('');
  };

  const handleSaveVault = async () => {
    if (!vault) return;
    setSaving(true);
    try {
      const res = await vaultAPI.updateVault(vault);
      if (res.success) {
        showToast('QA Vault saved successfully! All autonomous forms will reflect these answers.', 'success');
        setVault(res.vault);
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to save QA Vault', 'error');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="glass-card" style={{ padding: '40px', textAlign: 'center' }}>
        <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 12px', color: 'var(--primary)' }} />
        <div style={{ color: 'var(--text-secondary)' }}>Loading Candidate QA Vault...</div>
      </div>
    );
  }

  if (!vault) {
    return (
      <div className="glass-card" style={{ padding: '32px', textAlign: 'center' }}>
        <Database size={36} color="var(--warning)" style={{ margin: '0 auto 12px' }} />
        <h3 style={{ marginBottom: '8px' }}>QA Vault Not Available</h3>
        <p style={{ color: 'var(--text-muted)', marginBottom: '16px', fontSize: '0.9rem' }}>
          Please upload a resume first to initialize the candidate intelligence model.
        </p>
        <button
          onClick={loadVault}
          style={{
            padding: '8px 16px',
            background: 'var(--primary)',
            color: '#000',
            border: 'none',
            borderRadius: 'var(--radius-md)',
            fontWeight: 600,
            cursor: 'pointer'
          }}
        >
          Retry
        </button>
      </div>
    );
  }

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

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', borderBottom: '1px solid var(--border-color)', paddingBottom: '16px' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Database size={22} color="var(--primary)" />
            Candidate QA Vault & Screening Knowledge Base
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Authoritative source of truth for salary, work authorization, notice periods, and EEOC answers used across all job platforms.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={loadVault}
            disabled={saving}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: 'var(--radius-md)',
              background: 'transparent',
              border: '1px solid var(--border-color)',
              color: 'var(--text-secondary)',
              fontSize: '0.85rem',
              cursor: 'pointer'
            }}
          >
            <RefreshCw size={14} />
            Reset
          </button>

          <button
            onClick={handleSaveVault}
            disabled={saving}
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
            <Save size={15} />
            {saving ? 'Saving Vault...' : 'Save Vault Changes'}
          </button>
        </div>
      </div>

      {/* SECTION 1: COMPENSATION & AVAILABILITY */}
      <div>
        <h3 style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <DollarSign size={17} color="var(--primary)" />
          Compensation & Notice Period
        </h3>
        
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Expected CTC (LPA)</label>
            <input
              type="number"
              step="0.1"
              value={vault.expected_ctc_lpa || ''}
              onChange={(e) => handleChange('expected_ctc_lpa', parseFloat(e.target.value) || null)}
              style={{
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Current CTC (LPA)</label>
            <input
              type="number"
              step="0.1"
              value={vault.current_ctc_lpa || ''}
              onChange={(e) => handleChange('current_ctc_lpa', parseFloat(e.target.value) || null)}
              style={{
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Currency</label>
            <select
              value={vault.currency || 'INR'}
              onChange={(e) => handleChange('currency', e.target.value)}
              style={{
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="INR">INR (₹)</option>
              <option value="USD">USD ($)</option>
              <option value="EUR">EUR (€)</option>
              <option value="GBP">GBP (£)</option>
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Notice Period (Days)</label>
            <input
              type="number"
              value={vault.notice_period_days ?? 0}
              onChange={(e) => handleChange('notice_period_days', parseInt(e.target.value) || 0)}
              style={{
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Availability</label>
            <select
              value={vault.availability || 'Immediate'}
              onChange={(e) => handleChange('availability', e.target.value)}
              style={{
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="Immediate">Immediate</option>
              <option value="15 days">15 Days</option>
              <option value="30 days">30 Days</option>
              <option value="60 days">60 Days</option>
              <option value="90 days">90 Days</option>
            </select>
          </div>
        </div>
      </div>

      {/* SECTION 2: WORK AUTHORIZATION & MOBILITY */}
      <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '18px' }}>
        <h3 style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldCheck size={17} color="var(--primary)" />
          Work Authorization & Mobility
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Legally Authorized to Work?</label>
            <select
              value={vault.work_authorization || 'Yes'}
              onChange={(e) => handleChange('work_authorization', e.target.value)}
              style={{
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="Yes">Yes</option>
              <option value="No">No</option>
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Require Visa Sponsorship?</label>
            <select
              value={vault.require_sponsorship || 'No'}
              onChange={(e) => handleChange('require_sponsorship', e.target.value)}
              style={{
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="No">No</option>
              <option value="Yes">Yes</option>
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Willing to Relocate?</label>
            <select
              value={vault.willing_to_relocate || 'Yes'}
              onChange={(e) => handleChange('willing_to_relocate', e.target.value)}
              style={{
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="Yes">Yes</option>
              <option value="No">No</option>
              <option value="Negotiable">Negotiable</option>
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Remote Preference</label>
            <select
              value={vault.remote_preference || 'Yes'}
              onChange={(e) => handleChange('remote_preference', e.target.value)}
              style={{
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="Yes">Remote Preferred</option>
              <option value="Hybrid">Hybrid</option>
              <option value="No">Onsite Only</option>
            </select>
          </div>
        </div>
      </div>

      {/* SECTION 3: COMPLIANCE & EEOC */}
      <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '18px' }}>
        <h3 style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Briefcase size={17} color="var(--primary)" />
          EEOC, Demographics & Compliance
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Gender Identity</label>
            <select
              value={vault.gender || 'Decline to specify'}
              onChange={(e) => handleChange('gender', e.target.value)}
              style={{
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="Male">Male</option>
              <option value="Female">Female</option>
              <option value="Non-binary">Non-binary</option>
              <option value="Decline to specify">Decline to specify</option>
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Veteran Status</label>
            <select
              value={vault.veteran_status || 'No'}
              onChange={(e) => handleChange('veteran_status', e.target.value)}
              style={{
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="No">Not a Veteran</option>
              <option value="Yes">Protected Veteran</option>
              <option value="Decline to specify">Decline to self-identify</option>
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Disability Status</label>
            <select
              value={vault.disability_status || 'No'}
              onChange={(e) => handleChange('disability_status', e.target.value)}
              style={{
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="No">No Disability</option>
              <option value="Yes">Have a Disability</option>
              <option value="Decline to specify">Decline to self-identify</option>
            </select>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Driving License</label>
            <select
              value={vault.driving_license || 'Yes'}
              onChange={(e) => handleChange('driving_license', e.target.value)}
              style={{
                padding: '9px 12px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-input)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)'
              }}
            >
              <option value="Yes">Yes (Valid)</option>
              <option value="No">No</option>
            </select>
          </div>
        </div>
      </div>

      {/* SECTION 4: CUSTOM SCREENING Q&A DICTIONARY */}
      <div style={{ borderTop: '1px solid var(--border-color)', paddingTop: '18px' }}>
        <h3 style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <HelpCircle size={17} color="var(--primary)" />
          Authoritative Custom Q&A Dictionary ({Object.keys(vault.custom_qa || {}).length})
        </h3>
        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '14px' }}>
          Exact Q&A pairs answered with 100% confidence by the screening service without LLM hallucination.
        </p>

        {/* Existing Custom Q&A list */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '16px' }}>
          {Object.entries(vault.custom_qa || {}).map(([q, ans], idx) => (
            <div
              key={idx}
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr auto',
                gap: '12px',
                alignItems: 'center',
                background: 'var(--bg-input)',
                padding: '10px 14px',
                borderRadius: 'var(--radius-sm)',
                border: '1px solid var(--border-color)'
              }}
            >
              <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', fontWeight: 500 }}>
                {q}
              </div>
              <input
                type="text"
                value={ans}
                onChange={(e) => handleCustomQaChange(q, e.target.value)}
                style={{
                  padding: '6px 10px',
                  borderRadius: 'var(--radius-sm)',
                  background: 'rgba(0,0,0,0.3)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-primary)',
                  fontSize: '0.85rem'
                }}
              />
              <button
                type="button"
                onClick={() => handleRemoveCustomQa(q)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--danger)',
                  cursor: 'pointer',
                  padding: '4px'
                }}
                title="Remove Question"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>

        {/* Add New Custom Q&A Form */}
        <form onSubmit={handleAddCustomQa} style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr auto',
          gap: '12px',
          alignItems: 'center',
          background: 'rgba(255, 255, 255, 0.02)',
          padding: '12px 14px',
          borderRadius: 'var(--radius-sm)',
          border: '1px dashed var(--border-color)'
        }}>
          <input
            type="text"
            placeholder="New Question text (e.g. Do you have AWS certification?)"
            value={newQuestion}
            onChange={(e) => setNewQuestion(e.target.value)}
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-input)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
              fontSize: '0.85rem'
            }}
          />

          <input
            type="text"
            placeholder="Authoritative Answer (e.g. Yes, AWS Certified Solutions Architect)"
            value={newAnswer}
            onChange={(e) => setNewAnswer(e.target.value)}
            style={{
              padding: '8px 12px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--bg-input)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
              fontSize: '0.85rem'
            }}
          />

          <button
            type="submit"
            disabled={!newQuestion.trim() || !newAnswer.trim()}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 14px',
              borderRadius: 'var(--radius-sm)',
              background: 'var(--primary)',
              border: 'none',
              color: '#000',
              fontWeight: 600,
              fontSize: '0.85rem',
              cursor: 'pointer'
            }}
          >
            <Plus size={15} />
            Add Entry
          </button>
        </form>
      </div>
    </div>
  );
}
