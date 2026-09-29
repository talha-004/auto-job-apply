import axios from 'axios';

const API_BASE = '/api';

const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const resumeAPI = {
  uploadResume: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post('/resume/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getProfile: async () => {
    const response = await apiClient.get('/resume/profile');
    return response.data;
  },

  updateProfile: async (profileData) => {
    const response = await apiClient.put('/resume/profile', profileData);
    return response.data;
  },
};

export const botAPI = {
  getStatus: async () => {
    const response = await apiClient.get('/bot/status');
    return response.data;
  },

  startBot: async (config) => {
    const response = await apiClient.post('/bot/start', config);
    return response.data;
  },

  pauseBot: async () => {
    const response = await apiClient.post('/bot/pause');
    return response.data;
  },

  resumeBot: async () => {
    const response = await apiClient.post('/bot/resume');
    return response.data;
  },

  stopBot: async () => {
    const response = await apiClient.post('/bot/stop');
    return response.data;
  },

  getLogs: async (limit = 100) => {
    const response = await apiClient.get(`/bot/logs?limit=${limit}`);
    return response.data;
  },

  updateNaukriHeadline: async (headline) => {
    const response = await apiClient.post('/bot/naukri/update-headline', { headline });
    return response.data;
  },

  runPreflight: async (config = null) => {
    if (config) {
      const response = await apiClient.post('/bot/preflight', config);
      return response.data;
    }
    const response = await apiClient.get('/bot/preflight');
    return response.data;
  },
};

export const jobsAPI = {
  getList: async (limit = 200) => {
    const response = await apiClient.get(`/jobs/list?limit=${limit}`);
    return response.data;
  },

  getManualReviewQueue: async (limit = 100) => {
    const response = await apiClient.get(`/jobs/manual-review?limit=${limit}`);
    return response.data;
  },

  resolveManualReview: async (jobUrl, action, notes = '') => {
    const response = await apiClient.post('/jobs/manual-review/resolve', {
      job_url: jobUrl,
      action,
      notes
    });
    return response.data;
  },

  getStats: async () => {
    const response = await apiClient.get('/jobs/stats');
    return response.data;
  },

  getExportUrl: () => {
    return `${API_BASE}/jobs/export`;
  },
};

export const vaultAPI = {
  getVault: async () => {
    const response = await apiClient.get('/resume/vault');
    return response.data;
  },

  updateVault: async (vaultData) => {
    const response = await apiClient.put('/resume/vault', vaultData);
    return response.data;
  },
};

export const schedulerAPI = {
  getStatus: async () => {
    const response = await apiClient.get('/bot/scheduler/status');
    return response.data;
  },

  start: async () => {
    const response = await apiClient.post('/bot/scheduler/start');
    return response.data;
  },

  stop: async () => {
    const response = await apiClient.post('/bot/scheduler/stop');
    return response.data;
  },

  updateConfig: async (config) => {
    const response = await apiClient.post('/bot/scheduler/config', config);
    return response.data;
  },

  triggerJob: async (jobId) => {
    const response = await apiClient.post(`/bot/scheduler/trigger/${jobId}`);
    return response.data;
  },

  toggleJob: async (jobId, enabled) => {
    const response = await apiClient.post(`/bot/scheduler/toggle/${jobId}`, { enabled });
    return response.data;
  },
};

export const outreachAPI = {
  getMessages: async (status = null, limit = 50) => {
    const query = status ? `?status=${status}&limit=${limit}` : `?limit=${limit}`;
    const response = await apiClient.get(`/outreach/messages${query}`);
    return response.data;
  },

  sendEmail: async (outreachId, forceSend = true) => {
    const response = await apiClient.post('/outreach/send', {
      outreach_id: outreachId,
      force_send: forceSend,
    });
    return response.data;
  },

  declineMessage: async (outreachId) => {
    const response = await apiClient.post(`/outreach/decline/${outreachId}`);
    return response.data;
  },

  getWhatsAppUrl: async (phone, message) => {
    const response = await apiClient.get(`/outreach/whatsapp-url?phone=${encodeURIComponent(phone)}&message=${encodeURIComponent(message)}`);
    return response.data;
  },

  extractContacts: async (payload) => {
    const response = await apiClient.post('/outreach/extract-contacts', payload);
    return response.data;
  },

  draftOutreach: async (payload) => {
    const response = await apiClient.post('/outreach/draft', payload);
    return response.data;
  },
};

export const screeningAPI = {
  answerQuestion: async (payload) => {
    const response = await apiClient.post('/screening/answer', payload);
    return response.data;
  },

  batchAnswer: async (questions, jobContext = null) => {
    const response = await apiClient.post('/screening/batch', {
      questions,
      job_context: jobContext,
    });
    return response.data;
  },

  getProviders: async () => {
    const response = await apiClient.get('/screening/providers');
    return response.data;
  },
};

export const tailoredResumeAPI = {
  tailorResume: async (jobTitle, jobDescription, jobId = null) => {
    const response = await apiClient.post('/resume/tailor', {
      job_title: jobTitle,
      job_description: jobDescription,
      job_id: jobId,
    });
    return response.data;
  },

  getDownloadUrl: (jobId) => {
    return `${API_BASE}/resume/tailored/${jobId}/download`;
  },
};

export const notificationsAPI = {
  getConfig: async () => {
    const response = await apiClient.get('/notifications/config');
    return response.data;
  },

  sendTestNotification: async (payload = {}) => {
    const response = await apiClient.post('/notifications/test', payload);
    return response.data;
  },

  classifyEmail: async (payload) => {
    const response = await apiClient.post('/notifications/classify-email', payload);
    return response.data;
  },

  scanInbox: async (maxEmails = 10) => {
    const response = await apiClient.post(`/notifications/scan-inbox?max_emails=${maxEmails}`);
    return response.data;
  },
};

export const settingsAPI = {
  getSystemStatus: async () => {
    const response = await apiClient.get('/settings/status');
    return response.data;
  },
};

export function createLogWebSocket(onMessage, onError) {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = window.location.host;
  const wsUrl = `${protocol}//${host}/ws/logs`;

  const ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    console.log('Connected to live log WebSocket');
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (onMessage) onMessage(data);
    } catch (e) {
      console.error('Error parsing WS message:', e);
    }
  };

  ws.onerror = (err) => {
    console.error('WebSocket Error:', err);
    if (onError) onError(err);
  };

  return ws;
}

export default apiClient;
