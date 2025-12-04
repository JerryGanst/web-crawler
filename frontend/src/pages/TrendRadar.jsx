import React, { useEffect, useState, useRef } from 'react';
import { RefreshCw, Send, TrendingUp, DollarSign, Newspaper, Cpu, Users, ExternalLink, Filter, Link2 } from 'lucide-react';
import * as echarts from 'echarts';
import SupplyChainPanel from '../components/SupplyChainPanel';
import api from '../services/api';

// API 配置 - 连接到 TrendRadar 后端
const TRENDRADAR_API = 'http://localhost:8000';

const TrendRadar = () => {
    const [categories, setCategories] = useState([
        { id: 'finance', name: '财经' },
        { id: 'news', name: '新闻' },
        { id: 'social', name: '社交' },
        { id: 'tech', name: '科技' }
    ]);
    const [selectedCategory, setSelectedCategory] = useState('finance');
    const [newsData, setNewsData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [pushing, setPushing] = useState(false);
    const [stats, setStats] = useState({ total: 0, sources: {} });
    const chartRef = useRef(null);
    const chartInstance = useRef(null);
    
    // 防止 StrictMode 双重请求
    const hasFetchedCategories = useRef(false);

    // 分类图标映射
    const categoryIcons = {
        finance: <DollarSign size={18} />,
        news: <Newspaper size={18} />,
        social: <Users size={18} />,
        tech: <Cpu size={18} />,
        supply_chain: <Link2 size={18} />
    };

    // 分类颜色
    const categoryColors = {
        finance: '#3b82f6',
        news: '#10b981',
        social: '#f59e0b',
        tech: '#8b5cf6',
        supply_chain: '#ec4899'
    };

    // 默认分类（后备）
    const defaultCategories = [
        { id: 'finance', name: '财经' },
        { id: 'news', name: '新闻' },
        { id: 'social', name: '社交' },
        { id: 'tech', name: '科技' },
        { id: 'supply_chain', name: '上下游供应链' }
    ];

    // 供应链分类（固定添加）
    const supplyChainCategory = { id: 'supply_chain', name: '上下游供应链' };

    // 加载分类（带防重复保护）
    useEffect(() => {
        if (hasFetchedCategories.current) return;
        hasFetchedCategories.current = true;

        const fetchCategories = async () => {
            try {
                // 使用带缓存的 API 方法
                const response = await api.getCategories();
                const data = response.data || response;
                const apiCategories = data.categories || defaultCategories.slice(0, 4);
                // 确保供应链分类始终存在
                const hasSupplyChain = apiCategories.some(c => c.id === 'supply_chain');
                setCategories(hasSupplyChain ? apiCategories : [...apiCategories, supplyChainCategory]);
            } catch (e) {
                console.error('加载分类失败:', e);
                setCategories(defaultCategories);
            }
        };
        fetchCategories();
    }, []);

    // 加载新闻数据
    const loadNews = async (category, forceRefresh = false) => {
        setLoading(true);
        try {
            // forceRefresh=true 时强制从后端爬取最新数据
            const response = await api.getNews(category, true, forceRefresh);
            const data = response.data || response;
            
            // 如果缓存为空且不是强制刷新，自动触发一次爬取
            if (!data.data?.length && !forceRefresh) {
                console.log('缓存为空，自动爬取...');
                return loadNews(category, true);
            }
            
            setNewsData(data.data || []);
            setStats({ total: data.total, sources: data.sources || {} });
            updateChart(data.sources || {});
        } catch (e) {
            console.error('加载新闻失败:', e);
        } finally {
            setLoading(false);
        }
    };

    // 切换分类时加载数据（使用缓存）
    useEffect(() => {
        if (selectedCategory) {
            loadNews(selectedCategory);
        }
    }, [selectedCategory]);

    // 更新图表
    const updateChart = (sources) => {
        if (!chartRef.current) return;

        if (!chartInstance.current) {
            chartInstance.current = echarts.init(chartRef.current);
        }

        const pieData = Object.entries(sources).map(([name, count]) => ({
            name,
            value: count
        })).sort((a, b) => b.value - a.value);

        const option = {
            tooltip: {
                trigger: 'item',
                formatter: '{b}: {c} ({d}%)'
            },
            legend: {
                type: 'scroll',
                orient: 'vertical',
                right: 10,
                top: 20,
                bottom: 20,
                textStyle: { fontSize: 12 }
            },
            series: [
                {
                    name: '数据来源',
                    type: 'pie',
                    radius: ['40%', '70%'],
                    center: ['35%', '50%'],
                    avoidLabelOverlap: false,
                    itemStyle: {
                        borderRadius: 8,
                        borderColor: '#fff',
                        borderWidth: 2
                    },
                    label: {
                        show: false,
                        position: 'center'
                    },
                    emphasis: {
                        label: {
                            show: true,
                            fontSize: 18,
                            fontWeight: 'bold'
                        }
                    },
                    labelLine: { show: false },
                    data: pieData
                }
            ]
        };

        chartInstance.current.setOption(option);
    };

    // 触发爬取并推送
    const handleCrawlAndPush = async () => {
        setPushing(true);
        try {
            const res = await fetch(`${TRENDRADAR_API}/api/crawl`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category: selectedCategory, include_custom: true })
            });
            const data = await res.json();
            alert(`✅ ${data.message}`);
            // 强制刷新
            loadNews(selectedCategory, true);
        } catch (e) {
            alert('爬取失败: ' + e.message);
        } finally {
            setPushing(false);
        }
    };

    // 响应式图表
    useEffect(() => {
        const handleResize = () => {
            chartInstance.current?.resize();
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    return (
        <div style={{ padding: '30px', background: '#f8fafc', minHeight: '100vh' }}>
            {/* 头部 */}
            <div style={{ marginBottom: '30px' }}>
                <h1 style={{ fontSize: '28px', fontWeight: '700', color: '#1e293b', margin: 0, display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <TrendingUp size={32} color="#3b82f6" />
                    热点雷达
                </h1>
                <p style={{ color: '#64748b', marginTop: '8px' }}>实时追踪财经、新闻、科技热点</p>
            </div>

            {/* 分类选择 */}
            <div style={{ display: 'flex', gap: '12px', marginBottom: '24px', flexWrap: 'wrap' }}>
                {categories.map(cat => (
                    <button
                        key={cat.id}
                        onClick={() => setSelectedCategory(cat.id)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            padding: '12px 24px',
                            borderRadius: '12px',
                            border: selectedCategory === cat.id ? 'none' : '1px solid #e2e8f0',
                            background: selectedCategory === cat.id ? categoryColors[cat.id] || '#3b82f6' : '#fff',
                            color: selectedCategory === cat.id ? '#fff' : '#64748b',
                            fontSize: '15px',
                            fontWeight: '600',
                            cursor: 'pointer',
                            transition: 'all 0.2s',
                            boxShadow: selectedCategory === cat.id ? '0 4px 12px rgba(59, 130, 246, 0.3)' : 'none'
                        }}
                    >
                        {categoryIcons[cat.id]}
                        {cat.name}
                    </button>
                ))}

                <button
                    onClick={handleCrawlAndPush}
                    disabled={pushing}
                    style={{
                        marginLeft: 'auto',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '12px 24px',
                        borderRadius: '12px',
                        border: 'none',
                        background: pushing ? '#94a3b8' : '#10b981',
                        color: '#fff',
                        fontSize: '15px',
                        fontWeight: '600',
                        cursor: pushing ? 'not-allowed' : 'pointer',
                        transition: 'all 0.2s'
                    }}
                >
                    {pushing ? <RefreshCw size={18} className="animate-spin" /> : <Send size={18} />}
                    {pushing ? '推送中...' : '爬取并推送'}
                </button>
            </div>

            {/* 主内容区 */}
            {selectedCategory === 'supply_chain' ? (
                /* 供应链模式：全宽显示 */
                <SupplyChainPanel />
            ) : (
                /* 普通模式：新闻列表 + 右侧统计 */
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 350px', gap: '24px' }}>
                    {/* 左侧：新闻列表 */}
                    <div style={{ background: '#fff', borderRadius: '16px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', overflow: 'hidden' }}>
                        <div style={{ padding: '20px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: '600', color: '#1e293b' }}>
                                {loading ? '加载中...' : `最新热点 (${stats.total})`}
                            </h2>
                            <button
                                onClick={() => loadNews(selectedCategory, true)}
                                disabled={loading}
                                style={{ background: 'none', border: 'none', cursor: loading ? 'not-allowed' : 'pointer', padding: '8px' }}
                                title="刷新数据"
                            >
                                <RefreshCw size={18} color={loading ? '#94a3b8' : '#64748b'} className={loading ? 'animate-spin' : ''} />
                            </button>
                        </div>

                        <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
                            {newsData.slice(0, 50).map((item, i) => (
                                <a
                                    key={i}
                                    href={item.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{
                                        display: 'flex',
                                        alignItems: 'flex-start',
                                        gap: '12px',
                                        padding: '16px 20px',
                                        borderBottom: '1px solid #f1f5f9',
                                        textDecoration: 'none',
                                        transition: 'background 0.2s'
                                    }}
                                    onMouseEnter={(e) => e.currentTarget.style.background = '#f8fafc'}
                                    onMouseLeave={(e) => e.currentTarget.style.background = '#fff'}
                                >
                                    <span style={{
                                        minWidth: '28px',
                                        height: '28px',
                                        borderRadius: '8px',
                                        background: i < 3 ? '#ef4444' : i < 10 ? '#f97316' : '#e2e8f0',
                                        color: i < 10 ? '#fff' : '#64748b',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        fontSize: '13px',
                                        fontWeight: '600'
                                    }}>
                                        {i + 1}
                                    </span>
                                    <div style={{ flex: 1 }}>
                                        <div style={{ color: '#1e293b', fontSize: '14px', lineHeight: '1.5', marginBottom: '6px' }}>
                                            {item.title}
                                        </div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#94a3b8' }}>
                                            <span style={{
                                                background: '#f1f5f9',
                                                padding: '2px 8px',
                                                borderRadius: '4px'
                                            }}>
                                                {item.platform_name || item.platform}
                                            </span>
                                            {item.source === 'custom' && (
                                                <span style={{
                                                    background: '#dbeafe',
                                                    color: '#3b82f6',
                                                    padding: '2px 8px',
                                                    borderRadius: '4px'
                                                }}>
                                                    自定义
                                                </span>
                                            )}
                                            {item.url && <ExternalLink size={12} />}
                                        </div>
                                    </div>
                                </a>
                            ))}
                            {newsData.length === 0 && !loading && (
                                <div style={{ padding: '60px 20px', textAlign: 'center', color: '#94a3b8' }}>
                                    暂无数据，正在自动加载...
                                </div>
                            )}
                        </div>
                    </div>

                    {/* 右侧：统计图表 */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', maxHeight: 'calc(100vh - 200px)', overflowY: 'auto' }}>

                    {/* 数据来源饼图 */}
                    <div style={{ background: '#fff', borderRadius: '16px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '20px' }}>
                        <h3 style={{ margin: '0 0 16px 0', fontSize: '16px', fontWeight: '600', color: '#1e293b' }}>
                            数据来源分布
                        </h3>
                        <div ref={chartRef} style={{ height: '280px' }} />
                    </div>

                    {/* 统计卡片 */}
                    <div style={{ background: '#fff', borderRadius: '16px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '20px' }}>
                        <h3 style={{ margin: '0 0 16px 0', fontSize: '16px', fontWeight: '600', color: '#1e293b' }}>
                            来源统计
                        </h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            {Object.entries(stats.sources).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([name, count]) => (
                                <div key={name} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                    <div style={{ flex: 1 }}>
                                        <div style={{ fontSize: '14px', color: '#1e293b', marginBottom: '4px' }}>{name}</div>
                                        <div style={{
                                            height: '6px',
                                            background: '#f1f5f9',
                                            borderRadius: '3px',
                                            overflow: 'hidden'
                                        }}>
                                            <div style={{
                                                height: '100%',
                                                width: `${(count / stats.total) * 100}%`,
                                                background: categoryColors[selectedCategory] || '#3b82f6',
                                                borderRadius: '3px',
                                                transition: 'width 0.3s'
                                            }} />
                                        </div>
                                    </div>
                                    <span style={{ fontSize: '14px', fontWeight: '600', color: '#64748b', minWidth: '40px', textAlign: 'right' }}>
                                        {count}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>

                        {/* 缓存状态 */}
                        <div style={{ background: '#fff', borderRadius: '16px', boxShadow: '0 1px 3px rgba(0,0,0,0.1)', padding: '20px' }}>
                            <h3 style={{ margin: '0 0 12px 0', fontSize: '16px', fontWeight: '600', color: '#1e293b' }}>
                                数据状态
                            </h3>
                            <p style={{ margin: 0, fontSize: '14px', color: '#64748b' }}>
                                数据每 3 分钟自动缓存，点击顶部"爬取并推送"可刷新数据并推送
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default TrendRadar;
