import React, { useEffect, useState, useRef, useCallback, useMemo } from 'react';
import { RefreshCw, Send, TrendingUp, DollarSign, Newspaper, Cpu, Users, ExternalLink, Link2, Gem, Scale } from 'lucide-react';
import * as echarts from 'echarts/core';
import { PieChart } from 'echarts/charts';
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';
import SupplyChainPanel from '../components/SupplyChainPanel';
import api from '../services/api';

// 按需注册 ECharts 组件（减少包体积）
echarts.use([PieChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer]);

// API 配置
const TRENDRADAR_API = 'http://localhost:8000';

// 分类图标映射（静态配置）
const CATEGORY_CONFIG = {
    finance: { icon: DollarSign, color: '#3b82f6', name: '财经' },
    news: { icon: Newspaper, color: '#10b981', name: '新闻' },
    social: { icon: Users, color: '#f59e0b', name: '社交' },
    tech: { icon: Cpu, color: '#8b5cf6', name: '科技' },
    supply_chain: { icon: Link2, color: '#ec4899', name: '供应链分析' },
    commodity: { icon: Gem, color: '#f97316', name: '大宗商品' },
    tariff: { icon: Scale, color: '#dc2626', name: '关税政策' },
    plastics: { icon: Gem, color: '#10b981', name: '塑料' }  // 新增塑料分类
};

// 默认分类
const DEFAULT_CATEGORIES = [
    { id: 'finance', name: '财经' },
    { id: 'commodity', name: '大宗商品' },
    { id: 'plastics', name: '塑料' },  // 新增塑料分类
    { id: 'tariff', name: '关税政策' },
    { id: 'supply_chain', name: '供应链分析' }
];

// 骨架屏组件
const NewsSkeleton = () => (
    <div style={{ padding: '16px 20px', borderBottom: '1px solid #f1f5f9' }}>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
            <div style={{ width: '28px', height: '28px', borderRadius: '8px', background: '#e2e8f0', animation: 'pulse 1.5s infinite' }} />
            <div style={{ flex: 1 }}>
                <div style={{ height: '16px', background: '#e2e8f0', borderRadius: '4px', marginBottom: '8px', animation: 'pulse 1.5s infinite' }} />
                <div style={{ height: '12px', background: '#f1f5f9', borderRadius: '4px', width: '60%', animation: 'pulse 1.5s infinite' }} />
            </div>
        </div>
    </div>
);

