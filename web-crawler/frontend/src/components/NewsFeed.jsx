import React, { useState, useEffect, useRef } from 'react';
import { Newspaper, RefreshCw, TrendingUp, TrendingDown, Clock } from 'lucide-react';
import api from '../services/api';

const NewsFeed = () => {
    const [news, setNews] = useState([]);
    const [loading, setLoading] = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [cacheInfo, setCacheInfo] = useState(null);
    const [message, setMessage] = useState(null);
    
    // 使用 ref 防止 StrictMode 双重请求
    const hasFetched = useRef(false);

    // 加载缓存数据（不触发爬取）
    const loadCachedData = async () => {
        try {
            setLoading(true);
            const response = await api.getCommodityNews(false);
            const data = response.data || response;
            setNews((data.data || []).slice(0, 8));
            setCacheInfo({
                cached: data.cached,
                ttl: data.cache_ttl,
                timestamp: data.timestamp
            });
            setMessage(data.message || null);
        } catch (e) {
            console.error('加载市场快讯失败:', e);
        } finally {
            setLoading(false);
        }
    };

    // 刷新数据（触发爬取）
    const handleRefresh = async () => {
        try {
            setRefreshing(true);
            setMessage(null);
            const response = await api.getCommodityNews(true);
            const data = response.data || response;
            setNews((data.data || []).slice(0, 8));
            setCacheInfo({
                cached: false,
                ttl: data.cache_ttl,
                timestamp: data.timestamp
            });
        } catch (e) {
            console.error('刷新市场快讯失败:', e);
        } finally {
            setRefreshing(false);
        }
    };

    useEffect(() => {
        if (hasFetched.current) return;
        hasFetched.current = true;
        loadCachedData();
    }, []);

    // 判断新闻是涨还是跌
    const getTrend = (title) => {
        if (/涨|上涨|走高|突破|新高|飙升|大涨/.test(title)) return 'up';
        if (/跌|下跌|走低|跌破|新低|暴跌|大跌/.test(title)) return 'down';
        return null;
    };

    return (
        <div style={{ background: '#fff', padding: '24px', borderRadius: '16px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)', height: '100%' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
                <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Newspaper size={20} color="#f59e0b" />
                    大宗商品快讯
                </h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {cacheInfo?.cached && cacheInfo?.ttl > 0 && (
                        <span style={{ fontSize: '11px', color: '#9ca3af', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Clock size={12} />
                            缓存 {Math.floor(cacheInfo.ttl / 60)}分钟
                        </span>
                    )}
                    <button
                        onClick={handleRefresh}
                        disabled={refreshing}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '6px 12px',
                            fontSize: '12px',
                            fontWeight: '500',
                            color: refreshing ? '#9ca3af' : '#f59e0b',
                            background: refreshing ? '#f3f4f6' : '#fef3c7',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: refreshing ? 'not-allowed' : 'pointer',
                            transition: 'all 0.2s'
                        }}
                    >
                        <RefreshCw size={14} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
                        {refreshing ? '刷新中...' : '刷新'}
                    </button>
                </div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {loading || refreshing ? (
                    <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
                        <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', margin: '0 auto 10px' }} />
                        <div>{refreshing ? '正在爬取最新数据...' : '加载中...'}</div>
                    </div>
                ) : message ? (
                    <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
                        <div style={{ marginBottom: '10px' }}>{message}</div>
                        <button
                            onClick={handleRefresh}
                            style={{
                                padding: '8px 16px',
                                fontSize: '13px',
                                color: '#fff',
                                background: '#f59e0b',
                                border: 'none',
                                borderRadius: '6px',
                                cursor: 'pointer'
                            }}
                        >
                            点击刷新
                        </button>
                    </div>
                ) : news.length > 0 ? (
                    news.map((item, idx) => {
                        const trend = getTrend(item.title);
                        return (
                            <a 
                                key={idx} 
                                href={item.url} 
                                target="_blank" 
                                rel="noopener noreferrer"
                                style={{ 
                                    display: 'flex',
                                    alignItems: 'flex-start',
                                    gap: '10px',
                                    padding: '10px',
                                    borderRadius: '8px',
                                    background: '#f9fafb',
                                    textDecoration: 'none',
                                    transition: 'background 0.2s'
                                }}
                                onMouseOver={e => e.currentTarget.style.background = '#f3f4f6'}
                                onMouseOut={e => e.currentTarget.style.background = '#f9fafb'}
                            >
                                {trend === 'up' && <TrendingUp size={16} color="#10b981" style={{ marginTop: '2px', flexShrink: 0 }} />}
                                {trend === 'down' && <TrendingDown size={16} color="#ef4444" style={{ marginTop: '2px', flexShrink: 0 }} />}
                                {!trend && <div style={{ width: '16px', flexShrink: 0 }} />}
                                <div style={{ flex: 1 }}>
                                    <div style={{ 
                                        fontSize: '13px', 
                                        fontWeight: '500', 
                                        color: '#374151', 
                                        lineHeight: '1.4',
                                        marginBottom: '4px'
                                    }}>
                                        {item.title}
                                    </div>
                                    <div style={{ fontSize: '11px', color: '#9ca3af' }}>
                                        {item.platform_name || item.platform}
                                    </div>
                                </div>
                            </a>
                        );
                    })
                ) : (
                    <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
                        暂无大宗商品相关新闻
                    </div>
                )}
            </div>
        </div>
    );
};

export default NewsFeed;
