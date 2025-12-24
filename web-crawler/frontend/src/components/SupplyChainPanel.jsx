import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
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
    Send,
    Package,
    Users,
    AlertTriangle
} from 'lucide-react';
import api, { API_BASE } from '../services/api';

// API 配置
const TRENDRADAR_API = API_BASE || '';

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

// 立讯技术产业链数据（根据分析报告需求重新规划）
const LUXSHARE_DATA = {
    company: {
        name: '立讯技术',
        code: '002475.SZ',
        exchange: '深交所',
        mainBusiness: ['消费电子', '汽车电子', '通信及数据中心'],
        topCustomer: '苹果（占比约75%）',
        products: ['连接器', '线材', '电源模组', 'AirPods', 'Apple Watch']
    },
    // 友商数据（按产品分类）
    competitors: {
        '光电': [
            { name: 'Credo', code: '-', business: '光电模块', hot: true },
            { name: '旭创', code: '002281.SZ', business: '光模块', hot: true },
            { name: '新易盛', code: '300502.SZ', business: '光模块', hot: true },
            { name: '天孚', code: '300394.SZ', business: '光器件', hot: false },
            { name: '光迅', code: '002281.SZ', business: '光通信', hot: false },
            { name: 'Finisha', code: '-', business: '光电组件', hot: false }
        ],
        '连接器/线束': [
            { name: '安费诺', code: 'APH', business: '连接器', hot: true },
            { name: '莫仕', code: '-', business: '连接器', hot: true },
            { name: 'TE', code: 'TEL', business: '连接器', hot: true },
            { name: '中航', code: '002179.SZ', business: '连接器', hot: false },
            { name: '得意', code: '-', business: '连接器', hot: false },
            { name: '意华', code: '002897.SZ', business: '连接器', hot: false },
            { name: '金星诺', code: '-', business: '线束', hot: false },
            { name: '华旗', code: '-', business: '线束', hot: false }
        ],
        '电源': [
            { name: '奥海', code: '002993.SZ', business: '电源适配器', hot: true },
            { name: '航嘉', code: '300508.SZ', business: '电源', hot: false },
            { name: '赛尔康', code: '-', business: '电源管理', hot: false },
            { name: '台达', code: '2308.TW', business: '电源', hot: true }
        ]
    },
    // 供应商数据（按物料品类分类）
    suppliers: {
        'IC': ['安费诺', 'Marvell', 'Broadcom', 'Cisco', 'Macom', 'Semtech', 'ADI', 'ST', 'TI', 'MPS'],
        'PCB': ['莫仕', '龙腾电路', '方正'],
        '连接器': ['TE', '中航', '安费诺', '莫仕'],
        '注塑件': ['Marvell', '深圳市德发新材料有限公司', '东莞市华赢电子塑胶有限公司'],
        '压铸件': ['Broadcom', '广玮'],
        '电阻': ['Cisco', '国巨', '华科', '风华'],
        '电容': ['Macom', '村田', '华旗'],
        '传感器': ['Semtech', '林积为', '翰百']
    },
    // 物料品类
    materialCategories: ['IC', 'PCB', '连接器', '注塑件', '压铸件', '电阻', '电容', '传感器'],
    // 客户数据
    customers: [
        { name: '苹果', code: 'AAPL', relation: 'iPhone、AirPods、Apple Watch、Vision Pro代工', primary: true },
        { name: '华为', code: '-', relation: '消费电子组件', primary: true },
        { name: 'Meta', code: 'META', relation: 'VR设备', primary: false },
        { name: '奇瑞汽车', code: '-', relation: '合资成立汽车公司（ODM整车）', primary: true },
        { name: '各大车企', code: '-', relation: '汽车线束、连接器、智能座舱', primary: false }
    ]
};

// 新闻分类Tab配置（5个分类）
const NEWS_TABS = [
    { id: 'competitors', name: '友商', icon: 'Swords', color: '#ef4444', bgColor: '#fef2f2' },
    { id: 'customers', name: '客户', icon: 'Users', color: '#f59e0b', bgColor: '#fffbeb' },
    { id: 'suppliers', name: '供应商', icon: 'Truck', color: '#3b82f6', bgColor: '#eff6ff' },
    { id: 'materials', name: '物料品类', icon: 'Package', color: '#10b981', bgColor: '#ecfdf5' },
    { id: 'tariff', name: '关税政策', icon: 'FileText', color: '#8b5cf6', bgColor: '#f5f3ff' }
];

