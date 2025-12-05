import React, { useEffect, useState, useRef, useMemo } from 'react';
import { ArrowUp, ArrowDown, RefreshCw, Settings, Plus, Trash2, X, Save, Eye, Check, Calendar, ExternalLink, Globe, Search, DollarSign, Filter } from 'lucide-react';
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

const Dashboard = () => {
    const [data, setData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState(null);
    const [lastUpdate, setLastUpdate] = useState(null);
    const [priceHistory, setPriceHistory] = useState({});
    const [currency, setCurrency] = useState('CNY');
    const [timeRange, setTimeRange] = useState('day');
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

    const EXCHANGE_RATE = 7.2;
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

    const loadPriceHistory = async () => {
        try {
            const response = await api.getPriceHistory(null, timeRange === 'week' ? 7 : 1);
            const historyData = response.data?.commodities || {};
            setPriceHistory(historyData);
        } catch (err) {
            console.error('加载历史数据失败:', err);
        }
    };

    useEffect(() => {
        loadPriceHistory();
    }, [timeRange]);

    const getHistoryData = (commodityName, basePrice, points) => {
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
        
        let current = basePrice;
        const volatility = basePrice * 0.02;
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
                    : dateObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
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

    const formatPrice = (price) => {
        if (!price) return '0.00';
        const val = parseFloat(price);
        if (currency === 'CNY') {
            return (val * EXCHANGE_RATE).toFixed(2);
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
            name: '铝 (Aluminum)', 
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
    useEffect(() => {
        if (Object.keys(visibleCommodities).length === 0) {
            const initial = {};
            commodities.forEach((comm, idx) => {
                initial[comm.id] = idx < 6; // 默认显示前6个
            });
            setVisibleCommodities(initial);
        }
    }, []);

    // 按类别分组商品
    const commoditiesByCategory = useMemo(() => {
        const grouped = {};
        commodities.forEach(comm => {
            if (!grouped[comm.category]) {
                grouped[comm.category] = [];
            }
            grouped[comm.category].push(comm);
        });
        return grouped;
    }, []);

    // 过滤商品列表
    const filteredCommodities = useMemo(() => {
        if (!commoditySearchTerm) return commodities;
        const searchLower = commoditySearchTerm.toLowerCase();
        return commodities.filter(comm => 
            comm.name.toLowerCase().includes(searchLower) ||
            comm.category.toLowerCase().includes(searchLower)
        );
    }, [commoditySearchTerm]);

    // 按类别分组过滤后的商品
    const filteredCommoditiesByCategory = useMemo(() => {
        const grouped = {};
        filteredCommodities.forEach(comm => {
            if (!grouped[comm.category]) {
                grouped[comm.category] = [];
            }
            grouped[comm.category].push(comm);
        });
        return grouped;
    }, [filteredCommodities]);

    // 切换商品可见性
    const toggleCommodity = (id) => {
        setVisibleCommodities(prev => ({
            ...prev,
            [id]: !prev[id]
        }));
    };

    // 全选/全不选某个类别
    const toggleCategory = (category) => {
        const categoryComms = commoditiesByCategory[category] || [];
        const allVisible = categoryComms.every(comm => visibleCommodities[comm.id]);
        const updated = { ...visibleCommodities };
        categoryComms.forEach(comm => {
            updated[comm.id] = !allVisible;
        });
        setVisibleCommodities(updated);
    };

    // 全选/全不选
    const toggleAll = () => {
        const allVisible = commodities.every(comm => visibleCommodities[comm.id]);
        const updated = {};
        commodities.forEach(comm => {
            updated[comm.id] = !allVisible;
        });
        setVisibleCommodities(updated);
    };

    const commoditiesWithMultiSource = useMemo(() => {
        const sourceColors = ['#0284c7', '#dc2626', '#16a34a', '#9333ea', '#ea580c', '#0891b2'];
        
        return commodities.map(comm => {
            const matchingItems = data.filter(d => {
                const itemName = d.name || d.chinese_name || '';
                const matches = comm.matchPatterns.some(pattern => pattern.test(itemName));
                const excluded = comm.excludePatterns.some(pattern => pattern.test(itemName));
                const price = parseFloat(d.price || d.current_price || 0);
                const priceReasonable = price > 0 && price < comm.basePrice * 100 && price > comm.basePrice * 0.01;
                return matches && !excluded && priceReasonable;
            });

            if (matchingItems.length === 0) {
                return { ...comm, multiSourceItems: [], multiSourceHistory: null };
            }

            const multiSourceHistory = matchingItems.map((item, idx) => {
                const price = item.price || item.current_price || comm.basePrice;
                const itemName = item.chinese_name || item.name || comm.name;
                const histData = getHistoryData(
                    itemName,
                    parseFloat(price || 0),
                    timeRange === 'day' ? 24 : 7
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

            return {
                ...comm,
                unit,
                currentPrice,
                multiSourceItems: matchingItems,
                multiSourceHistory
            };
        });
    }, [data, timeRange, priceHistory]);

    if (loading) return (
        <div style={{ 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            height: '100vh',
            fontSize: '18px',
            color: '#6b7280'
        }}>
            <RefreshCw size={24} className="animate-spin" style={{ marginRight: '12px' }} />
            加载数据中...
        </div>
    );
    
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
        displayItems = commodities.filter(c => visibleCommodities[c.id]);
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
                    <h1 style={{ 
                        margin: 0, 
                        fontSize: '32px', 
                        fontWeight: '700',
                        color: '#111827',
                        letterSpacing: '-0.02em'
                    }}>
                        市场概览
                    </h1>
                    <p style={{ 
                        color: '#6b7280', 
                        marginTop: '8px',
                        fontSize: '15px'
                    }}>
                        实时大宗商品价格监控
                        {lastUpdate && (
                            <span style={{ 
                                marginLeft: '12px', 
                                fontSize: '13px', 
                                color: '#9ca3af',
                                fontWeight: '500'
                            }}>
                                更新: {new Date(lastUpdate).toLocaleTimeString()}
                            </span>
                        )}
                    </p>
                </div>

                <div className="controls" style={{ 
                    display: 'flex', 
                    gap: '12px', 
                    alignItems: 'center',
                    flexWrap: 'wrap'
                }}>
                    {/* 搜索输入框 */}
                    <div style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '8px', 
                        background: '#fff', 
                        border: '1px solid #e5e7eb', 
                        padding: '10px 14px', 
                        borderRadius: '10px', 
                        minWidth: '220px',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
                    }}>
                        <Search size={18} color="#9ca3af" />
                        <input
                            type="text"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            placeholder="搜索商品..."
                            style={{ 
                                border: 'none', 
                                outline: 'none', 
                                fontSize: '15px', 
                                color: '#374151', 
                                background: 'transparent', 
                                padding: 0, 
                                width: '100%',
                                fontWeight: '500'
                            }}
                        />
                        {searchTerm && (
                            <button 
                                onClick={() => setSearchTerm('')} 
                                style={{ 
                                    border: 'none', 
                                    background: 'none', 
                                    padding: 0, 
                                    cursor: 'pointer', 
                                    display: 'flex',
                                    alignItems: 'center'
                                }}
                            >
                                <X size={16} color="#9ca3af" />
                            </button>
                        )}
                    </div>

                    {/* URL 筛选器 */}
                    {urlStats.length > 0 && (
                        <div ref={urlFilterRef} style={{ position: 'relative' }}>
                            <div style={{ 
                                display: 'flex', 
                                alignItems: 'center', 
                                gap: '8px', 
                                background: '#fff', 
                                border: '1px solid #e5e7eb', 
                                padding: '10px 14px', 
                                borderRadius: '10px',
                                minWidth: '240px',
                                boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
                            }}>
                                <Globe size={18} color="#6b7280" />
                                <input
                                    type="text"
                                    value={urlInputValue}
                                    onChange={(e) => {
                                        setUrlInputValue(e.target.value);
                                        setSelectedUrl('');
                                        setShowUrlDropdown(true);
                                    }}
                                    onFocus={() => setShowUrlDropdown(true)}
                                    placeholder="筛选来源..."
                                    style={{ 
                                        border: 'none', 
                                        outline: 'none', 
                                        fontSize: '15px', 
                                        color: '#374151', 
                                        background: 'transparent', 
                                        padding: 0, 
                                        flex: 1,
                                        minWidth: '120px',
                                        fontWeight: '500'
                                    }}
                                />
                                {(selectedUrl || urlInputValue) && (
                                    <button
                                        onClick={() => {
                                            setSelectedUrl('');
                                            setUrlInputValue('');
                                        }}
                                        style={{ 
                                            border: 'none', 
                                            background: 'none', 
                                            padding: '2px', 
                                            cursor: 'pointer', 
                                            display: 'flex',
                                            alignItems: 'center'
                                        }}
                                    >
                                        <X size={16} color="#9ca3af" />
                                    </button>
                                )}
                            </div>
                            
                            {showUrlDropdown && (
                                <div style={{
                                    position: 'absolute',
                                    top: '100%',
                                    left: 0,
                                    right: 0,
                                    marginTop: '6px',
                                    background: '#fff',
                                    borderRadius: '12px',
                                    boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1)',
                                    border: '1px solid #e5e7eb',
                                    maxHeight: '320px',
                                    overflowY: 'auto',
                                    zIndex: 100
                                }}>
                                    <div
                                        onClick={() => {
                                            setSelectedUrl('');
                                            setUrlInputValue('');
                                            setShowUrlDropdown(false);
                                        }}
                                        style={{
                                            padding: '12px 16px',
                                            cursor: 'pointer',
                                            borderBottom: '1px solid #f3f4f6',
                                            fontSize: '15px',
                                            fontWeight: '500',
                                            color: '#374151',
                                            display: 'flex',
                                            justifyContent: 'space-between',
                                            alignItems: 'center',
                                            background: !selectedUrl && !urlInputValue ? '#f9fafb' : 'transparent'
                                        }}
                                        onMouseEnter={e => e.currentTarget.style.background = '#f9fafb'}
                                        onMouseLeave={e => e.currentTarget.style.background = !selectedUrl && !urlInputValue ? '#f9fafb' : 'transparent'}
                                    >
                                        <span>全部来源</span>
                                        <span style={{ 
                                            fontSize: '13px', 
                                            color: '#fff',
                                            background: '#6b7280',
                                            padding: '2px 10px',
                                            borderRadius: '12px',
                                            fontWeight: '600'
                                        }}>
                                            {data.length}
                                        </span>
                                    </div>
                                    {filteredUrlStats.map((stat, idx) => (
                                        <div
                                            key={idx}
                                            onClick={() => {
                                                setSelectedUrl(stat.hostname);
                                                setUrlInputValue(stat.hostname);
                                                setShowUrlDropdown(false);
                                            }}
                                            style={{
                                                padding: '12px 16px',
                                                cursor: 'pointer',
                                                borderBottom: idx < filteredUrlStats.length - 1 ? '1px solid #f3f4f6' : 'none',
                                                fontSize: '15px',
                                                fontWeight: '500',
                                                color: '#374151',
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center',
                                                background: selectedUrl === stat.hostname ? '#f0f9ff' : 'transparent'
                                            }}
                                            onMouseEnter={e => e.currentTarget.style.background = '#f9fafb'}
                                            onMouseLeave={e => e.currentTarget.style.background = selectedUrl === stat.hostname ? '#f0f9ff' : 'transparent'}
                                        >
                                            <div style={{ 
                                                display: 'flex', 
                                                flexDirection: 'column', 
                                                gap: '4px',
                                                flex: 1
                                            }}>
                                                <span>{stat.hostname}</span>
                                                <span style={{ 
                                                    fontSize: '12px', 
                                                    color: '#9ca3af', 
                                                    maxWidth: '200px', 
                                                    overflow: 'hidden', 
                                                    textOverflow: 'ellipsis', 
                                                    whiteSpace: 'nowrap'
                                                }}>
                                                    {stat.items.slice(0, 3).join(', ')}{stat.items.length > 3 ? '...' : ''}
                                                </span>
                                            </div>
                                            <span style={{ 
                                                fontSize: '13px', 
                                                color: '#fff',
                                                background: '#0284c7',
                                                padding: '2px 10px',
                                                borderRadius: '12px',
                                                fontWeight: '600'
                                            }}>
                                                {stat.count}
                                            </span>
                                        </div>
                                    ))}
                                    {filteredUrlStats.length === 0 && urlInputValue && (
                                        <div style={{ 
                                            padding: '24px', 
                                            textAlign: 'center', 
                                            color: '#9ca3af', 
                                            fontSize: '15px'
                                        }}>
                                            未找到匹配的来源
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                    {/* 日期选择器 */}
                    <div style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '8px', 
                        background: '#fff', 
                        border: '1px solid #e5e7eb', 
                        padding: '10px 14px', 
                        borderRadius: '10px',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
                    }}>
                        <Calendar size={18} color="#6b7280" />
                        <input
                            type="date"
                            value={selectedDate}
                            onChange={(e) => setSelectedDate(e.target.value)}
                            style={{ 
                                border: 'none', 
                                outline: 'none', 
                                fontSize: '15px', 
                                fontWeight: '500',
                                color: '#374151', 
                                background: 'transparent', 
                                padding: 0
                            }}
                        />
                    </div>

                    {/* 时间范围切换 */}
                    <div className="toggle-group" style={{ 
                        background: '#f3f4f6', 
                        padding: '4px', 
                        borderRadius: '10px', 
                        display: 'flex',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
                    }}>
                        <button
                            onClick={() => setTimeRange('day')}
                            style={{
                                padding: '8px 18px',
                                borderRadius: '8px',
                                border: 'none',
                                background: timeRange === 'day' ? '#fff' : 'transparent',
                                boxShadow: timeRange === 'day' ? '0 2px 4px rgba(0,0,0,0.1)' : 'none',
                                fontWeight: '600',
                                fontSize: '15px',
                                color: timeRange === 'day' ? '#111' : '#6b7280',
                                cursor: 'pointer',
                                transition: 'all 0.2s'
                            }}
                        >
                            24H
                        </button>
                        <button
                            onClick={() => setTimeRange('week')}
                            style={{
                                padding: '8px 18px',
                                borderRadius: '8px',
                                border: 'none',
                                background: timeRange === 'week' ? '#fff' : 'transparent',
                                boxShadow: timeRange === 'week' ? '0 2px 4px rgba(0,0,0,0.1)' : 'none',
                                fontWeight: '600',
                                fontSize: '15px',
                                color: timeRange === 'week' ? '#111' : '#6b7280',
                                cursor: 'pointer',
                                transition: 'all 0.2s'
                            }}
                        >
                            7D
                        </button>
                    </div>

                    {/* 货币切换 */}
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        background: '#f3f4f6',
                        padding: '4px',
                        borderRadius: '10px',
                        gap: '4px',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.05)'
                    }}>
                        <button
                            onClick={() => setCurrency('CNY')}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '8px 16px',
                                borderRadius: '8px',
                                border: 'none',
                                background: currency === 'CNY' ? '#fff' : 'transparent',
                                boxShadow: currency === 'CNY' ? '0 2px 4px rgba(0,0,0,0.1)' : 'none',
                                fontWeight: '700',
                                fontSize: '15px',
                                color: currency === 'CNY' ? '#dc2626' : '#6b7280',
                                cursor: 'pointer',
                                transition: 'all 0.2s'
                            }}
                        >
                            ¥ CNY
                        </button>
                        <button
                            onClick={() => setCurrency('USD')}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '8px 16px',
                                borderRadius: '8px',
                                border: 'none',
                                background: currency === 'USD' ? '#fff' : 'transparent',
                                boxShadow: currency === 'USD' ? '0 2px 4px rgba(0,0,0,0.1)' : 'none',
                                fontWeight: '700',
                                fontSize: '15px',
                                color: currency === 'USD' ? '#16a34a' : '#6b7280',
                                cursor: 'pointer',
                                transition: 'all 0.2s'
                            }}
                        >
                            $ USD
                        </button>
                    </div>

                    {/* 商品选择器 - 改进版 */}
                    <div style={{ position: 'relative' }} ref={commoditySelectorRef}>
                        <button
                            onClick={() => setShowCommoditySelector(!showCommoditySelector)}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                background: '#fff',
                                border: '1px solid #e5e7eb',
                                padding: '10px 16px',
                                borderRadius: '10px',
                                color: '#374151',
                                cursor: 'pointer',
                                fontWeight: '600',
                                fontSize: '15px',
                                boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                                transition: 'all 0.2s'
                            }}
                            onMouseEnter={e => e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)'}
                            onMouseLeave={e => e.currentTarget.style.boxShadow = '0 1px 2px rgba(0,0,0,0.05)'}
                        >
                            <Filter size={18} />
                            <span>商品筛选</span>
                            <span style={{
                                fontSize: '13px',
                                fontWeight: '700',
                                color: '#fff',
                                background: '#0284c7',
                                padding: '2px 8px',
                                borderRadius: '10px'
                            }}>
                                {visibleCount}/{commodities.length}
                            </span>
                        </button>
                        
                        {showCommoditySelector && (
                            <div style={{
                                position: 'absolute',
                                top: '100%',
                                right: 0,
                                marginTop: '8px',
                                background: '#fff',
                                borderRadius: '12px',
                                boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.1)',
                                border: '1px solid #e5e7eb',
                                width: '420px',
                                maxHeight: '580px',
                                zIndex: 100,
                                display: 'flex',
                                flexDirection: 'column'
                            }}>
                                {/* 标题和搜索 */}
                                <div style={{ 
                                    padding: '16px',
                                    borderBottom: '1px solid #e5e7eb'
                                }}>
                                    <div style={{ 
                                        display: 'flex', 
                                        justifyContent: 'space-between', 
                                        alignItems: 'center',
                                        marginBottom: '12px'
                                    }}>
                                        <h3 style={{ 
                                            margin: 0, 
                                            fontSize: '16px', 
                                            fontWeight: '700',
                                            color: '#111827'
                                        }}>
                                            选择商品
                                        </h3>
                                        <button
                                            onClick={toggleAll}
                                            style={{
                                                fontSize: '13px',
                                                fontWeight: '600',
                                                color: '#0284c7',
                                                background: 'none',
                                                border: 'none',
                                                cursor: 'pointer',
                                                padding: '4px 8px'
                                            }}
                                        >
                                            {commodities.every(c => visibleCommodities[c.id]) ? '全不选' : '全选'}
                                        </button>
                                    </div>
                                    
                                    {/* 搜索框 */}
                                    <div style={{ 
                                        display: 'flex', 
                                        alignItems: 'center', 
                                        gap: '8px', 
                                        background: '#f9fafb', 
                                        border: '1px solid #e5e7eb', 
                                        padding: '8px 12px', 
                                        borderRadius: '8px'
                                    }}>
                                        <Search size={16} color="#9ca3af" />
                                        <input
                                            type="text"
                                            value={commoditySearchTerm}
                                            onChange={(e) => setCommoditySearchTerm(e.target.value)}
                                            placeholder="搜索商品或类别..."
                                            style={{ 
                                                border: 'none', 
                                                outline: 'none', 
                                                fontSize: '14px', 
                                                fontWeight: '500',
                                                color: '#374151', 
                                                background: 'transparent', 
                                                padding: 0,
                                                width: '100%'
                                            }}
                                        />
                                        {commoditySearchTerm && (
                                            <button
                                                onClick={() => setCommoditySearchTerm('')}
                                                style={{ 
                                                    border: 'none', 
                                                    background: 'none', 
                                                    padding: 0, 
                                                    cursor: 'pointer', 
                                                    display: 'flex'
                                                }}
                                            >
                                                <X size={14} color="#9ca3af" />
                                            </button>
                                        )}
                                    </div>
                                </div>

                                {/* 商品列表 - 按类别分组 */}
                                <div style={{ 
                                    flex: 1,
                                    overflowY: 'auto',
                                    padding: '8px'
                                }}>
                                    {Object.entries(filteredCommoditiesByCategory).map(([category, comms]) => (
                                        <div key={category} style={{ marginBottom: '12px' }}>
                                            {/* 类别标题 */}
                                            <div
                                                onClick={() => toggleCategory(category)}
                                                style={{
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    gap: '8px',
                                                    padding: '8px 12px',
                                                    cursor: 'pointer',
                                                    borderRadius: '8px',
                                                    background: '#f9fafb',
                                                    marginBottom: '6px'
                                                }}
                                                onMouseEnter={e => e.currentTarget.style.background = '#f3f4f6'}
                                                onMouseLeave={e => e.currentTarget.style.background = '#f9fafb'}
                                            >
                                                <div style={{
                                                    width: '18px',
                                                    height: '18px',
                                                    border: '2px solid #d1d5db',
                                                    borderRadius: '4px',
                                                    display: 'flex',
                                                    alignItems: 'center',
                                                    justifyContent: 'center',
                                                    background: comms.every(c => visibleCommodities[c.id]) ? '#0284c7' : '#fff',
                                                    borderColor: comms.every(c => visibleCommodities[c.id]) ? '#0284c7' : '#d1d5db'
                                                }}>
                                                    {comms.every(c => visibleCommodities[c.id]) && (
                                                        <Check size={12} color="#fff" strokeWidth={3} />
                                                    )}
                                                </div>
                                                <span style={{
                                                    fontSize: '14px',
                                                    fontWeight: '700',
                                                    color: '#374151',
                                                    flex: 1
                                                }}>
                                                    {category}
                                                </span>
                                                <span style={{
                                                    fontSize: '12px',
                                                    color: '#9ca3af',
                                                    fontWeight: '600'
                                                }}>
                                                    {comms.filter(c => visibleCommodities[c.id]).length}/{comms.length}
                                                </span>
                                            </div>

                                            {/* 商品列表 */}
                                            {comms.map(comm => (
                                                <div
                                                    key={comm.id}
                                                    onClick={() => toggleCommodity(comm.id)}
                                                    style={{
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        gap: '10px',
                                                        padding: '10px 12px',
                                                        marginLeft: '12px',
                                                        cursor: 'pointer',
                                                        borderRadius: '8px',
                                                        fontSize: '14px',
                                                        fontWeight: '500',
                                                        color: '#374151',
                                                        background: visibleCommodities[comm.id] ? '#f0f9ff' : 'transparent'
                                                    }}
                                                    onMouseEnter={e => e.currentTarget.style.background = visibleCommodities[comm.id] ? '#e0f2fe' : '#f9fafb'}
                                                    onMouseLeave={e => e.currentTarget.style.background = visibleCommodities[comm.id] ? '#f0f9ff' : 'transparent'}
                                                >
                                                    <div style={{
                                                        width: '18px',
                                                        height: '18px',
                                                        border: '2px solid #d1d5db',
                                                        borderRadius: '4px',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        justifyContent: 'center',
                                                        background: visibleCommodities[comm.id] ? '#0284c7' : '#fff',
                                                        borderColor: visibleCommodities[comm.id] ? '#0284c7' : '#d1d5db'
                                                    }}>
                                                        {visibleCommodities[comm.id] && (
                                                            <Check size={12} color="#fff" strokeWidth={3} />
                                                        )}
                                                    </div>
                                                    <span style={{
                                                        width: '14px',
                                                        height: '14px',
                                                        borderRadius: '50%',
                                                        background: comm.color,
                                                        flexShrink: 0
                                                    }}></span>
                                                    <span style={{ flex: 1 }}>{comm.name}</span>
                                                </div>
                                            ))}
                                        </div>
                                    ))}
                                    
                                    {Object.keys(filteredCommoditiesByCategory).length === 0 && (
                                        <div style={{ 
                                            padding: '40px 20px', 
                                            textAlign: 'center', 
                                            color: '#9ca3af',
                                            fontSize: '14px'
                                        }}>
                                            未找到匹配的商品
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
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
                            gap: '8px',
                            background: refreshing ? '#f3f4f6' : '#10b981',
                            border: 'none',
                            padding: '10px 18px',
                            borderRadius: '10px',
                            color: '#fff',
                            cursor: refreshing ? 'not-allowed' : 'pointer',
                            fontWeight: '600',
                            fontSize: '15px',
                            boxShadow: refreshing ? 'none' : '0 2px 4px rgba(16, 185, 129, 0.3)',
                            transition: 'all 0.2s'
                        }}
                        onMouseEnter={e => {
                            if (!refreshing) e.currentTarget.style.boxShadow = '0 4px 8px rgba(16, 185, 129, 0.4)';
                        }}
                        onMouseLeave={e => {
                            if (!refreshing) e.currentTarget.style.boxShadow = '0 2px 4px rgba(16, 185, 129, 0.3)';
                        }}
                    >
                        <RefreshCw size={18} className={refreshing ? 'animate-spin' : ''} />
                        {refreshing ? '刷新中' : '刷新'}
                    </button>

                    {/* 设置按钮 */}
                    <button
                        onClick={() => setShowSettings(true)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            background: '#fff',
                            border: '1px solid #e5e7eb',
                            padding: '10px 18px',
                            borderRadius: '10px',
                            color: '#374151',
                            cursor: 'pointer',
                            fontWeight: '600',
                            fontSize: '15px',
                            boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                            transition: 'all 0.2s'
                        }}
                        onMouseEnter={e => e.currentTarget.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)'}
                        onMouseLeave={e => e.currentTarget.style.boxShadow = '0 1px 2px rgba(0,0,0,0.05)'}
                    >
                        <Settings size={18} />
                        设置
                    </button>
                </div>
            </div>

            {/* URL分组展示面板 */}
            {groupedByUrl && groupedByUrl.length > 0 && (selectedUrl || urlInputValue) && (
                <div style={{
                    background: 'linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%)',
                    padding: '24px',
                    borderRadius: '16px',
                    marginBottom: '24px',
                    border: '2px solid #bae6fd',
                    boxShadow: '0 4px 6px -1px rgba(56, 189, 248, 0.1)'
                }}>
                    <div style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        gap: '12px', 
                        marginBottom: '20px'
                    }}>
                        <Globe size={24} color="#0369a1" />
                        <h3 style={{ 
                            margin: 0, 
                            fontSize: '18px', 
                            fontWeight: '700', 
                            color: '#0c4a6e'
                        }}>
                            按来源分组显示
                        </h3>
                        <span style={{
                            fontSize: '14px',
                            fontWeight: '600',
                            color: '#0369a1',
                            background: '#fff',
                            padding: '4px 12px',
                            borderRadius: '12px'
                        }}>
                            {groupedByUrl.reduce((sum, g) => sum + g.items.length, 0)} 条数据，{groupedByUrl.length} 个来源
                        </span>
                    </div>
                    <div style={{ 
                        display: 'flex', 
                        flexDirection: 'column', 
                        gap: '16px'
                    }}>
                        {groupedByUrl.map((group, gIdx) => (
                            <div key={gIdx} style={{
                                background: '#fff',
                                borderRadius: '12px',
                                padding: '20px',
                                border: '1px solid #e0f2fe',
                                boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
                            }}>
                                <div style={{ 
                                    display: 'flex', 
                                    alignItems: 'center', 
                                    gap: '10px', 
                                    marginBottom: '16px',
                                    paddingBottom: '12px',
                                    borderBottom: '2px solid #f0f9ff'
                                }}>
                                    <a
                                        href={group.urls[0] || '#'}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '8px',
                                            fontSize: '16px',
                                            fontWeight: '700',
                                            color: '#0369a1',
                                            textDecoration: 'none'
                                        }}
                                    >
                                        <Globe size={18} />
                                        {group.hostname}
                                    </a>
                                    <span style={{
                                        fontSize: '14px',
                                        color: '#fff',
                                        background: '#0284c7',
                                        padding: '4px 12px',
                                        borderRadius: '12px',
                                        fontWeight: '700'
                                    }}>
                                        {group.items.length} 条
                                    </span>
                                </div>
                                <div style={{ 
                                    display: 'grid', 
                                    gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', 
                                    gap: '12px'
                                }}>
                                    {group.items.map((item, iIdx) => {
                                        const price = item.price || item.current_price || 0;
                                        const change = item.change || item.change_percent || 0;
                                        const isUp = change >= 0;
                                        return (
                                            <div key={iIdx} style={{
                                                padding: '14px',
                                                background: '#f9fafb',
                                                borderRadius: '10px',
                                                fontSize: '14px',
                                                border: '1px solid #f3f4f6'
                                            }}>
                                                <div style={{ 
                                                    fontWeight: '600', 
                                                    color: '#374151', 
                                                    marginBottom: '8px',
                                                    fontSize: '15px'
                                                }}>
                                                    {item.name || item.chinese_name}
                                                </div>
                                                <div style={{ 
                                                    display: 'flex', 
                                                    justifyContent: 'space-between', 
                                                    alignItems: 'center'
                                                }}>
                                                    <span style={{ 
                                                        fontWeight: '700', 
                                                        color: '#111',
                                                        fontSize: '16px'
                                                    }}>
                                                        {getCurrencySymbol()}{formatPrice(price)}
                                                        {item.unit && (
                                                            <span style={{ 
                                                                fontSize: '12px', 
                                                                color: '#6b7280',
                                                                fontWeight: '500'
                                                            }}>
                                                                /{item.unit}
                                                            </span>
                                                        )}
                                                    </span>
                                                    <span style={{
                                                        fontSize: '13px',
                                                        fontWeight: '700',
                                                        color: isUp ? '#10b981' : '#ef4444',
                                                        background: isUp ? '#d1fae5' : '#fee2e2',
                                                        padding: '3px 8px',
                                                        borderRadius: '8px'
                                                    }}>
                                                        {isUp ? '+' : ''}{change}%
                                                    </span>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <div style={{ 
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
                        <div style={{ 
                            background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)', 
                            padding: '24px', 
                            borderRadius: '16px', 
                            boxShadow: '0 8px 16px -4px rgba(59, 130, 246, 0.3)', 
                            color: '#fff'
                        }}>
                            <div style={{ 
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
                            <div style={{ 
                                fontSize: '36px', 
                                fontWeight: '800',
                                letterSpacing: '-0.02em'
                            }}>
                                ¥{EXCHANGE_RATE.toFixed(4)}
                            </div>
                            <div style={{ 
                                fontSize: '13px', 
                                opacity: 0.85, 
                                marginTop: '6px',
                                fontWeight: '500'
                            }}>
                                1 USD = {EXCHANGE_RATE} CNY
                            </div>
                        </div>
                        
                        {data.slice(0, 3).map((item, index) => {
                            const price = item.price || item.current_price || item.last_price || 0;
                            const change = item.change || item.change_percent || 0;
                            const isUp = change >= 0;
                            const hostname = safeGetHostname(item.url);
                            const cleanUnit = (item.unit || '')
                                .replace(/USD|CNY|RMB|美元|人民币/gi, '')
                                .replace(/[$¥/]/g, '')
                                .trim();

                            return (
                                <div key={index} style={{ 
                                    background: '#fff', 
                                    padding: '24px', 
                                    borderRadius: '16px', 
                                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
                                    border: '1px solid #f3f4f6'
                                }}>
                                    <div style={{ 
                                        display: 'flex', 
                                        justifyContent: 'space-between', 
                                        marginBottom: '12px'
                                    }}>
                                        <div style={{ 
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
                                    <div style={{ 
                                        fontSize: '36px', 
                                        fontWeight: '800', 
                                        color: '#111827',
                                        letterSpacing: '-0.02em'
                                    }}>
                                        {getCurrencySymbol()}{formatPrice(price)}
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
                        })}
                    </div>

                    {/* 图表区域 - 改进布局 */}
                    <div className="charts-section" style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))',
                        gap: '24px',
                        alignItems: 'start'
                    }}>
                        {(searchTerm || selectedUrl) ? (
                            displayItems.map((comm, index) => {
                                const realItem = comm.dataItem;
                                const currentPrice = realItem ? (realItem.price || realItem.current_price) : comm.basePrice;
                                const unit = (realItem && realItem.unit) ? realItem.unit : comm.unit;
                                const historyData = generateHistory(
                                    parseFloat(currentPrice || 0), 
                                    timeRange === 'day' ? 24 : 7, 
                                    parseFloat(currentPrice || 100) * 0.02
                                );
                                const isLastOdd = index === displayItems.length - 1 && displayItems.length % 2 !== 0;

                                return (
                                    <CommodityCard
                                        key={comm.id || index}
                                        comm={comm}
                                        realItem={realItem}
                                        currentPrice={currentPrice}
                                        unit={unit}
                                        historyData={historyData}
                                        currencySymbol={getCurrencySymbol()}
                                        formatPrice={formatPrice}
                                        isLastOdd={isLastOdd}
                                        currency={currency}
                                    />
                                );
                            })
                        ) : (
                            commoditiesWithMultiSource
                                .filter(c => visibleCommodities[c.id])
                                .map((comm, index, arr) => {
                                    const isLastOdd = index === arr.length - 1 && arr.length % 2 !== 0;

                                    return (
                                        <CommodityCard
                                            key={comm.id}
                                            comm={comm}
                                            multiSourceItems={comm.multiSourceItems}
                                            currentPrice={comm.currentPrice || comm.basePrice}
                                            unit={comm.unit}
                                            multiSourceHistory={comm.multiSourceHistory}
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
