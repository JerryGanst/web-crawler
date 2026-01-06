import React, { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { ArrowUp, ArrowDown, RefreshCw, Settings, Plus, Trash2, X, Save, Eye, Check, Calendar, ExternalLink, Globe, Search, DollarSign, Filter, ChevronDown } from 'lucide-react';
import CommodityCard from '../components/CommodityCard';
import ExchangeStatus from '../components/ExchangeStatus';
import NewsFeed from '../components/NewsFeed';
import AIAnalysis from '../components/AIAnalysis';
import api from '../services/api';
// ECharts 按需导入
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
                const regex = new RegExp(`(^|[^a-z])\${kwLower}($|[^a-z])`, 'i');
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
    // 铜
    'Copper': '铜',
    'COMEX铜': '铜',
    'COMEX Copper': '铜',
    '沪铜': '铜',
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
    // 铅
    'Lead': '铅',
    '铅': '铅',
    // 镍
    'Nickel': '镍',
    '镍': '镍',
    // 锡
    'Tin': '锡',
    '锡': '锡',
    // 锌
    'Zinc': '锌',
    '锌': '锌',
    // 能源扩展
    'Natural Gas (Henry Hub)': '天然气 (Henry Hub)',
    'Heating Oil': '取暖油',
    'RBOB Gasoline': 'RBOB汽油',
    'Coal': '煤炭',
    // 农产品
    'Corn': '玉米',
    'Wheat': '小麦',
    'Soybeans': '大豆',
    'Soybean Oil': '豆油',
    'Soybean Meal': '豆粕',
    'Palm Oil': '棕榈油',
    'Rapeseed': '油菜籽',
    'Cotton': '棉花',
    'Sugar': '糖',
    'Coffee': '咖啡',
    'Cocoa': '可可',
    'Rice': '大米',
    'Orange Juice': '橙汁',
    'Oats': '燕麦',
    'Lumber': '木材',
    'Milk': '牛奶',
    'Live Cattle': '活牛',
    'Feeder Cattle': '育肥牛',
    'Lean Hog': '瘦肉猪',
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
    const [exchangeRate, setExchangeRate] = useState(null); // null 表示尚未加载
    const [exchangeRateLoading, setExchangeRateLoading] = useState(true);
    const [timeRange, setTimeRange] = useState('week'); // Default to week
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

    // 商品选择器状态 - 改进的版本
    const [showCommoditySelector, setShowCommoditySelector] = useState(false);
    const [commoditySearchTerm, setCommoditySearchTerm] = useState('');
    const commoditySelectorRef = useRef(null);

    // Visibility State - 改为显示所有商品
    const [visibleCommodities, setVisibleCommodities] = useState({});


    // 新增：商品选择器状态
    const [selectedCommodities, setSelectedCommodities] = useState(new Set());

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
    const sourceFilterRef = useRef(null);


    // 安全获取数值
    const safeNumber = (val, defaultVal = 0) => {
        const num = parseFloat(val);
        return isNaN(num) ? defaultVal : num;
    };

    const getHistoryData = (commodityName, basePrice, points) => {
        let historyRecords = priceHistory[commodityName] || [];



        // 增强的匹配逻辑：如果精确匹配失败，尝试使用商品配置的matchPatterns
        if (historyRecords.length === 0) {
            // 1. 尝试简单的模糊匹配（原逻辑）
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
                source: record.source, // Add source field
                isReal: true
            }));
        }

        // 如果没有找到真实数据，生成模拟数据

        let current = basePrice;
        const volatility = basePrice * 0.02;
        // Fix: logic for week/month interval
        const isDayIter = timeRange === 'day'; // 1 hour interval
        const intervalMs = isDayIter ? 3600000 : 86400000; // Day=1hr, Week/Month=24hr

        return Array.from({ length: points }, (_, i) => {
            const change = (Math.random() - 0.5) * volatility;
            current += change;
            const dateObj = new Date(Date.now() - (points - i) * intervalMs);
            return {
                time: i,
                price: Math.max(0, current),
                date: dateObj.toISOString(),
                isReal: false
            };
        });
    };

    const generateHistory = (basePrice, points, volatility) => {
        let current = basePrice;
        const isWeek = timeRange === 'week';
        return Array.from({ length: points }, (_, i) => {
            const change = (Math.random() - 0.5) * volatility;
            current += change;
            const dateObj = new Date(Date.now() - (points - i) * (isWeek ? 86400000 : 3600000));
            return {
                time: i,
                price: current,
                date: isWeek
                    ? dateObj.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
                    : dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            };
        });
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

                    // 如果是区域商品，添加到区域列表
                    if (isRegional && regionName) {
                        const colorIdx = existing.regions.length % regionalColors.length;
                        existing.regions.push({
                            name: regionName,
                            fullName: normalizedName,
                            price: safeNumber(item.price || item.current_price, 0),
                            change: safeNumber(item.change || item.change_percent, 0),
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
        const maxSelect = tabCommodities.length;
        for (const commodity of tabCommodities.slice(0, maxSelect)) {
            newSelected.add(commodity.name);
        }

        // 只有当选中的商品发生变化时才更新
        if (newSelected.size > 0) {
            setSelectedCommodities(newSelected);
        }
    }, [activeCommodityTab, activePlasticSubTab, allCommodities]);

    // 根据当前TAB获取对应分类的商品数量
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

    // 获取实时汇率（只加载一次）
    const exchangeRateLoadedRef = useRef(false);
    useEffect(() => {
        if (exchangeRateLoadedRef.current) return;
        exchangeRateLoadedRef.current = true;

        const fetchExchangeRate = async () => {
            try {
                const response = await api.getExchangeRate();
                const rate = response.data?.rate || response?.rate;
                if (rate && typeof rate === 'number') {
                    setExchangeRate(rate);
                    console.log('✅ 汇率已更新:', rate);
                } else {
                    setExchangeRate(7.2); // 解析失败使用默认值
                }
            } catch (err) {
                console.warn('⚠️ 获取汇率失败，使用默认值 7.2:', err);
                setExchangeRate(7.2);
            } finally {
                setExchangeRateLoading(false);
            }
        };
        fetchExchangeRate();
    }, []);

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

    // 获取选中商品的显示数据（使用合并后的商品数据）
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

        // 1. 基础筛选
        let filtered = allCommodities.filter(commodity => {
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
        });

        // 2. 自动展开区域数据 (当选中具体塑料子分类时)
        if (activeCommodityTab === 'plastics' && activePlasticSubTab !== 'all') {
            filtered = filtered.flatMap(commodity => {
                // 如果是区域聚合商品，并且有具体区域数据，则展开
                if (commodity.isRegional && commodity.regions && commodity.regions.length > 0) {
                    return commodity.regions.map(region => ({
                        ...commodity,
                        name: region.fullName || `${commodity.name}(${region.name})`, // 使用全名 e.g. PP(华东)
                        chinese_name: region.fullName || `${commodity.name}(${region.name})`,
                        current_price: region.price,
                        price: region.price,
                        change: region.change,
                        unit: commodity.unit,
                        isRegional: false, // 展开后不再是聚合状态
                        regions: [], // 清空区域列表
                        rawNames: [region.fullName || `${commodity.name}(${region.name})`] // 重置 rawNames 以便获取对应历史数据
                    }));
                }
                return [commodity];
            });
        }

        // 3. 映射为前端显示对象
        return filtered.map((commodity, idx) => {
            const price = commodity.price;
            // 1. 聚合所有来源的历史数据 (New Logic)
            let uniqueHistoryRecords = new Map(); // key: val-source-date
            let hasRealHistory = false;

            // 遍历所有可能的名称，收集真实数据
            for (const rawName of commodity.rawNames || [commodity.name]) {
                const hData = getHistoryData(rawName, price, timeRange === 'day' ? 24 : (timeRange === 'week' ? 7 : 30));
                if (hData) {
                    hData.forEach(record => {
                        if (record.isReal) {
                            hasRealHistory = true;
                            // 使用 日期+来源 作为唯一键，避免重复
                            const key = `${record.date}-${record.source || 'default'}`;
                            uniqueHistoryRecords.set(key, record);
                        }
                    });
                }
            }

            let historyData = null;
            if (hasRealHistory) {
                // 将 Map 转回数组并排序
                historyData = Array.from(uniqueHistoryRecords.values())
                    .sort((a, b) => new Date(a.date) - new Date(b.date))
                    .map((r, i) => ({ ...r, time: i }));
            } else {
                // 回退到模拟数据
                historyData = getHistoryData(commodity.name, price, timeRange === 'day' ? 24 : (timeRange === 'week' ? 7 : 30));
            }

            // 为区域商品获取多区域历史数据 (只有未展开的聚合项才需要)
            let multiSourceHistory = null;

            // 情况1: 区域聚合商品 (e.g. 塑料PP)
            if (commodity.isRegional && commodity.regions && commodity.regions.length > 0) {
                multiSourceHistory = commodity.regions.map(region => {
                    const regionHistory = getHistoryData(region.fullName, region.price, timeRange === 'day' ? 24 : (timeRange === 'week' ? 7 : 30));
                    return {
                        source: region.name,
                        color: region.color,
                        url: commodity.url,
                        data: regionHistory || []
                    };
                }).filter(s => s.data && s.data.length > 0);
            }
            // 情况2: 普通多来源商品 (e.g. 黄金)
            // 情况2: 普通多来源商品 (e.g. 黄金) 或 历史数据包含多来源 (e.g. WTI原油)
            else if (historyData && hasRealHistory) {
                // 检查历史数据中是否包含不同 source 的记录
                const historyBySource = {};

                historyData.forEach(record => {
                    const src = record.source || 'Unknown';
                    if (!historyBySource[src]) historyBySource[src] = [];
                    historyBySource[src].push(record);
                });

                if (Object.keys(historyBySource).length > 1) {
                    multiSourceHistory = Object.entries(historyBySource).map(([src, data], idx) => {
                        // 尝试从 commodity.sources 查找 URL
                        let sourceUrl = commodity.sources?.find(s => s.source === src)?.url;

                        // 如果未找到且是新浪期货，使用固定 URL (针对 WTI 原油等情况)
                        if (!sourceUrl && src === '新浪期货') {
                            if (commodity.name.includes('WTI') || commodity.name.includes('原油')) {
                                // 用户提供的固定URL (注意: hf_SI 通常是白银, hf_CL 是原油, 这里按用户要求或修正为 CL)
                                // 修正: WTI原油对应 hf_CL
                                sourceUrl = 'https://finance.sina.com.cn/futures/quotes/hf_CL.shtml';
                            } else {
                                sourceUrl = 'https://finance.sina.com.cn/futures/quotes/hf_SI.shtml';
                            }
                        }

                        return {
                            source: src,
                            color: ['#f59e0b', '#8b5cf6', '#3b82f6', '#10b981', '#ef4444', '#06b6d4'][idx % 6],
                            data: data.sort((a, b) => new Date(a.date) - new Date(b.date)),
                            url: sourceUrl
                        };
                    });
                }
            }

            return {
                id: commodity.name,
                name: commodity.name,
                basePrice: price,
                currentPrice: price,
                price: price,
                color: colors[idx % colors.length],
                unit: commodity.unit || '',
                change: commodity.change,
                url: commodity.url,
                source: commodity.source,
                sources: commodity.sources || [],
                regions: commodity.regions || [],
                isRegional: commodity.isRegional,
                historyData: historyData,
                multiSourceHistory: multiSourceHistory,
                dataItem: commodity
            };
        });
    }, [allCommodities, activeCommodityTab, activePlasticSubTab, selectedCommodities, timeRange, priceHistory, getSourceFilteredCommodities]);
    const hasFetchedData = useRef(false);
    const intervalRef = useRef(null);

    // Connect charts for synchronized hover
    useEffect(() => {
        const timer = setTimeout(() => {
            echarts.connect('commodities');
        }, 500);
        return () => clearTimeout(timer);
    }, [visibleCommodities, timeRange]);

    useEffect(() => {
        if (hasFetchedData.current) return;
        hasFetchedData.current = true;

        const fetchData = async (forceRefresh = false) => {
            try {
                const response = await api.getData(forceRefresh);
                const responseData = response.data || response;
                setData(responseData.data || []);
                setLastUpdate(responseData.timestamp || new Date().toISOString());
                setLoading(false);
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

    useEffect(() => {
        // Fetch Exchange Rate
        const fetchExchangeRate = async () => {
            try {
                const response = await api.getExchangeRate();
                if (response && response.rate) {
                    setExchangeRate(response.rate);
                }
            } catch (err) {
                console.error("Error fetching exchange rate:", err);
            }
        };
        fetchExchangeRate();

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

    // Close menus when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (commoditySelectorRef.current && !commoditySelectorRef.current.contains(event.target)) {
                setShowCommoditySelector(false);
            }
            if (urlFilterRef.current && !urlFilterRef.current.contains(event.target)) {
                setShowUrlDropdown(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

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

    const loadPriceHistory = async (daysOverride = null, bypassCache = false) => {
        try {
            // Determine days based on override or current state
            let days = 1;
            const targetRange = daysOverride !== null
                ? (daysOverride === 1 ? 'day' : (daysOverride === 7 ? 'week' : 'month'))
                : timeRange;

            if (targetRange === 'week') days = 7;
            if (targetRange === 'month') days = 30;

            const response = await api.getPriceHistory(null, days, bypassCache);
            // Fix: Read 'data' field instead of 'commodities'
            const historyData = response.data?.data || {};
            console.log(`📦 [Price History] Loaded (${targetRange}, bypass=${bypassCache}):`, Object.keys(historyData).length, 'items');
            setPriceHistory(historyData);
        } catch (err) {
            console.error('加载历史数据失败:', err);
        }
    };

    useEffect(() => {
        // Initial load only
        loadPriceHistory();
    }, []);



    const formatPrice = (price, unit) => {
        if (!price) return '0.00';
        let val = parseFloat(price);

        // 判断源货币是否为人民币
        const isSourceCNY = unit && (unit.includes('元') || unit.includes('CNY') || unit.includes('RMB'));

        if (currency === 'CNY') {
            // 目标是CNY，源是CNY -> 不变
            // 目标是CNY，源是USD -> 乘汇率
            if (!isSourceCNY) {
                val = val * exchangeRate;
            }
        } else {
            // 目标是USD
            // 目标是USD，源是CNY -> 除汇率
            // 目标是USD，源是USD -> 不变
            if (isSourceCNY) {
                val = val / exchangeRate;
            }
        }

        return val.toFixed(2);
    };

    const getCurrencySymbol = () => currency === 'USD' ? '$' : '¥';

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

    const groupedByUrl = useMemo(() => {
        if (!selectedUrl && !urlInputValue) return null;

        const filtered = data.filter(item => {
            const hostname = safeGetHostname(item.url);
            const matchesUrl = !selectedUrl || hostname === selectedUrl;
            const matchesInput = !urlInputValue ||
                hostname.toLowerCase().includes(urlInputValue.toLowerCase());
            return matchesUrl && matchesInput;
        });

        const groups = {};
        filtered.forEach(item => {
            const hostname = safeGetHostname(item.url) || 'unknown';
            if (!groups[hostname]) {
                groups[hostname] = {
                    hostname,
                    urls: new Set(),
                    items: []
                };
            }
            groups[hostname].urls.add(item.url);
            groups[hostname].items.push(item);
        });

        return Object.values(groups).map(g => ({
            ...g,
            urls: Array.from(g.urls)
        })).sort((a, b) => b.items.length - a.items.length);
    }, [data, selectedUrl, urlInputValue]);

    // 扩展的商品定义 - 包含更多商品类型
    const commodities = [
        {
            id: 'gold',
            name: '黄金 (Gold)',
            basePrice: 2000,
            color: '#ffc658',
            matchPatterns: [/^Gold$/i, /黄金/, /COMEX黄金/, /Gold Spot/i, /XAU/i],
            excludePatterns: [/Gold Futures/i],
            unit: 'oz',
            category: '贵金属'
        },
        {
            id: 'silver',
            name: '白银 (Silver)',
            basePrice: 25,
            color: '#a4a9ad',
            matchPatterns: [/^Silver$/i, /白银/, /COMEX白银/, /Silver Spot/i, /XAG/i],
            excludePatterns: [],
            unit: 'oz',
            category: '贵金属'
        },
        {
            id: 'platinum',
            name: '铂金 (Platinum)',
            basePrice: 1000,
            color: '#c0c0c0',
            matchPatterns: [/^Platinum$/i, /铂金/, /白金/, /Platinum Spot/i],
            excludePatterns: [],
            unit: 'oz',
            category: '贵金属'
        },
        {
            id: 'palladium',
            name: '钯金 (Palladium)',
            basePrice: 1500,
            color: '#e5e4e2',
            matchPatterns: [/^Palladium$/i, /钯金/, /Palladium Spot/i],
            excludePatterns: [],
            unit: 'oz',
            category: '贵金属'
        },
        {
            id: 'copper',
            name: '铜 (Copper)',
            basePrice: 500,
            color: '#b87333',
            matchPatterns: [/^Copper$/i, /^铜$/, /COMEX铜/, /Copper Futures/i, /SMM铜/],
            excludePatterns: [],
            unit: 'lb',
            category: '基础金属'
        },
        {
            id: 'aluminum',
            name: '铝 (Aluminium)',
            basePrice: 2500,
            color: '#848789',
            matchPatterns: [/^Alum/i, /^铝$/, /SMM铝/],
            excludePatterns: [],
            unit: 'ton',
            category: '基础金属'
        },
        {
            id: 'zinc',
            name: '锌 (Zinc)',
            basePrice: 2800,
            color: '#7c7c7c',
            matchPatterns: [/^Zinc$/i, /^锌$/, /SMM锌/],
            excludePatterns: [],
            unit: 'ton',
            category: '基础金属'
        },
        {
            id: 'nickel',
            name: '镍 (Nickel)',
            basePrice: 18000,
            color: '#8a9597',
            matchPatterns: [/^Nickel$/i, /^镍$/, /SMM镍/],
            excludePatterns: [],
            unit: 'ton',
            category: '基础金属'
        },
        {
            id: 'lead',
            name: '铅 (Lead)',
            basePrice: 2000,
            color: '#54585a',
            matchPatterns: [/^Lead$/i, /^铅$/, /SMM铅/],
            excludePatterns: [],
            unit: 'ton',
            category: '基础金属'
        },
        {
            id: 'tin',
            name: '锡 (Tin)',
            basePrice: 25000,
            color: '#d4d4d4',
            matchPatterns: [/^Tin$/i, /^锡$/, /SMM锡/],
            excludePatterns: [],
            unit: 'ton',
            category: '基础金属'
        },
        {
            id: 'crude_oil',
            name: '原油 (Crude Oil)',
            basePrice: 70,
            color: '#2d2d2d',
            matchPatterns: [/Crude Oil/i, /^原油$/, /WTI原油/, /WTI Crude/i, /Brent/i, /布伦特/],
            excludePatterns: [/Heating Oil/i, /取暖油/],
            unit: 'barrel',
            category: '能源'
        },
        {
            id: 'natural_gas',
            name: '天然气 (Natural Gas)',
            basePrice: 4,
            color: '#4a90e2',
            matchPatterns: [/Natural Gas/i, /天然气/, /Henry Hub/i],
            excludePatterns: [],
            unit: 'MMBtu',
            category: '能源'
        },
        {
            id: 'heating_oil',
            name: '取暖油 (Heating Oil)',
            basePrice: 2.5,
            color: '#8b4513',
            matchPatterns: [/Heating Oil/i, /取暖油/],
            excludePatterns: [],
            unit: 'gallon',
            category: '能源'
        },
        {
            id: 'gasoline',
            name: '汽油 (Gasoline)',
            basePrice: 2.2,
            color: '#ff6b6b',
            matchPatterns: [/Gasoline/i, /汽油/, /RBOB/i],
            excludePatterns: [],
            unit: 'gallon',
            category: '能源'
        },
        {
            id: 'corn',
            name: '玉米 (Corn)',
            basePrice: 450,
            color: '#ffd700',
            matchPatterns: [/^Corn$/i, /^玉米$/],
            excludePatterns: [],
            unit: 'bushel',
            category: '农产品'
        },
        {
            id: 'wheat',
            name: '小麦 (Wheat)',
            basePrice: 550,
            color: '#daa520',
            matchPatterns: [/^Wheat$/i, /^小麦$/],
            excludePatterns: [],
            unit: 'bushel',
            category: '农产品'
        },
        {
            id: 'soybeans',
            name: '大豆 (Soybeans)',
            basePrice: 1200,
            color: '#8b7355',
            matchPatterns: [/Soybean/i, /大豆/],
            excludePatterns: [],
            unit: 'bushel',
            category: '农产品'
        },
        {
            id: 'sugar',
            name: '糖 (Sugar)',
            basePrice: 18,
            color: '#ffb6c1',
            matchPatterns: [/^Sugar$/i, /^糖$/],
            excludePatterns: [],
            unit: 'lb',
            category: '农产品'
        },
        {
            id: 'coffee',
            name: '咖啡 (Coffee)',
            basePrice: 180,
            color: '#6f4e37',
            matchPatterns: [/Coffee/i, /咖啡/],
            excludePatterns: [],
            unit: 'lb',
            category: '农产品'
        },
        {
            id: 'cotton',
            name: '棉花 (Cotton)',
            basePrice: 80,
            color: '#f5f5f5',
            matchPatterns: [/Cotton/i, /棉花/],
            excludePatterns: [],
            unit: 'lb',
            category: '农产品'
        }
    ];

    // 初始化可见性状态 - 默认显示前6个
    // 切换商品可见性 (Sync both states)
    const toggleCommodity = (name) => {
        setSelectedCommodities(prev => {
            const newSet = new Set(prev);
            let isSelected = false;
            if (newSet.has(name)) {
                newSet.delete(name);
            } else {
                newSet.add(name);
                isSelected = true;
            }
            // Sync visibleCommodities for charts consuming this specific state if any left
            setVisibleCommodities(prevVis => ({
                ...prevVis,
                [name]: isSelected
            }));
            return newSet;
        });
    };

    // 全选
    const selectAll = () => {
        const newSet = new Set();
        // Select all currently filtered/visible items
        const targetList = filteredCommodities || allCommodities;
        targetList.forEach(c => newSet.add(c.name));
        setSelectedCommodities(newSet);
    };

    // 全不选
    const selectNone = () => {
        setSelectedCommodities(new Set());
    };

    // Legacy support
    const toggleAll = selectAll;

    const commoditiesWithMultiSource = useMemo(() => {
        const sourceColors = ['#0284c7', '#dc2626', '#16a34a', '#9333ea', '#ea580c', '#0891b2'];

        // 商品名称映射：英文 -> 中文（用于匹配priceHistory的key）
        const getCommodityChineseName = (itemName, commodityConfig) => {
            // 如果已经是中文，直接返回
            if (/[\u4e00-\u9fff]/.test(itemName)) {
                return itemName;
            }

            // 使用配置中的中文名称（从name字段提取）
            const match = commodityConfig.name.match(/^([^(]+)/);
            if (match) {
                return match[1].trim();
            }

            // 如果配置的matchPatterns包含中文正则，使用它
            for (const pattern of commodityConfig.matchPatterns) {
                const patternStr = pattern.toString();
                const chineseMatch = patternStr.match(/\/([^/]*[\u4e00-\u9fff][^/]*)\//);
                if (chineseMatch) {
                    return chineseMatch[1];
                }
            }

            return itemName; // 降级返回原名称
        };

        return commodities.map(comm => {
            const matchingItems = data.filter(d => {
                const itemName = d.name || d.chinese_name || '';
                const matches = comm.matchPatterns.some(pattern => pattern.test(itemName));
                const excluded = comm.excludePatterns.some(pattern => pattern.test(itemName));
                const price = parseFloat(d.price || d.current_price || 0);
                const priceReasonable = price > 0 && price < comm.basePrice * 100 && price > comm.basePrice * 0.01;
                return matches && !excluded && priceReasonable;
            });

            // Debug logging for Palladium/Platinum
            if (comm.id === 'palladium' || comm.id === 'platinum') {
                console.log(`🔍 [${comm.id}] matchingItems count: ${matchingItems.length}`);
            }

            if (matchingItems.length === 0) {
                if (comm.id === 'palladium' || comm.id === 'platinum') {
                    console.warn(`⚠️ [${comm.id}] NO matchingItems found! multiSourceHistory will be null`);
                }
                // Fix: Ensure price/currentPrice exists even if no API match
                return {
                    ...comm,
                    price: comm.basePrice,
                    currentPrice: comm.basePrice,
                    multiSourceItems: [],
                    multiSourceHistory: null
                };
            }

            const multiSourceHistory = matchingItems.map((item, idx) => {
                const price = item.price || item.current_price || comm.basePrice;
                // 优先使用chinese_name，否则将英文name转换为中文
                let itemName = item.chinese_name || item.name || comm.name;

                // 如果itemName是英文，尝试转换为中文匹配priceHistory的key
                const chineseName = getCommodityChineseName(itemName, comm);

                // Debug logging for Palladium/Platinum
                if (comm.id === 'palladium' || comm.id === 'platinum') {
                    console.log(`🔍 [${comm.id}] matchingItem[${idx}]:`, {
                        name: item.name,
                        chinese_name: item.chinese_name,
                        originalItemName: itemName,
                        chineseName: chineseName,
                        price: price
                    });
                }

                const histData = getHistoryData(
                    chineseName, // 使用中文名称查询历史数据
                    parseFloat(price || 0),
                    timeRange === 'day' ? 24 : (timeRange === 'week' ? 7 : 30)
                );
                return {
                    source: safeGetHostname(item.url) || `来源${idx + 1}`,
                    color: sourceColors[idx % sourceColors.length],
                    data: histData,
                    url: item.url
                };
            });

            const unit = matchingItems[0]?.unit || comm.unit;
            const currentPrice = matchingItems[0]?.price || matchingItems[0]?.current_price || comm.basePrice;

            // Debug logging for Palladium/Platinum results
            if (comm.id === 'palladium' || comm.id === 'platinum') {
                console.log(`📊 [${comm.id}] multiSourceHistory:`, multiSourceHistory);
                console.log(`📊 [${comm.id}] histData lengths:`, multiSourceHistory.map(h => h.data?.length || 0));
                console.log(`📊 [${comm.id}] First histData sample:`, multiSourceHistory[0]?.data?.slice(0, 2));
            }

            return {
                ...comm,
                unit,
                currentPrice,
                price: currentPrice, // Fix: Ensure 'price' property exists for Table/List view
                multiSourceItems: matchingItems,
                multiSourceHistory
            };
        });
    }, [data, timeRange, priceHistory]);



    if (error) return (
        <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100vh',
            fontSize: '18px',
            color: '#ef4444'
        }}>
            错误: {error}
        </div>
    );

    let displayItems = [];

    if (searchTerm || selectedUrl) {
        displayItems = data.filter(item => {
            const searchLower = searchTerm.toLowerCase();
            const matchesSearch = !searchTerm || (
                (item.name && item.name.toLowerCase().includes(searchLower)) ||
                (item.chinese_name && item.chinese_name.toLowerCase().includes(searchLower)) ||
                (item.source && item.source.toLowerCase().includes(searchLower)) ||
                (item.symbol && item.symbol.toLowerCase().includes(searchLower))
            );
            const matchesUrl = !selectedUrl || item.url === selectedUrl;
            return matchesSearch && matchesUrl;
        }).map((item, idx) => {
            const colors = ['#ffc658', '#a4a9ad', '#8884d8', '#82ca9d', '#ff7c43', '#665191', '#2f4b7c', '#a05195'];
            return {
                id: item.name || item.chinese_name || `item-${idx}`,
                name: item.chinese_name || item.name,
                basePrice: item.current_price || item.price,
                color: colors[idx % colors.length],
                isDynamic: true,
                dataItem: item
            };
        });
    } else {
        displayItems = commoditiesWithMultiSource.filter(c => visibleCommodities[c.id]);
    }

    const visibleCount = Object.values(visibleCommodities).filter(Boolean).length;

    return (
        <div className="dashboard-container" style={{
            paddingBottom: '40px',
            position: 'relative',
            maxWidth: '1920px',
            margin: '0 auto'
        }}>
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
                            onClick={() => {
                                setTimeRange('day');
                                loadPriceHistory(1, true);
                            }}
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
                            onClick={() => {
                                setTimeRange('week');
                                loadPriceHistory(7, true);
                            }}
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
                            onClick={() => {
                                setTimeRange('month');
                                loadPriceHistory(30, true);
                            }}
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

                    {/* 刷新按钮 */}
                    <button
                        onClick={async () => {
                            setRefreshing(true);
                            try {
                                // 同时刷新商品数据和历史数据
                                const [dataResponse, historyResponse] = await Promise.all([
                                    api.getData(true),
                                    api.getPriceHistory(null, { day: 1, week: 7, month: 30 }[timeRange] || 7)
                                ]);
                                const responseData = dataResponse.data || dataResponse;
                                setData(responseData.data || []);
                                setLastUpdate(responseData.timestamp || new Date().toISOString());
                                // 更新历史数据并重置缓存标记
                                const historyData = historyResponse.data?.data || historyResponse.data?.commodities || {};
                                setPriceHistory(historyData);
                                priceHistoryLoadingRef.current = null; // 重置缓存标记
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
                        {refreshing ? '刷新中' : '刷新'}
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

            {/* URL分组展示面板 */}
            <div className="dashboard-layout-grid" style={{
                display: 'grid',
                gridTemplateColumns: '3fr 1fr',
                gap: '24px'
            }}>
                <div className="main-content">
                    {/* 概览卡片 - 改进为4列布局 */}
                    <div className="grid-cards" style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(4, 1fr)',
                        gap: '20px',
                        marginBottom: '30px'
                    }}>
                        {/* 汇率卡片 */}
                        <div className="exchange-rate-card" style={{
                            background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
                            padding: '24px',
                            borderRadius: '16px',
                            boxShadow: '0 8px 16px -4px rgba(59, 130, 246, 0.3)',
                            color: '#fff'
                        }}>
                            <div className="card-header" style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                marginBottom: '12px'
                            }}>
                                <span style={{
                                    fontSize: '15px',
                                    fontWeight: '600',
                                    opacity: 0.95
                                }}>
                                    USD/CNY 汇率
                                </span>
                                <span style={{
                                    fontSize: '13px',
                                    fontWeight: '700',
                                    background: 'rgba(255,255,255,0.25)',
                                    padding: '3px 10px',
                                    borderRadius: '999px'
                                }}>
                                    实时
                                </span>
                            </div>
                            <div className="rate-value" style={{
                                fontSize: '36px',
                                fontWeight: '800',
                                letterSpacing: '-0.02em'
                            }}>
                                {exchangeRateLoading ? (
                                    <span style={{ opacity: 0.6 }}>加载中...</span>
                                ) : (
                                    `¥${(exchangeRate || 7.2).toFixed(4)}`
                                )}
                            </div>
                            <div className="rate-info" style={{
                                fontSize: '13px',
                                opacity: 0.85,
                                marginTop: '6px',
                                fontWeight: '500'
                            }}>
                                {exchangeRateLoading ? '获取实时汇率...' : `1 USD = ${exchangeRate} CNY`}
                            </div>
                        </div>

                        {loading ? (
                            // Skeleton for Top Cards
                            Array.from({ length: 3 }).map((_, idx) => (
                                <div key={`skel-${idx}`} style={{
                                    background: '#fff',
                                    padding: '24px',
                                    borderRadius: '16px',
                                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
                                    border: '1px solid #f3f4f6',
                                    height: '140px',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    justifyContent: 'space-between'
                                }}>
                                    <div style={{ height: '20px', width: '60%', background: '#f3f4f6', borderRadius: '4px' }} className="animate-pulse"></div>
                                    <div style={{ height: '40px', width: '80%', background: '#e5e7eb', borderRadius: '4px' }} className="animate-pulse"></div>
                                </div>
                            ))
                        ) : (
                            displayCommodities.slice(0, 3).map((item, index) => {
                                const price = item.price || item.current_price || item.last_price || 0;
                                const change = item.change || item.change_percent || 0;
                                const isUp = change >= 0;
                                const hostname = safeGetHostname(item.url);
                                const cleanUnit = (item.unit || '')
                                    .replace(/USD|CNY|RMB|美元|人民币/gi, '')
                                    .replace(/[$¥/]/g, '')
                                    .trim();

                                return (
                                    <div key={index} className="commodity-card" style={{
                                        background: '#fff',
                                        padding: '24px',
                                        borderRadius: '16px',
                                        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
                                        border: '1px solid #f3f4f6'
                                    }}>
                                        <div className="card-content-header" style={{
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            marginBottom: '12px'
                                        }}>
                                            <div className="commodity-info" style={{
                                                display: 'flex',
                                                flexDirection: 'column',
                                                gap: '4px'
                                            }}>
                                                <span style={{
                                                    color: '#374151',
                                                    fontSize: '15px',
                                                    fontWeight: '600'
                                                }}>
                                                    {item.name || item.currency_pair || item.chinese_name || 'Unknown'}
                                                </span>
                                                {item.url && (
                                                    <a
                                                        href={item.url}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        style={{
                                                            display: 'inline-flex',
                                                            alignItems: 'center',
                                                            gap: '4px',
                                                            fontSize: '12px',
                                                            color: '#9ca3af',
                                                            textDecoration: 'none',
                                                            maxWidth: '140px',
                                                            overflow: 'hidden',
                                                            textOverflow: 'ellipsis',
                                                            whiteSpace: 'nowrap',
                                                            fontWeight: '500'
                                                        }}
                                                        title={item.url}
                                                    >
                                                        <ExternalLink size={11} />
                                                        {hostname}
                                                    </a>
                                                )}
                                            </div>
                                            <span style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                fontSize: '13px',
                                                fontWeight: '700',
                                                color: isUp ? '#10b981' : '#ef4444',
                                                background: isUp ? '#d1fae5' : '#fee2e2',
                                                padding: '4px 10px',
                                                borderRadius: '999px',
                                                height: 'fit-content'
                                            }}>
                                                {isUp ? <ArrowUp size={13} style={{ marginRight: '3px' }} /> : <ArrowDown size={13} style={{ marginRight: '3px' }} />}
                                                {Math.abs(change)}%
                                            </span>
                                        </div>
                                        <div className="commodity-price" style={{
                                            fontSize: '36px',
                                            fontWeight: '800',
                                            color: '#111827',
                                            letterSpacing: '-0.02em'
                                        }}>
                                            {getCurrencySymbol()}{formatPrice(price, item.unit)}
                                            <span style={{
                                                fontSize: '18px',
                                                color: '#6b7280',
                                                marginLeft: '6px',
                                                fontWeight: '600'
                                            }}>
                                                {cleanUnit ? `/${cleanUnit}` : ''}
                                            </span>
                                        </div>
                                    </div>
                                );
                            }))}
                    </div>


                    {/* ==================== 商品分类 TAB 区域 ==================== */}
                    <div className="commodity-tabs-container" style={{
                        background: '#fff',
                        borderRadius: '16px',
                        padding: '24px',
                        boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
                        marginBottom: '30px',
                        border: '1px solid #f3f4f6'
                    }}>
                        {/* Tabs Header */}
                        <div style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            marginBottom: '20px',
                            borderBottom: '1px solid #f3f4f6',
                            paddingBottom: '16px'
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                                <h3 style={{
                                    margin: 0,
                                    fontSize: '18px',
                                    fontWeight: '700',
                                    color: '#111827',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px'
                                }}>
                                    <span style={{ fontSize: '20px' }}>📊</span>
                                    数据仪表盘
                                </h3>
                                <div style={{
                                    display: 'flex',
                                    background: '#f3f4f6',
                                    padding: '4px',
                                    borderRadius: '12px',
                                    gap: '4px'
                                }}>
                                    {COMMODITY_TABS.map(tab => (
                                        <button
                                            key={tab.id}
                                            onClick={() => {
                                                setActiveCommodityTab(tab.id);
                                                if (tab.id !== 'plastics') setActivePlasticSubTab('all');
                                            }}
                                            style={{
                                                padding: '8px 16px',
                                                borderRadius: '8px',
                                                border: 'none',
                                                background: activeCommodityTab === tab.id ? '#fff' : 'transparent',
                                                color: activeCommodityTab === tab.id ? tab.color : '#6b7280',
                                                fontWeight: activeCommodityTab === tab.id ? '700' : '500',
                                                fontSize: '14px',
                                                cursor: 'pointer',
                                                boxShadow: activeCommodityTab === tab.id ? '0 2px 4px rgba(0,0,0,0.05)' : 'none',
                                                transition: 'all 0.2s',
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '6px'
                                            }}
                                        >
                                            <span>{tab.icon}</span>
                                            {tab.name}
                                            <span style={{
                                                fontSize: '12px',
                                                background: activeCommodityTab === tab.id ? tab.bgColor : '#e5e7eb',
                                                padding: '2px 6px',
                                                borderRadius: '10px',
                                                color: activeCommodityTab === tab.id ? tab.color : '#6b7280'
                                            }}>
                                                {getCommodityCountByTab(tab.id)}
                                            </span>
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* 表头配置按钮 */}
                            <div style={{ position: 'relative', display: 'flex', alignItems: 'center', marginLeft: 'auto', paddingRight: '12px' }} ref={columnSettingsRef}>
                                <button
                                    onClick={() => setShowColumnSettings(!showColumnSettings)}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '6px',
                                        padding: '8px 12px',
                                        background: '#fff',
                                        border: '1px solid #e5e7eb',
                                        borderRadius: '8px',
                                        fontSize: '13px',
                                        fontWeight: '600',
                                        color: '#374151',
                                        cursor: 'pointer'
                                    }}
                                >
                                    <Settings size={14} />
                                    表头配置
                                </button>
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

                        {/* 塑料子分类 Tabs */}
                        {activeCommodityTab === 'plastics' && COMMODITY_TABS.find(t => t.id === 'plastics').subTabs && (
                            <div style={{
                                display: 'flex',
                                flexWrap: 'wrap',
                                gap: '8px',
                                marginBottom: '20px',
                                padding: '12px',
                                background: '#f9fafb',
                                borderRadius: '12px',
                                border: '1px solid #e5e7eb'
                            }}>
                                {COMMODITY_TABS.find(t => t.id === 'plastics').subTabs.map(subTab => {
                                    const isActive = activePlasticSubTab === subTab.id;
                                    // 计算该子分类的商品数量（基于所有塑料商品）
                                    const plasticCommodities = allCommodities.filter(c =>
                                        getCommodityCategory(c.name, c.category) === 'plastics'
                                    );
                                    const subCount = plasticCommodities.reduce((acc, c) => {
                                        // 检查是否属于当前子分类
                                        const matches = subTab.id === 'all' || c.name.toUpperCase().startsWith(subTab.id);
                                        if (!matches) return acc;

                                        // 如果是区域聚合商品，加上区域数量
                                        if (c.isRegional && c.regions && c.regions.length > 0) {
                                            return acc + c.regions.length;
                                        }
                                        // 否则普通商品算1个
                                        return acc + 1;
                                    }, 0);

                                    return (
                                        <button
                                            key={subTab.id}
                                            onClick={() => setActivePlasticSubTab(subTab.id)}
                                            title={subTab.desc || subTab.name}
                                            style={{
                                                padding: '6px 12px',
                                                borderRadius: '20px',
                                                border: isActive ? `1px solid ${subTab.color}` : '1px solid transparent',
                                                background: isActive ? subTab.color : '#fff',
                                                color: isActive ? '#fff' : '#6b7280',
                                                fontWeight: isActive ? '600' : '500',
                                                fontSize: '13px',
                                                cursor: 'pointer',
                                                transition: 'all 0.2s',
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '6px'
                                            }}
                                        >
                                            {subTab.name}
                                            {subCount > 0 && (
                                                <span style={{
                                                    fontSize: '10px',
                                                    background: isActive ? '#fff' : subTab.color,
                                                    color: isActive ? subTab.color : '#fff',
                                                    padding: '0px 4px',
                                                    borderRadius: '6px',
                                                    fontWeight: '700',
                                                    minWidth: '14px',
                                                    height: '14px',
                                                    lineHeight: '14px',
                                                    textAlign: 'center',
                                                    marginLeft: '4px',
                                                    marginBottom: '8px' // Slight lift
                                                }}>
                                                    {subCount}
                                                </span>
                                            )}
                                        </button>
                                    );
                                })}
                            </div>
                        )}

                        {/* Data Table */}
                        <div style={{ overflowX: 'auto', maxHeight: '600px', overflowY: 'auto' }}>
                            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '800px' }}>
                                <thead>
                                    <tr style={{ background: '#f9fafb', borderBottom: '2px solid #e5e7eb' }}>
                                        {tableColumns.filter(c => c.visible).map(col => (
                                            <th key={col.id} style={{
                                                padding: '12px 16px',
                                                textAlign: 'left',
                                                fontSize: '13px',
                                                fontWeight: '600',
                                                color: '#6b7280',
                                                width: col.width
                                            }}>
                                                {col.label}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {loading ? (
                                        // Skeleton Rows
                                        Array.from({ length: 5 }).map((_, idx) => (
                                            <tr key={`skel-row-${idx}`} style={{ borderBottom: '1px solid #f3f4f6' }}>
                                                {tableColumns.filter(c => c.visible).map(col => (
                                                    <td key={col.id} style={{ padding: '16px' }}>
                                                        <div style={{ height: '20px', width: '80%', background: '#f3f4f6', borderRadius: '4px' }} className="animate-pulse"></div>
                                                    </td>
                                                ))}
                                            </tr>
                                        ))
                                    ) : (
                                        displayCommodities.map((item, idx) => {
                                            const isUp = item.change >= 0;
                                            return (
                                                <tr key={idx} style={{
                                                    borderBottom: '1px solid #f3f4f6',
                                                    transition: 'background 0.2s'
                                                }}
                                                    onMouseEnter={e => e.currentTarget.style.background = '#f9fafb'}
                                                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                                                >
                                                    {/* 商品名称 */}
                                                    {tableColumns.find(c => c.id === 'name')?.visible && (
                                                        <td style={{ padding: '16px' }}>
                                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                                <div style={{
                                                                    width: '32px',
                                                                    height: '32px',
                                                                    borderRadius: '8px',
                                                                    background: '#eff6ff',
                                                                    display: 'flex',
                                                                    alignItems: 'center',
                                                                    justifyContent: 'center',
                                                                    color: '#3b82f6',
                                                                    fontWeight: '700',
                                                                    fontSize: '14px'
                                                                }}>
                                                                    {item.name.charAt(0)}
                                                                </div>
                                                                <div>
                                                                    <div style={{ fontWeight: '600', color: '#111827' }}>
                                                                        {item.name}
                                                                    </div>
                                                                    {item.isRegional && (
                                                                        <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '2px' }}>
                                                                            区域均价 (包含 {item.regions?.length || 0} 个地区)
                                                                        </div>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        </td>
                                                    )}

                                                    {/* 当前价格 */}
                                                    {tableColumns.find(c => c.id === 'price')?.visible && (
                                                        <td style={{ padding: '16px' }}>
                                                            <div style={{ fontWeight: '700', color: '#111827', fontSize: '15px' }}>
                                                                {getCurrencySymbol()}{formatPrice(item.price, item.unit)}
                                                            </div>
                                                        </td>
                                                    )}

                                                    {/* 涨跌幅 */}
                                                    {tableColumns.find(c => c.id === 'change')?.visible && (
                                                        <td style={{ padding: '16px' }}>
                                                            <div style={{
                                                                display: 'inline-flex',
                                                                alignItems: 'center',
                                                                padding: '4px 8px',
                                                                borderRadius: '6px',
                                                                background: isUp ? '#d1fae5' : '#fee2e2',
                                                                color: isUp ? '#10b981' : '#ef4444',
                                                                fontWeight: '600',
                                                                fontSize: '13px'
                                                            }}>
                                                                {isUp ? <ArrowUp size={12} /> : <ArrowDown size={12} />}
                                                                {Math.abs(item.change)}%
                                                            </div>
                                                        </td>
                                                    )}

                                                    {/* 数据来源 */}
                                                    {tableColumns.find(c => c.id === 'source')?.visible && (
                                                        <td style={{ padding: '16px' }}>
                                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                                                {item.sources?.slice(0, 2).map((source, sIdx) => {
                                                                    const hostname = source.source || 'Unknown';
                                                                    return (
                                                                        <div key={sIdx} style={{
                                                                            display: 'flex',
                                                                            alignItems: 'center',
                                                                            gap: '4px',
                                                                            fontSize: '12px',
                                                                            color: '#6b7280'
                                                                        }}>
                                                                            <Globe size={10} />
                                                                            <a href={source.url} target="_blank" rel="noopener noreferrer" style={{ color: '#4b5563', textDecoration: 'none' }}>
                                                                                {hostname}
                                                                            </a>
                                                                        </div>
                                                                    );
                                                                })}
                                                                {(item.sources?.length || 0) > 2 && (
                                                                    <span style={{ fontSize: '11px', color: '#9ca3af' }}>
                                                                        +{item.sources.length - 2} 更多来源...
                                                                    </span>
                                                                )}
                                                            </div>
                                                        </td>
                                                    )}

                                                    {/* 单位 */}
                                                    {tableColumns.find(c => c.id === 'unit')?.visible && (
                                                        <td style={{ padding: '16px' }}>
                                                            <span style={{
                                                                background: '#f3f4f6',
                                                                padding: '2px 8px',
                                                                borderRadius: '4px',
                                                                fontSize: '12px',
                                                                color: '#4b5563',
                                                                fontWeight: '500'
                                                            }}>
                                                                {item.unit || '-'}
                                                            </span>
                                                        </td>
                                                    )}

                                                    {/* 更新时间 - 模拟数据 */}
                                                    {tableColumns.find(c => c.id === 'update')?.visible && (
                                                        <td style={{ padding: '16px', fontSize: '13px', color: '#6b7280' }}>
                                                            15分钟前
                                                        </td>
                                                    )}
                                                </tr>
                                            );
                                        })
                                    )}
                                    {!loading && displayCommodities.length === 0 && (
                                        <tr>
                                            <td colSpan={tableColumns.filter(c => c.visible).length} style={{ padding: '32px', textAlign: 'center', color: '#9ca3af' }}>
                                                未找到符合条件的商品
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    {/* 图表区域 - 改进布局 */}
                    <div className="charts-section" style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))',
                        gap: '24px',
                        alignItems: 'start'
                    }}>
                        {loading ? (
                            // Skeleton for Charts
                            Array.from({ length: 4 }).map((_, idx) => (
                                <div key={`chart-skel-${idx}`} style={{
                                    background: '#fff',
                                    borderRadius: '12px',
                                    height: '350px',
                                    padding: '20px',
                                    border: '1px solid #f3f4f6'
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '20px' }}>
                                        <div style={{ width: '120px', height: '24px', background: '#f3f4f6', borderRadius: '4px' }} className="animate-pulse"></div>
                                        <div style={{ width: '80px', height: '30px', background: '#f3f4f6', borderRadius: '4px' }} className="animate-pulse"></div>
                                    </div>
                                    <div style={{ width: '100%', height: '240px', background: '#f9fafb', borderRadius: '8px' }} className="animate-pulse"></div>
                                </div>
                            ))
                        ) : (
                            displayCommodities.map((comm, index) => {
                                const isLastOdd = index === displayCommodities.length - 1 && displayCommodities.length % 2 !== 0;
                                return (
                                    <CommodityCard
                                        key={comm.id || index}
                                        comm={comm}
                                        multiSourceItems={comm.sources}
                                        currentPrice={comm.currentPrice}
                                        unit={comm.unit}
                                        multiSourceHistory={comm.multiSourceHistory}
                                        historyData={comm.historyData}
                                        currencySymbol={getCurrencySymbol()}
                                        formatPrice={formatPrice}
                                        isLastOdd={isLastOdd}
                                        currency={currency}
                                        exchangeRate={exchangeRate}
                                    />
                                );
                            }))}
                    </div>
                </div>

                <div className="sidebar-content" style={{ position: 'sticky', top: '24px' }}>
                    <ExchangeStatus />
                    <AIAnalysis />
                    <NewsFeed />
                </div>
            </div>

            {/* 设置模态框 */}
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
                    zIndex: 1000,
                    backdropFilter: 'blur(4px)'
                }}>
                    <div style={{
                        background: '#fff',
                        borderRadius: '20px',
                        width: '560px',
                        maxWidth: '90%',
                        maxHeight: '85vh',
                        display: 'flex',
                        flexDirection: 'column',
                        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)'
                    }}>
                        <div style={{
                            padding: '24px',
                            borderBottom: '1px solid #e5e7eb',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center'
                        }}>
                            <h2 style={{
                                margin: 0,
                                fontSize: '22px',
                                fontWeight: '700',
                                color: '#111827'
                            }}>
                                配置设置
                            </h2>
                            <button
                                onClick={() => setShowSettings(false)}
                                style={{
                                    background: 'none',
                                    border: 'none',
                                    padding: '6px',
                                    cursor: 'pointer',
                                    borderRadius: '8px'
                                }}
                                onMouseEnter={e => e.currentTarget.style.background = '#f3f4f6'}
                                onMouseLeave={e => e.currentTarget.style.background = 'none'}
                            >
                                <X size={24} color="#6b7280" />
                            </button>
                        </div>

                        <div style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
                            <h3 style={{
                                fontSize: '16px',
                                fontWeight: '700',
                                color: '#374151',
                                marginBottom: '16px'
                            }}>
                                爬取目标 URL
                            </h3>

                            <div className="url-list" style={{
                                display: 'flex',
                                flexDirection: 'column',
                                gap: '12px',
                                marginBottom: '24px'
                            }}>
                                {(config.target_urls || []).map((url, index) => (
                                    <div key={index} style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '12px',
                                        padding: '14px',
                                        background: '#f9fafb',
                                        borderRadius: '10px',
                                        border: '1px solid #f3f4f6'
                                    }}>
                                        <span style={{
                                            flex: 1,
                                            overflow: 'hidden',
                                            textOverflow: 'ellipsis',
                                            fontSize: '15px',
                                            fontWeight: '500',
                                            color: '#4b5563'
                                        }}>
                                            {url}
                                        </span>
                                        <button
                                            onClick={() => handleDeleteUrl(index)}
                                            style={{
                                                padding: '8px',
                                                color: '#ef4444',
                                                background: 'none',
                                                border: 'none',
                                                cursor: 'pointer',
                                                borderRadius: '6px'
                                            }}
                                            onMouseEnter={e => e.currentTarget.style.background = '#fee2e2'}
                                            onMouseLeave={e => e.currentTarget.style.background = 'none'}
                                        >
                                            <Trash2 size={18} />
                                        </button>
                                    </div>
                                ))}
                                {(!config.target_urls || config.target_urls.length === 0) && (
                                    <p style={{
                                        color: '#9ca3af',
                                        fontSize: '15px',
                                        textAlign: 'center',
                                        padding: '24px'
                                    }}>
                                        暂无配置的 URL
                                    </p>
                                )}
                            </div>

                            <div className="add-url" style={{ display: 'flex', gap: '12px' }}>
                                <input
                                    type="text"
                                    value={newUrl}
                                    onChange={(e) => setNewUrl(e.target.value)}
                                    placeholder="输入新的 URL..."
                                    style={{
                                        flex: 1,
                                        padding: '12px 16px',
                                        borderRadius: '10px',
                                        border: '1px solid #d1d5db',
                                        fontSize: '15px',
                                        fontWeight: '500',
                                        outline: 'none'
                                    }}
                                    onFocus={e => e.currentTarget.style.borderColor = '#0284c7'}
                                    onBlur={e => e.currentTarget.style.borderColor = '#d1d5db'}
                                />
                                <button
                                    onClick={handleAddUrl}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '6px',
                                        background: '#f3f4f6',
                                        border: '1px solid #e5e7eb',
                                        color: '#374151',
                                        padding: '12px 20px',
                                        borderRadius: '10px',
                                        fontSize: '15px',
                                        fontWeight: '600',
                                        cursor: 'pointer'
                                    }}
                                    onMouseEnter={e => {
                                        e.currentTarget.style.background = '#e5e7eb';
                                    }}
                                    onMouseLeave={e => {
                                        e.currentTarget.style.background = '#f3f4f6';
                                    }}
                                >
                                    <Plus size={18} /> 添加
                                </button>
                            </div>
                        </div>

                        <div style={{
                            padding: '24px',
                            borderTop: '1px solid #e5e7eb',
                            display: 'flex',
                            justifyContent: 'flex-end',
                            gap: '12px'
                        }}>
                            <button
                                onClick={() => setShowSettings(false)}
                                style={{
                                    padding: '12px 24px',
                                    borderRadius: '10px',
                                    border: '1px solid #e5e7eb',
                                    background: '#fff',
                                    color: '#374151',
                                    fontSize: '15px',
                                    fontWeight: '600',
                                    cursor: 'pointer'
                                }}
                                onMouseEnter={e => e.currentTarget.style.background = '#f9fafb'}
                                onMouseLeave={e => e.currentTarget.style.background = '#fff'}
                            >
                                取消
                            </button>
                            <button
                                onClick={handleSaveConfig}
                                disabled={savingConfig}
                                style={{
                                    padding: '12px 24px',
                                    borderRadius: '10px',
                                    border: 'none',
                                    background: '#0284c7',
                                    color: '#fff',
                                    fontSize: '15px',
                                    fontWeight: '600',
                                    cursor: savingConfig ? 'not-allowed' : 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px',
                                    opacity: savingConfig ? 0.6 : 1
                                }}
                            >
                                <Save size={18} /> {savingConfig ? '保存中...' : '保存配置'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Dashboard;
