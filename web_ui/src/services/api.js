import axios from 'axios';
import { MOCK_COMMODITIES, MOCK_CONFIG } from './mockData';

// Toggle this to force mock mode even in development if needed, 
// or rely on build environment. For this task, we default to true for the demo.
// Toggle this to force mock mode even in development if needed, 
// or rely on build environment. For this task, we default to true for the demo.
const DEMO_MODE = import.meta.env.VITE_USE_MOCK === 'true';

const api = {
    getData: async () => {
        if (DEMO_MODE) {
            // Simulate network delay
            await new Promise(resolve => setTimeout(resolve, 500));
            return { data: { data: MOCK_COMMODITIES } };
        }
        return axios.get('http://localhost:8000/api/data');
    },

    getConfig: async () => {
        if (DEMO_MODE) {
            await new Promise(resolve => setTimeout(resolve, 300));
            // Check local storage for persisted mock config
            const saved = localStorage.getItem('mock_config');
            return { data: saved ? JSON.parse(saved) : MOCK_CONFIG };
        }
        return axios.get('http://localhost:8000/api/config');
    },

    saveConfig: async (config) => {
        if (DEMO_MODE) {
            await new Promise(resolve => setTimeout(resolve, 600));
            localStorage.setItem('mock_config', JSON.stringify(config));
            return { data: { success: true } };
        }
        return axios.post('http://localhost:8000/api/config', config);
    }
};

export default api;
