import axios from 'axios';

// TrendRadar API 后端地址（可通过 VITE_API_BASE 配置，默认同源）
const rawApiBase = import.meta.env.VITE_API_BASE || '';
export const API_BASE = rawApiBase.replace(/\/$/, '');

// ============================================
// 增强版请求缓存 + 去重 + 防抖机制
// ============================================

// 缓存存储
const cache = new Map();
const CACHE_TTL = 60000; // 60秒缓存有效期（增加到1分钟）

// 进行中的请求（用于去重）
const pendingRequests = new Map();

// 请求防抖计时器
const debounceTimers = new Map();

// AbortController 存储（用于取消重复请求）
const abortControllers = new Map();

/**
 * 带缓存、去重、防抖的请求函数
 * @param {string} key - 缓存键
 * @param {Function} fetcher - 实际请求函数
 * @param {Object} options - 配置选项
 */
const cachedRequest = async (key, fetcher, options = {}) => {
    const {
        ttl = CACHE_TTL,
        debounce = 0,
        forceRefresh = false
    } = options;

    // 1. 检查缓存是否有效（非强制刷新时）
    if (!forceRefresh) {
        const cached = cache.get(key);
        if (cached && Date.now() - cached.timestamp < ttl) {
            console.log(`[Cache HIT] ${key} (age: ${Math.round((Date.now() - cached.timestamp) / 1000)}s)`);
            return cached.data;
        }
    }

    // 2. 检查是否有相同请求正在进行中（去重）
    if (pendingRequests.has(key)) {
        console.log(`[Request DEDUP] ${key} - waiting for pending request`);
        return pendingRequests.get(key);
    }

    // 3. 防抖处理
    if (debounce > 0) {
        if (debounceTimers.has(key)) {
            clearTimeout(debounceTimers.get(key));
        }

        return new Promise((resolve, reject) => {
            const timer = setTimeout(async () => {
                debounceTimers.delete(key);
                try {
                    const result = await executeRequest(key, fetcher, ttl);
                    resolve(result);
                } catch (error) {
                    reject(error);
                }
            }, debounce);
            debounceTimers.set(key, timer);
        });
    }

    // 4. 直接执行请求
    return executeRequest(key, fetcher, ttl);
};

/**
 * 执行实际请求
 */
