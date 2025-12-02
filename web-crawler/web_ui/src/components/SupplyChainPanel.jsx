import React, { useState, useEffect } from 'react';
import { 
    Building2, 
    Swords, 
    ExternalLink,
    TrendingUp,
    Factory,
    Truck,
    ChevronDown,
    ChevronUp,
    Newspaper,
    Loader2,
    FileText,
    Sparkles,
    X,
    Copy,
    Check,
    RefreshCw,
    Send
} from 'lucide-react';

// API 配置
const TRENDRADAR_API = 'http://localhost:8000';

// 增强版 Markdown 渲染器（支持表格、代码块、图表数据）
const renderMarkdown = (text) => {
    if (!text) return '';
    
    let html = text;
    
    // 1. 处理代码块（JSON等）- 先处理避免被其他规则干扰
    html = html.replace(/```json\n?([\s\S]*?)```/g, (match, code) => {
        return `<pre style="background:#1e293b;color:#e2e8f0;padding:16px;border-radius:8px;overflow-x:auto;font-size:13px;margin:16px 0;font-family:monospace"><code>${code.trim()}</code></pre>`;
    });
    html = html.replace(/```\n?([\s\S]*?)```/g, (match, code) => {
        return `<pre style="background:#f1f5f9;color:#334155;padding:16px;border-radius:8px;overflow-x:auto;font-size:13px;margin:16px 0;font-family:monospace"><code>${code.trim()}</code></pre>`;
    });
    
    // 2. 处理表格
    html = html.replace(/\n(\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|\n?)+)/g, (match, table) => {
        const rows = table.trim().split('\n');
        if (rows.length < 2) return match;
        
        let tableHtml = '<div style="overflow-x:auto;margin:16px 0"><table style="width:100%;border-collapse:collapse;font-size:14px">';
        
        rows.forEach((row, idx) => {
            // 跳过分隔行
            if (row.match(/^\|[\s:-]+\|$/)) return;
            
            const cells = row.split('|').filter(c => c.trim() !== '');
            const tag = idx === 0 ? 'th' : 'td';
            const bgColor = idx === 0 ? '#f8fafc' : (idx % 2 === 0 ? '#fff' : '#fafafa');
            const fontWeight = idx === 0 ? '600' : '400';
            
            tableHtml += '<tr>';
            cells.forEach(cell => {
                const cellContent = cell.trim();
                // 处理单元格内的emoji和特殊标记
                let styledContent = cellContent
                    .replace(/🔴/g, '<span style="color:#ef4444">🔴</span>')
                    .replace(/🟡|⚠️/g, '<span style="color:#f59e0b">⚠️</span>')
                    .replace(/🟢|✅/g, '<span style="color:#22c55e">✅</span>')
                    .replace(/⭐/g, '<span style="color:#f59e0b">⭐</span>')
                    .replace(/🚀/g, '<span style="color:#3b82f6">🚀</span>');
                
                tableHtml += `<${tag} style="padding:10px 12px;border:1px solid #e2e8f0;background:${bgColor};font-weight:${fontWeight};text-align:left">${styledContent}</${tag}>`;
            });
            tableHtml += '</tr>';
        });
        
        tableHtml += '</table></div>';
        return tableHtml;
    });
    
    // 3. 处理标题
    html = html.replace(/^#### (.*$)/gim, '<h4 style="font-size:15px;font-weight:600;margin:14px 0 8px;color:#334155">$1</h4>');
    html = html.replace(/^### (.*$)/gim, '<h3 style="font-size:16px;font-weight:700;margin:18px 0 10px;color:#1e293b;border-bottom:1px solid #e2e8f0;padding-bottom:8px">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 style="font-size:18px;font-weight:700;margin:24px 0 12px;color:#0f172a;border-left:4px solid #3b82f6;padding-left:12px">$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 style="font-size:22px;font-weight:800;margin:28px 0 14px;color:#0f172a">$1</h1>');
    
    // 4. 处理加粗和斜体
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong style="font-weight:600;color:#1e293b">$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em style="font-style:italic">$1</em>');
    
    // 5. 处理列表
    html = html.replace(/^- (.*$)/gim, '<li style="margin:6px 0;padding-left:8px;list-style-type:disc;margin-left:20px">$1</li>');
    html = html.replace(/^\d+\. (.*$)/gim, '<li style="margin:6px 0;padding-left:8px;list-style-type:decimal;margin-left:20px">$1</li>');
    
    // 6. 处理分隔线
    html = html.replace(/^---$/gim, '<hr style="border:none;border-top:2px solid #e2e8f0;margin:24px 0"/>');
    
    // 7. 处理引用块
    html = html.replace(/^> (.*$)/gim, '<blockquote style="border-left:4px solid #3b82f6;padding:12px 16px;margin:16px 0;background:#f0f9ff;color:#1e40af;font-style:italic">$1</blockquote>');
    
    // 8. 处理行内代码
    html = html.replace(/`([^`]+)`/g, '<code style="background:#f1f5f9;padding:2px 6px;border-radius:4px;font-size:13px;color:#e11d48;font-family:monospace">$1</code>');
    
    // 9. 处理段落和换行
    html = html.replace(/\n\n/g, '</p><p style="margin:14px 0;line-height:1.8;color:#374151">');
    html = html.replace(/\n/g, '<br/>');
    
    // 10. 包装段落
    html = '<p style="margin:14px 0;line-height:1.8;color:#374151">' + html + '</p>';
    
    return html;
};

// 立讯精密产业链数据
const LUXSHARE_DATA = {
    company: {
        name: '立讯精密',
        code: '002475.SZ',
        exchange: '深交所',
        mainBusiness: ['消费电子', '汽车电子', '通信及数据中心'],
        topCustomer: '苹果（占比约75%）',
        products: ['iPhone代工', 'AirPods', 'Apple Watch', 'Vision Pro']
    },
    competitors: [
        { name: '歌尔股份', code: '002241.SZ', business: '声学元件、VR/AR代工、AirPods', compete: 'TWS耳机、声学模组、VR头显', hot: true },
        { name: '蓝思科技', code: '300433.SZ', business: '玻璃盖板、结构件', compete: '手机/穿戴结构件、汽车玻璃', hot: false },
        { name: '工业富联', code: '601138.SH', business: 'iPhone整机组装、AI服务器', compete: 'iPhone代工、服务器', hot: true },
        { name: '鹏鼎控股', code: '002938.SZ', business: 'FPC柔性电路板', compete: 'PCB/FPC供应', hot: false },
        { name: '东山精密', code: '002384.SZ', business: 'PCB、精密制造', compete: '电路板、精密组件', hot: false },
        { name: '领益智造', code: '002600.SZ', business: '精密结构件、模组', compete: '消费电子结构件', hot: false },
        { name: '瑞声科技', code: '02018.HK', business: '声学元件、光学元件', compete: '声学、马达', hot: true }
    ],
    upstream: [
        { name: '京东方A', code: '000725.SZ', supply: '显示面板、OLED屏幕', category: '显示' },
        { name: '舜宇光学', code: '02382.HK', supply: '光学镜头模组', category: '光学' },
        { name: '欣旺达', code: '300207.SZ', supply: '锂电池、电源管理', category: '电池' },
        { name: '德赛电池', code: '000049.SZ', supply: '电池模组', category: '电池' },
        { name: '信维通信', code: '300136.SZ', supply: '天线、无线充电模组', category: '无线' },
        { name: '速腾聚创', code: '02498.HK', supply: '激光雷达（汽车业务合作）', category: '汽车' },
        { name: '长盈精密', code: '300115.SZ', supply: '精密结构件、连接器', category: '连接器' }
    ],
    downstream: [
        { name: '苹果', code: 'AAPL', relation: 'iPhone、AirPods、Apple Watch、Vision Pro代工', icon: 'apple', primary: true },
        { name: '华为', code: '-', relation: '消费电子组件', icon: 'phone', primary: true },
        { name: 'Meta', code: 'META', relation: 'VR设备', icon: 'vr', primary: false },
        { name: '奇瑞汽车', code: '-', relation: '合资成立汽车公司（ODM整车）', icon: 'car', primary: true },
        { name: '各大车企', code: '-', relation: '汽车线束、连接器、智能座舱', icon: 'car', primary: false },
        { name: '通信运营商/AI智算中心', code: '-', relation: '数据中心产品', icon: 'server', primary: false }
    ]
};

// 获取股票链接
const getStockUrl = (code) => {
    if (!code || code === '-') return null;
    if (code.endsWith('.SZ')) {
        return `https://quote.eastmoney.com/${code.replace('.SZ', '')}.html`;
    } else if (code.endsWith('.SH')) {
        return `https://quote.eastmoney.com/${code.replace('.SH', '')}.html`;
    } else if (code.endsWith('.HK')) {
        return `https://finance.sina.com.cn/stock/hkstock/${code.replace('.HK', '')}/`;
    } else if (code === 'AAPL' || code === 'META') {
        return `https://finance.yahoo.com/quote/${code}`;
    }
    return null;
};

