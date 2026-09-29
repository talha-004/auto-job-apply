import React, { useState, useEffect } from 'react';
import { 
  ShieldAlert, 
  Mail, 
  HelpCircle, 
  ExternalLink, 
  CheckCircle, 
  XCircle, 
  Play, 
  Send, 
  MessageSquare, 
  Sparkles, 
  RefreshCw, 
  AlertTriangle,
  FileText,
  BookmarkPlus
} from 'lucide-react';
import { jobsAPI, outreachAPI, screeningAPI, vaultAPI } from '../services/api';

export function InterventionCenter({ onBadgeUpdate }) {
  const [activeTab, setActiveTab] = useState('review'); // 'review' | 'outreach' | 'screening'
  
  // Review Queue State
  const [reviewJobs, setReviewJobs] = useState([]);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [actionLoadingUrl, setActionLoadingUrl] = useState(null);

  // Outreach Drafts State
  const [outreachMessages, setOutreachMessages] = useState([]);
  const [outreachFilter, setOutreachFilter] = useState('DRAFTED');
  const [outreachLoading, setOutreachLoading] = useState(false);
  const [actionLoadingOutreachId, setActionLoadingOutreachId] = useState(null);

  // Screening Sandbox State
  const [testQuestion, setTestQuestion] = useState('');
  const [testQuestionType, setTestQuestionType] = useState('text');
  const [testOptions, setTestOptions] = useState('');
  const [screeningResult, setScreeningResult] = useState(null);
  const [screeningLoading, setScreeningLoading] = useState(false);
  const [vaultSaveSuccess, setVaultSaveSuccess] = useState(false);

  // Global alert/toast state
  const [feedback, setFeedback] = useState(null);

  const showToast = (msg, type = 'success') => {
    setFeedback({ msg, type });
    setTimeout(() => setFeedback(null), 4000);
  };

  // Load Review Queue
  const fetchReviewQueue = async () => {
    setReviewLoading(true);
    try {
      const data = await jobsAPI.getManualReviewQueue();
      setReviewJobs(Array.isArray(data) ? data : []);
      if (onBadgeUpdate) onBadgeUpdate(data.length);
    } catch (err) {
      console.error('Failed to load manual review queue:', err);
    } finally {
      setReviewLoading(false);
    }
  };

  // Load Outreach Messages
  const fetchOutreachMessages = async () => {
    setOutreachLoading(true);
    try {
      const statusParam = outreachFilter === 'ALL' ? null : outreachFilter;
      const data = await outreachAPI.getMessages(statusParam);
      setOutreachMessages(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Failed to load outreach messages:', err);
    } finally {
      setOutreachLoading(false);
    }
  };

  useEffect(() => {
    fetchReviewQueue();
    fetchOutreachMessages();
  }, [outreachFilter]);

  // Handle Review Actions
  const handleResolveReview = async (jobUrl, action) => {
    setActionLoadingUrl(jobUrl);
    try {
      const res = await jobsAPI.resolveManualReview(jobUrl, action);
      if (res.success) {
        showToast(res.message || `Job updated (${action})`, 'success');
        fetchReviewQueue();
      } else {
        showToast(res.message || 'Operation failed', 'error');
      }
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to update review item', 'error');
    } finally {
      setActionLoadingUrl(null);
    }
  };

  // Handle Outreach Send
  const handleSendOutreach = async (outreachId) => {
    setActionLoadingOutreachId(outreachId);
    try {
      const res = await outreachAPI.sendEmail(outreachId, true);
      showToast(`Email delivered to ${res.recipient?.email || 'recruiter'}!`, 'success');
      fetchOutreachMessages();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to send outreach email', 'error');
    } finally {
      setActionLoadingOutreachId(null);
    }
  };

  // Handle Outreach Decline
  const handleDeclineOutreach = async (outreachId) => {
    setActionLoadingOutreachId(outreachId);
    try {
      await outreachAPI.declineMessage(outreachId);
      showToast('Outreach message declined.', 'info');
      fetchOutreachMessages();
    } catch (err) {
      showToast('Failed to decline message', 'error');
    } finally {
      setActionLoadingOutreachId(null);
    }
  };

  // Handle Screening Sandbox Run
  const handleTestScreening = async (e) => {
    e.preventDefault();
    if (!testQuestion.trim()) return;

    setScreeningLoading(true);
    setScreeningResult(null);
    setVaultSaveSuccess(false);

    try {
      const optionsArray = testOptions
        ? testOptions.split(',').map(s => s.trim()).filter(Boolean)
        : null;

      const res = await screeningAPI.answerQuestion({
        question_text: testQuestion,
        question_type: testQuestionType,
        options: optionsArray
      });
      setScreeningResult(res);
    } catch (err) {
      showToast(err.response?.data?.detail || 'Screening test failed', 'error');
    } finally {
      setScreeningLoading(false);
    }
  };

  // Save Tested Answer to QA Vault
  const handleSaveToVault = async () => {
    if (!screeningResult || !testQuestion.trim()) return;

    try {
      const currentVaultRes = await vaultAPI.getVault();
      const vaultData = currentVaultRes.vault || {};
      const customQa = { ...(vaultData.custom_qa || {}) };
      
      customQa[testQuestion.trim()] = String(screeningResult.answer);
      vaultData.custom_qa = customQa;

      await vaultAPI.updateVault(vaultData);
      setVaultSaveSuccess(true);
      showToast('Successfully committed to Candidate QA Vault!', 'success');
    } catch (err) {
      showToast('Failed to save to QA Vault', 'error');
    }
  };

  return (
    <div className="glass-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
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
          justifyContent: 'space-between',
          animation: 'fadeIn 0.2s ease-in-out'
        }}>
          <span>{feedback.msg}</span>
          <button onClick={() => setFeedback(null)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>×</button>
        </div>
      )}

      {/* Header & Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px', borderBottom: '1px solid var(--border-color)', paddingBottom: '16px' }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <ShieldAlert size={22} color="var(--primary)" />
            Human Intervention Center
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Inspect CAPTCHA blocks, review cold outreach drafts, and train candidate intelligence.
          </p>
        </div>

        {/* Tab Switcher */}
        <div style={{ display: 'flex', gap: '8px', background: 'var(--bg-input)', padding: '4px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
          <button
            onClick={() => setActiveTab('review')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              background: activeTab === 'review' ? 'var(--primary-dark)' : 'transparent',
              color: activeTab === 'review' ? '#fff' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontWeight: 500,
              fontSize: '0.85rem',
              transition: 'all 0.2s'
            }}
          >
            <AlertTriangle size={15} />
            Manual Review & CAPTCHA ({reviewJobs.length})
          </button>

          <button
            onClick={() => setActiveTab('outreach')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              background: activeTab === 'outreach' ? 'var(--primary-dark)' : 'transparent',
              color: activeTab === 'outreach' ? '#fff' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontWeight: 500,
              fontSize: '0.85rem',
              transition: 'all 0.2s'
            }}
          >
            <Mail size={15} />
            Outreach Approval ({outreachMessages.filter(m => m.status === 'DRAFTED').length})
          </button>

          <button
            onClick={() => setActiveTab('screening')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              border: 'none',
              background: activeTab === 'screening' ? 'var(--primary-dark)' : 'transparent',
              color: activeTab === 'screening' ? '#fff' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontWeight: 500,
              fontSize: '0.85rem',
              transition: 'all 0.2s'
            }}
          >
            <Sparkles size={15} />
            Screening Q&A Sandbox
          </button>
        </div>
      </div>

      {/* TAB 1: MANUAL REVIEW & CAPTCHA QUEUE */}
      {activeTab === 'review' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Jobs paused for human verification (unsolved CAPTCHAs, external multi-factor logins, or suspicious prompts).
            </span>
            <button
              onClick={fetchReviewQueue}
              disabled={reviewLoading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                background: 'transparent',
                border: '1px solid var(--border-color)',
                color: 'var(--text-secondary)',
                borderRadius: 'var(--radius-sm)',
                padding: '4px 10px',
                fontSize: '0.8rem',
                cursor: 'pointer'
              }}
            >
              <RefreshCw size={13} className={reviewLoading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>

          {reviewJobs.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: '48px 16px',
              background: 'rgba(15, 23, 42, 0.4)',
              borderRadius: 'var(--radius-md)',
              border: '1px dashed var(--border-color)'
            }}>
              <CheckCircle size={36} color="var(--success)" style={{ margin: '0 auto 12px' }} />
              <h4 style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '4px' }}>Queue is Clear</h4>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                No active CAPTCHA challenges or blocked applications require your attention.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {reviewJobs.map((job, idx) => (
                <div
                  key={idx}
                  style={{
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-md)',
                    padding: '16px 20px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                    transition: 'border-color 0.2s'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px' }}>
                    <div>
                      <h4 style={{ fontSize: '1rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {job.job_title || 'Software Role'}
                        <span style={{ fontSize: '0.75rem', padding: '2px 8px', borderRadius: '4px', background: 'rgba(245, 158, 11, 0.15)', color: 'var(--warning)', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                          {job.platform || 'Platform'}
                        </span>
                      </h4>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                        {job.company || 'Company'} • {job.location || 'Location'}
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <a
                        href={job.job_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px',
                          padding: '6px 12px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'rgba(255, 255, 255, 0.05)',
                          border: '1px solid var(--border-color)',
                          color: 'var(--primary)',
                          textDecoration: 'none',
                          fontSize: '0.8rem'
                        }}
                      >
                        <ExternalLink size={13} />
                        Open Job URL
                      </a>

                      <button
                        onClick={() => handleResolveReview(job.job_url, 'apply_now')}
                        disabled={actionLoadingUrl === job.job_url}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px',
                          padding: '6px 12px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'var(--primary)',
                          border: 'none',
                          color: '#000',
                          fontWeight: 600,
                          fontSize: '0.8rem',
                          cursor: 'pointer'
                        }}
                      >
                        <Play size={13} />
                        Run Bot Now
                      </button>

                      <button
                        onClick={() => handleResolveReview(job.job_url, 'mark_applied')}
                        disabled={actionLoadingUrl === job.job_url}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px',
                          padding: '6px 12px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'rgba(16, 185, 129, 0.15)',
                          border: '1px solid rgba(16, 185, 129, 0.3)',
                          color: 'var(--success)',
                          fontSize: '0.8rem',
                          cursor: 'pointer'
                        }}
                      >
                        <CheckCircle size={13} />
                        Mark Applied
                      </button>

                      <button
                        onClick={() => handleResolveReview(job.job_url, 'dismiss')}
                        disabled={actionLoadingUrl === job.job_url}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '5px',
                          padding: '6px 12px',
                          borderRadius: 'var(--radius-sm)',
                          background: 'rgba(239, 68, 68, 0.15)',
                          border: '1px solid rgba(239, 68, 68, 0.3)',
                          color: 'var(--danger)',
                          fontSize: '0.8rem',
                          cursor: 'pointer'
                        }}
                      >
                        <XCircle size={13} />
                        Dismiss
                      </button>
                    </div>
                  </div>

                  {job.notes && (
                    <div style={{ fontSize: '0.8rem', color: 'var(--warning)', background: 'rgba(245, 158, 11, 0.08)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', borderLeft: '3px solid var(--warning)' }}>
                      <strong>Intervention Reason:</strong> {job.notes}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: RECRUITER OUTREACH APPROVAL */}
      {activeTab === 'outreach' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
            <div style={{ display: 'flex', gap: '8px' }}>
              {['DRAFTED', 'READY_TO_SEND', 'SENT', 'DECLINED', 'ALL'].map(st => (
                <button
                  key={st}
                  onClick={() => setOutreachFilter(st)}
                  style={{
                    padding: '4px 10px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-color)',
                    background: outreachFilter === st ? 'var(--primary-dark)' : 'transparent',
                    color: outreachFilter === st ? '#fff' : 'var(--text-secondary)',
                    fontSize: '0.75rem',
                    cursor: 'pointer'
                  }}
                >
                  {st}
                </button>
              ))}
            </div>

            <button
              onClick={fetchOutreachMessages}
              disabled={outreachLoading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                background: 'transparent',
                border: '1px solid var(--border-color)',
                color: 'var(--text-secondary)',
                borderRadius: 'var(--radius-sm)',
                padding: '4px 10px',
                fontSize: '0.8rem',
                cursor: 'pointer'
              }}
            >
              <RefreshCw size={13} className={outreachLoading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>

          {outreachMessages.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: '48px 16px',
              background: 'rgba(15, 23, 42, 0.4)',
              borderRadius: 'var(--radius-md)',
              border: '1px dashed var(--border-color)'
            }}>
              <Mail size={36} color="var(--primary)" style={{ margin: '0 auto 12px' }} />
              <h4 style={{ fontSize: '1rem', color: 'var(--text-primary)', marginBottom: '4px' }}>No Outreach Messages</h4>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                Drafted recruiter cold messages will appear here for review and safety approval.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {outreachMessages.map((msg) => (
                <div
                  key={msg.id}
                  style={{
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-color)',
                    borderRadius: 'var(--radius-md)',
                    padding: '18px 22px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '10px' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{
                          padding: '2px 8px',
                          borderRadius: '4px',
                          fontSize: '0.75rem',
                          fontWeight: 600,
                          background: msg.channel === 'WHATSAPP' ? 'rgba(37, 211, 102, 0.15)' : 'rgba(56, 189, 248, 0.15)',
                          color: msg.channel === 'WHATSAPP' ? '#25d366' : 'var(--primary)',
                          border: `1px solid ${msg.channel === 'WHATSAPP' ? 'rgba(37, 211, 102, 0.3)' : 'rgba(56, 189, 248, 0.3)'}`
                        }}>
                          {msg.channel}
                        </span>
                        <h4 style={{ fontSize: '1rem', color: 'var(--text-primary)' }}>
                          {msg.job_title} @ {msg.company}
                        </h4>
                      </div>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
                        To: <strong>{msg.recipient?.name || 'Hiring Lead'}</strong> ({msg.recipient?.email || msg.recipient?.phone || 'Direct'}) • Confidence: {msg.recipient?.confidence || 'medium'}
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {msg.status === 'DRAFTED' && (
                        <>
                          {msg.channel === 'EMAIL' && (
                            <button
                              onClick={() => handleSendOutreach(msg.id)}
                              disabled={actionLoadingOutreachId === msg.id}
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '6px 14px',
                                borderRadius: 'var(--radius-sm)',
                                background: 'var(--primary)',
                                border: 'none',
                                color: '#000',
                                fontWeight: 600,
                                fontSize: '0.8rem',
                                cursor: 'pointer'
                              }}
                            >
                              <Send size={13} />
                              Approve & Send
                            </button>
                          )}

                          {msg.channel === 'WHATSAPP' && msg.whatsapp_url && (
                            <a
                              href={msg.whatsapp_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '6px 14px',
                                borderRadius: 'var(--radius-sm)',
                                background: '#25d366',
                                border: 'none',
                                color: '#000',
                                fontWeight: 600,
                                fontSize: '0.8rem',
                                textDecoration: 'none'
                              }}
                            >
                              <MessageSquare size={13} />
                              Open WhatsApp
                            </a>
                          )}

                          <button
                            onClick={() => handleDeclineOutreach(msg.id)}
                            disabled={actionLoadingOutreachId === msg.id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '6px',
                              padding: '6px 12px',
                              borderRadius: 'var(--radius-sm)',
                              background: 'rgba(239, 68, 68, 0.15)',
                              border: '1px solid rgba(239, 68, 68, 0.3)',
                              color: 'var(--danger)',
                              fontSize: '0.8rem',
                              cursor: 'pointer'
                            }}
                          >
                            <XCircle size={13} />
                            Decline
                          </button>
                        </>
                      )}

                      {msg.status === 'SENT' && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--success)', fontSize: '0.8rem' }}>
                          <CheckCircle size={14} /> Sent on {new Date(msg.sent_at).toLocaleDateString()}
                        </span>
                      )}

                      {msg.status === 'DECLINED' && (
                        <span style={{ display: 'flex', alignItems: 'center', gap: '5px', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                          <XCircle size={14} /> Declined
                        </span>
                      )}
                    </div>
                  </div>

                  {msg.subject && (
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '6px' }}>
                      <strong>Subject:</strong> {msg.subject}
                    </div>
                  )}

                  <div style={{
                    fontSize: '0.85rem',
                    color: 'var(--text-secondary)',
                    whiteSpace: 'pre-wrap',
                    background: 'rgba(0,0,0,0.2)',
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-sm)',
                    lineHeight: 1.5
                  }}>
                    {msg.body_text}
                  </div>

                  {msg.attachment_path && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: 'var(--primary)' }}>
                      <FileText size={14} />
                      Attached Resume: {msg.attachment_path.split(/[\\/]/).pop()}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* TAB 3: SCREENING Q&A SANDBOX & TRAINER */}
      {activeTab === 'screening' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Test screening questions against the candidate's QA Vault and LLM reasoning engine. Review answer provenance (<span style={{ color: 'var(--success)' }}>EXACT_VAULT</span>, <span style={{ color: 'var(--primary)' }}>DERIVED</span>, or <span style={{ color: 'var(--warning)' }}>UNKNOWN</span>) and commit learned answers directly into candidate memory.
          </div>

          <form onSubmit={handleTestScreening} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                Screening Question Text *
              </label>
              <input
                type="text"
                placeholder="e.g. How many years of experience do you have in React? or What is your current notice period?"
                value={testQuestion}
                onChange={(e) => setTestQuestion(e.target.value)}
                style={{
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-md)',
                  background: 'var(--bg-input)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-primary)',
                  fontSize: '0.9rem',
                  outline: 'none'
                }}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                  Question Field Type
                </label>
                <select
                  value={testQuestionType}
                  onChange={(e) => setTestQuestionType(e.target.value)}
                  style={{
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    fontSize: '0.9rem'
                  }}
                >
                  <option value="text">Free Text</option>
                  <option value="number">Numeric</option>
                  <option value="boolean">Yes / No (Boolean)</option>
                  <option value="select">Dropdown / Single Select</option>
                </select>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                  Options (Comma-separated, for select/radio)
                </label>
                <input
                  type="text"
                  placeholder="e.g. Immediate, 15 days, 30 days, 60+ days"
                  value={testOptions}
                  onChange={(e) => setTestOptions(e.target.value)}
                  style={{
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--bg-input)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                    fontSize: '0.9rem'
                  }}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={screeningLoading || !testQuestion.trim()}
              style={{
                alignSelf: 'flex-start',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '10px 20px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--primary)',
                border: 'none',
                color: '#000',
                fontWeight: 600,
                fontSize: '0.9rem',
                cursor: 'pointer'
              }}
            >
              <Sparkles size={16} />
              {screeningLoading ? 'Evaluating with AI...' : 'Ask AI / Evaluate Answer'}
            </button>
          </form>

          {/* Screening Test Result Panel */}
          {screeningResult && (
            <div style={{
              background: 'var(--bg-input)',
              border: '1px solid var(--border-color)',
              borderRadius: 'var(--radius-md)',
              padding: '20px',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px'
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                  Evaluated Answer Details:
                </span>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{
                    padding: '3px 10px',
                    borderRadius: '9999px',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    background: 
                      screeningResult.provenance === 'EXACT_VAULT' ? 'rgba(16, 185, 129, 0.15)' :
                      screeningResult.provenance === 'DERIVED' ? 'rgba(56, 189, 248, 0.15)' :
                      'rgba(245, 158, 11, 0.15)',
                    color: 
                      screeningResult.provenance === 'EXACT_VAULT' ? 'var(--success)' :
                      screeningResult.provenance === 'DERIVED' ? 'var(--primary)' :
                      'var(--warning)',
                    border: `1px solid ${
                      screeningResult.provenance === 'EXACT_VAULT' ? 'rgba(16, 185, 129, 0.3)' :
                      screeningResult.provenance === 'DERIVED' ? 'rgba(56, 189, 248, 0.3)' :
                      'rgba(245, 158, 11, 0.3)'
                    }`
                  }}>
                    PROVENANCE: {screeningResult.provenance}
                  </span>

                  <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    Confidence: <strong>{Math.round((screeningResult.confidence || 0) * 100)}%</strong>
                  </span>
                </div>
              </div>

              <div style={{
                background: 'rgba(0,0,0,0.3)',
                padding: '14px 16px',
                borderRadius: 'var(--radius-sm)',
                borderLeft: '4px solid var(--primary)'
              }}>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '4px' }}>
                  Answer Value:
                </div>
                <div style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                  {String(screeningResult.answer)}
                </div>
              </div>

              {screeningResult.reasoning && (
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                  <strong>Source Rationale:</strong> {screeningResult.reasoning}
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '6px' }}>
                <button
                  type="button"
                  onClick={handleSaveToVault}
                  disabled={vaultSaveSuccess}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '8px 16px',
                    borderRadius: 'var(--radius-sm)',
                    background: vaultSaveSuccess ? 'rgba(16, 185, 129, 0.2)' : 'rgba(168, 85, 247, 0.2)',
                    border: `1px solid ${vaultSaveSuccess ? 'var(--success)' : 'var(--accent)'}`,
                    color: vaultSaveSuccess ? 'var(--success)' : 'var(--accent)',
                    fontSize: '0.85rem',
                    fontWeight: 600,
                    cursor: vaultSaveSuccess ? 'default' : 'pointer'
                  }}
                >
                  <BookmarkPlus size={15} />
                  {vaultSaveSuccess ? 'Saved to Candidate Vault!' : 'Save & Retain in QA Vault'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
