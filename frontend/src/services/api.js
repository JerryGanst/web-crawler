import axios from 'axios';

// TrendRadar API 后端地址
const API_BASE = 'http://localhost:8000';

// ============================================
// 简单的请求缓存 + 去重机制
// ============================================

// 缓存存储
const cache = new Map();
const CACHE_TTL = 30000; // 30秒缓存有效期

// 进行中的请求（用于去重）
const pendingRequests = new Map();

/**
 * 带缓存和去重的请求函数
 * @param {string} key - 缓存键
 * @param {Function} fetcher - 实际请求函数
 * @param {number} ttl - 缓存时间（毫秒）
 */
const cachedRequest = async (key, fetcher, ttl = CACHE_TTL) => {
    // 1. 检查缓存是否有效
    const cached = cache.get(key);
    if (cached && Date.now() - cached.timestamp < ttl) {
        console.log(`[Cache HIT] ${key}`);
        return cached.data;
    }

    // 2. 检查是否有相同请求正在进行中（去重）
    if (pendingRequests.has(key)) {
        console.log(`[Request DEDUP] ${key} - waiting for pending request`);
        return pendingRequests.get(key);
    }

    // 3. 发起新请求
    console.log(`[Cache MISS] ${key} - fetching...`);
    const promise = fetcher().then(response => {
        // 存入缓存
        cache.set(key, {
            data: response,
            timestamp: Date.now()
        });
        // 清除进行中标记
        pendingRequests.delete(key);
        return response;
    }).catch(error => {
        pendingRequests.delete(key);
        throw error;
    });

    // 标记请求进行中
    pendingRequests.set(key, promise);
    return promise;
};

/**
 * 清除特定缓存
 */
const clearCache = (keyPattern) => {
    if (!keyPattern) {
        cache.clear();
        console.log('[Cache] Cleared all');
        return;
    }
    for (const key of cache.keys()) {
        if (key.includes(keyPattern)) {
            cache.delete(key);
            console.log(`[Cache] Cleared: ${key}`);
        }
    }
};

// ============================================
// API 方法
// ============================================

const api = {
    // 获取大宗商品数据
    // refresh=false: 从 Redis 缓存获取
    // refresh=true: 强制重新爬取
    getData: (refresh = false) => {
        if (refresh) {
            clearCache('api:data');
            return axios.get(`${API_BASE}/api/data?refresh=true`);
        }
        return cachedRequest(
            'api:data',
            () => axios.get(`${API_BASE}/api/data`),
            60000  // 前端缓存1分钟
        );
    },

    // 获取配置（不缓存）
    getConfig: () => axios.get(`${API_BASE}/api/config`),

    // 保存配置
    saveConfig: (config) => axios.post(`${API_BASE}/api/config`, config),

    // 获取分类（5分钟缓存，分类很少变化）
    getCategories: () => cachedRequest(
        'api:categories',
        () => axios.get(`${API_BASE}/api/categories`),
        300000
    ),

    // 获取新闻
    // refresh=false: 从 Redis 缓存获取
    // refresh=true: 强制重新爬取
    getNews: (category, includeCustom = true, refresh = false) => {
        if (refresh) {
            clearCache(`api:news:${category}`);
            return axios.get(`${API_BASE}/api/news/${category}?include_custom=${includeCustom}&refresh=true`);
        }
        return cachedRequest(
            `api:news:${category}:${includeCustom}`,
            () => axios.get(`${API_BASE}/api/news/${category}?include_custom=${includeCustom}`),
            60000
        );
    },

    // 获取大宗商品新闻
    getCommodityNews: (refresh = false) => {
        if (refresh) {
            clearCache('api:commodity-news');
            return axios.get(`${API_BASE}/api/commodity-news?refresh=true`);
        }
        return cachedRequest(
            'api:commodity-news',
            () => axios.get(`${API_BASE}/api/commodity-news`),
            60000
        );
    },

    // 获取供应链新闻
    getSupplyChainNews: (refresh = false) => {
        if (refresh) {
            clearCache('api:supply-chain');
            return axios.get(`${API_BASE}/api/news/supply-chain?refresh=true`);
        }
        return cachedRequest(
            'api:supply-chain',
            () => axios.get(`${API_BASE}/api/news/supply-chain`),
            60000
        );
    },

    // 触发爬取（保留兼容）
    crawl: async (category, includeCustom = true) => {
        const result = await axios.post(`${API_BASE}/api/crawl`, {
            category,
            include_custom: includeCustom
        });
        clearCache(`api:news:${category}`);
        return result;
    },

    // 刷新指定分类数据（新方法，推荐使用）
    refresh: async (type, category = null) => {
        switch (type) {
            case 'news':
                return api.getNews(category || 'finance', true, true);
            case 'supply-chain':
                return api.getSupplyChainNews(true);
            case 'commodity':
                return api.getData(true);
            case 'commodity-news':
                return api.getCommodityNews(true);
            default:
                throw new Error(`Unknown refresh type: ${type}`);
        }
    },

    // 获取 Redis 缓存状态
    getRedisCacheStatus: () => axios.get(`${API_BASE}/api/cache/status`),

    // 清除 Redis 缓存
    clearRedisCache: () => axios.post(`${API_BASE}/api/cache/clear`),

    // 工具方法
    clearCache,
    
    // 获取前端缓存状态（用于调试）
    getCacheStatus: () => {
        const status = {};
        for (const [key, value] of cache.entries()) {
            status[key] = {
                age: Math.round((Date.now() - value.timestamp) / 1000) + 's',
                valid: Date.now() - value.timestamp < CACHE_TTL
            };
        }
        return status;
    }
};

export default api;
