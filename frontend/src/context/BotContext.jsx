import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { botAPI, resumeAPI, jobsAPI, settingsAPI, createLogWebSocket } from '../services/api';

const BotContext = createContext(null);

export const BotProvider = ({ children }) => {
  const [status, setStatus] = useState({
    state: 'Idle',
    current_platform: null,
    current_job: null,
    applied_count: 0,
    success_count: 0,
    failed_count: 0,
    skipped_count: 0,
    total_target: 0,
    is_paused_for_captcha: false,
    captcha_message: null,
    start_time: null,
  });

  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(true);
  const [logs, setLogs] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState({
    total_applications: 0,
    success_count: 0,
    failed_count: 0,
    manual_review_count: 0,
    platform_breakdown: {},
  });
  const [systemHealth, setSystemHealth] = useState(null);

  // Fetch initial data
  const refreshProfile = useCallback(async () => {
    try {
      setProfileLoading(true);
      const res = await resumeAPI.getProfile();
      if (res.exists) {
        setProfile(res.profile);
      }
    } catch (e) {
      console.error('Error loading profile:', e);
    } finally {
      setProfileLoading(false);
    }
  }, []);

  const refreshStatus = useCallback(async () => {
    try {
      const res = await botAPI.getStatus();
      setStatus(res);
    } catch (e) {
      console.error('Error fetching bot status:', e);
    }
  }, []);

  const refreshJobsAndStats = useCallback(async () => {
    try {
      const [jobsData, statsData] = await Promise.all([
        jobsAPI.getList(200),
        jobsAPI.getStats(),
      ]);
      setJobs(jobsData);
      setStats(statsData);
    } catch (e) {
      console.error('Error fetching jobs and stats:', e);
    }
  }, []);

  const refreshSystemHealth = useCallback(async () => {
    try {
      const res = await settingsAPI.getSystemStatus();
      setSystemHealth(res);
    } catch (e) {
      console.error('Error fetching system health:', e);
    }
  }, []);

  const refreshLogs = useCallback(async () => {
    try {
      const logData = await botAPI.getLogs(100);
      if (Array.isArray(logData) && logData.length > 0) {
        setLogs(logData);
      }
    } catch (e) {
      console.error('Error fetching logs:', e);
    }
  }, []);

  // WebSocket Live Logs
  useEffect(() => {
    let ws = null;
    try {
      ws = createLogWebSocket(
        (logEntry) => {
          setLogs((prev) => [...prev.slice(-400), logEntry]);
          if (logEntry.level === 'SUCCESS' || logEntry.level === 'ACTION' || logEntry.level === 'WARNING') {
            refreshJobsAndStats();
            refreshStatus();
          }
        },
        (err) => console.log('WS reconnecting soon...')
      );
    } catch (e) {
      console.error('WS Init error:', e);
    }

    return () => {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [refreshJobsAndStats, refreshStatus]);

  // Periodic polling fallback
  useEffect(() => {
    refreshProfile();
    refreshStatus();
    refreshJobsAndStats();
    refreshSystemHealth();
    refreshLogs();

    const interval = setInterval(() => {
      refreshStatus();
      refreshJobsAndStats();
      refreshLogs();
      refreshSystemHealth();
    }, 3000);

    return () => clearInterval(interval);
  }, [refreshProfile, refreshStatus, refreshJobsAndStats, refreshSystemHealth, refreshLogs]);

  const clearLogs = useCallback(() => {
    setLogs([]);
  }, []);

  return (
    <BotContext.Provider
      value={{
        status,
        profile,
        profileLoading,
        logs,
        setLogs,
        clearLogs,
        jobs,
        stats,
        systemHealth,
        setProfile,
        refreshProfile,
        refreshStatus,
        refreshJobsAndStats,
        refreshSystemHealth,
        refreshLogs,
      }}
    >
      {children}
    </BotContext.Provider>
  );
};

export const useBot = () => {
  const context = useContext(BotContext);
  if (!context) {
    throw new Error('useBot must be used within a BotProvider');
  }
  return context;
};
