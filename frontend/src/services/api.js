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
};

export const jobsAPI = {
  getList: async (limit = 200) => {
    const response = await apiClient.get(`/jobs/list?limit=${limit}`);
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
