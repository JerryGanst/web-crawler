import axios from 'axios';

// TrendRadar API 后端地址
const API_BASE = 'http://localhost:8000';

const api = {
    getData: async () => {
        return axios.get(`${API_BASE}/api/data`);
    },

    getConfig: async () => {
        return axios.get(`${API_BASE}/api/config`);
    },

    saveConfig: async (config) => {
        return axios.post(`${API_BASE}/api/config`, config);
    }
};

export default api;
