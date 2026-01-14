import React, { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { ArrowUp, ArrowDown, RefreshCw, Settings, Plus, Trash2, X, Save, Eye, Check, Calendar, ExternalLink, Globe, Search, DollarSign, ChevronDown, Filter } from 'lucide-react';
import CommodityCard from '../components/CommodityCard';
import ExchangeStatus from '../components/ExchangeStatus';
import NewsFeed from '../components/NewsFeed';
import AIAnalysis from '../components/AIAnalysis';
import api from '../services/api';
// ECharts 按需导入（仅导入 connect 功能用于图表联动）
import * as echarts from 'echarts/core';
import { LineChart } from 'echarts/charts';
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

// 注册 ECharts 组件
echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

// Safe URL parsing helper to avoid errors
const safeGetHostname = (url) => {
    if (!url) return '';
    try {
        return new URL(url).hostname;
    } catch {
        return url.substring(0, 30) + (url.length > 30 ? '...' : '');
    }
};

// ==================== 商品分类 TAB 配置 ====================
// 基于后端返回的 category 字段进行分类（贵金属/工业金属/能源/农产品/其他）
const COMMODITY_TABS = [
    {
        id: 'metals',
        name: '金属',
        icon: '🪙',
        color: '#f59e0b',
        bgColor: '#fffbeb',
        // 匹配后端 category: 贵金属、工业金属
        categories: ['贵金属', '工业金属'],
        keywords: ['黄金', 'Gold', '白银', 'Silver', '铜', 'Copper', '铝', 'Aluminium', '铂金', 'Platinum', '钯金', 'Palladium', '镍', 'Nickel', '锌', 'Zinc', '铅', 'Lead', '锡', 'Tin']
    },
    {
        id: 'energy',
        name: '能源',
        icon: '⛽',
        color: '#3b82f6',
        bgColor: '#eff6ff',
        categories: ['能源'],
        keywords: ['原油', 'Oil', 'Crude', 'WTI', 'Brent', '天然气', 'Natural Gas', '汽油', 'Gasoline', '柴油', 'Diesel']
    },
    {
        id: 'plastics',
        name: '塑料',
        icon: '🧪',
        color: '#10b981',
        bgColor: '#ecfdf5',
        categories: ['塑料', '化工'],
        keywords: ['塑料', 'Plastic', 'PA66', 'PBT', 'PC', 'ABS', 'PP', 'PE', 'PVC', 'HDPE', 'LDPE', '聚丙烯', '聚乙烯', '聚氯乙烯', '尼龙', 'Nylon', '树脂', 'Resin', '改性塑料', '工程塑料'],
        // 塑料子分类（大类）
        subTabs: [
            { id: 'all', name: '全部', color: '#6b7280' },
            { id: 'ABS', name: 'ABS', color: '#3b82f6', desc: '丙烯腈-丁二烯-苯乙烯共聚物' },
            { id: 'PP', name: 'PP', color: '#10b981', desc: '聚丙烯' },
            { id: 'PE', name: 'PE', color: '#f59e0b', desc: '聚乙烯' },
            { id: 'GPPS', name: 'GPPS', color: '#a855f7', desc: '通用级聚苯乙烯（含低端）' },
            { id: 'HIPS', name: 'HIPS', color: '#7c3aed', desc: '高抗冲聚苯乙烯（含低端）' },
            { id: 'PVC', name: 'PVC', color: '#ef4444', desc: '聚氯乙烯' },
            { id: 'PA66', name: 'PA66', color: '#ec4899', desc: '尼龙66' },
            { id: 'PC', name: 'PC', color: '#06b6d4', desc: '聚碳酸酯' },
            { id: 'PET', name: 'PET', color: '#84cc16', desc: '聚对苯二甲酸乙二醇酯' },
        ]
    },
    {
        id: 'all',
        name: '全部',
        icon: '📊',
        color: '#6b7280',
        bgColor: '#f3f4f6',
        categories: [],
        keywords: []
    }
];

// 可配置的表头列定义
const TABLE_COLUMNS_CONFIG = [
    { id: 'name', label: '商品名称', width: '25%', visible: true },
    { id: 'price', label: '当前价格', width: '20%', visible: true },
    { id: 'change', label: '涨跌幅', width: '15%', visible: true },
    { id: 'source', label: '数据来源', width: '20%', visible: true },
    { id: 'unit', label: '单位', width: '10%', visible: true },
    { id: 'update', label: '更新时间', width: '10%', visible: false }
];

// 判断商品属于哪个分类（优先使用后端category，其次关键词匹配）
const getCommodityCategory = (name, category) => {
    if (!name) return 'all';
    // 优先使用后端返回的 category 字段
    if (category) {
        for (const tab of COMMODITY_TABS) {
            if (tab.id === 'all') continue;
            if (tab.categories && tab.categories.includes(category)) {
                return tab.id;
            }
        }
    }
    // 备用：关键词匹配（使用单词边界避免误匹配）
    const normalizedName = name.toLowerCase();
    for (const tab of COMMODITY_TABS) {
        if (tab.id === 'all') continue;
        if (tab.keywords && tab.keywords.some(kw => {
            const kwLower = kw.toLowerCase();
            // 短关键词（<=3字符）使用精确匹配或单词边界
            if (kwLower.length <= 3) {
                // 使用正则表达式进行单词边界匹配
                const regex = new RegExp(`(^|[^a-z])${kwLower}($|[^a-z])`, 'i');
                return regex.test(normalizedName);
            }
            // 长关键词使用包含匹配
            return normalizedName.includes(kwLower);
        })) {
            return tab.id;
        }
    }
    return 'all';
};

// 商品名称归一化映射（将不同来源的相同商品合并）
const COMMODITY_ALIASES = {
    // 黄金
    'Gold': '黄金',
    'COMEX黄金': '黄金',
    'COMEX Gold': '黄金',
    '国际金价': '黄金',
    'XAU': '黄金',
    // 白银
    'Silver': '白银',
    'COMEX白银': '白银',
    'COMEX Silver': '白银',
    'XAG': '白银',
    // 原油
    'WTI Crude Oil': 'WTI原油',
    'WTI原油': 'WTI原油',
    'Crude Oil WTI': 'WTI原油',
    'Brent Crude': '布伦特原油',
    'Brent原油': '布伦特原油',
    '布伦特原油': '布伦特原油',
    // 铜 - 注意：不同市场的铜价使用不同单位，不应该合并
    // COMEX铜: 美分/磅 (USc/lb)，需要 ÷100 转换为美元，×2204.62 转换为吨
    // SMM铜/沪铜: 元/吨 (CNY/ton)，直接使用
    // 保持分开以确保价格计算正确
    'Copper': 'COMEX铜',           // Business Insider 的 Copper 通常是 COMEX
    'COMEX铜': 'COMEX铜',
    'COMEX Copper': 'COMEX铜',
    'SMM铜': 'SMM铜',              // 上海有色网的铜价，元/吨
    '沪铜': '沪铜',                 // 上海期货交易所，元/吨
    // 铝
    'Aluminium': '铝',
    '沪铝': '铝',
    // 天然气
    'Natural Gas': '天然气',
    '天然气': '天然气',
    // 铂金
    'Platinum': '铂金',
    '铂金': '铂金',
    // 钯金
    'Palladium': '钯金',
    '钯金': '钯金',
};

// 获取标准化商品名称
const getNormalizedName = (name) => {
    if (!name) return name;
    return COMMODITY_ALIASES[name] || name;
};

// 提取基础商品名称（去掉区域后缀）
// 例如: "ABS(华南)" -> "ABS", "PP(华东区域)" -> "PP"
const getBaseCommodityName = (name) => {
    if (!name) return name;
    // 匹配括号内的区域名称
    const match = name.match(/^(.+?)\s*[\(（].*[\)）]$/);
    return match ? match[1].trim() : name;
};

// 判断是否为区域商品（名称包含区域信息）
const isRegionalCommodity = (name) => {
    if (!name) return false;
    return /[\(（].*(华东|华南|华北|华中|华西|东北|西南|西北|区域).*[\)）]/.test(name);
};

const Dashboard = () => {
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState(null);
    const [lastUpdate, setLastUpdate] = useState(null);
    const [priceHistory, setPriceHistory] = useState({});
    const [currency, setCurrency] = useState('CNY');
    const [timeRange, setTimeRange] = useState('week'); // 默认周视图
    const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);

    // Settings Modal State
    const [showSettings, setShowSettings] = useState(false);
    const [config, setConfig] = useState({ urls: [] });
    const [newUrl, setNewUrl] = useState('');
    const [savingConfig, setSavingConfig] = useState(false);

    // Search State
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedUrl, setSelectedUrl] = useState('');
    const [urlInputValue, setUrlInputValue] = useState('');
    const [showUrlDropdown, setShowUrlDropdown] = useState(false);
    const urlFilterRef = useRef(null);

    // 新增：商品选择器状态
    const [showCommoditySelector, setShowCommoditySelector] = useState(false);
    const [commoditySearchTerm, setCommoditySearchTerm] = useState('');
    const [selectedCommodities, setSelectedCommodities] = useState(new Set());
    const commoditySelectorRef = useRef(null);

    // 新增：数据来源筛选状态
    const [dataSources, setDataSources] = useState(null);
    const [showSourceFilter, setShowSourceFilter] = useState(false);
    // 新增：商品分类TAB状态
    const [activeCommodityTab, setActiveCommodityTab] = useState('metals');
    // 新增：塑料子分类TAB状态
    const [activePlasticSubTab, setActivePlasticSubTab] = useState('all');
    // 新增：表头配置状态
    const [tableColumns, setTableColumns] = useState(TABLE_COLUMNS_CONFIG);
    const [showColumnSettings, setShowColumnSettings] = useState(false);
    const columnSettingsRef = useRef(null);
    const [selectedCountry, setSelectedCountry] = useState('all');
    // 改为多选：使用Set存储选中的网站ID
    const [selectedWebsites, setSelectedWebsites] = useState(new Set());
    // 临时状态：用于在弹窗中暂存选择，点击确定后才应用
    const [tempSelectedCountry, setTempSelectedCountry] = useState('all');
    const [tempSelectedWebsites, setTempSelectedWebsites] = useState(new Set());
    const sourceFilterRef = useRef(null);

    // 新增：保存和恢复用户偏好
    useEffect(() => {
        // 恢复保存的设置
        const savedSettings = localStorage.getItem('trendradar_dashboard_settings');
        if (savedSettings) {
            try {
                const settings = JSON.parse(savedSettings);
                if (settings.currency) setCurrency(settings.currency);
                if (settings.timeRange) setTimeRange(settings.timeRange);
                if (settings.selectedCommodities && Array.isArray(settings.selectedCommodities)) {
                    setSelectedCommodities(new Set(settings.selectedCommodities));
                }
                // 不恢复 selectedCountry 和 selectedWebsites，每次默认显示全部数据
            } catch (e) {
                console.error('恢复设置失败:', e);
            }
        }
    }, []);

    // 保存设置到 localStorage（不保存网站筛选，避免混淆）
    useEffect(() => {
        const settings = {
            currency,
            timeRange,
            selectedCommodities: Array.from(selectedCommodities),
            // 不保存 selectedCountry 和 selectedWebsites，每次刷新默认显示全部
        };
        localStorage.setItem('trendradar_dashboard_settings', JSON.stringify(settings));
    }, [currency, timeRange, selectedCommodities]);

    // 汇率状态（从 API 获取）
    const [exchangeRate, setExchangeRate] = useState(7.2);

    // 加载实时汇率
    useEffect(() => {
        const loadExchangeRate = async () => {
            try {
                const response = await api.getExchangeRate();
                const rate = response.data?.rate || response.rate;
                if (rate) {
                    setExchangeRate(rate);
                }
            } catch (err) {
                console.error('获取汇率失败:', err);
            }
        };
        loadExchangeRate();
        // 每10分钟刷新一次
        const interval = setInterval(loadExchangeRate, 600000);
        return () => clearInterval(interval);
    }, []);

    const EXCHANGE_RATE = exchangeRate;

    // 防止 StrictMode 双重请求的标记
    const hasFetchedData = useRef(false);
    const intervalRef = useRef(null);

    // Connect charts for synchronized hover
    useEffect(() => {
        const timer = setTimeout(() => {
            echarts.connect('commodities');
        }, 500);
        return () => clearTimeout(timer);
    }, [selectedCommodities, timeRange]);

    useEffect(() => {
        if (hasFetchedData.current) return;
        hasFetchedData.current = true;

        const fetchData = async (forceRefresh = false) => {
            try {
                const response = await api.getData(forceRefresh);
                const responseData = response.data || response;
                const newData = responseData.data || [];
                setData(newData);
                setLastUpdate(responseData.timestamp || new Date().toISOString());
                setLoading(false);

                // 初始化选中的商品（默认选中前6个，使用归一化名称）
                if (newData.length > 0 && selectedCommodities.size === 0) {
                    const normalizedNames = new Set();
                    const initialSelected = new Set();
                    for (const item of newData) {
                        const rawName = item.name || item.chinese_name;
                        const normalizedName = getNormalizedName(rawName);
                        if (normalizedName && !normalizedNames.has(normalizedName)) {
                            normalizedNames.add(normalizedName);
                            initialSelected.add(normalizedName);
                            if (initialSelected.size >= 6) break;
                        }
                    }
                    setSelectedCommodities(initialSelected);
                }
            } catch (err) {
                console.error("Error fetching data:", err);
                setError("Failed to load data");
                setLoading(false);
            }
        };

        fetchData();
        intervalRef.current = setInterval(fetchData, 30000);

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        };
    }, []);

    // Fetch config when modal opens
    useEffect(() => {
        if (showSettings) {
            const fetchConfig = async () => {
                try {
                    const response = await api.getConfig();
                    setConfig(response.data || {});
                } catch (err) {
                    console.error("Error loading config:", err);
                }
            };
            fetchConfig();
        }
    }, [showSettings]);

    // 获取数据来源信息（只加载一次）
    const sourcesLoadedRef = useRef(false);
    useEffect(() => {
        if (sourcesLoadedRef.current) return;
        sourcesLoadedRef.current = true;

        const fetchSources = async () => {
            try {
                const response = await api.getDataSources();
                setDataSources(response.data);
            } catch (err) {
                console.error("Error loading data sources:", err);
            }
        };
        fetchSources();
    }, []);

    // Close dropdowns when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (commoditySelectorRef.current && !commoditySelectorRef.current.contains(event.target)) {
                setShowCommoditySelector(false);
            }
            if (urlFilterRef.current && !urlFilterRef.current.contains(event.target)) {
                setShowUrlDropdown(false);
            }
            if (sourceFilterRef.current && !sourceFilterRef.current.contains(event.target)) {
                setShowSourceFilter(false);
            }
            if (columnSettingsRef.current && !columnSettingsRef.current.contains(event.target)) {
                setShowColumnSettings(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    // Config Handlers
    const handleAddUrl = () => {
        if (!newUrl) return;
        const currentUrls = config.target_urls || [];
        const updatedConfig = { ...config, target_urls: [...currentUrls, newUrl] };
        setConfig(updatedConfig);
        setNewUrl('');
    };

    const handleDeleteUrl = (index) => {
        const currentUrls = config.target_urls || [];
        const updatedUrls = currentUrls.filter((_, i) => i !== index);
        const updatedConfig = { ...config, target_urls: updatedUrls };
        setConfig(updatedConfig);
    };

    const handleSaveConfig = async () => {
        setSavingConfig(true);
        try {
            await api.saveConfig(config);
            alert('Configuration saved!');
            setShowSettings(false);
        } catch (err) {
            console.error("Error saving config:", err);
            alert('Failed to save configuration');
        } finally {
            setSavingConfig(false);
        }
    };

    // 加载历史数据（日/周/月）- 防止重复请求
    const priceHistoryLoadingRef = useRef(null);
    const loadPriceHistory = useCallback(async () => {
        const daysMap = { day: 1, week: 7, month: 30 };
        const days = daysMap[timeRange] || 7;
        const cacheKey = `history-${days}`;

        // 防止相同参数重复请求
        if (priceHistoryLoadingRef.current === cacheKey) return;
        priceHistoryLoadingRef.current = cacheKey;

        try {
            const response = await api.getPriceHistory(null, days);
            const historyData = response.data?.data || response.data?.commodities || {};
            setPriceHistory(historyData);
        } catch (err) {
            console.error('加载历史数据失败:', err);
        }
    }, [timeRange]);

    useEffect(() => {
        loadPriceHistory();
    }, [loadPriceHistory]);

    // 获取商品的历史数据
    const getHistoryData = useCallback((commodityName, basePrice, points) => {
        let historyRecords = priceHistory[commodityName] || [];

        if (historyRecords.length === 0) {
            const lowerName = commodityName.toLowerCase();
            for (const [key, records] of Object.entries(priceHistory)) {
                if (key.toLowerCase().includes(lowerName) || lowerName.includes(key.toLowerCase())) {
                    historyRecords = records;
                    break;
                }
            }
        }

        if (historyRecords.length > 0) {
            return historyRecords.map((record, i) => ({
                time: i,
                price: record.price,
                date: record.date,
                isReal: true
            }));
        }

        // 无真实数据时返回空数组（不再生成假数据）
        return [];
    }, [priceHistory, timeRange]);

    const formatPrice = (price, unit = '') => {
        if (!price) return '0.00';
        let val = parseFloat(price);
        if (!isFinite(val)) return '0.00';

        // 判断原始价格是否为人民币（根据单位判断）
        const isOriginalCNY = unit && (unit.includes('元') || unit.includes('CNY') || unit.includes('RMB'));

        // 货币转换逻辑:
        // - 如果原始价格是USD，目标是CNY：乘以汇率
        // - 如果原始价格是CNY（元），目标是USD：除以汇率
        if (currency === 'CNY' && !isOriginalCNY) {
            // 原价是USD，转换为CNY
            val = val * EXCHANGE_RATE;
        } else if (currency === 'USD' && isOriginalCNY) {
            // 原价是CNY，转换为USD
            val = val / EXCHANGE_RATE;
        }

        // 智能格式化：根据价格大小选择精度
        const absVal = Math.abs(val);
        if (absVal >= 10000) return val.toFixed(0);
        if (absVal >= 100) return val.toFixed(0);
        if (absVal >= 1) return val.toFixed(2);
        if (absVal >= 0.01) return val.toFixed(4);
        return val.toFixed(2);
    };

    const getCurrencySymbol = () => currency === 'USD' ? '$' : '¥';

    // 安全获取数值
    const safeNumber = (val, defaultVal = 0) => {
        const num = parseFloat(val);
        return isNaN(num) ? defaultVal : num;
    };

    // 从数据中提取所有唯一商品（合并相同商品的不同来源和区域）
    const allCommodities = useMemo(() => {
        const commodityMap = new Map();
        const regionalColors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

        (data || []).forEach(item => {
            const rawName = item.name || item.chinese_name;
            let normalizedName = getNormalizedName(rawName);

            if (!normalizedName) return;

            // 检查是否为区域商品，如果是则使用基础名称作为 key
            const isRegional = isRegionalCommodity(normalizedName);
            const baseName = isRegional ? getBaseCommodityName(normalizedName) : normalizedName;
            const regionName = isRegional ? normalizedName.match(/[\(（](.*)[\)）]/)?.[1] || '默认' : null;

            if (!commodityMap.has(baseName)) {
                commodityMap.set(baseName, {
                    name: baseName,
                    rawNames: [rawName],
                    sources: [{
                        name: rawName,
                        price: safeNumber(item.price || item.current_price, 0),
                        change: safeNumber(item.change || item.change_percent, 0),
                        unit: item.unit,
                        url: item.url,
                        source: safeGetHostname(item.url)
                    }],
                    // 区域数据（用于多折线图表）
                    regions: isRegional ? [{
                        name: regionName,
                        fullName: normalizedName,
                        price: safeNumber(item.price || item.current_price, 0),
                        change: safeNumber(item.change || item.change_percent, 0),
                        unit: item.unit,  // 添加单位用于正确的货币/重量转换
                        color: regionalColors[0]
                    }] : [],
                    isRegional: isRegional,
                    price: safeNumber(item.price || item.current_price, 0),
                    change: safeNumber(item.change || item.change_percent, 0),
                    unit: item.unit,
                    url: item.url,
                    source: safeGetHostname(item.url),
                    category: item.category
                });
            } else {
                // 合并多个来源/区域
                const existing = commodityMap.get(baseName);
                if (!existing.rawNames.includes(rawName)) {
                    existing.rawNames.push(rawName);
                    existing.sources.push({
                        name: rawName,
                        price: safeNumber(item.price || item.current_price, 0),
                        change: safeNumber(item.change || item.change_percent, 0),
                        unit: item.unit,
                        url: item.url,
                        source: safeGetHostname(item.url)
                    });

                    // 多来源时清除顶层url/source，让组件使用sources数组
                    // 这样避免只显示第一个来源的链接
                    existing.url = null;
                    existing.source = null;

                    // 如果是区域商品，添加到区域列表
                    if (isRegional && regionName) {
                        const colorIdx = existing.regions.length % regionalColors.length;
                        existing.regions.push({
                            name: regionName,
                            fullName: normalizedName,
                            price: safeNumber(item.price || item.current_price, 0),
                            change: safeNumber(item.change || item.change_percent, 0),
                            unit: item.unit,  // 添加单位用于正确的货币/重量转换
                            color: regionalColors[colorIdx]
                        });
                        existing.isRegional = true;
                    }
                }
            }
        });
        return Array.from(commodityMap.values());
    }, [data]);

    // TAB 切换时联动更新选中的商品
    useEffect(() => {
        if (allCommodities.length === 0) return;

        // 获取当前 TAB 下的所有商品
        let tabCommodities = allCommodities.filter(commodity => {
            if (activeCommodityTab === 'all') return true;
            return getCommodityCategory(commodity.name, commodity.category) === activeCommodityTab;
        });

        // 如果是塑料分类且选中了子分类，进一步过滤
        if (activeCommodityTab === 'plastics' && activePlasticSubTab !== 'all') {
            tabCommodities = tabCommodities.filter(c =>
                c.name.toUpperCase().startsWith(activePlasticSubTab)
            );
        }

        // 自动选中该分类下的所有商品（塑料子分类通常不多）
        const newSelected = new Set();
        const maxSelect = activeCommodityTab === 'plastics' ? tabCommodities.length : 6;
        for (const commodity of tabCommodities.slice(0, maxSelect)) {
            newSelected.add(commodity.name);
        }

        // 只有当选中的商品发生变化时才更新
        if (newSelected.size > 0) {
            setSelectedCommodities(newSelected);
        }
    }, [activeCommodityTab, activePlasticSubTab, allCommodities]);

    // URL统计
    const urlStats = useMemo(() => {
        const stats = {};
        (data || []).forEach(item => {
            if (item.url) {
                const hostname = safeGetHostname(item.url);
                if (!stats[hostname]) {
                    stats[hostname] = {
                        hostname: hostname,
                        urls: new Set(),
                        count: 0,
                        items: []
                    };
                }
                stats[hostname].urls.add(item.url);
                stats[hostname].count++;
                stats[hostname].items.push(item.name || item.chinese_name);
            }
        });
        return Object.values(stats).map(s => ({
            ...s,
            urls: Array.from(s.urls)
        })).sort((a, b) => b.count - a.count);
    }, [data]);

    const filteredUrlStats = useMemo(() => {
        if (!urlInputValue) return urlStats;
        const searchLower = urlInputValue.toLowerCase();
        return urlStats.filter(stat =>
            stat.hostname.toLowerCase().includes(searchLower)
        );
    }, [urlStats, urlInputValue]);

    // 切换商品选中状态
    const toggleCommodity = (name) => {
        setSelectedCommodities(prev => {
            const newSet = new Set(prev);
            if (newSet.has(name)) {
                newSet.delete(name);
            } else {
                newSet.add(name);
            }
            return newSet;
        });
    };

    // 全选/全不选
    const selectAll = () => {
        // 智能全选：只选择符合当前数据源过滤的商品
        if (getSourceFilteredCommodities && getSourceFilteredCommodities.size > 0) {
            const filteredCommodities = allCommodities.filter(c => {
                const hasMatch = c.rawNames?.some(name => getSourceFilteredCommodities.has(name))
                    || getSourceFilteredCommodities.has(c.name);
                return hasMatch;
            });
            setSelectedCommodities(new Set(filteredCommodities.map(c => c.name)));
        } else {
            // 没有数据源过滤时，选择全部
            setSelectedCommodities(new Set(allCommodities.map(c => c.name)));
        }
    };

    const selectNone = () => {
        setSelectedCommodities(new Set());
    };

    // 根据来源过滤的商品列表（支持多选网站）
    const getSourceFilteredCommodities = useMemo(() => {
        // 如果没有选择任何国家或网站，不过滤
        if (!dataSources || (selectedCountry === 'all' && selectedWebsites.size === 0)) {
            return null; // 不过滤
        }

        // 获取选中网站的商品列表
        const allowedCommodities = new Set();
        const sources = dataSources.sources || {};

        for (const [countryCode, countryInfo] of Object.entries(sources)) {
            if (selectedCountry !== 'all' && countryCode !== selectedCountry) continue;

            for (const website of countryInfo.websites) {
                // 多选：检查网站是否在选中列表中，或者选中列表为空（表示全选该国家）
                if (selectedWebsites.size > 0 && !selectedWebsites.has(website.id)) continue;

                for (const commodity of website.commodities) {
                    allowedCommodities.add(commodity);
                    // 也添加归一化后的名称
                    const normalized = getNormalizedName(commodity);
                    if (normalized) allowedCommodities.add(normalized);
                }
            }
        }

        return allowedCommodities;
    }, [dataSources, selectedCountry, selectedWebsites]);

    // 根据选中国家过滤后的商品列表（用于商品选择器的级联）
    const commoditiesForSelectedCountry = useMemo(() => {
        if (selectedCountry === 'all' || !getSourceFilteredCommodities) {
            return allCommodities; // 全部国家时显示所有商品
        }
        // 只显示当前国家有的商品
        return allCommodities.filter(c => {
            return c.rawNames?.some(name => getSourceFilteredCommodities.has(name))
                || getSourceFilteredCommodities.has(c.name);
        });
    }, [allCommodities, selectedCountry, getSourceFilteredCommodities]);

    // 过滤商品列表（用于选择器搜索）- 基于当前TAB分类和选中国家
    const filteredCommodities = useMemo(() => {
        // 使用级联过滤后的商品列表
        let baseCommodities = commoditiesForSelectedCountry || allCommodities;

        // 先按 TAB 分类过滤
        if (activeCommodityTab !== 'all') {
            baseCommodities = baseCommodities.filter(c =>
                getCommodityCategory(c.name, c.category) === activeCommodityTab
            );
        }

        // 再按搜索词过滤
        if (!commoditySearchTerm) return baseCommodities;
        const searchLower = commoditySearchTerm.toLowerCase();
        return baseCommodities.filter(c =>
            c.name.toLowerCase().includes(searchLower) ||
            (c.source && c.source.toLowerCase().includes(searchLower))
        );
    }, [commoditiesForSelectedCountry, allCommodities, commoditySearchTerm, activeCommodityTab]);

    // 根据当前TAB获取对应分类的商品数量
    const getCommodityCountByTab = useCallback((tabId) => {
        return allCommodities.filter(commodity => {
            if (tabId === 'all') return true;
            return getCommodityCategory(commodity.name, commodity.category) === tabId;
        }).length;
    }, [allCommodities]);

    // 获取选中商品的显示数据（使用合并后的商品数据）
    const displayCommodities = useMemo(() => {
        const colors = ['#f59e0b', '#8b5cf6', '#3b82f6', '#10b981', '#ef4444', '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1', '#14b8a6', '#a855f7'];

        return allCommodities
            .filter(commodity => {
                // 先检查TAB分类过滤
                if (activeCommodityTab !== 'all') {
                    const commodityCategory = getCommodityCategory(commodity.name, commodity.category);
                    if (commodityCategory !== activeCommodityTab && commodityCategory !== 'all') return false;
                }
                // 塑料子分类过滤
                if (activeCommodityTab === 'plastics' && activePlasticSubTab !== 'all') {
                    // 检查商品名称是否以子分类开头（如 ABS、PP、PE、PS）
                    if (!commodity.name.toUpperCase().startsWith(activePlasticSubTab)) return false;
                }
                // 再检查是否选中
                if (!selectedCommodities.has(commodity.name)) return false;
                // 再检查来源过滤
                if (getSourceFilteredCommodities) {
                    const hasMatch = commodity.rawNames?.some(name => getSourceFilteredCommodities.has(name))
                        || getSourceFilteredCommodities.has(commodity.name);
                    if (!hasMatch) return false;
                }
                return true;
            })
            .map((commodity, idx) => {
                const price = commodity.price;
                // 尝试从所有原始名称获取历史数据
                let historyData = null;
                for (const rawName of commodity.rawNames || [commodity.name]) {
                    historyData = getHistoryData(rawName, price, timeRange === 'day' ? 24 : 7);
                    if (historyData && historyData.some(h => h.isReal)) break;
                }
                if (!historyData) {
                    historyData = getHistoryData(commodity.name, price, timeRange === 'day' ? 24 : 7);
                }

                // 为区域商品获取多区域历史数据
                let multiSourceHistory = null;
                if (commodity.isRegional && commodity.regions && commodity.regions.length > 0) {
                    multiSourceHistory = commodity.regions.map(region => {
                        const regionHistory = getHistoryData(region.fullName, region.price, timeRange === 'day' ? 24 : 7);
                        return {
                            source: region.name,
                            color: region.color,
                            url: commodity.url,
                            unit: region.unit || commodity.unit || '',  // 添加单位字段用于正确的磅/吨转换
                            data: regionHistory || []
                        };
                    }).filter(s => s.data && s.data.length > 0);
                }

                return {
                    id: commodity.name,
                    name: commodity.name,
                    basePrice: price,
                    currentPrice: price,
                    color: colors[idx % colors.length],
                    unit: commodity.unit || '',
                    change: commodity.change,
                    url: commodity.url,
                    source: commodity.source,
                    sources: commodity.sources || [],  // 多个来源
                    regions: commodity.regions || [],  // 区域信息
                    isRegional: commodity.isRegional,
                    historyData: historyData,
                    multiSourceHistory: multiSourceHistory,  // 多区域历史数据
                    dataItem: commodity
                };
            });
    }, [allCommodities, selectedCommodities, getHistoryData, timeRange, activeCommodityTab, activePlasticSubTab, getSourceFilteredCommodities]);

    // 加载状态移除全局阻塞
    // if (loading) return ...

    return (
        <div className="dashboard-container" style={{
            padding: '24px 32px 40px',
            position: 'relative',
            minHeight: '100vh',
            background: '#f8fafc'
        }}>
            {/* Header */}
            <div className="header" style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '24px',
                flexWrap: 'wrap',
                gap: '16px'
            }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: '24px', fontWeight: '700', color: '#111827' }}>市场概览</h1>
                    <p style={{ color: '#6b7280', marginTop: '4px', fontSize: '13px' }}>
                        实时大宗商品价格监控
                        {lastUpdate && (
                            <span style={{ marginLeft: '12px', color: '#9ca3af' }}>
                                更新: {new Date(lastUpdate).toLocaleTimeString()}
                            </span>
                        )}
                    </p>
                </div>

                {/* Controls */}
                <div className="controls" style={{
                    display: 'flex',
                    gap: '10px',
                    alignItems: 'center',
                    flexWrap: 'wrap'
                }}>
                    {/* 搜索框 */}
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        background: '#fff',
                        border: '1px solid #e5e7eb',
                        padding: '7px 12px',
                        borderRadius: '8px',
                        minWidth: '160px'
                    }}>
                        <Search size={14} color="#9ca3af" />
                        <input
                            type="text"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            placeholder="搜索..."
                            style={{
                                border: 'none',
                                outline: 'none',
                                fontSize: '13px',
                                color: '#374151',
                                background: 'transparent',
                                width: '100%'
                            }}
                        />
                        {searchTerm && (
                            <button onClick={() => setSearchTerm('')} style={{ border: 'none', background: 'none', padding: 0, cursor: 'pointer' }}>
                                <X size={12} color="#9ca3af" />
                            </button>
                        )}
                    </div>

                    {/* 1️⃣ 国家/来源选择器 - 放在最前面 */}
                    <div ref={sourceFilterRef} style={{ position: 'relative' }}>
                        <button
                            onClick={() => setShowSourceFilter(!showSourceFilter)}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                                background: selectedCountry !== 'all' ? '#dbeafe' : '#fff',
                                border: '1px solid #e5e7eb',
                                padding: '7px 12px',
                                borderRadius: '8px',
                                color: selectedCountry !== 'all' ? '#1e40af' : '#374151',
                                cursor: 'pointer',
                                fontSize: '13px',
                                fontWeight: '500'
                            }}
                        >
                            <Globe size={14} />
                            {selectedCountry === 'all' ? '🌍 全部国家' : `${dataSources?.sources?.[selectedCountry]?.flag || ''} ${dataSources?.sources?.[selectedCountry]?.name || selectedCountry}`}
                            <ChevronDown size={14} />
                        </button>

                        {showSourceFilter && dataSources && (
                            <div style={{
                                position: 'absolute',
                                top: '100%',
                                left: 0,
                                marginTop: '6px',
                                background: '#fff',
                                borderRadius: '12px',
                                boxShadow: '0 10px 40px -5px rgba(0, 0, 0, 0.15)',
                                border: '1px solid #e5e7eb',
                                width: '260px',
                                zIndex: 200,
                                overflow: 'hidden'
                            }}>
                                <div style={{ padding: '8px' }}>
                                    <div
                                        onClick={() => { setSelectedCountry('all'); setSelectedWebsites(new Set()); setShowSourceFilter(false); }}
                                        style={{
                                            padding: '10px 12px',
                                            cursor: 'pointer',
                                            borderRadius: '8px',
                                            background: selectedCountry === 'all' ? '#eff6ff' : 'transparent',
                                            marginBottom: '4px',
                                            fontSize: '13px',
                                            fontWeight: selectedCountry === 'all' ? '600' : '400'
                                        }}
                                    >
                                        🌍 全部国家 ({allCommodities.length} 商品)
                                    </div>
                                    {dataSources.cascade?.map(country => (
                                        <div
                                            key={country.code}
                                            onClick={() => {
                                                setSelectedCountry(country.code);
                                                setSelectedWebsites(new Set());
                                                setShowSourceFilter(false);
                                                // 自动选择该国家的商品
                                                setTimeout(() => {
                                                    const countryInfo = dataSources.sources?.[country.code];
                                                    if (countryInfo) {
                                                        const countryCommodities = new Set();
                                                        countryInfo.websites?.forEach(w => w.commodities?.forEach(c => {
                                                            countryCommodities.add(c);
                                                            const normalized = getNormalizedName(c);
                                                            if (normalized) countryCommodities.add(normalized);
                                                        }));

                                                        // 修改筛选逻辑：不强制使用 slice(0, 6) 限制，而是尝试保留用户之前感兴趣的商品类型
                                                        // 或者至少确保当前 Tab 下的商品被选中

                                                        const matchedCommodities = allCommodities.filter(c =>
                                                            c.rawNames?.some(name => countryCommodities.has(name)) || countryCommodities.has(c.name)
                                                        );

                                                        if (matchedCommodities.length > 0) {
                                                            // 1. 优先选择符合当前 Tab 分类的商品
                                                            let priorityCommodities = matchedCommodities.filter(c => {
                                                                if (activeCommodityTab === 'all') return true;
                                                                const category = getCommodityCategory(c.name, c.category);
                                                                return category === activeCommodityTab;
                                                            });

                                                            // 如果当前 Tab 下没有商品，则降级显示所有匹配商品
                                                            if (priorityCommodities.length === 0) {
                                                                priorityCommodities = matchedCommodities;
                                                            }

                                                            // 选中这些商品（最多显示 6 个，避免图表过于拥挤，但确保是相关的）
                                                            setSelectedCommodities(new Set(priorityCommodities.slice(0, 6).map(c => c.name)));
                                                        } else {
                                                            // 如果该国家完全没有商品，清空选择
                                                            setSelectedCommodities(new Set());
                                                        }
                                                    }
                                                }, 50);
                                            }}
                                            style={{
                                                padding: '10px 12px',
                                                cursor: 'pointer',
                                                borderRadius: '8px',
                                                background: selectedCountry === country.code ? '#eff6ff' : 'transparent',
                                                marginBottom: '4px',
                                                fontSize: '13px',
                                                fontWeight: selectedCountry === country.code ? '600' : '400',
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center'
                                            }}
                                        >
                                            <span>{country.flag} {country.name}</span>
                                            <span style={{ color: '#9ca3af', fontSize: '12px' }}>{country.commodity_count} 商品</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* 2️⃣ 商品选择器 - 基于选中国家过滤 */}
                    <div ref={commoditySelectorRef} style={{ position: 'relative' }}>
                        <button
                            onClick={() => setShowCommoditySelector(!showCommoditySelector)}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                                background: '#fff',
                                border: '1px solid #e5e7eb',
                                padding: '7px 12px',
                                borderRadius: '8px',
                                color: '#374151',
                                cursor: 'pointer',
                                fontSize: '13px',
                                fontWeight: '500'
                            }}
                        >
                            <Filter size={14} />
                            商品 ({selectedCommodities.size}/{(commoditiesForSelectedCountry || allCommodities).length})
                            <ChevronDown size={14} />
                        </button>

                        {showCommoditySelector && (
                            <div style={{
                                position: 'absolute',
                                top: '100%',
                                left: 0,
                                marginTop: '6px',
                                background: '#fff',
                                borderRadius: '12px',
                                boxShadow: '0 10px 40px -5px rgba(0, 0, 0, 0.15)',
                                border: '1px solid #e5e7eb',
                                width: '320px',
                                zIndex: 200,
                                overflow: 'hidden'
                            }}>
                                {/* 搜索框 */}
                                <div style={{
                                    padding: '12px',
                                    borderBottom: '1px solid #f3f4f6',
                                    background: '#fafafa'
                                }}>
                                    <div style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '8px',
                                        background: '#fff',
                                        border: '1px solid #e5e7eb',
                                        borderRadius: '8px',
                                        padding: '8px 12px'
                                    }}>
                                        <Search size={14} color="#9ca3af" />
                                        <input
                                            type="text"
                                            value={commoditySearchTerm}
                                            onChange={(e) => setCommoditySearchTerm(e.target.value)}
                                            placeholder="搜索商品..."
                                            style={{
                                                border: 'none',
                                                outline: 'none',
                                                fontSize: '13px',
                                                width: '100%',
                                                background: 'transparent'
                                            }}
                                            autoFocus
                                        />
                                        {commoditySearchTerm && (
                                            <button onClick={() => setCommoditySearchTerm('')} style={{ border: 'none', background: 'none', padding: 0, cursor: 'pointer' }}>
                                                <X size={12} color="#9ca3af" />
                                            </button>
                                        )}
                                    </div>

                                    {/* 快捷操作 */}
                                    <div style={{
                                        display: 'flex',
                                        gap: '8px',
                                        marginTop: '10px',
                                        fontSize: '12px'
                                    }}>
                                        <button
                                            onClick={selectAll}
                                            style={{
                                                padding: '4px 10px',
                                                borderRadius: '6px',
                                                border: '1px solid #e5e7eb',
                                                background: '#fff',
                                                color: '#374151',
                                                cursor: 'pointer',
                                                fontSize: '12px'
                                            }}
                                        >
                                            {getSourceFilteredCommodities && getSourceFilteredCommodities.size > 0
                                                ? '选择当前源'
                                                : '全选'}
                                        </button>
                                        <button
                                            onClick={selectNone}
                                            style={{
                                                padding: '4px 10px',
                                                borderRadius: '6px',
                                                border: '1px solid #e5e7eb',
                                                background: '#fff',
                                                color: '#374151',
                                                cursor: 'pointer',
                                                fontSize: '12px'
                                            }}
                                        >
                                            全不选
                                        </button>
                                        <span style={{
                                            marginLeft: 'auto',
                                            color: '#9ca3af',
                                            alignSelf: 'center'
                                        }}>
                                            已选 {selectedCommodities.size} 项
                                            {getSourceFilteredCommodities && getSourceFilteredCommodities.size > 0 && (
                                                <span style={{ color: '#f59e0b', marginLeft: '4px' }}>
                                                    · {filteredCommodities.filter(c => {
                                                        const willBeFiltered = !(
                                                            c.rawNames?.some(name => getSourceFilteredCommodities.has(name))
                                                            || getSourceFilteredCommodities.has(c.name)
                                                        );
                                                        return selectedCommodities.has(c.name) && willBeFiltered;
                                                    }).length} 被过滤
                                                </span>
                                            )}
                                        </span>
                                    </div>
                                </div>

                                {/* 商品列表 - 滚动区域 */}
                                <div style={{
                                    maxHeight: '360px',
                                    overflowY: 'auto',
                                    padding: '8px'
                                }}>
                                    {filteredCommodities.length === 0 ? (
                                        <div style={{
                                            padding: '24px',
                                            textAlign: 'center',
                                            color: '#9ca3af',
                                            fontSize: '13px'
                                        }}>
                                            未找到匹配的商品
                                        </div>
                                    ) : (
                                        filteredCommodities.map((comm, idx) => {
                                            const isSelected = selectedCommodities.has(comm.name);
                                            const isUp = (comm.change || 0) >= 0;

                                            // 检查是否会被数据源过滤
                                            const willBeFiltered = getSourceFilteredCommodities && getSourceFilteredCommodities.size > 0 && !(
                                                comm.rawNames?.some(name => getSourceFilteredCommodities.has(name))
                                                || getSourceFilteredCommodities.has(comm.name)
                                            );

                                            return (
                                                <div
                                                    key={idx}
                                                    onClick={() => toggleCommodity(comm.name)}
                                                    style={{
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        gap: '10px',
                                                        padding: '10px 12px',
                                                        cursor: 'pointer',
                                                        borderRadius: '8px',
                                                        marginBottom: '4px',
                                                        background: isSelected ? '#eff6ff' : 'transparent',
                                                        border: isSelected ? '1px solid #bfdbfe' : '1px solid transparent',
                                                        transition: 'all 0.15s ease',
                                                        opacity: willBeFiltered ? 0.4 : 1,  // 被过滤的商品变灰
                                                        position: 'relative'
                                                    }}
                                                    onMouseEnter={e => {
                                                        if (!isSelected) e.currentTarget.style.background = '#f9fafb';
                                                    }}
                                                    onMouseLeave={e => {
                                                        if (!isSelected) e.currentTarget.style.background = 'transparent';
                                                    }}
                                                >
                                                    {/* Checkbox */}
                                                    <div style={{
                                                        width: '18px',
                                                        height: '18px',
                                                        border: isSelected ? 'none' : '2px solid #d1d5db',
                                                        borderRadius: '4px',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        justifyContent: 'center',
                                                        background: isSelected ? '#3b82f6' : '#fff',
                                                        flexShrink: 0,
                                                        transition: 'all 0.15s ease'
                                                    }}>
                                                        {isSelected && <Check size={12} color="#fff" strokeWidth={3} />}
                                                    </div>

                                                    {/* 商品信息 */}
                                                    <div style={{ flex: 1, minWidth: 0 }}>
                                                        <div style={{
                                                            fontSize: '13px',
                                                            fontWeight: '500',
                                                            color: '#111827',
                                                            whiteSpace: 'nowrap',
                                                            overflow: 'hidden',
                                                            textOverflow: 'ellipsis',
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            gap: '6px'
                                                        }}>
                                                            <span>{comm.name}</span>
                                                            {willBeFiltered && (
                                                                <span style={{
                                                                    fontSize: '10px',
                                                                    color: '#f59e0b',
                                                                    background: '#fef3c7',
                                                                    padding: '2px 6px',
                                                                    borderRadius: '4px',
                                                                    fontWeight: '600',
                                                                    whiteSpace: 'nowrap'
                                                                }}>
                                                                    被过滤
                                                                </span>
                                                            )}
                                                        </div>
                                                        <div style={{
                                                            fontSize: '11px',
                                                            color: '#9ca3af',
                                                            marginTop: '2px'
                                                        }}>
                                                            {comm.source}
                                                        </div>
                                                    </div>

                                                    {/* 价格和涨跌 */}
                                                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                                                        <div style={{
                                                            fontSize: '13px',
                                                            fontWeight: '600',
                                                            color: '#111827'
                                                        }}>
                                                            ${parseFloat(comm.price || 0).toFixed(2)}
                                                        </div>
                                                        <div style={{
                                                            fontSize: '11px',
                                                            fontWeight: '500',
                                                            color: isUp ? '#10b981' : '#ef4444'
                                                        }}>
                                                            {isUp ? '+' : ''}{parseFloat(comm.change || 0).toFixed(2)}%
                                                        </div>
                                                    </div>
                                                </div>
                                            );
                                        })
                                    )}
                                </div>
                            </div>
                        )}
                    </div>

                    {/* 时间范围切换 */}
                    <div style={{
                        background: '#fff',
                        border: '1px solid #e5e7eb',
                        padding: '3px',
                        borderRadius: '8px',
                        display: 'flex'
                    }}>
                        <button
                            onClick={() => setTimeRange('day')}
                            style={{
                                padding: '5px 14px',
                                borderRadius: '6px',
                                border: 'none',
                                background: timeRange === 'day' ? '#3b82f6' : 'transparent',
                                color: timeRange === 'day' ? '#fff' : '#6b7280',
                                fontWeight: '500',
                                fontSize: '13px',
                                cursor: 'pointer',
                                transition: 'all 0.15s ease'
                            }}
                        >
                            日
                        </button>
                        <button
                            onClick={() => setTimeRange('week')}
                            style={{
                                padding: '5px 14px',
                                borderRadius: '6px',
                                border: 'none',
                                background: timeRange === 'week' ? '#3b82f6' : 'transparent',
                                color: timeRange === 'week' ? '#fff' : '#6b7280',
                                fontWeight: '500',
                                fontSize: '13px',
                                cursor: 'pointer',
                                transition: 'all 0.15s ease'
                            }}
                        >
                            周
                        </button>
                        <button
                            onClick={() => setTimeRange('month')}
                            style={{
                                padding: '5px 14px',
                                borderRadius: '6px',
                                border: 'none',
                                background: timeRange === 'month' ? '#3b82f6' : 'transparent',
                                color: timeRange === 'month' ? '#fff' : '#6b7280',
                                fontWeight: '500',
                                fontSize: '13px',
                                cursor: 'pointer',
                                transition: 'all 0.15s ease'
                            }}
                        >
                            月
                        </button>
                    </div>

                    {/* 货币切换 */}
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        background: '#fff',
                        border: '1px solid #e5e7eb',
                        padding: '3px',
                        borderRadius: '8px'
                    }}>
                        <button
                            onClick={() => setCurrency('CNY')}
                            style={{
                                padding: '5px 12px',
                                borderRadius: '6px',
                                border: 'none',
                                background: currency === 'CNY' ? '#dc2626' : 'transparent',
                                color: currency === 'CNY' ? '#fff' : '#6b7280',
                                fontWeight: '600',
                                fontSize: '13px',
                                cursor: 'pointer',
                                transition: 'all 0.15s ease'
                            }}
                        >
                            ¥ CNY
                        </button>
                        <button
                            onClick={() => setCurrency('USD')}
                            style={{
                                padding: '5px 12px',
                                borderRadius: '6px',
                                border: 'none',
                                background: currency === 'USD' ? '#16a34a' : 'transparent',
                                color: currency === 'USD' ? '#fff' : '#6b7280',
                                fontWeight: '600',
                                fontSize: '13px',
                                cursor: 'pointer',
                                transition: 'all 0.15s ease'
                            }}
                        >
                            $ USD
                        </button>
                    </div>

                    {/* 刷新按钮 - 使用同步刷新获取最新数据 */}
                    <button
                        onClick={async () => {
                            setRefreshing(true);
                            try {
                                // 使用同步刷新(sync=true)确保获取最新数据
                                const [dataResponse, historyResponse] = await Promise.all([
                                    api.getData(true, true),  // sync=true 同步刷新
                                    api.getPriceHistory(null, { day: 1, week: 7, month: 30 }[timeRange] || 7, true)  // bypassCache
                                ]);
                                const responseData = dataResponse.data || dataResponse;
                                setData(responseData.data || []);
                                setLastUpdate(responseData.timestamp || new Date().toISOString());
                                // 更新历史数据并重置缓存标记
                                const historyData = historyResponse.data?.data || historyResponse.data?.commodities || {};
                                setPriceHistory(historyData);
                                priceHistoryLoadingRef.current = null; // 重置缓存标记
                                console.log("✅ 数据刷新完成:", {
                                    commodities: responseData.data?.length,
                                    timestamp: responseData.timestamp,
                                    source: responseData.source
                                });
                            } catch (err) {
                                console.error("Refresh failed:", err);
                            } finally {
                                setRefreshing(false);
                            }
                        }}
                        disabled={refreshing}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            background: refreshing ? '#e5e7eb' : '#10b981',
                            border: 'none',
                            padding: '7px 14px',
                            borderRadius: '8px',
                            color: '#fff',
                            cursor: refreshing ? 'not-allowed' : 'pointer',
                            fontWeight: '500',
                            fontSize: '13px',
                            transition: 'all 0.15s ease'
                        }}
                    >
                        <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
                        {refreshing ? '刷新中...' : '刷新'}
                    </button>

                    {/* 设置按钮 */}
                    <button
                        onClick={() => setShowSettings(true)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            background: '#fff',
                            border: '1px solid #e5e7eb',
                            padding: '7px 14px',
                            borderRadius: '8px',
                            color: '#374151',
                            cursor: 'pointer',
                            fontSize: '13px'
                        }}
                    >
                        <Settings size={14} />
                        设置
                    </button>
                </div>
            </div>

            {/* Main Layout */}
            <div className="dashboard-main-layout" style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '24px' }}>
                <div className="main-content">
                    {/* Summary Cards */}
                    <div className="summary-cards-grid" style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                        gap: '16px',
                        marginBottom: '24px'
                    }}>
                        {/* 汇率卡片 */}
                        <div className="exchange-rate-card" style={{
                            background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
                            padding: '20px',
                            borderRadius: '12px',
                            boxShadow: '0 4px 12px -2px rgba(59, 130, 246, 0.25)',
                            color: '#fff'
                        }}>
                            <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                <span style={{ fontSize: '13px', fontWeight: '500', opacity: 0.9 }}>USD/CNY 汇率</span>
                                <span style={{
                                    fontSize: '11px',
                                    fontWeight: '600',
                                    background: 'rgba(255,255,255,0.2)',
                                    padding: '2px 8px',
                                    borderRadius: '999px'
                                }}>实时</span>
                            </div>
                            <div className="rate-value" style={{ fontSize: '28px', fontWeight: '700' }}>¥{EXCHANGE_RATE.toFixed(4)}</div>
                            <div className="rate-info" style={{ fontSize: '11px', opacity: 0.8, marginTop: '4px' }}>1 USD = {EXCHANGE_RATE} CNY</div>
                        </div>

                        {/* 前4个商品卡片 */}
                        {loading ? (
                            Array(4).fill(0).map((_, i) => (
                                <div key={i} className="commodity-card-skeleton" style={{
                                    background: '#fff',
                                    padding: '20px',
                                    borderRadius: '12px',
                                    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
                                    border: '1px solid #f3f4f6',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    height: '110px'
                                }}>
                                    <RefreshCw className="animate-spin" size={24} color="#cbd5e1" />
                                </div>
                            ))
                        ) : (
                            displayCommodities.slice(0, 4).map((comm, index) => {
                                const isUp = (comm.change || 0) >= 0;
                                return (
                                    <div key={index} className="commodity-card" style={{
                                        background: '#fff',
                                        padding: '20px',
                                        borderRadius: '12px',
                                        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
                                        border: '1px solid #f3f4f6'
                                    }}>
                                        <div className="card-content-header" style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                                            <div className="commodity-info">
                                                <span style={{ color: '#374151', fontSize: '13px', fontWeight: '500' }}>
                                                    {comm.name}
                                                </span>
                                                {comm.source && (
                                                    <div className="commodity-source" style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>
                                                        {comm.source}
                                                    </div>
                                                )}
                                            </div>
                                            <span style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                fontSize: '11px',
                                                fontWeight: '600',
                                                color: isUp ? '#10b981' : '#ef4444',
                                                background: isUp ? '#d1fae5' : '#fee2e2',
                                                padding: '2px 8px',
                                                borderRadius: '999px',
                                                height: 'fit-content'
                                            }}>
                                                {isUp ? <ArrowUp size={10} /> : <ArrowDown size={10} />}
                                                {Math.abs(comm.change || 0).toFixed(2)}%
                                            </span>
                                        </div>
                                        <div className="commodity-price" style={{ fontSize: '24px', fontWeight: '700', color: '#111827' }}>
                                            {getCurrencySymbol()}{formatPrice(comm.currentPrice, comm.unit)}
                                            {comm.unit && (
                                                <span style={{ fontSize: '12px', color: '#6b7280', marginLeft: '4px', fontWeight: '500' }}>
                                                    /{comm.unit.replace(/USD|CNY|RMB|美元|人民币|\$|¥|\//gi, '').trim()}
                                                </span>
                                            )}
                                        </div>
                                    </div>
                                );
                            }))}
                    </div>

                    {/* ==================== 商品分类 TAB 区域 ==================== */}
                    <div className="commodity-tabs-container" style={{
                        background: '#fff',
                        borderRadius: '16px',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                        marginBottom: '24px',
                        overflow: 'hidden'
                    }}>
                        {/* Tab栏标题 */}
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '16px 20px',
                            borderBottom: '1px solid #e2e8f0'
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                <div style={{
                                    width: '32px',
                                    height: '32px',
                                    borderRadius: '8px',
                                    background: 'linear-gradient(135deg, #f59e0b, #d97706)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center'
                                }}>
                                    <DollarSign size={16} color="#fff" />
                                </div>
                                <div>
                                    <div style={{ fontWeight: '600', fontSize: '15px', color: '#1e293b' }}>
                                        数据仪表盘
                                    </div>
                                    <div style={{ fontSize: '12px', color: '#64748b' }}>
                                        按分类查看商品行情
                                    </div>
                                </div>
                            </div>
                            {/* 表头配置按钮 */}
                            <div ref={columnSettingsRef} style={{ position: 'relative' }}>
                                <button
                                    onClick={() => setShowColumnSettings(!showColumnSettings)}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '6px',
                                        padding: '8px 14px',
                                        background: showColumnSettings ? '#eff6ff' : '#f8fafc',
                                        border: '1px solid #e2e8f0',
                                        borderRadius: '8px',
                                        color: '#374151',
                                        cursor: 'pointer',
                                        fontSize: '13px',
                                        fontWeight: '500'
                                    }}
                                >
                                    <Settings size={14} />
                                    表头配置
                                </button>

                                {/* 表头配置弹窗 */}
                                {showColumnSettings && (
                                    <div style={{
                                        position: 'absolute',
                                        top: '100%',
                                        right: 0,
                                        marginTop: '6px',
                                        background: '#fff',
                                        borderRadius: '12px',
                                        boxShadow: '0 10px 40px -5px rgba(0, 0, 0, 0.15)',
                                        border: '1px solid #e5e7eb',
                                        width: '220px',
                                        zIndex: 200,
                                        padding: '12px'
                                    }}>
                                        <div style={{ fontSize: '12px', fontWeight: '600', color: '#374151', marginBottom: '10px' }}>
                                            选择显示的列
                                        </div>
                                        {tableColumns.map((col, idx) => (
                                            <div
                                                key={col.id}
                                                onClick={() => {
                                                    const newColumns = [...tableColumns];
                                                    newColumns[idx] = { ...col, visible: !col.visible };
                                                    setTableColumns(newColumns);
                                                }}
                                                style={{
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '8px',
                                                    padding: '8px 10px',
                                                    cursor: 'pointer',
                                                    borderRadius: '6px',
                                                    background: col.visible ? '#eff6ff' : 'transparent',
                                                    marginBottom: '4px'
                                                }}
                                            >
                                                <div style={{
                                                    width: '16px',
                                                    height: '16px',
                                                    border: col.visible ? 'none' : '2px solid #d1d5db',
                                                    borderRadius: '4px',
                                                    background: col.visible ? '#3b82f6' : '#fff',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'center'
                                                }}>
                                                    {col.visible && <Check size={10} color="#fff" strokeWidth={3} />}
                                                </div>
                                                <span style={{ fontSize: '13px', color: '#374151' }}>{col.label}</span>
                                            </div>
                                        ))}
                                        <button
                                            onClick={() => setShowColumnSettings(false)}
                                            style={{
                                                width: '100%',
                                                marginTop: '8px',
                                                padding: '8px',
                                                background: '#3b82f6',
                                                color: '#fff',
                                                border: 'none',
                                                borderRadius: '6px',
                                                fontSize: '12px',
                                                cursor: 'pointer'
                                            }}
                                        >
                                            确定
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* Tab栏 - 参考供应商展示形式 */}
                        <div style={{
                            display: 'flex',
                            borderBottom: '1px solid #e2e8f0',
                            background: '#f8fafc'
                        }}>
                            {COMMODITY_TABS.map(tab => {
                                const count = getCommodityCountByTab(tab.id);
                                const isActive = activeCommodityTab === tab.id;
                                return (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveCommodityTab(tab.id)}
                                        style={{
                                            flex: 1,
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            gap: '8px',
                                            padding: '14px 16px',
                                            background: isActive ? '#fff' : 'transparent',
                                            border: 'none',
                                            borderBottom: isActive ? `3px solid ${tab.color}` : '3px solid transparent',
                                            cursor: 'pointer',
                                            transition: 'all 0.2s',
                                            color: isActive ? tab.color : '#64748b',
                                            fontWeight: isActive ? '600' : '400',
                                            fontSize: '14px'
                                        }}
                                    >
                                        <span style={{ fontSize: '16px' }}>{tab.icon}</span>
                                        {tab.name}
                                        <span style={{
                                            fontSize: '11px',
                                            background: isActive ? tab.color : '#e2e8f0',
                                            color: isActive ? '#fff' : '#64748b',
                                            padding: '2px 8px',
                                            borderRadius: '10px',
                                            fontWeight: '600'
                                        }}>
                                            {count}
                                        </span>
                                    </button>
                                );
                            })}
                        </div>

                        {/* 塑料子分类TAB - 仅在塑料分类下显示 */}
                        {activeCommodityTab === 'plastics' && COMMODITY_TABS.find(t => t.id === 'plastics')?.subTabs && (
                            <div style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                padding: '12px 20px',
                                background: '#f0fdf4',
                                borderBottom: '1px solid #bbf7d0',
                                overflowX: 'auto'
                            }}>
                                <span style={{ fontSize: '12px', color: '#166534', fontWeight: '500', marginRight: '4px' }}>大类:</span>
                                {COMMODITY_TABS.find(t => t.id === 'plastics').subTabs.map(subTab => {
                                    const isActive = activePlasticSubTab === subTab.id;
                                    // 计算该子分类的商品数量（基于所有塑料商品）
                                    const plasticCommodities = allCommodities.filter(c =>
                                        getCommodityCategory(c.name, c.category) === 'plastics'
                                    );
                                    const subCount = subTab.id === 'all'
                                        ? plasticCommodities.length
                                        : plasticCommodities.filter(c => c.name.toUpperCase().startsWith(subTab.id)).length;
                                    return (
                                        <button
                                            key={subTab.id}
                                            onClick={() => setActivePlasticSubTab(subTab.id)}
                                            title={subTab.desc}
                                            style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '6px',
                                                padding: '6px 14px',
                                                borderRadius: '20px',
                                                border: isActive ? `2px solid ${subTab.color}` : '1px solid #d1d5db',
                                                background: isActive ? subTab.color : '#fff',
                                                color: isActive ? '#fff' : '#374151',
                                                cursor: 'pointer',
                                                fontSize: '13px',
                                                fontWeight: isActive ? '600' : '500',
                                                transition: 'all 0.15s ease',
                                                whiteSpace: 'nowrap'
                                            }}
                                        >
                                            {subTab.name}
                                            {subCount > 0 && (
                                                <span style={{
                                                    fontSize: '10px',
                                                    background: isActive ? 'rgba(255,255,255,0.3)' : '#e5e7eb',
                                                    padding: '1px 6px',
                                                    borderRadius: '10px',
                                                    fontWeight: '600'
                                                }}>
                                                    {subCount}
                                                </span>
                                            )}
                                        </button>
                                    );
                                })}
                            </div>
                        )}

                        {/* 可配置表头的数据表格 */}
                        <div style={{ padding: '16px 20px', overflowX: 'auto' }}>
                            {loading ? (
                                <div style={{ padding: '32px', textAlign: 'center' }}>
                                    <RefreshCw className="animate-spin" size={24} color="#cbd5e1" style={{ margin: '0 auto' }} />
                                    <div style={{ marginTop: '12px', color: '#94a3b8', fontSize: '13px' }}>加载商品数据...</div>
                                </div>
                            ) : displayCommodities.length === 0 ? (
                                <div style={{ textAlign: 'center', padding: '32px', color: '#9ca3af' }}>
                                    当前分类暂无商品数据
                                </div>
                            ) : (
                                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
                                    <thead>
                                        <tr style={{ borderBottom: '2px solid #e2e8f0' }}>
                                            {tableColumns.filter(col => col.visible).map(col => (
                                                <th key={col.id} style={{
                                                    padding: '10px 12px',
                                                    textAlign: 'left',
                                                    fontWeight: '600',
                                                    color: '#374151',
                                                    width: col.width,
                                                    whiteSpace: 'nowrap'
                                                }}>
                                                    {col.label}
                                                </th>
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {displayCommodities.slice(0, 10).map((comm, idx) => {
                                            const isUp = (comm.change || 0) >= 0;
                                            return (
                                                <tr key={comm.id || idx} style={{
                                                    borderBottom: '1px solid #f3f4f6',
                                                    transition: 'background 0.15s'
                                                }}
                                                    onMouseEnter={e => e.currentTarget.style.background = '#f9fafb'}
                                                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                                                >
                                                    {tableColumns.filter(col => col.visible).map(col => (
                                                        <td key={col.id} style={{ padding: '12px', color: '#374151' }}>
                                                            {col.id === 'name' && (
                                                                <div style={{ fontWeight: '500' }}>{comm.name}</div>
                                                            )}
                                                            {col.id === 'price' && (
                                                                <span style={{ fontWeight: '600', color: '#111827' }}>
                                                                    {getCurrencySymbol()}{formatPrice(comm.currentPrice, comm.unit)}
                                                                </span>
                                                            )}
                                                            {col.id === 'change' && (
                                                                <span style={{
                                                                    display: 'inline-flex',
                                                                    alignItems: 'center',
                                                                    gap: '4px',
                                                                    fontSize: '12px',
                                                                    fontWeight: '600',
                                                                    color: isUp ? '#10b981' : '#ef4444',
                                                                    background: isUp ? '#d1fae5' : '#fee2e2',
                                                                    padding: '2px 8px',
                                                                    borderRadius: '999px'
                                                                }}>
                                                                    {isUp ? <ArrowUp size={10} /> : <ArrowDown size={10} />}
                                                                    {Math.abs(comm.change || 0).toFixed(2)}%
                                                                </span>
                                                            )}
                                                            {col.id === 'source' && (
                                                                <span style={{ color: '#6b7280', fontSize: '12px' }}>
                                                                    {comm.source || '-'}
                                                                </span>
                                                            )}
                                                            {col.id === 'unit' && (
                                                                <span style={{ color: '#9ca3af', fontSize: '12px' }}>
                                                                    {comm.unit?.replace(/USD|CNY|RMB|美元|人民币|\$|¥|\//gi, '').trim() || '-'}
                                                                </span>
                                                            )}
                                                            {col.id === 'update' && (
                                                                <span style={{ color: '#9ca3af', fontSize: '12px' }}>
                                                                    {lastUpdate ? new Date(lastUpdate).toLocaleTimeString() : '-'}
                                                                </span>
                                                            )}
                                                        </td>
                                                    ))}
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            )}
                        </div>
                    </div>

                    {/* Charts Grid */}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
                        gap: '20px',
                        alignItems: 'start'
                    }}>
                        {loading ? (
                            <div style={{
                                gridColumn: '1 / -1',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                height: '200px',
                                fontSize: '16px',
                                color: '#6b7280',
                                background: '#fff',
                                borderRadius: '12px'
                            }}>
                                <RefreshCw className="animate-spin" style={{ marginRight: '8px' }} size={20} />
                                加载商品数据...
                            </div>
                        ) : error ? (
                            <div style={{
                                gridColumn: '1 / -1',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                height: '200px',
                                fontSize: '16px',
                                color: '#ef4444',
                                background: '#fff',
                                borderRadius: '12px'
                            }}>
                                错误: {error}
                            </div>
                        ) : displayCommodities.length === 0 ? (
                            <div style={{
                                gridColumn: '1 / -1',
                                background: '#fff',
                                padding: '48px',
                                borderRadius: '12px',
                                textAlign: 'center',
                                color: '#6b7280'
                            }}>
                                <Filter size={48} style={{ marginBottom: '16px', opacity: 0.3 }} />
                                {selectedCommodities.size === 0 ? (
                                    // 真的没选择商品
                                    <>
                                        <p style={{ fontSize: '15px', marginBottom: '8px', fontWeight: '600' }}>未选择任何商品</p>
                                        <p style={{ fontSize: '13px', color: '#9ca3af' }}>
                                            点击上方"商品"按钮选择要显示的商品
                                        </p>
                                    </>
                                ) : (
                                    // 选择了商品但被数据来源过滤掉了
                                    <>
                                        <p style={{ fontSize: '15px', marginBottom: '8px', fontWeight: '600', color: '#f59e0b' }}>
                                            已选择 {selectedCommodities.size} 个商品，但都被数据来源筛选器过滤
                                        </p>
                                        <p style={{ fontSize: '13px', color: '#9ca3af', marginBottom: '16px' }}>
                                            当前数据来源: {selectedCountry === 'all' ? '全部来源' : dataSources?.sources?.[selectedCountry]?.name}
                                            {selectedWebsites.size > 0 && ` · ${selectedWebsites.size} 个网站`}
                                        </p>
                                        <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
                                            <button
                                                onClick={() => {
                                                    setSelectedCountry('all');
                                                    setSelectedWebsites(new Set());
                                                }}
                                                style={{
                                                    padding: '8px 16px',
                                                    borderRadius: '8px',
                                                    border: '1px solid #e5e7eb',
                                                    background: '#fff',
                                                    color: '#374151',
                                                    fontSize: '13px',
                                                    cursor: 'pointer',
                                                    fontWeight: '500'
                                                }}
                                            >
                                                清除数据来源筛选
                                            </button>
                                            <button
                                                onClick={() => setShowCommoditySelector(true)}
                                                style={{
                                                    padding: '8px 16px',
                                                    borderRadius: '8px',
                                                    border: 'none',
                                                    background: '#3b82f6',
                                                    color: '#fff',
                                                    fontSize: '13px',
                                                    cursor: 'pointer',
                                                    fontWeight: '500'
                                                }}
                                            >
                                                重新选择商品
                                            </button>
                                        </div>
                                    </>
                                )}
                            </div>
                        ) : (
                            displayCommodities.map((comm, index) => {
                                const isLastOdd = index === displayCommodities.length - 1 && displayCommodities.length % 2 !== 0;
                                return (
                                    <CommodityCard
                                        key={comm.id || index}
                                        comm={comm}
                                        realItem={comm.dataItem}
                                        multiSourceItems={comm.sources}
                                        currentPrice={comm.currentPrice}
                                        unit={comm.unit}
                                        historyData={comm.historyData}
                                        multiSourceHistory={comm.multiSourceHistory}
                                        currencySymbol={getCurrencySymbol()}
                                        formatPrice={formatPrice}
                                        isLastOdd={isLastOdd}
                                        currency={currency}
                                        exchangeRate={EXCHANGE_RATE}
                                    />
                                );
                            })
                        )}
                    </div>
                </div>

                {/* Sidebar */}
                <div className="sidebar-content" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <ExchangeStatus />
                    <AIAnalysis />
                    <NewsFeed />
                </div>
            </div>

            {/* Settings Modal */}
            {showSettings && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'rgba(0,0,0,0.5)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 1000
                }}>
                    <div style={{
                        background: '#fff',
                        borderRadius: '16px',
                        width: '500px',
                        maxWidth: '90%',
                        maxHeight: '80vh',
                        display: 'flex',
                        flexDirection: 'column',
                        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)'
                    }}>
                        <div style={{ padding: '20px', borderBottom: '1px solid #e5e7eb', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: '600' }}>配置设置</h2>
                            <button onClick={() => setShowSettings(false)} style={{ background: 'none', border: 'none', padding: '4px', cursor: 'pointer' }}>
                                <X size={24} color="#6b7280" />
                            </button>
                        </div>

                        <div style={{ padding: '20px', overflowY: 'auto' }}>
                            <h3 style={{ fontSize: '13px', fontWeight: '600', color: '#374151', marginBottom: '10px' }}>爬取目标 URL</h3>

                            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '20px' }}>
                                {(config.target_urls || []).map((url, index) => (
                                    <div key={index} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '10px', background: '#f9f9f9', borderRadius: '8px', border: '1px solid #f3f4f6' }}>
                                        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', fontSize: '13px', color: '#4b5563' }}>{url}</span>
                                        <button onClick={() => handleDeleteUrl(index)} style={{ padding: '6px', color: '#ef4444', background: 'none', border: 'none', cursor: 'pointer' }}>
                                            <Trash2 size={14} />
                                        </button>
                                    </div>
                                ))}
                                {(!config.target_urls || config.target_urls.length === 0) && (
                                    <p style={{ color: '#9ca3af', fontSize: '13px', textAlign: 'center', padding: '20px' }}>暂无配置的 URL</p>
                                )}
                            </div>

                            <div style={{ display: 'flex', gap: '10px' }}>
                                <input
                                    type="text"
                                    value={newUrl}
                                    onChange={(e) => setNewUrl(e.target.value)}
                                    placeholder="输入新的 URL..."
                                    style={{ flex: 1, padding: '8px 12px', borderRadius: '8px', border: '1px solid #d1d5db', fontSize: '13px' }}
                                />
                                <button
                                    onClick={handleAddUrl}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '5px',
                                        background: '#f3f4f6',
                                        border: '1px solid #e5e7eb',
                                        color: '#374151',
                                        padding: '8px 16px',
                                        borderRadius: '8px',
                                        fontSize: '13px',
                                        fontWeight: '500',
                                        cursor: 'pointer'
                                    }}
                                >
                                    <Plus size={14} /> 添加
                                </button>
                            </div>
                        </div>

                        <div style={{ padding: '20px', borderTop: '1px solid #e5e7eb', display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                            <button
                                onClick={() => setShowSettings(false)}
                                style={{
                                    padding: '8px 16px',
                                    borderRadius: '8px',
                                    border: '1px solid #e5e7eb',
                                    background: '#fff',
                                    color: '#374151',
                                    fontSize: '13px',
                                    fontWeight: '500',
                                    cursor: 'pointer'
                                }}
                            >
                                取消
                            </button>
                            <button
                                onClick={handleSaveConfig}
                                disabled={savingConfig}
                                style={{
                                    padding: '8px 16px',
                                    borderRadius: '8px',
                                    border: 'none',
                                    background: '#3b82f6',
                                    color: '#fff',
                                    fontSize: '13px',
                                    fontWeight: '500',
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px'
                                }}
                            >
                                <Save size={14} /> {savingConfig ? '保存中...' : '保存配置'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Dashboard;