// 新闻关键词配置（用于分类新闻）
const NEWS_KEYWORDS = {
    competitors: ['Credo', '旭创', '新易盛', '天孚', '光迅', '安费诺', '莫仕', 'TE', '中航', '得意', '意华', '金星诺', '华旗', '奥海', '航嘉', '赛尔康', '台达', '工业富联', '歌尔', '蓝思', '鹏鼎', '东山精密', '领益智造', '瑞声'],
    customers: ['苹果', 'Apple', 'iPhone', 'AirPods', '华为', 'Huawei', 'Meta', 'Quest', '奇瑞', '汽车', '车企', 'VR', '特斯拉', 'Tesla'],
    suppliers: ['Marvell', 'Broadcom', 'Cisco', 'Macom', 'Semtech', 'ADI', 'ST', 'TI', 'MPS', '龙腾', '方正', '德发', '华赢', '广玮', '国巨', '华科', '风华', '村田', '林积为', '翰百', '供应商', '采购'],
    materials: ['IC', 'PCB', '连接器', '注塑', '压铸', '电阻', '电容', '传感器', '芯片', '元器件', '半导体', '物料', '原材料', '铜', '铝', '塑料', 'PA66', 'PBT'],
    tariff: ['关税', '贸易战', '制裁', '出口管制', '进口', '加征', '关税政策', '贸易摩擦', '中美', '实体清单', '海关']
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

    // 新闻分类Tab状态
    const [activeNewsTab, setActiveNewsTab] = useState('competitors');

    // 防止 StrictMode 双重请求
    const hasFetchedNews = React.useRef(false);
    const hasFetchedSupplyNews = React.useRef(false);

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

    // 友商新闻统计
    const [partnerStats, setPartnerStats] = useState(null);
    const [loadingPartnerStats, setLoadingPartnerStats] = useState(true);
    const [expandedPartners, setExpandedPartners] = useState({});
    const hasFetchedPartnerStats = useRef(false);

    // 客户新闻统计
    const [customerStats, setCustomerStats] = useState(null);
    const [loadingCustomerStats, setLoadingCustomerStats] = useState(true);
    const hasFetchedCustomerStats = useRef(false);

    // 供应商新闻统计
    const [supplierStats, setSupplierStats] = useState(null);
    const [loadingSupplierStats, setLoadingSupplierStats] = useState(true);
    const hasFetchedSupplierStats = useRef(false);

    // 物料新闻统计
    const [materialStats, setMaterialStats] = useState(null);
    const [loadingMaterialStats, setLoadingMaterialStats] = useState(true);
    const hasFetchedMaterialStats = useRef(false);

    // 关税新闻统计
    const [tariffStats, setTariffStats] = useState(null);
    const [loadingTariffStats, setLoadingTariffStats] = useState(true);
    const hasFetchedTariffStats = useRef(false);

    // 根据关键词分类新闻
    const categorizeNews = (news, category) => {
        if (!news || !news.length) return [];
        const keywords = NEWS_KEYWORDS[category] || [];
        return news.filter(item =>
            keywords.some(kw => item.title && item.title.toLowerCase().includes(kw.toLowerCase()))
        );
    };

    // 获取当前Tab的新闻列表（用于内容显示）
    const getNewsForTab = (tabId) => {
        return categorizeNews(supplyChainNews, tabId);
    };

    // 获取当前Tab的新闻数量（使用各API统计数据）
    const getNewsCountForTab = (tabId) => {
        switch (tabId) {
            case 'competitors': return partnerStats?.total_news || 0;
            case 'customers': return customerStats?.total_news || 0;
            case 'suppliers': return supplierStats?.total_news || 0;
            case 'materials': return materialStats?.total_news || 0;
            case 'tariff': return tariffStats?.total_news || 0;
            default: return 0;
        }
    };

    // Tab图标映射
    const getTabIcon = (iconName) => {
        switch (iconName) {
            case 'Swords': return <Swords size={16} />;
            case 'Users': return <Users size={16} />;
            case 'Truck': return <Truck size={16} />;
            case 'Package': return <Package size={16} />;
            case 'FileText': return <AlertTriangle size={16} />;
            default: return <Newspaper size={16} />;
        }
    };

    // 获取财经新闻（用于公司卡片）
    useEffect(() => {
        if (hasFetchedNews.current) return;
        hasFetchedNews.current = true;

        const fetchNews = async () => {
            setLoadingNews(true);
            try {
                // 使用带缓存的 API 方法
                const response = await api.getNews('finance', true);
                const data = response.data || response;
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
        if (hasFetchedSupplyNews.current) return;
        hasFetchedSupplyNews.current = true;

        const fetchSupplyChainNews = async () => {
            setLoadingSupplyNews(true);
            try {
                // 使用带缓存的 API 方法
                const response = await api.getSupplyChainNews();
                const data = response.data || response;
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

    // 获取友商新闻统计
    useEffect(() => {
        if (hasFetchedPartnerStats.current) return;
        hasFetchedPartnerStats.current = true;

        const fetchPartnerStats = async () => {
            setLoadingPartnerStats(true);
            try {
                const response = await api.getPartnerNewsStats();
                const data = response.data || response;
                setPartnerStats(data);
            } catch (e) {
                console.error('获取友商新闻统计失败:', e);
            } finally {
                setLoadingPartnerStats(false);
            }
        };
        fetchPartnerStats();
    }, []);

    // 获取客户新闻统计
    useEffect(() => {
        if (hasFetchedCustomerStats.current) return;
        hasFetchedCustomerStats.current = true;
        const fetch = async () => {
            setLoadingCustomerStats(true);
            try {
                const response = await api.getCustomerNewsStats();
                setCustomerStats(response.data || response);
            } catch (e) {
                console.error('获取客户新闻统计失败:', e);
            } finally {
                setLoadingCustomerStats(false);
            }
        };
        fetch();
    }, []);

    // 获取供应商新闻统计
    useEffect(() => {
        if (hasFetchedSupplierStats.current) return;
        hasFetchedSupplierStats.current = true;
        const fetch = async () => {
            setLoadingSupplierStats(true);
            try {
                const response = await api.getSupplierNewsStats();
                setSupplierStats(response.data || response);
            } catch (e) {
                console.error('获取供应商新闻统计失败:', e);
            } finally {
                setLoadingSupplierStats(false);
            }
        };
        fetch();
    }, []);

    // 获取物料新闻统计
    useEffect(() => {
        if (hasFetchedMaterialStats.current) return;
        hasFetchedMaterialStats.current = true;
        const fetch = async () => {
            setLoadingMaterialStats(true);
            try {
                const response = await api.getMaterialNewsStats();
                setMaterialStats(response.data || response);
            } catch (e) {
                console.error('获取物料新闻统计失败:', e);
            } finally {
                setLoadingMaterialStats(false);
            }
        };
        fetch();
    }, []);

    // 获取关税新闻统计
    useEffect(() => {
        if (hasFetchedTariffStats.current) return;
        hasFetchedTariffStats.current = true;
        const fetch = async () => {
            setLoadingTariffStats(true);
            try {
                const response = await api.getTariffNewsStats();
                setTariffStats(response.data || response);
            } catch (e) {
                console.error('获取关税新闻统计失败:', e);
            } finally {
                setLoadingTariffStats(false);
            }
        };
        fetch();
    }, []);

    // 切换新闻展开状态（通用）
    const togglePartnerExpand = (partnerName) => {
        setExpandedPartners(prev => ({
            ...prev,
            [partnerName]: !prev[partnerName]
        }));
    };

    // 生成分析报告 - 使用已缓存的供应链新闻
    const generateReport = async () => {
        setGeneratingReport(true);
        setReportError('');
        setShowReport(true);

        try {
            // 获取所有友商名称（从对象中提取）
            const allCompetitors = Object.values(LUXSHARE_DATA.competitors).flat().map(c => c.name);
            // 获取所有供应商名称
            const allSuppliers = Object.values(LUXSHARE_DATA.suppliers).flat();
            // 获取所有客户名称
            const allCustomers = LUXSHARE_DATA.customers.map(c => c.name);

            // 使用已缓存的供应链新闻
            const response = await fetch(`${TRENDRADAR_API}/api/generate-analysis`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    company_name: LUXSHARE_DATA.company.name,
                    competitors: allCompetitors,
                    upstream: allSuppliers,
                    downstream: allCustomers,
                    news: supplyChainNews  // 使用已缓存的新闻
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '生成报告失败');
            }

            const result = await response.json();
            setReportContent(result.content || result.report);
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
            {/* 顶部：标题和操作按钮 */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '4px'
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{
                        width: '40px',
                        height: '40px',
                        background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
                        borderRadius: '10px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                    }}>
                        <Building2 size={20} color="#fff" />
                    </div>
                    <div>
                        <div style={{ fontWeight: '700', fontSize: '18px', color: '#1e293b' }}>
                            供应链分析
                        </div>
                        <div style={{ fontSize: '12px', color: '#64748b' }}>
                            立讯技术 · 友商/客户/物料/关税
                        </div>
                    </div>
                </div>
                <button
                    onClick={generateReport}
                    disabled={generatingReport}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        padding: '10px 18px',
                        background: generatingReport ? '#94a3b8' : 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
                        border: 'none',
                        borderRadius: '10px',
                        color: '#fff',
                        cursor: generatingReport ? 'not-allowed' : 'pointer',
                        fontSize: '14px',
                        fontWeight: '600',
                        transition: 'all 0.2s',
                        boxShadow: generatingReport ? 'none' : '0 2px 8px rgba(59, 130, 246, 0.3)'
                    }}
                >
                    {generatingReport ? (
                        <Loader2 size={16} className="animate-spin" />
                    ) : (
                        <Sparkles size={16} />
                    )}
                    {generatingReport ? '生成中...' : '生成分析报告'}
                </button>
            </div>

            {/* 供应链新闻 - 四分类Tab */}
            <div style={{
                background: '#fff',
                borderRadius: '16px',
                boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                overflow: 'hidden'
            }}>
                {/* 标题栏 */}
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
                            background: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                        }}>
                            <Newspaper size={16} color="#fff" />
                        </div>
                        <div>
                            <div style={{ fontWeight: '600', fontSize: '15px', color: '#1e293b' }}>
                                供应链分析新闻
                            </div>
                            <div style={{ fontSize: '12px', color: '#64748b' }}>
                                按友商、客户、物料品类、关税政策分类
                            </div>
                        </div>
                    </div>
                    <button
                        onClick={async () => {
                            setLoadingSupplyNews(true);
                            try {
                                const response = await api.getSupplyChainNews(true);
                                const data = response.data || response;
                                setSupplyChainNews(data.data || []);
                                setNewsStatus(data.status || 'success');
                            } catch (e) {
                                console.error('刷新供应链新闻失败:', e);
                            } finally {
                                setLoadingSupplyNews(false);
                            }
                        }}
                        disabled={loadingSupplyNews}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            fontSize: '13px',
                            color: loadingSupplyNews ? '#94a3b8' : '#3b82f6',
                            background: loadingSupplyNews ? '#f1f5f9' : '#eff6ff',
                            padding: '8px 14px',
                            borderRadius: '8px',
                            border: 'none',
                            cursor: loadingSupplyNews ? 'not-allowed' : 'pointer',
                            transition: 'all 0.2s'
                        }}
                    >
                        <RefreshCw size={14} style={{ animation: loadingSupplyNews ? 'spin 1s linear infinite' : 'none' }} />
                        {loadingSupplyNews ? '爬取中...' : '刷新数据'}
                    </button>
                </div>

                {/* Tab栏 */}
                <div style={{
                    display: 'flex',
                    borderBottom: '1px solid #e2e8f0',
                    background: '#f8fafc'
                }}>
                    {NEWS_TABS.map(tab => {
                        const newsCount = getNewsCountForTab(tab.id);
                        const isActive = activeNewsTab === tab.id;
                        return (
                            <button
                                key={tab.id}
                                onClick={() => setActiveNewsTab(tab.id)}
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
                                {getTabIcon(tab.icon)}
                                {tab.name}
                                <span style={{
                                    fontSize: '11px',
                                    background: isActive ? tab.color : '#e2e8f0',
                                    color: isActive ? '#fff' : '#64748b',
                                    padding: '2px 8px',
                                    borderRadius: '10px',
                                    fontWeight: '600'
                                }}>
                                    {newsCount}
                                </span>
                            </button>
                        );
                    })}
                </div>

                {/* 新闻内容区 */}
                <div style={{ padding: '16px 20px' }}>
                    {loadingSupplyNews ? (
                        <div style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
                            <Loader2 size={24} className="animate-spin" style={{ margin: '0 auto 10px' }} />
                            正在抓取最新新闻...
                        </div>
                    ) : (() => {
                        const currentNews = getNewsForTab(activeNewsTab);
                        const currentTab = NEWS_TABS.find(t => t.id === activeNewsTab);

                        // 友商Tab：按公司分组展示
                        if (activeNewsTab === 'competitors' && partnerStats?.stats) {
                            return (
                                <div style={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    gap: '12px',
                                    maxHeight: '400px',
                                    overflowY: 'auto'
                                }}>
                                    {Object.entries(partnerStats.stats).map(([category, partners]) => (
                                        <div key={category}>
                                            <div style={{
                                                fontSize: '12px',
                                                fontWeight: '600',
                                                color: '#64748b',
                                                marginBottom: '8px',
                                                padding: '4px 8px',
                                                background: '#fef2f2',
                                                borderRadius: '4px',
                                                display: 'inline-flex',
                                                alignItems: 'center',
                                                gap: '6px'
                                            }}>
                                                {category === '光电模块' && '💡'}
                                                {category === '连接器' && '🔌'}
                                                {category === '电源' && '⚡'}
                                                {category}
                                            </div>
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                                {Object.entries(partners).map(([name, data]) => {
                                                    const isExpanded = expandedPartners[name];
                                                    const hasNews = data.news_count > 0;
                                                    return (
                                                        <div key={name} style={{
                                                            background: hasNews ? '#fef2f2' : '#f8fafc',
                                                            borderRadius: '8px',
                                                            overflow: 'hidden',
                                                            border: hasNews ? '1px solid #fecaca' : '1px solid #e2e8f0'
                                                        }}>
                                                            <button
                                                                onClick={() => hasNews && togglePartnerExpand(name)}
                                                                style={{
                                                                    width: '100%',
                                                                    display: 'flex',
                                                                    alignItems: 'center',
                                                                    justifyContent: 'space-between',
                                                                    padding: '10px 12px',
                                                                    background: 'transparent',
                                                                    border: 'none',
                                                                    cursor: hasNews ? 'pointer' : 'default'
                                                                }}
                                                            >
                                                                <span style={{
                                                                    fontWeight: '500',
                                                                    color: hasNews ? '#1e293b' : '#94a3b8',
                                                                    fontSize: '14px'
                                                                }}>
                                                                    {name}
                                                                </span>
                                                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                                    <span style={{
                                                                        background: hasNews ? '#ef4444' : '#e2e8f0',
                                                                        color: hasNews ? '#fff' : '#94a3b8',
                                                                        fontSize: '12px',
                                                                        padding: '2px 8px',
                                                                        borderRadius: '10px',
                                                                        fontWeight: '600'
                                                                    }}>
                                                                        {data.news_count}
                                                                    </span>
                                                                    {hasNews && (isExpanded ? <ChevronUp size={14} color="#64748b" /> : <ChevronDown size={14} color="#64748b" />)}
                                                                </div>
                                                            </button>
                                                            {isExpanded && hasNews && (
                                                                <div style={{
                                                                    padding: '0 12px 12px',
                                                                    display: 'flex',
                                                                    flexDirection: 'column',
                                                                    gap: '6px'
                                                                }}>
                                                                    {data.news.map((news, idx) => (
                                                                        <a
                                                                            key={idx}
                                                                            href={news.url}
                                                                            target="_blank"
                                                                            rel="noopener noreferrer"
                                                                            style={{
                                                                                display: 'block',
                                                                                padding: '8px 10px',
                                                                                background: '#fff',
                                                                                borderRadius: '6px',
                                                                                fontSize: '12px',
                                                                                color: '#334155',
                                                                                textDecoration: 'none',
                                                                                lineHeight: '1.4',
                                                                                borderLeft: '3px solid #ef4444'
                                                                            }}
                                                                        >
                                                                            <div style={{ marginBottom: '4px' }}>{news.title}</div>
                                                                            <div style={{
                                                                                fontSize: '10px',
                                                                                color: '#94a3b8',
                                                                                display: 'flex',
                                                                                alignItems: 'center',
                                                                                gap: '6px'
                                                                            }}>
                                                                                <span style={{
                                                                                    background: '#e0f2fe',
                                                                                    color: '#0284c7',
                                                                                    padding: '1px 6px',
                                                                                    borderRadius: '4px',
                                                                                    fontWeight: 'bold'
                                                                                }}>
                                                                                    {news.platform_name || news.platform || news.source}
                                                                                </span>
                                                                                <span>
                                                                                    {news.crawled_at ? new Date(news.crawled_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).replace(/\//g, '-') :
                                                                                        news.publish_time}
                                                                                </span>
                                                                                <ExternalLink size={10} />
                                                                            </div>
                                                                        </a>
                                                                    ))}
                                                                </div>
                                                            )}
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            );
                        }

                        // 客户Tab：按客户分类展示
                        if (activeNewsTab === 'customers' && customerStats?.stats) {
                            return (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxHeight: '400px', overflowY: 'auto' }}>
                                    {Object.entries(customerStats.stats).map(([name, data]) => {
                                        const isExpanded = expandedPartners[name];
                                        const hasNews = data.news_count > 0;
                                        return (
                                            <div key={name} style={{
                                                background: hasNews ? '#fffbeb' : '#f8fafc',
                                                borderRadius: '8px',
                                                border: hasNews ? '1px solid #fcd34d' : '1px solid #e2e8f0'
                                            }}>
                                                <button onClick={() => hasNews && togglePartnerExpand(name)} style={{
                                                    width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                                    padding: '10px 12px', background: 'transparent', border: 'none', cursor: hasNews ? 'pointer' : 'default'
                                                }}>
                                                    <span style={{ fontWeight: '500', color: hasNews ? '#1e293b' : '#94a3b8', fontSize: '14px' }}>{name}</span>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                        <span style={{ background: hasNews ? '#f59e0b' : '#e2e8f0', color: hasNews ? '#fff' : '#94a3b8', fontSize: '12px', padding: '2px 8px', borderRadius: '10px', fontWeight: '600' }}>{data.news_count}</span>
                                                        {hasNews && (isExpanded ? <ChevronUp size={14} color="#64748b" /> : <ChevronDown size={14} color="#64748b" />)}
                                                    </div>
                                                </button>
                                                {isExpanded && hasNews && (
                                                    <div style={{ padding: '0 12px 12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                                        {data.news.map((news, idx) => (
                                                            <a key={idx} href={news.url} target="_blank" rel="noopener noreferrer" style={{ display: 'block', padding: '8px 10px', background: '#fff', borderRadius: '6px', fontSize: '12px', color: '#334155', textDecoration: 'none', lineHeight: '1.4', borderLeft: '3px solid #f59e0b' }}>
                                                                <div style={{ marginBottom: '4px' }}>{news.title}</div>
                                                                <div style={{ fontSize: '10px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                                                    <span style={{ background: '#e0f2fe', color: '#0284c7', padding: '1px 6px', borderRadius: '4px', fontWeight: 'bold' }}>
                                                                        {news.platform_name || news.platform || news.source}
                                                                    </span>
                                                                    <span>
                                                                        {news.crawled_at ? new Date(news.crawled_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).replace(/\//g, '-') : news.publish_time}
                                                                    </span>
                                                                    <ExternalLink size={10} style={{ display: 'inline' }} />
                                                                </div>
                                                            </a>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            );
                        }

                        // 供应商Tab：按分类展示
                        if (activeNewsTab === 'suppliers' && supplierStats?.stats) {
                            return (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '400px', overflowY: 'auto' }}>
                                    {Object.entries(supplierStats.stats).map(([category, suppliers]) => (
                                        <div key={category}>
                                            <div style={{ fontSize: '12px', fontWeight: '600', color: '#64748b', marginBottom: '8px', padding: '4px 8px', background: '#eff6ff', borderRadius: '4px', display: 'inline-flex' }}>🏭 {category}</div>
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                                {Object.entries(suppliers).map(([name, data]) => {
                                                    const isExpanded = expandedPartners[name];
                                                    const hasNews = data.news_count > 0;
                                                    return (
                                                        <div key={name} style={{ background: hasNews ? '#eff6ff' : '#f8fafc', borderRadius: '8px', border: hasNews ? '1px solid #93c5fd' : '1px solid #e2e8f0' }}>
                                                            <button onClick={() => hasNews && togglePartnerExpand(name)} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', background: 'transparent', border: 'none', cursor: hasNews ? 'pointer' : 'default' }}>
                                                                <span style={{ fontWeight: '500', color: hasNews ? '#1e293b' : '#94a3b8', fontSize: '14px' }}>{name}</span>
                                                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                                    <span style={{ background: hasNews ? '#3b82f6' : '#e2e8f0', color: hasNews ? '#fff' : '#94a3b8', fontSize: '12px', padding: '2px 8px', borderRadius: '10px', fontWeight: '600' }}>{data.news_count}</span>
                                                                    {hasNews && (isExpanded ? <ChevronUp size={14} color="#64748b" /> : <ChevronDown size={14} color="#64748b" />)}
                                                                </div>
                                                            </button>
                                                            {isExpanded && hasNews && (
                                                                <div style={{ padding: '0 12px 12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                                                    {data.news.map((news, idx) => (
                                                                        <a key={idx} href={news.url} target="_blank" rel="noopener noreferrer" style={{ display: 'block', padding: '8px 10px', background: '#fff', borderRadius: '6px', fontSize: '12px', color: '#334155', textDecoration: 'none', lineHeight: '1.4', borderLeft: '3px solid #3b82f6' }}>
                                                                            <div style={{ marginBottom: '4px' }}>{news.title}</div>
                                                                            <div style={{ fontSize: '10px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                                                                <span style={{ background: '#e0f2fe', color: '#0284c7', padding: '1px 6px', borderRadius: '4px', fontWeight: 'bold' }}>
                                                                                    {news.platform_name || news.platform || news.source}
                                                                                </span>
                                                                                <span>
                                                                                    {news.crawled_at ? new Date(news.crawled_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).replace(/\//g, '-') : news.publish_time}
                                                                                </span>
                                                                                <ExternalLink size={10} style={{ display: 'inline' }} />
                                                                            </div>
                                                                        </a>
                                                                    ))}
                                                                </div>
                                                            )}
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            );
                        }

                        // 物料品类Tab
                        if (activeNewsTab === 'materials' && materialStats?.stats) {
                            return (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxHeight: '400px', overflowY: 'auto' }}>
                                    {Object.entries(materialStats.stats).map(([name, data]) => {
                                        const isExpanded = expandedPartners[name];
                                        const hasNews = data.news_count > 0;
                                        return (
                                            <div key={name} style={{ background: hasNews ? '#ecfdf5' : '#f8fafc', borderRadius: '8px', border: hasNews ? '1px solid #6ee7b7' : '1px solid #e2e8f0' }}>
                                                <button onClick={() => hasNews && togglePartnerExpand(name)} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', background: 'transparent', border: 'none', cursor: hasNews ? 'pointer' : 'default' }}>
                                                    <span style={{ fontWeight: '500', color: hasNews ? '#1e293b' : '#94a3b8', fontSize: '14px' }}>📦 {name}</span>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                        <span style={{ background: hasNews ? '#10b981' : '#e2e8f0', color: hasNews ? '#fff' : '#94a3b8', fontSize: '12px', padding: '2px 8px', borderRadius: '10px', fontWeight: '600' }}>{data.news_count}</span>
                                                        {hasNews && (isExpanded ? <ChevronUp size={14} color="#64748b" /> : <ChevronDown size={14} color="#64748b" />)}
                                                    </div>
                                                </button>
                                                {isExpanded && hasNews && (
                                                    <div style={{ padding: '0 12px 12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                                        {data.news.map((news, idx) => (
                                                            <a key={idx} href={news.url} target="_blank" rel="noopener noreferrer" style={{ display: 'block', padding: '8px 10px', background: '#fff', borderRadius: '6px', fontSize: '12px', color: '#334155', textDecoration: 'none', lineHeight: '1.4', borderLeft: '3px solid #10b981' }}>
                                                                <div style={{ marginBottom: '4px' }}>{news.title}</div>
                                                                <div style={{ fontSize: '10px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                                                    <span style={{ background: '#e0f2fe', color: '#0284c7', padding: '1px 6px', borderRadius: '4px', fontWeight: 'bold' }}>
                                                                        {news.platform_name || news.platform || news.source}
                                                                    </span>
                                                                    <span>
                                                                        {news.crawled_at ? new Date(news.crawled_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).replace(/\//g, '-') : news.publish_time}
                                                                    </span>
                                                                    <ExternalLink size={10} style={{ display: 'inline' }} />
                                                                </div>
                                                            </a>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            );
                        }

                        // 关税政策Tab（AI智能分类）
                        if (activeNewsTab === 'tariff' && tariffStats?.stats) {
                            return (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', maxHeight: '400px', overflowY: 'auto' }}>
                                    {Object.entries(tariffStats.stats).map(([category, data]) => {
                                        const isExpanded = expandedPartners[`tariff-${category}`];
                                        const hasNews = data.news_count > 0;
                                        const icons = { '中美关税': '🇺🇸', '欧盟政策': '🇪🇺', '出口管制': '🚫', '进口关税': '📥', '自贸协定': '🤝', '其他政策': '📋' };
                                        return (
                                            <div key={category} style={{ background: hasNews ? '#f5f3ff' : '#f8fafc', borderRadius: '8px', border: hasNews ? '1px solid #c4b5fd' : '1px solid #e2e8f0' }}>
                                                <button onClick={() => hasNews && togglePartnerExpand(`tariff-${category}`)} style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px', background: 'transparent', border: 'none', cursor: hasNews ? 'pointer' : 'default' }}>
                                                    <span style={{ fontWeight: '600', color: hasNews ? '#1e293b' : '#94a3b8', fontSize: '14px' }}>{icons[category] || '📋'} {category}</span>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                        <span style={{ background: hasNews ? '#8b5cf6' : '#e2e8f0', color: hasNews ? '#fff' : '#94a3b8', fontSize: '12px', padding: '2px 8px', borderRadius: '10px', fontWeight: '600' }}>{data.news_count}</span>
                                                        {hasNews && (isExpanded ? <ChevronUp size={14} color="#64748b" /> : <ChevronDown size={14} color="#64748b" />)}
                                                    </div>
                                                </button>
                                                {isExpanded && hasNews && (
                                                    <div style={{ padding: '0 12px 12px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                                        {data.news.map((news, idx) => (
                                                            <a key={idx} href={news.url} target="_blank" rel="noopener noreferrer" style={{ display: 'block', padding: '8px 10px', background: '#fff', borderRadius: '6px', fontSize: '12px', color: '#334155', textDecoration: 'none', lineHeight: '1.4', borderLeft: '3px solid #8b5cf6' }}>
                                                                <div style={{ marginBottom: '4px' }}>{news.title}</div>
                                                                <div style={{ fontSize: '10px', color: '#94a3b8', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                                                    <span style={{ background: '#e0f2fe', color: '#0284c7', padding: '1px 6px', borderRadius: '4px', fontWeight: 'bold' }}>
                                                                        {news.platform_name || news.platform || news.source}
                                                                    </span>
                                                                    <span>
                                                                        {news.crawled_at ? new Date(news.crawled_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).replace(/\//g, '-') : news.publish_time}
                                                                    </span>
                                                                    <ExternalLink size={10} style={{ display: 'inline' }} />
                                                                </div>
                                                            </a>
                                                        ))}
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            );
                        }

                        // 其他Tab：暂无数据
                        return (
                            <div style={{
                                textAlign: 'center',
                                padding: '40px',
                                color: '#94a3b8',
                                background: currentTab?.bgColor || '#f8fafc',
                                borderRadius: '12px'
                            }}>
                                <div style={{ marginBottom: '8px' }}>
                                    {getTabIcon(currentTab?.icon)}
                                </div>
                                暂无{currentTab?.name}相关新闻
                            </div>
                        );
                    })()}
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
                        minHeight: '500px',
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
                            minHeight: '400px',
                            overflowY: 'auto',
                            padding: '24px',
                            background: '#fafafa'
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
