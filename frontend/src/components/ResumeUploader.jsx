import React, { useState, useRef } from 'react';
import { useBot } from '../context/BotContext';
import { resumeAPI } from '../services/api';
import { 
  UploadCloud, 
  FileText, 
  CheckCircle, 
  Edit3, 
  Save, 
  User, 
  Mail, 
  Phone, 
  MapPin, 
  Briefcase, 
  GraduationCap, 
  Award, 
  Code, 
  Sparkles,
  ChevronDown,
  ChevronUp,
  AlertCircle
} from 'lucide-react';

export const ResumeUploader = () => {
  const { profile, setProfile, refreshProfile, profileLoading } = useBot();
  const [uploading, setUploading] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editData, setEditData] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const [newSkill, setNewSkill] = useState('');
  const fileInputRef = useRef(null);

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setUploading(true);
      const res = await resumeAPI.uploadResume(file);
      if (res.success) {
        setProfile(res.profile);
        setEditData(res.profile);
      }
    } catch (err) {
      alert('Failed to upload/parse resume: ' + (err.response?.data?.detail || err.message));
    } finally {
      setUploading(false);
    }
  };

  const handleStartEditing = () => {
    setEditData(JSON.parse(JSON.stringify(profile)));
    setIsEditing(true);
    setExpanded(true);
  };

  const handleSaveProfile = async () => {
    try {
      const res = await resumeAPI.updateProfile(editData);
      if (res.success) {
        setProfile(res.profile);
        setIsEditing(false);
      }
    } catch (err) {
      alert('Error updating profile: ' + err.message);
    }
  };

  const handleAddSkill = () => {
    if (newSkill.trim() && editData) {
      setEditData({
        ...editData,
        skills: [...(editData.skills || []), newSkill.trim()]
      });
      setNewSkill('');
    }
  };

  const handleRemoveSkill = (idxToRemove) => {
    if (editData) {
      setEditData({
        ...editData,
        skills: editData.skills.filter((_, idx) => idx !== idxToRemove)
      });
    }
  };

  return (
    <div className="glass-card" style={{ padding: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            padding: '8px',
            borderRadius: 'var(--radius-md)',
            background: 'rgba(56, 189, 248, 0.15)',
            color: 'var(--primary)'
          }}>
            <FileText size={20} />
          </div>
          <div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: '600' }}>Candidate Resume Profile</h3>
            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Parsed using local LLM to auto-fill applications intelligently
            </p>
          </div>
        </div>

        {profile && (
          <div style={{ display: 'flex', gap: '10px' }}>
            {isEditing ? (
              <button onClick={handleSaveProfile} className="btn btn-success" style={{ padding: '8px 14px' }}>
                <Save size={15} /> Save Changes
              </button>
            ) : (
              <button onClick={handleStartEditing} className="btn btn-outline" style={{ padding: '8px 14px' }}>
                <Edit3 size={15} /> Edit Details
              </button>
            )}
            <button 
              onClick={() => setExpanded(!expanded)} 
              className="btn btn-outline" 
              style={{ padding: '8px 10px' }}
            >
              {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
            </button>
          </div>
        )}
      </div>

      {/* Upload Dropzone */}
      <input 
        type="file" 
        ref={fileInputRef} 
        onChange={handleFileUpload} 
        accept=".pdf,.docx,.doc" 
        style={{ display: 'none' }} 
      />

      {!profile && !uploading && (
        <div 
          onClick={() => fileInputRef.current?.click()}
          style={{
            border: '2px dashed rgba(56, 189, 248, 0.3)',
            borderRadius: 'var(--radius-md)',
            padding: '36px 20px',
            textAlign: 'center',
            cursor: 'pointer',
            background: 'rgba(15, 23, 42, 0.4)',
            transition: 'all 0.2s ease'
          }}
          onMouseOver={(e) => e.currentTarget.style.borderColor = 'var(--primary)'}
          onMouseOut={(e) => e.currentTarget.style.borderColor = 'rgba(56, 189, 248, 0.3)'}
        >
          <UploadCloud size={40} color="var(--primary)" style={{ margin: '0 auto 12px' }} />
          <h4 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '4px' }}>
            Upload your Resume (PDF or DOCX)
          </h4>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
            Ollama will analyze your resume and structure it for auto-filling form fields
          </p>
        </div>
      )}

      {uploading && (
        <div style={{
          textAlign: 'center',
          padding: '36px 20px',
          background: 'rgba(15, 23, 42, 0.4)',
          borderRadius: 'var(--radius-md)'
        }}>
          <Sparkles size={36} color="var(--primary)" className="pulse" style={{ margin: '0 auto 12px' }} />
          <h4 style={{ fontSize: '1rem', fontWeight: '600' }}>Analyzing resume with local LLM...</h4>
          <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Extracting candidate skills, experience, education, and credentials
          </p>
        </div>
      )}

      {/* Profile Summary & Expansion */}
      {profile && !uploading && (
        <div>
          {/* Quick Header Details */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
            gap: '12px',
            background: 'rgba(15, 23, 42, 0.6)',
            padding: '16px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-color)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <User size={16} color="var(--primary)" />
              <span style={{ fontSize: '0.875rem', fontWeight: '600' }}>
                {isEditing ? (
                  <input 
                    className="form-input" 
                    value={editData?.full_name || ''} 
                    onChange={(e) => setEditData({ ...editData, full_name: e.target.value })}
                  />
                ) : profile.full_name || 'Candidate'}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Mail size={16} color="var(--primary)" />
              <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                {isEditing ? (
                  <input 
                    className="form-input" 
                    value={editData?.email || ''} 
                    onChange={(e) => setEditData({ ...editData, email: e.target.value })}
                  />
                ) : profile.email || 'No email'}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Phone size={16} color="var(--primary)" />
              <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                {isEditing ? (
                  <input 
                    className="form-input" 
                    value={editData?.phone || ''} 
                    onChange={(e) => setEditData({ ...editData, phone: e.target.value })}
                  />
                ) : profile.phone || 'No phone'}
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <MapPin size={16} color="var(--primary)" />
              <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                {isEditing ? (
                  <input 
                    className="form-input" 
                    value={editData?.location || ''} 
                    onChange={(e) => setEditData({ ...editData, location: e.target.value })}
                  />
                ) : profile.location || 'Remote'}
              </span>
            </div>
          </div>

          {/* Re-upload button */}
          <div style={{ marginTop: '12px', display: 'flex', justifyContent: 'flex-end' }}>
            <button 
              onClick={() => fileInputRef.current?.click()} 
              className="btn btn-outline" 
              style={{ fontSize: '0.75rem', padding: '5px 10px' }}
            >
              <UploadCloud size={13} /> Upload New Resume Version
            </button>
          </div>

          {/* Expanded Profile Info */}
          {expanded && (
            <div style={{ marginTop: '18px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Skills Chips */}
              <div>
                <h4 style={{ fontSize: '0.875rem', fontWeight: '600', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <Code size={15} color="var(--primary)" /> Extracted Skills ({(profile.skills || []).length})
                </h4>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {(isEditing ? editData?.skills : profile.skills)?.map((skill, idx) => (
                    <span 
                      key={idx}
                      style={{
                        background: 'rgba(56, 189, 248, 0.12)',
                        border: '1px solid rgba(56, 189, 248, 0.25)',
                        color: 'var(--primary)',
                        padding: '4px 10px',
                        borderRadius: '999px',
                        fontSize: '0.8rem',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px'
                      }}
                    >
                      {skill}
                      {isEditing && (
                        <button 
                          onClick={() => handleRemoveSkill(idx)} 
                          style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', fontSize: '0.9rem' }}
                        >
                          ×
                        </button>
                      )}
                    </span>
                  ))}
                </div>

                {isEditing && (
                  <div style={{ display: 'flex', gap: '8px', marginTop: '10px', maxWidth: '300px' }}>
                    <input 
                      className="form-input" 
                      placeholder="Add new skill..." 
                      value={newSkill} 
                      onChange={(e) => setNewSkill(e.target.value)} 
                      onKeyDown={(e) => e.key === 'Enter' && handleAddSkill()}
                    />
                    <button onClick={handleAddSkill} className="btn btn-outline" style={{ padding: '6px 12px' }}>
                      Add
                    </button>
                  </div>
                )}
              </div>

              {/* Work Experience */}
              {profile.work_experience?.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '0.875rem', fontWeight: '600', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Briefcase size={15} color="var(--secondary)" /> Work Experience
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {profile.work_experience.map((exp, idx) => (
                      <div key={idx} style={{
                        padding: '10px 14px',
                        background: 'rgba(15, 23, 42, 0.5)',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--border-color)',
                        fontSize: '0.8125rem'
                      }}>
                        <div style={{ fontWeight: '600', color: 'var(--text-primary)' }}>
                          {exp.title} • <span style={{ color: 'var(--primary)' }}>{exp.company}</span>
                        </div>
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '2px' }}>
                          {exp.start_date} – {exp.end_date} | {exp.location}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Education */}
              {profile.education?.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '0.875rem', fontWeight: '600', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <GraduationCap size={15} color="var(--accent)" /> Education
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {profile.education.map((edu, idx) => (
                      <div key={idx} style={{
                        padding: '10px 14px',
                        background: 'rgba(15, 23, 42, 0.5)',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--border-color)',
                        fontSize: '0.8125rem'
                      }}>
                        <div style={{ fontWeight: '600' }}>
                          {edu.degree} in {edu.field}
                        </div>
                        <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                          {edu.institution} ({edu.graduation_year})
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
