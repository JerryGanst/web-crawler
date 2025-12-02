import React, { useState, useEffect } from 'react';
import { Newspaper, RefreshCw, TrendingUp, TrendingDown } from 'lucide-react';

const NewsFeed = () => {
    const [news, setNews] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchNews = async () => {
            try {
                // 使用大宗商品专用新闻接口
                const res = await fetch('http://localhost:8000/api/commodity-news');
                const data = await res.json();
                setNews((data.data || []).slice(0, 8));
            } catch (e) {
                console.error('加载市场快讯失败:', e);
            } finally {
                setLoading(false);
            }
        };
        fetchNews();
    }, []);

    // 判断新闻是涨还是跌
    const getTrend = (title) => {
        if (/涨|上涨|走高|突破|新高|飙升|大涨/.test(title)) return 'up';
        if (/跌|下跌|走低|跌破|新低|暴跌|大跌/.test(title)) return 'down';
        return null;
    };

    return (
        <div style={{ background: '#fff', padding: '24px', borderRadius: '16px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)', height: '100%' }}>
            <h3 style={{ margin: '0 0 15px 0', fontSize: '18px', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Newspaper size={20} color="#f59e0b" />
                大宗商品快讯
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {loading ? (
                    <div style={{ textAlign: 'center', padding: '40px', color: '#9ca3af' }}>
                        <RefreshCw size={24} style={{ animation: 'spin 1s linear infinite', margin: '0 auto 10px' }} />
                        <div>加载中...</div>
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