const executeRequest = async (key, fetcher, ttl) => {
    // 取消之前的同类请求
    if (abortControllers.has(key)) {
        abortControllers.get(key).abort();
    }

    // 创建新的 AbortController
    const controller = new AbortController();
    abortControllers.set(key, controller);

    console.log(`[Cache MISS] ${key} - fetching...`);

    const promise = fetcher(controller.signal)
        .then(response => {
            // 存入缓存
            cache.set(key, {
                data: response,
                timestamp: Date.now()
            });
            // 清除状态
            pendingRequests.delete(key);
            abortControllers.delete(key);
            return response;
        })
        .catch(error => {
            pendingRequests.delete(key);
            abortControllers.delete(key);

            // 如果是取消请求，不抛出错误
            if (error.name === 'AbortError' || error.name === 'CanceledError') {
                console.log(`[Request CANCELLED] ${key}`);
                // 返回缓存数据（如果有）
                const cached = cache.get(key);
                if (cached) {
                    return cached.data;
                }
            }
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

/**
 * 预加载数据到缓存（后台静默加载）
 */
const preloadCache = async (keys) => {
    console.log('[Preload] Starting preload for:', keys);
    const promises = keys.map(key => {
        if (key === 'categories') {
            return api.getCategories().catch(() => null);
        }
        // 可以添加更多预加载逻辑
        return Promise.resolve();
    });
    await Promise.allSettled(promises);
    console.log('[Preload] Complete');
};

// ============================================
// API 方法
// ============================================

const api = {
    // 获取大宗商品数据
    getData: (refresh = false) => {
        if (refresh) {
            clearCache('api:data');
            return axios.get(`${API_BASE}/api/data?refresh=true`);
        }
        return cachedRequest(
            'api:data',
            (signal) => axios.get(`${API_BASE}/api/data`, { signal }),
            { ttl: 120000 }  // 2分钟缓存
        );
    },

    // 获取配置（不缓存）
    getConfig: () => axios.get(`${API_BASE}/api/config`),

    // 保存配置
    saveConfig: (config) => axios.post(`${API_BASE}/api/config`, config),

    // 获取分类（10分钟缓存，分类很少变化）
    getCategories: () => cachedRequest(
        'api:categories',
        (signal) => axios.get(`${API_BASE}/api/categories`, { signal }),
        { ttl: 600000 }  // 10分钟
    ),

    // 获取新闻（核心方法，带防抖）
    getNews: (category, includeCustom = true, refresh = false) => {
        const cacheKey = `api:news:${category}:${includeCustom}`;

        if (refresh) {
            clearCache(`api:news:${category}`);
            return axios.get(
                `${API_BASE}/api/news/${category}?include_custom=${includeCustom}&refresh=true`,
                { timeout: 90000 }  // 90秒超时
            );
        }

        return cachedRequest(
            cacheKey,
            (signal) => axios.get(
                `${API_BASE}/api/news/${category}?include_custom=${includeCustom}`,
                { signal, timeout: 90000 }
            ),
            {
                ttl: 120000,  // 2分钟缓存
                debounce: 100  // 100ms 防抖
            }
        );
    },

    // 获取大宗商品新闻
    getCommodityNews: (refresh = false) => {
        if (refresh) {
            clearCache('api:commodity-news');
            return axios.get(`${API_BASE}/api/commodity-news?refresh=true`, { timeout: 90000 });
        }
        return cachedRequest(
            'api:commodity-news',
            (signal) => axios.get(`${API_BASE}/api/commodity-news`, { signal, timeout: 90000 }),
            { ttl: 120000 }
        );
    },

    // 获取供应链新闻
    getSupplyChainNews: (refresh = false) => {
        if (refresh) {
            clearCache('api:supply-chain');
            return axios.get(`${API_BASE}/api/news/supply-chain?refresh=true`, { timeout: 90000 });
        }
        return cachedRequest(
            'api:supply-chain',
            (signal) => axios.get(`${API_BASE}/api/news/supply-chain`, { signal, timeout: 90000 }),
            { ttl: 120000 }
        );
    },

    // 触发爬取
    crawl: async (category, includeCustom = true) => {
        const result = await axios.post(`${API_BASE}/api/crawl`, {
            category,
            include_custom: includeCustom
        }, { timeout: 120000 });
        clearCache(`api:news:${category}`);
        return result;
    },

    // 刷新指定分类数据
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

    // 获取价格历史数据（带缓存）
    getPriceHistory: (commodity = null, days = 7, bypassCache = false) => {
        const cacheKey = `api:price-history:${commodity || 'all'}:${days}`;
        return cachedRequest(
            cacheKey,
            (signal) => {
                const params = new URLSearchParams();
                if (commodity) params.append('commodity', commodity);
                params.append('days', days.toString());
                return axios.get(`${API_BASE}/api/price-history?${params.toString()}`, { signal });
            },
            { ttl: 300000, forceRefresh: bypassCache }  // 5分钟缓存（价格历史变化不频繁）
        );
    },

    // 获取 AI 市场分析（带缓存）
    getMarketAnalysis: (refresh = false) => {
        const cacheKey = 'api:market-analysis';
        if (refresh) {
            clearCache(cacheKey);
        }
        return cachedRequest(
            cacheKey,
            (signal) => axios.get(`${API_BASE}/api/market-analysis`, { signal, timeout: 120000 }),
            { ttl: 600000 }  // 10分钟缓存（AI分析更新较慢）
        );
    },

    // 获取数据来源（带缓存，数据源很少变化）
    getDataSources: () => cachedRequest(
        'api:data-sources',
        (signal) => axios.get(`${API_BASE}/api/data/sources`, { signal }),
        { ttl: 3600000 }  // 1小时缓存（数据源配置很少变化）
    ),

    // 获取友商新闻统计
    getPartnerNewsStats: () => cachedRequest(
        'api:partner-news-stats',
        (signal) => axios.get(`${API_BASE}/api/partner-news-stats`, { signal }),
        { ttl: 300000 }
    ),

    // 获取客户新闻统计
    getCustomerNewsStats: () => cachedRequest(
        'api:customer-news-stats',
        (signal) => axios.get(`${API_BASE}/api/customer-news-stats`, { signal }),
        { ttl: 300000 }
    ),

    // 获取供应商新闻统计
    getSupplierNewsStats: () => cachedRequest(
        'api:supplier-news-stats',
        (signal) => axios.get(`${API_BASE}/api/supplier-news-stats`, { signal }),
        { ttl: 300000 }
    ),

    // 获取物料新闻统计
    getMaterialNewsStats: () => cachedRequest(
        'api:material-news-stats',
        (signal) => axios.get(`${API_BASE}/api/material-news-stats`, { signal }),
        { ttl: 300000 }
    ),

    // 获取关税新闻统计
    getTariffNewsStats: () => cachedRequest(
        'api:tariff-news-stats',
        (signal) => axios.get(`${API_BASE}/api/tariff-news-stats`, { signal }),
        { ttl: 300000 }
    ),

    // 获取 Redis 缓存状态
    getRedisCacheStatus: () => axios.get(`${API_BASE}/api/cache/status`),

    // 清除 Redis 缓存
    clearRedisCache: () => axios.post(`${API_BASE}/api/cache/clear`),

    // 获取实时汇率（带缓存，10分钟）
    getExchangeRate: () => cachedRequest(
        'api:exchange-rate',
        (signal) => axios.get(`${API_BASE}/api/exchange-rate`, { signal }),
        { ttl: 600000 }  // 10分钟缓存
    ),

    // 工具方法
    clearCache,
    preloadCache,

    // 获取前端缓存状态（用于调试）
    getCacheStatus: () => {
        const status = {};
        for (const [key, value] of cache.entries()) {
            const age = Math.round((Date.now() - value.timestamp) / 1000);
            status[key] = {
                age: age + 's',
                valid: Date.now() - value.timestamp < CACHE_TTL,
                expires_in: Math.max(0, Math.round((CACHE_TTL - (Date.now() - value.timestamp)) / 1000)) + 's'
            };
        }
        return status;
    },

    // 获取待处理请求数（用于调试）
    getPendingRequests: () => Array.from(pendingRequests.keys())
};

export default api;