const SupplyChainPanel = () => {
    const [expandedSections, setExpandedSections] = useState({
        competitors: true,
        upstream: true,
        downstream: true
    });
    const [expandedNews, setExpandedNews] = useState({}); // 跟踪每个公司的新闻展开状态
    const [newsData, setNewsData] = useState([]);
    const [loadingNews, setLoadingNews] = useState(true);
    
    // 报告相关状态
    const [showReport, setShowReport] = useState(false);
    const [reportContent, setReportContent] = useState('');
    const [generatingReport, setGeneratingReport] = useState(false);
    const [reportError, setReportError] = useState('');
    const [copied, setCopied] = useState(false);
    const [pushing, setPushing] = useState(false);
    const [pushSuccess, setPushSuccess] = useState(false);
    
    // 供应链实时新闻
    const [supplyChainNews, setSupplyChainNews] = useState([]);
    const [loadingSupplyNews, setLoadingSupplyNews] = useState(true);
    const [newsStatus, setNewsStatus] = useState(''); // cache 或 success

    // 获取财经新闻（用于公司卡片）
    useEffect(() => {
        const fetchNews = async () => {
            setLoadingNews(true);
            try {
                const res = await fetch(`${TRENDRADAR_API}/api/news/finance?include_custom=true`);
                const data = await res.json();
                setNewsData(data.data || []);
            } catch (e) {
                console.error('获取新闻失败:', e);
            } finally {
                setLoadingNews(false);
            }
        };
        fetchNews();
    }, []);
    
    // 获取供应链实时新闻
    useEffect(() => {
        const fetchSupplyChainNews = async () => {
            setLoadingSupplyNews(true);
            try {
                const res = await fetch(`${TRENDRADAR_API}/api/news/supply-chain`);
                const data = await res.json();
                setSupplyChainNews(data.data || []);
                setNewsStatus(data.status);
            } catch (e) {
                console.error('获取供应链新闻失败:', e);
            } finally {
                setLoadingSupplyNews(false);
            }
        };
        fetchSupplyChainNews();
        
        // 每5分钟自动刷新
        const interval = setInterval(fetchSupplyChainNews, 5 * 60 * 1000);
        return () => clearInterval(interval);
    }, []);

    // 生成分析报告 - 使用已缓存的供应链新闻
    const generateReport = async () => {
        setGeneratingReport(true);
        setReportError('');
        setShowReport(true);
        
        try {
            // 使用已缓存的供应链新闻
            const response = await fetch(`${TRENDRADAR_API}/api/generate-analysis`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    company_name: LUXSHARE_DATA.company.name,
                    competitors: LUXSHARE_DATA.competitors.map(c => c.name),
                    upstream: LUXSHARE_DATA.upstream.map(c => c.name),
                    downstream: LUXSHARE_DATA.downstream.map(c => c.name),
                    news: supplyChainNews  // 使用已缓存的新闻
                })
            });
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '生成报告失败');
            }
            
            const result = await response.json();
            setReportContent(result.report);
        } catch (e) {
            console.error('生成报告失败:', e);
            setReportError(e.message || '生成报告失败，请检查API配置');
        } finally {
            setGeneratingReport(false);
        }
    };

    // 复制报告
    const copyReport = () => {
        navigator.clipboard.writeText(reportContent);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    // 推送报告到企业微信
    const pushToWework = async () => {
        if (!reportContent) return;
        
        setPushing(true);
        setPushSuccess(false);
        try {
            const res = await fetch(`${TRENDRADAR_API}/api/push-report`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: `${LUXSHARE_DATA.company.name} 产业链分析报告`,
                    content: reportContent
                })
            });
            const data = await res.json();
            if (data.status === 'success') {
                setPushSuccess(true);
                setTimeout(() => setPushSuccess(false), 3000);
            } else {
                alert('推送失败: ' + (data.message || '未知错误'));
            }
        } catch (e) {
            alert('推送失败: ' + e.message);
        } finally {
            setPushing(false);
        }
    };

    // 根据公司名称筛选相关新闻
    const getRelatedNews = (companyName) => {
        if (!newsData.length) return [];
        // 匹配公司名称（支持简称）
        const keywords = [companyName];
        // 添加一些常见简称
        if (companyName === '京东方A') keywords.push('京东方', 'BOE');
        if (companyName === '歌尔股份') keywords.push('歌尔');
        if (companyName === '蓝思科技') keywords.push('蓝思');
        if (companyName === '工业富联') keywords.push('富联', '富士康');
        if (companyName === '立讯精密') keywords.push('立讯');
        if (companyName === '苹果') keywords.push('Apple', 'iPhone', 'AirPods');
        if (companyName === '华为') keywords.push('Huawei', 'HUAWEI');
        if (companyName === 'Meta') keywords.push('Facebook', 'Quest');
        
        return newsData.filter(news => 
            keywords.some(kw => news.title && news.title.includes(kw))
        ).slice(0, 5); // 最多显示5条
    };

    const toggleSection = (section) => {
        setExpandedSections(prev => ({
            ...prev,
            [section]: !prev[section]
        }));
    };

    const toggleNews = (companyName) => {
        setExpandedNews(prev => ({
            ...prev,
            [companyName]: !prev[companyName]
        }));
    };

    // 渲染公司卡片
    const renderCompanyCard = (item, type) => {
        const url = getStockUrl(item.code);
        
        return (
            <div
                key={item.name}
                style={{
                    background: '#fff',
                    borderRadius: '12px',
                    padding: '16px',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.08)',
                    border: '1px solid #e2e8f0',
                    transition: 'all 0.2s',
                    cursor: 'default'
                }}
                onMouseEnter={e => {
                    e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.1)';
                    e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={e => {
                    e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.08)';
                    e.currentTarget.style.transform = 'translateY(0)';
                }}
            >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '10px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontWeight: '600', fontSize: '15px', color: '#1e293b' }}>
                            {item.name}
                        </span>
                        {item.hot && (
                            <span style={{
                                background: '#fef2f2',
                                color: '#dc2626',
                                fontSize: '11px',
                                padding: '2px 8px',
                                borderRadius: '6px',
                                fontWeight: '500'
                            }}>
                                热门
                            </span>
                        )}
                        {item.primary && (
                            <span style={{
                                background: '#dbeafe',
                                color: '#2563eb',
                                fontSize: '11px',
                                padding: '2px 8px',
                                borderRadius: '6px',
                                fontWeight: '500'
                            }}>
                                核心
                            </span>
                        )}
                    </div>
                    {url ? (
                        <a
                            href={url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                fontSize: '12px',
                                color: '#3b82f6',
                                textDecoration: 'none',
                                padding: '4px 10px',
                                background: '#eff6ff',
                                borderRadius: '6px',
                                transition: 'all 0.2s'
                            }}
                            onClick={e => e.stopPropagation()}
                        >
                            {item.code}
                            <ExternalLink size={12} />
                        </a>
                    ) : item.code !== '-' && (
                        <span style={{
                            fontSize: '12px',
                            color: '#94a3b8',
                            padding: '4px 10px',
                            background: '#f1f5f9',
                            borderRadius: '6px'
                        }}>
                            {item.code}
                        </span>
                    )}
                </div>
                
                {type === 'competitor' && (
                    <>
                        <div style={{ fontSize: '13px', color: '#64748b', marginBottom: '6px' }}>
                            <strong>主营：</strong>{item.business}
                        </div>
                        <div style={{ fontSize: '13px', color: '#f59e0b' }}>
                            <strong>竞争领域：</strong>{item.compete}
                        </div>
                    </>
                )}
                {type === 'upstream' && (
                    <div style={{ fontSize: '13px', color: '#64748b' }}>
                        <span style={{ 
                            display: 'inline-block',
                            background: '#ecfdf5', 
                            color: '#059669',
                            padding: '2px 8px',
                            borderRadius: '4px',
                            marginRight: '8px',
                            fontSize: '11px',
                            fontWeight: '500'
                        }}>
                            {item.category}
                        </span>
                        {item.supply}
                    </div>
                )}
                {type === 'downstream' && (
                    <div style={{ fontSize: '13px', color: '#64748b' }}>
                        {item.relation}
                    </div>
                )}

                {/* 相关新闻区域 */}
                {(() => {
                    const relatedNews = getRelatedNews(item.name);
                    const hasNews = relatedNews.length > 0;
                    const isExpanded = expandedNews[item.name];
                    
                    return (
                        <div style={{ marginTop: '12px', borderTop: '1px solid #e2e8f0', paddingTop: '10px' }}>
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    toggleNews(item.name);
                                }}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                    width: '100%',
                                    padding: '6px 0',
                                    background: 'none',
                                    border: 'none',
                                    cursor: hasNews ? 'pointer' : 'default',
                                    fontSize: '12px',
                                    color: hasNews ? '#3b82f6' : '#94a3b8'
                                }}
                                disabled={!hasNews}
                            >
                                <Newspaper size={14} />
                                <span style={{ flex: 1, textAlign: 'left' }}>
                                    {loadingNews ? '加载中...' : hasNews ? `相关资讯 (${relatedNews.length})` : '暂无相关资讯'}
                                </span>
                                {hasNews && (isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />)}
                            </button>
                            
                            {isExpanded && hasNews && (
                                <div style={{ 
                                    marginTop: '8px', 
                                    display: 'flex', 
                                    flexDirection: 'column', 
                                    gap: '6px' 
                                }}>
                                    {relatedNews.map((news, idx) => (
                                        <a
                                            key={idx}
                                            href={news.url}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            style={{
                                                display: 'block',
                                                padding: '8px 10px',
                                                background: '#f8fafc',
                                                borderRadius: '6px',
                                                fontSize: '12px',
                                                color: '#334155',
                                                textDecoration: 'none',
                                                lineHeight: '1.4',
                                                transition: 'all 0.2s',
                                                borderLeft: '3px solid #3b82f6'
                                            }}
                                            onMouseEnter={e => e.currentTarget.style.background = '#e2e8f0'}
                                            onMouseLeave={e => e.currentTarget.style.background = '#f8fafc'}
                                            onClick={e => e.stopPropagation()}
                                        >
                                            <div style={{ 
                                                overflow: 'hidden', 
                                                textOverflow: 'ellipsis',
                                                display: '-webkit-box',
                                                WebkitLineClamp: 2,
                                                WebkitBoxOrient: 'vertical'
                                            }}>
                                                {news.title}
                                            </div>
                                            <div style={{ 
                                                fontSize: '10px', 
                                                color: '#94a3b8', 
                                                marginTop: '4px',
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '6px'
                                            }}>
                                                <span>{news.platform_name || news.platform}</span>
                                                <ExternalLink size={10} />
                                            </div>
                                        </a>
                                    ))}
                                </div>
                            )}
                        </div>
                    );
                })()}
            </div>
        );
    };

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* 顶部：立讯精密概览 */}
            <div style={{ 
                background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)', 
                borderRadius: '16px',
                padding: '24px',
                color: '#fff',
                boxShadow: '0 4px 20px rgba(59, 130, 246, 0.3)'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                        <div style={{
                            width: '56px',
                            height: '56px',
                            background: 'rgba(255,255,255,0.2)',
                            borderRadius: '14px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                        }}>
                            <Building2 size={28} />
                        </div>
                        <div>
                            <div style={{ fontWeight: '700', fontSize: '24px', marginBottom: '4px' }}>
                                {LUXSHARE_DATA.company.name}
                            </div>
                            <div style={{ fontSize: '14px', opacity: 0.9 }}>
                                {LUXSHARE_DATA.company.code} · {LUXSHARE_DATA.company.exchange}
                            </div>
                        </div>
                    </div>
                    <div style={{ display: 'flex', gap: '12px' }}>
                        <button
                            onClick={generateReport}
                            disabled={generatingReport}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                fontSize: '14px',
                                color: '#fff',
                                background: generatingReport ? 'rgba(255,255,255,0.1)' : 'linear-gradient(135deg, #f59e0b, #d97706)',
                                padding: '10px 20px',
                                borderRadius: '10px',
                                border: 'none',
                                cursor: generatingReport ? 'wait' : 'pointer',
                                transition: 'all 0.2s',
                                fontWeight: '600',
                                boxShadow: '0 2px 8px rgba(245, 158, 11, 0.3)'
                            }}
                        >
                            {generatingReport ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />}
                            {generatingReport ? '生成中...' : '生成分析报告'}
                        </button>
                        <a
                            href={getStockUrl(LUXSHARE_DATA.company.code)}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                fontSize: '14px',
                                color: '#fff',
                                background: 'rgba(255,255,255,0.2)',
                                padding: '10px 20px',
                                borderRadius: '10px',
                                textDecoration: 'none',
                                transition: 'all 0.2s'
                            }}
                        >
                            <TrendingUp size={18} />
                            查看行情
                        </a>
                    </div>
                </div>
                
                <div style={{ display: 'flex', gap: '40px', flexWrap: 'wrap' }}>
                    <div>
                        <div style={{ fontSize: '12px', opacity: 0.8, marginBottom: '8px' }}>主营业务</div>
                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                            {LUXSHARE_DATA.company.mainBusiness.map(biz => (
                                <span key={biz} style={{
                                    fontSize: '13px',
                                    background: 'rgba(255,255,255,0.2)',
                                    padding: '6px 14px',
                                    borderRadius: '8px'
                                }}>
                                    {biz}
                                </span>
                            ))}
                        </div>
                    </div>
                    <div>
                        <div style={{ fontSize: '12px', opacity: 0.8, marginBottom: '8px' }}>第一大客户</div>
                        <div style={{ fontSize: '16px', fontWeight: '600' }}>
                            🍎 {LUXSHARE_DATA.company.topCustomer}
                        </div>
                    </div>
                    <div>
                        <div style={{ fontSize: '12px', opacity: 0.8, marginBottom: '8px' }}>代工产品</div>
                        <div style={{ fontSize: '14px' }}>
                            {LUXSHARE_DATA.company.products.join(' · ')}
                        </div>
                    </div>
                </div>
            </div>

            {/* 实时供应链新闻 */}
            <div style={{ 
                background: '#fff', 
                borderRadius: '16px', 
                padding: '20px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                marginBottom: '20px'
            }}>
                <div style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'space-between',
                    marginBottom: '16px'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <div style={{
                            width: '32px',
                            height: '32px',
                            borderRadius: '8px',
                            background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                        }}>
                            <Newspaper size={16} color="#fff" />
                        </div>
                        <div>
                            <div style={{ fontWeight: '600', fontSize: '15px', color: '#1e293b' }}>
                                实时供应链动态
                            </div>
                            <div style={{ fontSize: '12px', color: '#64748b' }}>
                                {loadingSupplyNews ? '加载中...' : 
                                 newsStatus === 'cache' ? '缓存数据' : '实时抓取'} · {supplyChainNews.length} 条相关新闻
                            </div>
                        </div>
                    </div>
                    <button
                        onClick={() => {
                            setLoadingSupplyNews(true);
                            fetch(`${TRENDRADAR_API}/api/news/supply-chain`)
                                .then(res => res.json())
                                .then(data => {
                                    setSupplyChainNews(data.data || []);
                                    setNewsStatus(data.status);
                                })
                                .finally(() => setLoadingSupplyNews(false));
                        }}
                        disabled={loadingSupplyNews}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            fontSize: '13px',
                            color: '#3b82f6',
                            background: '#eff6ff',
                            padding: '8px 14px',
                            borderRadius: '8px',
                            border: 'none',
                            cursor: loadingSupplyNews ? 'wait' : 'pointer'
                        }}
                    >
                        <RefreshCw size={14} className={loadingSupplyNews ? 'animate-spin' : ''} />
                        刷新
                    </button>
                </div>
                
                {loadingSupplyNews ? (
                    <div style={{ textAlign: 'center', padding: '20px', color: '#64748b' }}>
                        <Loader2 size={24} className="animate-spin" style={{ margin: '0 auto 10px' }} />
                        正在抓取最新新闻...
                    </div>
                ) : supplyChainNews.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '20px', color: '#94a3b8' }}>
                        暂无相关新闻
                    </div>
                ) : (
                    <div style={{ 
                        display: 'grid', 
                        gridTemplateColumns: 'repeat(2, 1fr)', 
                        gap: '12px',
                        maxHeight: '300px',
                        overflowY: 'auto'
                    }}>
                        {supplyChainNews.map((news, idx) => (
                            <a
                                key={idx}
                                href={news.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{
                                    display: 'flex',
                                    alignItems: 'flex-start',
                                    gap: '10px',
                                    padding: '12px',
                                    background: '#f8fafc',
                                    borderRadius: '10px',
                                    textDecoration: 'none',
                                    transition: 'all 0.2s'
                                }}
                                onMouseEnter={e => e.currentTarget.style.background = '#f1f5f9'}
                                onMouseLeave={e => e.currentTarget.style.background = '#f8fafc'}
                            >
                                <span style={{
                                    fontSize: '12px',
                                    color: '#3b82f6',
                                    background: '#dbeafe',
                                    padding: '2px 8px',
                                    borderRadius: '4px',
                                    whiteSpace: 'nowrap'
                                }}>
                                    {news.source || '新闻'}
                                </span>
                                <span style={{ 
                                    fontSize: '13px', 
                                    color: '#334155',
                                    lineHeight: '1.5',
                                    flex: 1
                                }}>
                                    {news.title}
                                </span>
                                <ExternalLink size={14} color="#94a3b8" style={{ flexShrink: 0 }} />
                            </a>
                        ))}
                    </div>
                )}
            </div>

            {/* 三栏布局：竞争对手 | 上游 | 下游 */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
                {/* 竞争对手 */}
                <div style={{ 
                    background: '#fff', 
                    borderRadius: '16px', 
                    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                    overflow: 'hidden'
                }}>
                    <button
                        onClick={() => toggleSection('competitors')}
                        style={{
                            width: '100%',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '12px',
                            padding: '18px 20px',
                            background: '#fef2f2',
                            border: 'none',
                            cursor: 'pointer',
                            borderBottom: '1px solid #fecaca'
                        }}
                    >
                        <div style={{
                            width: '36px',
                            height: '36px',
                            borderRadius: '10px',
                            background: '#ef4444',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                        }}>
                            <Swords size={18} color="#fff" />
                        </div>
                        <div style={{ flex: 1, textAlign: 'left' }}>
                            <div style={{ fontWeight: '600', fontSize: '16px', color: '#1e293b' }}>
                                主要竞争对手
                            </div>
                            <div style={{ fontSize: '12px', color: '#64748b' }}>
                                果链企业竞争格局
                            </div>
                        </div>
                        <span style={{
                            background: '#ef4444',
                            color: '#fff',
                            fontSize: '12px',
                            padding: '4px 10px',
                            borderRadius: '10px',
                            fontWeight: '600'
                        }}>
                            {LUXSHARE_DATA.competitors.length}
                        </span>
                        {expandedSections.competitors ? <ChevronUp size={20} color="#64748b" /> : <ChevronDown size={20} color="#64748b" />}
                    </button>
                    {expandedSections.competitors && (
                        <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '400px', overflowY: 'auto' }}>
                            {LUXSHARE_DATA.competitors.map(item => renderCompanyCard(item, 'competitor'))}
                        </div>
                    )}
                </div>

                {/* 上游供应商 */}
                <div style={{ 
                    background: '#fff', 
                    borderRadius: '16px', 
                    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                    overflow: 'hidden'
                }}>
                    <button
                        onClick={() => toggleSection('upstream')}
                        style={{
                            width: '100%',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '12px',
                            padding: '18px 20px',
                            background: '#ecfdf5',
                            border: 'none',
                            cursor: 'pointer',
                            borderBottom: '1px solid #a7f3d0'
                        }}
                    >
                        <div style={{
                            width: '36px',
                            height: '36px',
                            borderRadius: '10px',
                            background: '#10b981',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                        }}>
                            <Factory size={18} color="#fff" />
                        </div>
                        <div style={{ flex: 1, textAlign: 'left' }}>
                            <div style={{ fontWeight: '600', fontSize: '16px', color: '#1e293b' }}>
                                上游供应商
                            </div>
                            <div style={{ fontSize: '12px', color: '#64748b' }}>
                                零部件及原材料
                            </div>
                        </div>
                        <span style={{
                            background: '#10b981',
                            color: '#fff',
                            fontSize: '12px',
                            padding: '4px 10px',
                            borderRadius: '10px',
                            fontWeight: '600'
                        }}>
                            {LUXSHARE_DATA.upstream.length}
                        </span>
                        {expandedSections.upstream ? <ChevronUp size={20} color="#64748b" /> : <ChevronDown size={20} color="#64748b" />}
                    </button>
                    {expandedSections.upstream && (
                        <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '400px', overflowY: 'auto' }}>
                            {LUXSHARE_DATA.upstream.map(item => renderCompanyCard(item, 'upstream'))}
                        </div>
                    )}
                </div>

                {/* 下游客户 */}
                <div style={{ 
                    background: '#fff', 
                    borderRadius: '16px', 
                    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                    overflow: 'hidden'
                }}>
                    <button
                        onClick={() => toggleSection('downstream')}
                        style={{
                            width: '100%',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '12px',
                            padding: '18px 20px',
                            background: '#fffbeb',
                            border: 'none',
                            cursor: 'pointer',
                            borderBottom: '1px solid #fde68a'
                        }}
                    >
                        <div style={{
                            width: '36px',
                            height: '36px',
                            borderRadius: '10px',
                            background: '#f59e0b',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                        }}>
                            <Truck size={18} color="#fff" />
                        </div>
                        <div style={{ flex: 1, textAlign: 'left' }}>
                            <div style={{ fontWeight: '600', fontSize: '16px', color: '#1e293b' }}>
                                下游客户
                            </div>
                            <div style={{ fontSize: '12px', color: '#64748b' }}>
                                终端客户与合作伙伴
                            </div>
                        </div>
                        <span style={{
                            background: '#f59e0b',
                            color: '#fff',
                            fontSize: '12px',
                            padding: '4px 10px',
                            borderRadius: '10px',
                            fontWeight: '600'
                        }}>
                            {LUXSHARE_DATA.downstream.length}
                        </span>
                        {expandedSections.downstream ? <ChevronUp size={20} color="#64748b" /> : <ChevronDown size={20} color="#64748b" />}
                    </button>
                    {expandedSections.downstream && (
                        <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '400px', overflowY: 'auto' }}>
                            {LUXSHARE_DATA.downstream.map(item => renderCompanyCard(item, 'downstream'))}
                        </div>
                    )}
                </div>
            </div>

            {/* 分析报告弹窗 */}
            {showReport && (
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
                    padding: '20px'
                }}>
                    <div style={{
                        background: '#fff',
                        borderRadius: '20px',
                        width: '100%',
                        maxWidth: '900px',
                        maxHeight: '85vh',
                        display: 'flex',
                        flexDirection: 'column',
                        boxShadow: '0 20px 60px rgba(0,0,0,0.3)'
                    }}>
                        {/* 弹窗头部 */}
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '20px 24px',
                            borderBottom: '1px solid #e2e8f0',
                            background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
                            borderRadius: '20px 20px 0 0',
                            color: '#fff'
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                <FileText size={24} />
                                <div>
                                    <div style={{ fontWeight: '700', fontSize: '18px' }}>
                                        {LUXSHARE_DATA.company.name} 产业链分析报告
                                    </div>
                                    <div style={{ fontSize: '12px', opacity: 0.9 }}>
                                        立讯技术专有新闻分析AI助手 · 基于实时数据生成
                                    </div>
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: '8px' }}>
                                {reportContent && (
                                    <button
                                        onClick={copyReport}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '6px',
                                            padding: '8px 16px',
                                            background: 'rgba(255,255,255,0.2)',
                                            border: 'none',
                                            borderRadius: '8px',
                                            color: '#fff',
                                            cursor: 'pointer',
                                            fontSize: '13px'
                                        }}
                                    >
                                        {copied ? <Check size={16} /> : <Copy size={16} />}
                                        {copied ? '已复制' : '复制'}
                                    </button>
                                )}
                                {reportContent && (
                                    <button
                                        onClick={pushToWework}
                                        disabled={pushing}
                                        style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '6px',
                                            padding: '8px 16px',
                                            background: pushSuccess ? 'rgba(34,197,94,0.8)' : 'rgba(255,255,255,0.2)',
                                            border: 'none',
                                            borderRadius: '8px',
                                            color: '#fff',
                                            cursor: pushing ? 'not-allowed' : 'pointer',
                                            fontSize: '13px',
                                            opacity: pushing ? 0.7 : 1
                                        }}
                                    >
                                        {pushing ? <Loader2 size={16} className="animate-spin" /> : 
                                         pushSuccess ? <Check size={16} /> : <Send size={16} />}
                                        {pushing ? '推送中...' : pushSuccess ? '已推送' : '推送企微'}
                                    </button>
                                )}
                                <button
                                    onClick={() => setShowReport(false)}
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        width: '36px',
                                        height: '36px',
                                        background: 'rgba(255,255,255,0.2)',
                                        border: 'none',
                                        borderRadius: '8px',
                                        color: '#fff',
                                        cursor: 'pointer'
                                    }}
                                >
                                    <X size={20} />
                                </button>
                            </div>
                        </div>

                        {/* 弹窗内容 */}
                        <div style={{
                            flex: 1,
                            overflowY: 'auto',
                            padding: '24px'
                        }}>
                            {generatingReport ? (
                                <div style={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    padding: '60px 20px',
                                    color: '#64748b'
                                }}>
                                    <Loader2 size={48} className="animate-spin" style={{ color: '#3b82f6', marginBottom: '20px' }} />
                                    <div style={{ fontSize: '18px', fontWeight: '600', marginBottom: '8px' }}>正在生成分析报告...</div>
                                    <div style={{ fontSize: '14px' }}>立讯技术专有新闻分析AI助手正在工作，请稍候...</div>
                                </div>
                            ) : reportError ? (
                                <div style={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    padding: '60px 20px',
                                    color: '#ef4444'
                                }}>
                                    <X size={48} style={{ marginBottom: '20px' }} />
                                    <div style={{ fontSize: '18px', fontWeight: '600', marginBottom: '8px' }}>生成失败</div>
                                    <div style={{ fontSize: '14px', textAlign: 'center', maxWidth: '400px' }}>{reportError}</div>
                                    <button
                                        onClick={generateReport}
                                        style={{
                                            marginTop: '20px',
                                            padding: '10px 24px',
                                            background: '#3b82f6',
                                            color: '#fff',
                                            border: 'none',
                                            borderRadius: '8px',
                                            cursor: 'pointer',
                                            fontSize: '14px',
                                            fontWeight: '600'
                                        }}
                                    >
                                        重新生成
                                    </button>
                                </div>
                            ) : (
                                <div 
                                    style={{
                                        fontSize: '14px',
                                        color: '#334155',
                                        lineHeight: '1.8'
                                    }}
                                    dangerouslySetInnerHTML={{ __html: renderMarkdown(reportContent) }}
                                />
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default SupplyChainPanel;
