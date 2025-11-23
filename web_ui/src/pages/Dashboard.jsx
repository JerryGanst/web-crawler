import React, { useEffect, useState, useRef, useMemo } from 'react';
import { ArrowUp, ArrowDown, RefreshCw, Settings, Plus, Trash2, X, Save, Eye, Check, Calendar, ExternalLink, Globe, Filter } from 'lucide-react';
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
    const [error, setError] = useState(null);
    const [currency, setCurrency] = useState('CNY'); // 'CNY' or 'USD'
    const [timeRange, setTimeRange] = useState('day'); // 'day' or 'week'
    const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0]);

    // Settings Modal State
    const [showSettings, setShowSettings] = useState(false);
    const [config, setConfig] = useState({ urls: [] });
    const [newUrl, setNewUrl] = useState('');
    const [savingConfig, setSavingConfig] = useState(false);

    // Search State
    const [searchTerm, setSearchTerm] = useState('');
    const [selectedUrl, setSelectedUrl] = useState('');

    // Visibility State
    const [visibleCommodities, setVisibleCommodities] = useState({
        gold: true,
        silver: true,
        copper: true,
        oil: true
    });
    const [showVisibilityMenu, setShowVisibilityMenu] = useState(false);
    const visibilityMenuRef = useRef(null);

    // Exchange rate (Mock)
    const EXCHANGE_RATE = 7.2;

    // Connect charts for synchronized hover
    useEffect(() => {
        // Small delay to ensure charts are mounted
        const timer = setTimeout(() => {
            echarts.connect('commodities');
        }, 500);
        return () => clearTimeout(timer);
    }, [visibleCommodities, timeRange]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const response = await api.getData();
                setData(response.data.data || []);
                setLoading(false);
            } catch (err) {
                console.error("Error fetching data:", err);
                setError("Failed to load data");
                setLoading(false);
            }
        };

        fetchData();
        const interval = setInterval(fetchData, 30000);
        return () => clearInterval(interval);
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

    // Close visibility menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (visibilityMenuRef.current && !visibilityMenuRef.current.contains(event.target)) {
                setShowVisibilityMenu(false);
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

    const toggleVisibility = (id) => {
        setVisibleCommodities(prev => ({
            ...prev,
            [id]: !prev[id]
        }));
    };

    // Mock Historical Data Generator
    const generateHistory = (basePrice, points, volatility) => {
        let current = basePrice;
        return Array.from({ length: points }, (_, i) => {
            const change = (Math.random() - 0.5) * volatility;
            current += change;
            return {
                time: i,
                price: current,
                date: new Date(Date.now() - (points - i) * (timeRange === 'day' ? 3600000 : 86400000)).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            };
        });
    };

    const formatPrice = (price) => {
        if (!price) return '0.00';
        const val = parseFloat(price);
        if (currency === 'USD') {
            return (val / EXCHANGE_RATE).toFixed(2);
        }
        return val.toFixed(2);
    };

    const getCurrencySymbol = () => currency === 'USD' ? '$' : '¥';

    if (loading) return <div className="p-8">Loading data...</div>;
    if (error) return <div className="p-8 text-red-500">Error: {error}</div>;

    const commodities = [
        { id: 'gold', name: '黄金 (Gold)', basePrice: 450, color: '#ffc658', matchNames: ['Gold', '黄金'], unit: 'g' },
        { id: 'silver', name: '白银 (Silver)', basePrice: 30, color: '#a4a9ad', matchNames: ['Silver', '白银'], unit: 'kg' },
        { id: 'copper', name: '铜 (Copper)', basePrice: 68, color: '#8884d8', matchNames: ['Copper', '铜'], unit: 'ton' },
        { id: 'oil', name: '原油 (Oil)', basePrice: 560, color: '#82ca9d', matchNames: ['Oil', '原油', 'WTI', 'Brent', '布伦特', 'WTI原油'], unit: 'barrel' },
    ];

    // Filter data based on search term or visibility
    let displayItems = [];

    // Extract available URLs with statistics
    const urlStats = useMemo(() => {
        const stats = {};
        data.forEach(item => {
            if (item.url) {
                if (!stats[item.url]) {
                    stats[item.url] = {
                        url: item.url,
                        hostname: safeGetHostname(item.url),
                        count: 0,
                        items: []
                    };
                }
                stats[item.url].count++;
                stats[item.url].items.push(item.name || item.chinese_name);
            }
        });
        return Object.values(stats).sort((a, b) => b.count - a.count);
    }, [data]);

    const availableUrls = urlStats.map(s => s.url);

    if (searchTerm || selectedUrl) {
        // If searching or filtering by URL, show matching items
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
        }).map(item => ({
            id: item.name || item.chinese_name,
            name: item.chinese_name || item.name,
            basePrice: item.current_price || item.price,
            color: '#' + Math.floor(Math.random() * 16777215).toString(16), // Random color for search results
            isDynamic: true,
            dataItem: item
        }));
    } else {
        // Default view: show selected commodities
        displayItems = commodities.filter(c => visibleCommodities[c.id] || (c.id === 'silver' && visibleCommodities.silver === undefined)); // Default silver to visible if not set
    }

    return (
        <div className="dashboard-container" style={{ paddingBottom: '40px', position: 'relative' }}>
            <div className="header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '30px' }}>
                <div>
                    <h1 style={{ margin: 0, fontSize: '28px', fontWeight: '600' }}>市场概览</h1>
                    <p style={{ color: '#6b7280', marginTop: '5px' }}>实时大宗商品价格监控</p>
                </div>

                <div className="controls" style={{ display: 'flex', gap: '15px', alignItems: 'center' }}>

                    {/* Search Input */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#fff', border: '1px solid #e5e7eb', padding: '6px 12px', borderRadius: '8px', width: '200px' }}>
                        <Eye size={16} color="#9ca3af" />
                        <input
                            type="text"
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            placeholder="搜索商品/URL..."
                            style={{ border: 'none', outline: 'none', fontSize: '14px', color: '#374151', background: 'transparent', padding: 0, width: '100%' }}
                        />
                        {searchTerm && (
                            <button onClick={() => setSearchTerm('')} style={{ border: 'none', background: 'none', padding: 0, cursor: 'pointer', display: 'flex' }}>
                                <X size={14} color="#9ca3af" />
                            </button>
                        )}
                    </div>

                    {/* URL Filter - Enhanced with count display */}
                    {urlStats.length > 0 && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#fff', border: '1px solid #e5e7eb', padding: '6px 12px', borderRadius: '8px' }}>
                            <Globe size={16} color="#6b7280" />
                            <select
                                value={selectedUrl}
                                onChange={(e) => setSelectedUrl(e.target.value)}
                                style={{ border: 'none', outline: 'none', fontSize: '14px', color: '#374151', background: 'transparent', padding: 0, minWidth: '120px', maxWidth: '200px' }}
                            >
                                <option value="">全部来源 ({data.length})</option>
                                {urlStats.map((stat, idx) => (
                                    <option key={idx} value={stat.url}>
                                        {stat.hostname} ({stat.count})
                                    </option>
                                ))}
                            </select>
                            {selectedUrl && (
                                <button
                                    onClick={() => setSelectedUrl('')}
                                    style={{ border: 'none', background: 'none', padding: '2px', cursor: 'pointer', display: 'flex' }}
                                    title="清除筛选"
                                >
                                    <X size={14} color="#9ca3af" />
                                </button>
                            )}
                        </div>
                    )}

                    {/* Date Picker */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', background: '#fff', border: '1px solid #e5e7eb', padding: '6px 12px', borderRadius: '8px' }}>
                        <Calendar size={16} color="#6b7280" />
                        <input
                            type="date"
                            value={selectedDate}
                            onChange={(e) => setSelectedDate(e.target.value)}
                            style={{ border: 'none', outline: 'none', fontSize: '14px', color: '#374151', background: 'transparent', padding: 0, width: 'auto' }}
                        />
                    </div>

                    <div className="toggle-group" style={{ background: '#f3f4f6', padding: '4px', borderRadius: '8px', display: 'flex' }}>
                        <button
                            onClick={() => setTimeRange('day')}
                            style={{
                                padding: '6px 16px',
                                borderRadius: '6px',
                                border: 'none',
                                background: timeRange === 'day' ? '#fff' : 'transparent',
                                boxShadow: timeRange === 'day' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                                fontWeight: '500',
                                color: timeRange === 'day' ? '#111' : '#6b7280'
                            }}
                        >
                            24H
                        </button>
                        <button
                            onClick={() => setTimeRange('week')}
                            style={{
                                padding: '6px 16px',
                                borderRadius: '6px',
                                border: 'none',
                                background: timeRange === 'week' ? '#fff' : 'transparent',
                                boxShadow: timeRange === 'week' ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                                fontWeight: '500',
                                color: timeRange === 'week' ? '#111' : '#6b7280'
                            }}
                        >
                            7D
                        </button>
                    </div>

                    <button
                        onClick={() => setCurrency(c => c === 'CNY' ? 'USD' : 'CNY')}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            background: '#fff',
                            border: '1px solid #e5e7eb',
                            padding: '8px 16px',
                            borderRadius: '8px',
                            color: '#374151'
                        }}
                    >
                        <RefreshCw size={16} />
                        {currency}
                    </button>

                    {/* Visibility Toggle */}
                    <div style={{ position: 'relative' }} ref={visibilityMenuRef}>
                        <button
                            onClick={() => setShowVisibilityMenu(!showVisibilityMenu)}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                                background: '#fff',
                                border: '1px solid #e5e7eb',
                                padding: '8px 16px',
                                borderRadius: '8px',
                                color: '#374151',
                                cursor: 'pointer'
                            }}
                        >
                            <Eye size={16} />
                            显示
                        </button>
                        {showVisibilityMenu && (
                            <div style={{
                                position: 'absolute',
                                top: '100%',
                                right: 0,
                                marginTop: '8px',
                                background: '#fff',
                                borderRadius: '8px',
                                boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
                                border: '1px solid #e5e7eb',
                                padding: '8px',
                                zIndex: 50,
                                minWidth: '150px'
                            }}>
                                {commodities.map(comm => (
                                    <div
                                        key={comm.id}
                                        onClick={() => toggleVisibility(comm.id)}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '8px',
                                            padding: '8px 12px',
                                            cursor: 'pointer',
                                            borderRadius: '6px',
                                            fontSize: '14px',
                                            color: '#374151',
                                            background: visibleCommodities[comm.id] ? '#f3f4f6' : 'transparent'
                                        }}
                                    >
                                        <div style={{
                                            width: '16px',
                                            height: '16px',
                                            border: '1px solid #d1d5db',
                                            borderRadius: '4px',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            background: visibleCommodities[comm.id] ? '#0284c7' : '#fff',
                                            borderColor: visibleCommodities[comm.id] ? '#0284c7' : '#d1d5db'
                                        }}>
                                            {visibleCommodities[comm.id] && <Check size={12} color="#fff" />}
                                        </div>
                                        {comm.name}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>

                    <button
                        onClick={() => setShowSettings(true)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            background: '#fff',
                            border: '1px solid #e5e7eb',
                            padding: '8px 16px',
                            borderRadius: '8px',
                            color: '#374151'
                        }}
                    >
                        <Settings size={16} />
                        设置
                    </button>
                </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '3fr 1fr', gap: '20px' }}>
                <div className="main-content">
                    {/* Summary Cards - Enhanced with URL display */}
                    <div className="grid-cards" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px', marginBottom: '30px' }}>
                        {data.slice(0, 4).map((item, index) => {
                            const price = item.price || item.current_price || item.last_price || 0;
                            const change = item.change || item.change_percent || 0;
                            const isUp = change >= 0;
                            const hostname = safeGetHostname(item.url);

                            return (
                                <div key={index} style={{ background: '#fff', padding: '24px', borderRadius: '16px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                            <span style={{ color: '#6b7280', fontSize: '14px', fontWeight: '500' }}>
                                                {item.name || item.currency_pair || item.chinese_name || 'Unknown'}
                                            </span>
                                            {/* URL Source Display */}
                                            {item.url && (
                                                <a
                                                    href={item.url}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    style={{
                                                        display: 'inline-flex',
                                                        alignItems: 'center',
                                                        gap: '3px',
                                                        fontSize: '11px',
                                                        color: '#9ca3af',
                                                        textDecoration: 'none',
                                                        maxWidth: '120px',
                                                        overflow: 'hidden',
                                                        textOverflow: 'ellipsis',
                                                        whiteSpace: 'nowrap'
                                                    }}
                                                    title={item.url}
                                                >
                                                    <ExternalLink size={10} />
                                                    {hostname}
                                                </a>
                                            )}
                                        </div>
                                        <span style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            fontSize: '12px',
                                            fontWeight: '600',
                                            color: isUp ? '#10b981' : '#ef4444',
                                            background: isUp ? '#d1fae5' : '#fee2e2',
                                            padding: '2px 8px',
                                            borderRadius: '999px',
                                            height: 'fit-content'
                                        }}>
                                            {isUp ? <ArrowUp size={12} style={{ marginRight: '2px' }} /> : <ArrowDown size={12} style={{ marginRight: '2px' }} />}
                                            {Math.abs(change)}%
                                        </span>
                                    </div>
                                    <div style={{ fontSize: '32px', fontWeight: '700', color: '#111827' }}>
                                        {getCurrencySymbol()}{formatPrice(price)}
                                        <span style={{ fontSize: '16px', color: '#6b7280', marginLeft: '4px', fontWeight: '500' }}>
                                            {item.unit ? `/${item.unit}` : ''}
                                        </span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    <div className="charts-section" style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(2, 1fr)',
                        gap: '20px',
                        alignItems: 'start'
                    }}>
                        {displayItems.map((comm, index) => {
                            let realItem = comm.dataItem;

                            if (!realItem) {
                                // Find data for predefined commodities
                                realItem = data.find(d => {
                                    if (comm.matchNames) {
                                        return comm.matchNames.some(name =>
                                            (d.name && d.name.includes(name)) ||
                                            (d.chinese_name && d.chinese_name.includes(name))
                                        );
                                    }
                                    return (d.name && d.name.includes(comm.name)) || (d.chinese_name && d.chinese_name.includes(comm.name.split(' ')[0]));
                                });
                            }

                            const currentPrice = realItem ? (realItem.price || realItem.current_price) : comm.basePrice;
                            const unit = (realItem && realItem.unit) ? realItem.unit : comm.unit;
                            const historyData = generateHistory(parseFloat(currentPrice || 0), timeRange === 'day' ? 24 : 7, parseFloat(currentPrice || 100) * 0.02);

                            // Check if this is the last item and the total count is odd
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
                                />
                            );
                        })}
                    </div>
                </div>

                <div className="sidebar-content">
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
                            <h2 style={{ margin: 0, fontSize: '20px', fontWeight: '600' }}>配置设置</h2>
                            <button onClick={() => setShowSettings(false)} style={{ background: 'none', border: 'none', padding: '4px', cursor: 'pointer' }}>
                                <X size={24} color="#6b7280" />
                            </button>
                        </div>

                        <div style={{ padding: '20px', overflowY: 'auto' }}>
                            <h3 style={{ fontSize: '14px', fontWeight: '600', color: '#374151', marginBottom: '10px' }}>爬取目标 URL</h3>

                            <div className="url-list" style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '20px' }}>
                                {(config.target_urls || []).map((url, index) => (
                                    <div key={index} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '10px', background: '#f9f9f9', borderRadius: '8px', border: '1px solid #f3f4f6' }}>
                                        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', fontSize: '14px', color: '#4b5563' }}>{url}</span>
                                        <button onClick={() => handleDeleteUrl(index)} style={{ padding: '6px', color: '#ef4444', background: 'none', border: 'none', cursor: 'pointer' }}>
                                            <Trash2 size={16} />
                                        </button>
                                    </div>
                                ))}
                                {(!config.target_urls || config.target_urls.length === 0) && (
                                    <p style={{ color: '#9ca3af', fontSize: '14px', textAlign: 'center', padding: '20px' }}>暂无配置的 URL</p>
                                )}
                            </div>

                            <div className="add-url" style={{ display: 'flex', gap: '10px' }}>
                                <input
                                    type="text"
                                    value={newUrl}
                                    onChange={(e) => setNewUrl(e.target.value)}
                                    placeholder="输入新的 URL..."
                                    style={{ flex: 1, padding: '8px 12px', borderRadius: '8px', border: '1px solid #d1d5db', fontSize: '14px' }}
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
                                        fontSize: '14px',
                                        fontWeight: '500',
                                        cursor: 'pointer'
                                    }}
                                >
                                    <Plus size={16} /> 添加
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
                                    fontSize: '14px',
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
                                    background: '#0284c7',
                                    color: '#fff',
                                    fontSize: '14px',
                                    fontWeight: '500',
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px'
                                }}
                            >
                                <Save size={16} /> {savingConfig ? '保存中...' : '保存配置'}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Dashboard;