const TrendRadar = () => {
    const [categories, setCategories] = useState(DEFAULT_CATEGORIES);
    const [selectedCategory, setSelectedCategory] = useState('finance');
    const [newsData, setNewsData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [pushing, setPushing] = useState(false);
    const [stats, setStats] = useState({ total: 0, sources: {} });
    const chartRef = useRef(null);
    const chartInstance = useRef(null);
    
    // 请求控制 refs
    const hasFetchedCategories = useRef(false);
    const currentRequestRef = useRef(null);  // 跟踪当前请求
    const isMountedRef = useRef(true);  // 跟踪组件挂载状态

    // 组件卸载时清理
    useEffect(() => {
        isMountedRef.current = true;
        return () => {
            isMountedRef.current = false;
            // 清理图表实例
            if (chartInstance.current) {
                chartInstance.current.dispose();
                chartInstance.current = null;
            }
        };
    }, []);

    // 加载分类（只执行一次）
    useEffect(() => {
        if (hasFetchedCategories.current) return;
        hasFetchedCategories.current = true;

        const fetchCategories = async () => {
            try {
                const response = await api.getCategories();
                const data = response.data || response;
                const apiCategories = data.categories || DEFAULT_CATEGORIES.slice(0, 4);
                
                // 确保供应链分类始终存在
                const hasSupplyChain = apiCategories.some(c => c.id === 'supply_chain');
                if (isMountedRef.current) {
                    setCategories(hasSupplyChain ? apiCategories : [...apiCategories, { id: 'supply_chain', name: '供应链分析' }]);
                }
            } catch (e) {
                console.error('加载分类失败:', e);
                if (isMountedRef.current) {
                    setCategories(DEFAULT_CATEGORIES);
                }
            }
        };
        fetchCategories();
    }, []);

    // 加载新闻数据（带取消逻辑）
    const loadNews = useCallback(async (category, forceRefresh = false) => {
        // 生成请求 ID
        const requestId = `${category}-${Date.now()}`;
        currentRequestRef.current = requestId;
        
        setLoading(true);
        
        try {
            const response = await api.getNews(category, true, forceRefresh);
            
            // 检查请求是否已过期（被新请求取代）
            if (currentRequestRef.current !== requestId) {
                console.log('[Request STALE] Ignoring response for:', category);
                return;
            }
            
            const data = response.data || response;
            
            // 如果缓存为空且不是强制刷新，自动触发一次刷新
            if (!data.data?.length && !forceRefresh) {
                console.log('缓存为空，自动爬取...');
                return loadNews(category, true);
            }
            
            if (isMountedRef.current) {
                setNewsData(data.data || []);
                setStats({ total: data.total || 0, sources: data.sources || {} });
                updateChart(data.sources || {});
            }
        } catch (e) {
            // 忽略取消的请求错误
            if (e.name === 'AbortError' || e.name === 'CanceledError') {
                return;
            }
            console.error('加载新闻失败:', e);
        } finally {
            // 只有当前请求才能取消 loading
            if (currentRequestRef.current === requestId && isMountedRef.current) {
                setLoading(false);
            }
        }
    }, []);

    // 切换分类时加载数据
    useEffect(() => {
        if (selectedCategory && selectedCategory !== 'supply_chain') {
            loadNews(selectedCategory);
        }
    }, [selectedCategory, loadNews]);

    // 更新图表（使用 useMemo 优化配置）
    const chartOptions = useMemo(() => ({
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
        series: [{
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
            label: { show: false, position: 'center' },
            emphasis: {
                label: {
                    show: true,
                    fontSize: 18,
                    fontWeight: 'bold'
                }
            },
            labelLine: { show: false },
            data: []
        }]
    }), []);

    const updateChart = useCallback((sources) => {
        if (!chartRef.current) return;

        if (!chartInstance.current) {
            chartInstance.current = echarts.init(chartRef.current);
        }

        // 处理空数据：显示空图表而不是保留旧数据
        const pieData = (!sources || Object.keys(sources).length === 0)
            ? []
            : Object.entries(sources)
                .map(([name, count]) => ({ name, value: count }))
                .sort((a, b) => b.value - a.value);
        
        chartInstance.current.setOption({
            ...chartOptions,
            series: [{
                ...chartOptions.series[0],
                data: pieData
            }]
        }, true);  // true = notMerge, ensures old data is cleared
    }, [chartOptions]);

    // 触发爬取并推送
    const handleCrawlAndPush = useCallback(async () => {
        setPushing(true);
        try {
            const res = await fetch(`${TRENDRADAR_API}/api/crawl`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category: selectedCategory, include_custom: true })
            });
            const data = await res.json();
            alert(`✅ ${data.message}`);
            loadNews(selectedCategory, true);
        } catch (e) {
            alert('爬取失败: ' + e.message);
        } finally {
            setPushing(false);
        }
    }, [selectedCategory, loadNews]);

    // 响应式图表
    useEffect(() => {
        const handleResize = () => {
            chartInstance.current?.resize();
        };
        window.addEventListener('resize', handleResize);
        return () => window.removeEventListener('resize', handleResize);
    }, []);

    // 当分类切换回非supply_chain时，确保图表正确初始化
    useEffect(() => {
        if (selectedCategory !== 'supply_chain' && chartRef.current && Object.keys(stats.sources).length > 0) {
            // 延迟初始化以确保DOM已渲染
            const timer = setTimeout(() => {
                if (chartRef.current) {
                    if (chartInstance.current) {
                        chartInstance.current.dispose();
                    }
                    chartInstance.current = echarts.init(chartRef.current);
                    updateChart(stats.sources);
                }
            }, 100);
            return () => clearTimeout(timer);
        }
    }, [selectedCategory, stats.sources, updateChart]);

    // 渲染分类按钮
    const renderCategoryButton = useCallback((cat) => {
        const config = CATEGORY_CONFIG[cat.id] || { icon: Newspaper, color: '#64748b' };
        const IconComponent = config.icon;
        const isSelected = selectedCategory === cat.id;
        
        return (
            <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '12px 24px',
                    borderRadius: '12px',
                    border: isSelected ? 'none' : '1px solid #e2e8f0',
                    background: isSelected ? config.color : '#fff',
                    color: isSelected ? '#fff' : '#64748b',
                    fontSize: '15px',
                    fontWeight: '600',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    boxShadow: isSelected ? `0 4px 12px ${config.color}4D` : 'none'
                }}
            >
                <IconComponent size={18} />
                {cat.name}
            </button>
        );
    }, [selectedCategory]);

    // 渲染新闻列表
    const renderNewsList = useMemo(() => {
        if (loading) {
            return Array(8).fill(0).map((_, i) => <NewsSkeleton key={i} />);
        }
        
        if (newsData.length === 0) {
            return (
                <div style={{ padding: '60px 20px', textAlign: 'center', color: '#94a3b8' }}>
                    暂无数据，请点击刷新按钮获取最新数据
                </div>
            );
        }
        
        return newsData.slice(0, 50).map((item, i) => (
            <a
                key={`${item.url || i}-${i}`}
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
                        <span style={{ background: '#f1f5f9', padding: '2px 8px', borderRadius: '4px' }}>
                            {item.platform_name || item.platform}
                        </span>
                        {item.source === 'custom' && (
                            <span style={{ background: '#dbeafe', color: '#3b82f6', padding: '2px 8px', borderRadius: '4px' }}>
                                自定义
                            </span>
                        )}
                        {item.url && <ExternalLink size={12} />}
                    </div>
                </div>
            </a>
        ));
    }, [newsData, loading]);

    return (
        <div style={{ padding: '30px', background: '#f8fafc', minHeight: '100vh' }}>
            {/* 添加骨架屏动画样式 */}
            <style>{`
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
            `}</style>
            
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
                {categories.map(renderCategoryButton)}

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
                <SupplyChainPanel />
            ) : (
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
                                <RefreshCw 
                                    size={18} 
                                    color={loading ? '#94a3b8' : '#64748b'} 
                                    style={{ animation: loading ? 'spin 1s linear infinite' : 'none' }} 
                                />
                            </button>
                        </div>

                        <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
                            {renderNewsList}
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
                                            <div style={{ height: '6px', background: '#f1f5f9', borderRadius: '3px', overflow: 'hidden' }}>
                                                <div style={{
                                                    height: '100%',
                                                    width: `${(count / stats.total) * 100}%`,
                                                    background: CATEGORY_CONFIG[selectedCategory]?.color || '#3b82f6',
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
                                数据缓存2分钟，点击刷新按钮获取最新数据
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default TrendRadar;
