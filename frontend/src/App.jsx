import React from 'react';
import { BotProvider } from './context/BotContext';
import { Navbar } from './components/Navbar';
import { StatusIndicator } from './components/StatusIndicator';
import { ResumeUploader } from './components/ResumeUploader';
import { BotControlPanel } from './components/BotControlPanel';
import { LiveLogFeed } from './components/LiveLogFeed';
import { JobApplicationsTable } from './components/JobApplicationsTable';

function DashboardContent() {
  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <Navbar />

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
      </main>

      <footer style={{
        marginTop: 'auto',
        borderTop: '1px solid var(--border-color)',
        padding: '20px',
        textAlign: 'center',
        fontSize: '0.8rem',
        color: 'var(--text-muted)'
      }}>
        AutoApplyJobs • Free & Open-Source Autonomous Application Agent • Powered by Ollama & Playwright
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
