import React, { useState, useEffect } from 'react';
import { BotProvider } from './context/BotContext';
import { Navbar } from './components/Navbar';
import { StatusIndicator } from './components/StatusIndicator';
import { ResumeUploader } from './components/ResumeUploader';
import { BotControlPanel } from './components/BotControlPanel';
import { LiveLogFeed } from './components/LiveLogFeed';
import { JobApplicationsTable } from './components/JobApplicationsTable';
import { InterventionCenter } from './components/InterventionCenter';
import { QAVaultEditor } from './components/QAVaultEditor';
import { SchedulerSettings } from './components/SchedulerSettings';
import { jobsAPI, outreachAPI } from './services/api';

function DashboardContent() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [interventionCount, setInterventionCount] = useState(0);

  // Poll for manual review and draft counts to show in the navigation badge
  const updateInterventionBadge = async () => {
    try {
      const [reviews, drafts] = await Promise.all([
        jobsAPI.getManualReviewQueue().catch(() => []),
        outreachAPI.getMessages('DRAFTED').catch(() => [])
      ]);
      const total = (Array.isArray(reviews) ? reviews.length : 0) + (Array.isArray(drafts) ? drafts.length : 0);
      setInterventionCount(total);
    } catch {
      // Ignore background badge errors
    }
  };

  useEffect(() => {
    updateInterventionBadge();
    const timer = setInterval(updateInterventionBadge, 15000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar 
        activeTab={activeTab} 
        onSelectTab={setActiveTab} 
        interventionCount={interventionCount} 
      />

      <main style={{
        maxWidth: '1440px',
        margin: '0 auto',
        padding: '24px 28px',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '24px'
      }}>
        {/* Top Status & Metrics Bar */}
        <StatusIndicator />

        {/* Dynamic View based on Active Tab */}
        {activeTab === 'dashboard' && (
          <>
            {/* Two-Column Workspace Layout */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))',
              gap: '24px',
              alignItems: 'start'
            }}>
              {/* Left Column: Resume & Profile */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                <ResumeUploader />
                <BotControlPanel />
              </div>

              {/* Right Column: Live Logs */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                <LiveLogFeed />
              </div>
            </div>

            {/* Bottom Full-Width Job Applications Table */}
            <JobApplicationsTable />
          </>
        )}

        {activeTab === 'interventions' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <InterventionCenter onBadgeUpdate={updateInterventionBadge} />
            <JobApplicationsTable />
          </div>
        )}

        {activeTab === 'vault' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <QAVaultEditor />
            <ResumeUploader />
          </div>
        )}

        {activeTab === 'scheduler' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            <SchedulerSettings />
            <JobApplicationsTable />
          </div>
        )}
      </main>

      <footer style={{
        marginTop: 'auto',
        borderTop: '1px solid var(--border-color)',
        padding: '20px',
        textAlign: 'center',
        fontSize: '0.8rem',
        color: 'var(--text-muted)'
      }}>
        AutoApplyJobs • Autonomous AI Application Agent • Powered by Ollama, APScheduler, & Playwright
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <BotProvider>
      <DashboardContent />
    </BotProvider>
  );
}
