import React, { useEffect, useState, useRef, useMemo, useCallback } from 'react';
import { ArrowUp, ArrowDown, RefreshCw, Settings, Plus, Trash2, X, Save, Eye, Check, Calendar, ExternalLink, Globe, Search, DollarSign, ChevronDown, Filter } from 'lucide-react';
import CommodityCard from '../components/CommodityCard';
import ExchangeStatus from '../components/ExchangeStatus';
import NewsFeed from '../components/NewsFeed';
import AIAnalysis from '../components/AIAnalysis';
import api from '../services/api';
import * as echarts from 'echarts';

// Safe URL parsing helper to avoid errors
const safeGetHostname = (url) => {
    if (!url) return '';
    try {
        return new URL(url).hostname;
    } catch {
        return url.substring(0, 30) + (url.length > 30 ? '...' : '');
    }
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
    'Aluminum': '铝',
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
    const [selectedCountry, setSelectedCountry] = useState('all');
    // 改为多选：使用Set存储选中的网站ID
    const [selectedWebsites, setSelectedWebsites] = useState(new Set());
    // 临时状态：用于在弹窗中暂存选择，点击确定后才应用
    const [tempSelectedCountry, setTempSelectedCountry] = useState('all');
    const [tempSelectedWebsites, setTempSelectedWebsites] = useState(new Set());
    const sourceFilterRef = useRef(null);

    // Exchange rate (Mock)
    const EXCHANGE_RATE = 7.2;

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

    // 获取数据来源信息
    useEffect(() => {
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

    // 加载历史数据（日/周/月）
    const loadPriceHistory = async () => {
        try {
            // 根据时间范围确定天数：日=1，周=7，月=30
            const daysMap = { day: 1, week: 7, month: 30 };
            const days = daysMap[timeRange] || 7;
            const response = await api.getPriceHistory(null, days);
            const historyData = response.data?.data || response.data?.commodities || {};
            setPriceHistory(historyData);
        } catch (err) {
            console.error('加载历史数据失败:', err);
        }
    };

    useEffect(() => {
        loadPriceHistory();
    }, [timeRange]);

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

    const formatPrice = (price) => {
        if (!price) return '0.00';
        const val = parseFloat(price);
        if (currency === 'CNY') {
            return (val * EXCHANGE_RATE).toFixed(2);
        }
        return val.toFixed(2);
    };

    const getCurrencySymbol = () => currency === 'USD' ? '$' : '¥';

    // 安全获取数值
    const safeNumber = (val, defaultVal = 0) => {
        const num = parseFloat(val);
        return isNaN(num) ? defaultVal : num;
    };

    // 从数据中提取所有唯一商品（合并相同商品的不同来源）
    const allCommodities = useMemo(() => {
        const commodityMap = new Map();
        (data || []).forEach(item => {
            const rawName = item.name || item.chinese_name;
            const normalizedName = getNormalizedName(rawName);
            
            if (!normalizedName) return;
            
            if (!commodityMap.has(normalizedName)) {
                commodityMap.set(normalizedName, {
                    name: normalizedName,
                    rawNames: [rawName],
                    sources: [{
                        name: rawName,
                        price: safeNumber(item.price || item.current_price, 0),
                        change: safeNumber(item.change || item.change_percent, 0),
                        unit: item.unit,
                        url: item.url,
                        source: safeGetHostname(item.url)
                    }],
                    price: safeNumber(item.price || item.current_price, 0),
                    change: safeNumber(item.change || item.change_percent, 0),
                    unit: item.unit,
                    url: item.url,
                    source: safeGetHostname(item.url)
                });
            } else {
                // 合并多个来源
                const existing = commodityMap.get(normalizedName);
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
                }
            }
        });
        return Array.from(commodityMap.values());
    }, [data]);

    // 过滤商品列表（用于选择器搜索）
    const filteredCommodities = useMemo(() => {
        if (!commoditySearchTerm) return allCommodities;
        const searchLower = commoditySearchTerm.toLowerCase();
        return allCommodities.filter(c => 
            c.name.toLowerCase().includes(searchLower) ||
            (c.source && c.source.toLowerCase().includes(searchLower))
        );
    }, [allCommodities, commoditySearchTerm]);

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
        setSelectedCommodities(new Set(allCommodities.map(c => c.name)));
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

    // 获取选中商品的显示数据（使用合并后的商品数据）
    const displayCommodities = useMemo(() => {
        const colors = ['#f59e0b', '#8b5cf6', '#3b82f6', '#10b981', '#ef4444', '#06b6d4', '#ec4899', '#84cc16', '#f97316', '#6366f1', '#14b8a6', '#a855f7'];
        
        return allCommodities
            .filter(commodity => {
                // 先检查是否选中
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
                    historyData: historyData,
                    dataItem: commodity
                };
            });
    }, [allCommodities, selectedCommodities, getHistoryData, timeRange]);

    if (loading) return (
        <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            height: '100vh',
            fontSize: '16px',
            color: '#6b7280'
        }}>
            <RefreshCw className="animate-spin" style={{ marginRight: '8px' }} size={20} />
            加载数据中...
        </div>
    );
    
    if (error) return (
        <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            height: '100vh',
            fontSize: '16px',
            color: '#ef4444'
        }}>
            错误: {error}
        </div>
    );

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

                    {/* 商品选择器 - 新增带搜索和滚动的可勾选框 */}
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
                            商品 ({selectedCommodities.size}/{allCommodities.length})
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
                                            全选
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
                                                        transition: 'all 0.15s ease'
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
                                                            textOverflow: 'ellipsis'
                                                        }}>
                                                            {comm.name}
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

                    {/* 数据来源筛选器 */}
                    <div ref={sourceFilterRef} style={{ position: 'relative' }}>
                        <button
                            onClick={() => setShowSourceFilter(!showSourceFilter)}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                                background: (selectedCountry !== 'all' || selectedWebsites.size > 0) ? '#dbeafe' : '#fff',
                                border: '1px solid #e5e7eb',
                                padding: '7px 12px',
                                borderRadius: '8px',
                                color: '#374151',
                                cursor: 'pointer',
                                fontSize: '13px',
                                fontWeight: '500'
                            }}
                        >
                            <Globe size={14} />
                            {selectedCountry === 'all' ? '全部来源' : dataSources?.sources?.[selectedCountry]?.flag + ' ' + dataSources?.sources?.[selectedCountry]?.name}
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
                                width: '300px',
                                zIndex: 200,
                                overflow: 'hidden'
                            }}>
                                <div style={{ padding: '12px', borderBottom: '1px solid #f3f4f6', background: '#fafafa' }}>
                                    <div style={{ fontSize: '12px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
                                        按国家/地区筛选
                                    </div>
                                    <select
                                        value={selectedCountry}
                                        onChange={(e) => {
                                            setSelectedCountry(e.target.value);
                                            setSelectedWebsites(new Set());
                                        }}
                                        style={{
                                            width: '100%',
                                            padding: '8px 12px',
                                            borderRadius: '8px',
                                            border: '1px solid #e5e7eb',
                                            fontSize: '13px',
                                            background: '#fff',
                                            cursor: 'pointer'
                                        }}
                                    >
                                        <option value="all">🌍 全部国家/地区</option>
                                        {dataSources.cascade?.map(country => (
                                            <option key={country.code} value={country.code}>
                                                {country.flag} {country.name} ({country.commodity_count} 商品)
                                            </option>
                                        ))}
                                    </select>
                                </div>
                                
                                {selectedCountry !== 'all' && (
                                    <div style={{ padding: '12px', borderBottom: '1px solid #f3f4f6' }}>
                                        <div style={{ fontSize: '12px', fontWeight: '600', color: '#374151', marginBottom: '8px' }}>
                                            按网站筛选
                                        </div>
                                        <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                                            {dataSources.sources?.[selectedCountry]?.websites?.map(website => {
                                                const isChecked = selectedWebsites.has(website.id);
                                                return (
                                                    <div
                                                        key={website.id}
                                                        onClick={() => {
                                                            setSelectedWebsites(prev => {
                                                                const newSet = new Set(prev);
                                                                if (newSet.has(website.id)) {
                                                                    newSet.delete(website.id);
                                                                } else {
                                                                    newSet.add(website.id);
                                                                }
                                                                return newSet;
                                                            });
                                                        }}
                                                        style={{
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            gap: '8px',
                                                            padding: '8px 10px',
                                                            cursor: 'pointer',
                                                            borderRadius: '6px',
                                                            background: isChecked ? '#eff6ff' : 'transparent',
                                                            marginBottom: '4px'
                                                        }}
                                                    >
                                                        <div style={{
                                                            width: '16px',
                                                            height: '16px',
                                                            border: isChecked ? 'none' : '2px solid #d1d5db',
                                                            borderRadius: '4px',
                                                            background: isChecked ? '#3b82f6' : '#fff',
                                                            display: 'flex',
                                                            alignItems: 'center',
                                                            justifyContent: 'center'
                                                        }}>
                                                            {isChecked && <Check size={10} color="#fff" strokeWidth={3} />}
                                                        </div>
                                                        <span style={{ fontSize: '13px', color: '#374151' }}>
                                                            {website.name} ({website.commodities.length})
                                                        </span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                )}
                                
                                <div style={{ padding: '12px', display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                                    <button
                                        onClick={() => {
                                            setSelectedCountry('all');
                                            setSelectedWebsites(new Set());
                                        }}
                                        style={{
                                            padding: '6px 12px',
                                            borderRadius: '6px',
                                            border: '1px solid #e5e7eb',
                                            background: '#fff',
                                            color: '#374151',
                                            fontSize: '12px',
                                            cursor: 'pointer'
                                        }}
                                    >
                                        清除筛选
                                    </button>
                                    <button
                                        onClick={() => setShowSourceFilter(false)}
                                        style={{
                                            padding: '6px 12px',
                                            borderRadius: '6px',
                                            border: 'none',
                                            background: '#3b82f6',
                                            color: '#fff',
                                            fontSize: '12px',
                                            cursor: 'pointer'
                                        }}
                                    >
                                        确定
                                    </button>
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

                    {/* 刷新按钮 */}
                    <button
                        onClick={async () => {
                            setRefreshing(true);
                            try {
                                const response = await api.getData(true);
                                const responseData = response.data || response;
                                setData(responseData.data || []);
                                setLastUpdate(responseData.timestamp || new Date().toISOString());
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

            {/* Main Layout */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '24px' }}>
                <div className="main-content">
                    {/* Summary Cards */}
                    <div style={{ 
                        display: 'grid', 
                        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', 
                        gap: '16px', 
                        marginBottom: '24px' 
                    }}>
                        {/* 汇率卡片 */}
                        <div style={{ 
                            background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)', 
                            padding: '20px', 
                            borderRadius: '12px', 
                            boxShadow: '0 4px 12px -2px rgba(59, 130, 246, 0.25)', 
                            color: '#fff' 
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                                <span style={{ fontSize: '13px', fontWeight: '500', opacity: 0.9 }}>USD/CNY 汇率</span>
                                <span style={{
                                    fontSize: '11px',
                                    fontWeight: '600',
                                    background: 'rgba(255,255,255,0.2)',
                                    padding: '2px 8px',
                                    borderRadius: '999px'
                                }}>实时</span>
                            </div>
                            <div style={{ fontSize: '28px', fontWeight: '700' }}>¥{EXCHANGE_RATE.toFixed(4)}</div>
                            <div style={{ fontSize: '11px', opacity: 0.8, marginTop: '4px' }}>1 USD = {EXCHANGE_RATE} CNY</div>
                        </div>
                        
                        {/* 前4个商品卡片 */}
                        {displayCommodities.slice(0, 4).map((comm, index) => {
                            const isUp = (comm.change || 0) >= 0;
                            return (
                                <div key={index} style={{ 
                                    background: '#fff', 
                                    padding: '20px', 
                                    borderRadius: '12px', 
                                    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
                                    border: '1px solid #f3f4f6'
                                }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                                        <div>
                                            <span style={{ color: '#374151', fontSize: '13px', fontWeight: '500' }}>
                                                {comm.name}
                                            </span>
                                            {comm.source && (
                                                <div style={{ fontSize: '11px', color: '#9ca3af', marginTop: '2px' }}>
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
                                    <div style={{ fontSize: '24px', fontWeight: '700', color: '#111827' }}>
                                        {getCurrencySymbol()}{formatPrice(comm.currentPrice)}
                                        {comm.unit && (
                                            <span style={{ fontSize: '12px', color: '#6b7280', marginLeft: '4px', fontWeight: '500' }}>
                                                /{comm.unit.replace(/USD|CNY|RMB|美元|人民币|\$|¥|\//gi, '').trim()}
                                            </span>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    {/* Charts Grid */}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))',
                        gap: '20px',
                        alignItems: 'start'
                    }}>
                        {displayCommodities.length === 0 ? (
                            <div style={{ 
                                gridColumn: '1 / -1',
                                background: '#fff', 
                                padding: '48px', 
                                borderRadius: '12px',
                                textAlign: 'center',
                                color: '#6b7280'
                            }}>
                                <Filter size={48} style={{ marginBottom: '16px', opacity: 0.3 }} />
                                <p style={{ fontSize: '15px', marginBottom: '8px' }}>未选择任何商品</p>
                                <p style={{ fontSize: '13px', color: '#9ca3af' }}>
                                    点击上方"商品"按钮选择要显示的商品
                                </p>
                            </div>
                        ) : (
                            displayCommodities.map((comm, index) => {
                                const isLastOdd = index === displayCommodities.length - 1 && displayCommodities.length % 2 !== 0;
                                return (
                                    <CommodityCard
                                        key={comm.id || index}
                                        comm={comm}
                                        realItem={comm.dataItem}
                                        currentPrice={comm.currentPrice}
                                        unit={comm.unit}
                                        historyData={comm.historyData}
                                        currencySymbol={getCurrencySymbol()}
                                        formatPrice={formatPrice}
                                        isLastOdd={isLastOdd}
                                        currency={currency}
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
