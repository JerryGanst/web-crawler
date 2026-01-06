import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
    ArrowLeft, 
    Download, 
    Printer, 
    Loader2, 
    AlertCircle,
    Clock,
    FileText,
    ChevronUp
} from 'lucide-react';

import { API_BASE } from '../services/api';

const TRENDRADAR_API = API_BASE || '';

// 生成SVG雷达图
const generateRadarSVG = (data) => {
    const { dimensions, companies, title } = data;
    const colors = [
        { stroke: '#6366f1', fill: 'rgba(99,102,241,0.2)' },
        { stroke: '#22c55e', fill: 'rgba(34,197,94,0.2)' },
        { stroke: '#f59e0b', fill: 'rgba(245,158,11,0.2)' },
        { stroke: '#ef4444', fill: 'rgba(239,68,68,0.2)' },
        { stroke: '#3b82f6', fill: 'rgba(59,130,246,0.2)' },
    ];
    
    const size = 300;
    const center = size / 2;
    const maxRadius = 120;
    const levels = 5;
    const angleStep = (2 * Math.PI) / dimensions.length;
    
    // 计算点坐标
    const getPoint = (angle, value) => {
        const r = (value / 10) * maxRadius;
        return {
            x: center + r * Math.sin(angle),
            y: center - r * Math.cos(angle)
        };
    };
    
    // 生成网格
    let gridLines = '';
    for (let l = 1; l <= levels; l++) {
        const r = (l / levels) * maxRadius;
        let points = [];
        for (let i = 0; i < dimensions.length; i++) {
            const angle = i * angleStep;
            points.push(`${center + r * Math.sin(angle)},${center - r * Math.cos(angle)}`);
        }
        gridLines += `<polygon points="${points.join(' ')}" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>`;
    }
    
    // 生成轴线和标签
    let axisLines = '';
    let labels = '';
    dimensions.forEach((dim, i) => {
        const angle = i * angleStep;
        const endPoint = getPoint(angle, 10);
        axisLines += `<line x1="${center}" y1="${center}" x2="${endPoint.x}" y2="${endPoint.y}" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>`;
        
        const labelPoint = getPoint(angle, 12);
        const textAnchor = Math.abs(labelPoint.x - center) < 10 ? 'middle' : (labelPoint.x > center ? 'start' : 'end');
        labels += `<text x="${labelPoint.x}" y="${labelPoint.y}" fill="#a0a0b0" font-size="11" text-anchor="${textAnchor}" dominant-baseline="middle">${dim}</text>`;
    });
    
    // 生成数据区域
    let dataPolygons = '';
    let legendItems = '';
    Object.entries(companies).forEach(([name, scores], idx) => {
        const color = colors[idx % colors.length];
        let points = [];
        scores.forEach((score, i) => {
            const angle = i * angleStep;
            const point = getPoint(angle, score);
            points.push(`${point.x},${point.y}`);
        });
        dataPolygons += `<polygon points="${points.join(' ')}" fill="${color.fill}" stroke="${color.stroke}" stroke-width="2"/>`;
        
        // 图例
        const legendX = 20 + idx * 100;
        legendItems += `<rect x="${legendX}" y="${size + 10}" width="12" height="12" fill="${color.stroke}" rx="2"/>`;
        legendItems += `<text x="${legendX + 16}" y="${size + 20}" fill="#a0a0b0" font-size="11">${name}</text>`;
    });
    
    return `
        <div style="max-width:450px;margin:24px auto;background:#1e293b;border-radius:12px;padding:20px;text-align:center">
            <h4 style="color:#818cf8;margin-bottom:16px;font-size:15px">${title || '竞争力对比雷达图'}</h4>
            <svg width="${size}" height="${size + 40}" viewBox="0 0 ${size} ${size + 40}" style="max-width:100%">
                ${gridLines}
                ${axisLines}
                ${dataPolygons}
                ${labels}
                <g transform="translate(${(size - Object.keys(companies).length * 100) / 2}, 0)">
                    ${legendItems}
                </g>
            </svg>
        </div>
    `;
};

// Markdown 渲染器（增强版，支持SVG雷达图）
const renderMarkdown = (text) => {
    if (!text) return '';
    
    let html = text;
    
    // 1. 提取雷达图 JSON 并转换为 SVG
    html = html.replace(/```(?:json:radar-chart|json)\n?(\{[\s\S]*?"dimensions"[\s\S]*?\})\n?```/g, (match, jsonStr) => {
        try {
            const data = JSON.parse(jsonStr);
            if (data.dimensions && data.companies) {
                return generateRadarSVG(data);
            }
        } catch (e) {
            console.error('JSON parse error:', e);
        }
        return match;
    });
    
    // 2. 处理普通代码块
    html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, (match, lang, code) => {
        return `<pre style="background:#0f172a;color:#e2e8f0;padding:16px;border-radius:8px;overflow-x:auto;font-size:13px;margin:16px 0;font-family:'SF Mono',monospace;border:1px solid #334155"><code>${code.trim()}</code></pre>`;
    });
    
    // 3. 处理表格
    html = html.replace(/\n(\|[^\n]+\|\n\|[-:| ]+\|\n(?:\|[^\n]+\|\n?)+)/g, (match, table) => {
        const rows = table.trim().split('\n');
        if (rows.length < 2) return match;
        
        let tableHtml = '<div style="overflow-x:auto;margin:20px 0;border-radius:10px;border:1px solid #334155"><table style="width:100%;border-collapse:collapse;font-size:14px">';
        
        rows.forEach((row, idx) => {
            if (row.match(/^\|[\s:-]+\|$/)) return;
            
            const cells = row.split('|').filter(c => c.trim() !== '');
            const tag = idx === 0 ? 'th' : 'td';
            const bgColor = idx === 0 ? '#1e293b' : '#0f172a';
            const textColor = idx === 0 ? '#818cf8' : '#e2e8f0';
            
            tableHtml += '<tr>';
            cells.forEach(cell => {
                let content = cell.trim()
                    .replace(/🔴/g, '<span style="color:#ef4444">🔴</span>')
                    .replace(/⚠️/g, '<span style="color:#f59e0b">⚠️</span>')
                    .replace(/✅/g, '<span style="color:#22c55e">✅</span>')
                    .replace(/⭐/g, '<span style="color:#f59e0b">⭐</span>')
                    .replace(/🚀/g, '<span style="color:#3b82f6">🚀</span>')
                    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color:#60a5fa;text-decoration:none">$1</a>');
                    
                tableHtml += `<${tag} style="padding:12px;border-bottom:1px solid #334155;background:${bgColor};color:${textColor};text-align:left;vertical-align:top">${content}</${tag}>`;
            });
            tableHtml += '</tr>';
        });
        
        tableHtml += '</table></div>';
        return tableHtml;
    });
    
    // 4. 处理标题
    html = html.replace(/^#### (.*$)/gim, '<h4 style="font-size:15px;font-weight:600;margin:16px 0 10px;color:#e2e8f0">$1</h4>');
    html = html.replace(/^### (.*$)/gim, '<h3 style="font-size:17px;font-weight:600;margin:20px 0 12px;color:#f0f0f5">$1</h3>');
    html = html.replace(/^## (.*$)/gim, '<h2 style="font-size:20px;font-weight:700;margin:32px 0 16px;color:#fff;padding-bottom:12px;border-bottom:2px solid #6366f1;display:flex;align-items:center;gap:10px"><span style="width:4px;height:20px;background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:2px"></span>$1</h2>');
    html = html.replace(/^# (.*$)/gim, '<h1 style="font-size:26px;font-weight:700;margin:0 0 24px;color:#fff;letter-spacing:-0.02em">$1</h1>');
    
    // 5. 处理链接
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" style="color:#60a5fa;text-decoration:none;border-bottom:1px solid transparent;transition:border-color 0.2s" onmouseover="this.style.borderColor=\'#60a5fa\'" onmouseout="this.style.borderColor=\'transparent\'">$1</a>');
    
    // 6. 处理加粗和斜体
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong style="font-weight:600;color:#f0f0f5">$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em style="font-style:italic;color:#a0a0b0">$1</em>');
    
    // 7. 处理列表
    html = html.replace(/^- (.*$)/gim, '<li style="margin:8px 0;padding-left:8px;list-style-type:disc;margin-left:20px;color:#a0a0b0">$1</li>');
    html = html.replace(/^\d+\. (.*$)/gim, '<li style="margin:8px 0;padding-left:8px;list-style-type:decimal;margin-left:20px;color:#a0a0b0">$1</li>');
    
    // 8. 处理引用块
    html = html.replace(/^> (.*$)/gim, '<blockquote style="border-left:4px solid #6366f1;padding:14px 18px;margin:20px 0;background:rgba(99,102,241,0.1);color:#e2e8f0;border-radius:0 8px 8px 0">$1</blockquote>');
    
    // 9. 处理分隔线
    html = html.replace(/^---$/gim, '<hr style="border:none;height:1px;background:linear-gradient(90deg,transparent,#334155,transparent);margin:32px 0"/>');
    
    // 10. 处理行内代码
    html = html.replace(/`([^`]+)`/g, '<code style="background:#1e293b;padding:3px 8px;border-radius:4px;font-size:13px;color:#22c55e;font-family:\'SF Mono\',monospace;border:1px solid #334155">$1</code>');
    
    // 11. 处理段落
    html = html.replace(/\n\n/g, '</p><p style="margin:16px 0;line-height:1.8;color:#a0a0b0">');
    html = html.replace(/\n/g, '<br/>');
    
    return `<p style="margin:16px 0;line-height:1.8;color:#a0a0b0">${html}</p>`;
};

export default function ReportViewer() {
    const { filename } = useParams();
    const [content, setContent] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [showBackToTop, setShowBackToTop] = useState(false);
    
    useEffect(() => {
        const fetchReport = async () => {
            if (!filename) {
                setError('未指定报告文件');
                setLoading(false);
                return;
            }
            
            try {
                // 获取原始 Markdown
                const res = await fetch(`${TRENDRADAR_API}/api/reports/${filename}?format=md`);
                if (!res.ok) throw new Error('报告不存在');
                const text = await res.text();
                setContent(text);
            } catch (e) {
                setError(e.message);
            } finally {
                setLoading(false);
            }
        };
        
        fetchReport();
    }, [filename]);
    
    
    // 滚动监听
    useEffect(() => {
        const handleScroll = () => setShowBackToTop(window.scrollY > 300);
        window.addEventListener('scroll', handleScroll);
        return () => window.removeEventListener('scroll', handleScroll);
    }, []);
    
    const scrollToTop = () => window.scrollTo({ top: 0, behavior: 'smooth' });
    
    if (loading) {
        return (
            <div style={{ 
                display: 'flex', 
                flexDirection: 'column',
                alignItems: 'center', 
                justifyContent: 'center', 
                height: '100vh',
                background: '#0a0a0f',
                color: '#a0a0b0'
            }}>
                <Loader2 size={40} className="animate-spin" style={{ marginBottom: 16 }} />
                <div>加载报告中...</div>
            </div>
        );
    }
    
    if (error) {
        return (
            <div style={{ 
                display: 'flex', 
                flexDirection: 'column',
                alignItems: 'center', 
                justifyContent: 'center', 
                height: '100vh',
                background: '#0a0a0f',
                color: '#ef4444'
            }}>
                <AlertCircle size={48} style={{ marginBottom: 16 }} />
                <div style={{ fontSize: 18, marginBottom: 8 }}>加载失败</div>
                <div style={{ color: '#a0a0b0', marginBottom: 24 }}>{error}</div>
                <Link to="/radar" style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '10px 20px',
                    background: '#1e293b',
                    color: '#e2e8f0',
                    borderRadius: 8,
                    textDecoration: 'none'
                }}>
                    <ArrowLeft size={18} />
                    返回
                </Link>
            </div>
        );
    }
    
    return (
        <div style={{ 
            minHeight: '100vh',
            background: '#0a0a0f',
            color: '#e2e8f0'
        }}>
            {/* 顶部导航 */}
            <nav style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                height: 60,
                background: 'rgba(10, 10, 15, 0.9)',
                backdropFilter: 'blur(20px)',
                borderBottom: '1px solid #2a2a3a',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0 24px',
                zIndex: 1000
            }}>
                <Link to="/radar" style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    color: '#a0a0b0',
                    textDecoration: 'none',
                    fontSize: 14,
                    transition: 'color 0.2s'
                }}>
                    <ArrowLeft size={18} />
                    返回产业链
                </Link>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <FileText size={20} style={{ color: '#6366f1' }} />
                    <span style={{ fontWeight: 600 }}>立讯技术新闻专业分析助手</span>
                </div>
                
                <div style={{ display: 'flex', gap: 12 }}>
                    {filename && (
                        <a 
                            href={`${TRENDRADAR_API}/api/reports/${encodeURIComponent(filename)}?format=md`}
                            download={filename}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6,
                                padding: '8px 14px',
                                background: 'transparent',
                                border: '1px solid #334155',
                                color: '#a0a0b0',
                                borderRadius: 8,
                                fontSize: 13,
                                textDecoration: 'none',
                                cursor: 'pointer'
                            }}
                        >
                            <Download size={16} />
                            下载 MD
                        </a>
                    )}
                    <button 
                        onClick={() => window.print()}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6,
                            padding: '8px 14px',
                            background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                            border: 'none',
                            color: '#fff',
                            borderRadius: 8,
                            fontSize: 13,
                            cursor: 'pointer'
                        }}
                    >
                        <Printer size={16} />
                        打印
                    </button>
                </div>
            </nav>
            
            {/* 主内容 */}
            <main style={{ 
                maxWidth: 900, 
                margin: '0 auto', 
                padding: '100px 24px 60px'
            }}>
                <div style={{ marginBottom: 24, display: 'flex', alignItems: 'center', gap: 8, color: '#6b6b7a', fontSize: 13 }}>
                    <Clock size={14} />
                    {filename?.match(/(\d{8})_(\d{6})/)?.[0]?.replace(/_/, ' ').replace(/(\d{4})(\d{2})(\d{2})/, '$1-$2-$3 ').replace(/(\d{2})(\d{2})(\d{2})$/, '$1:$2:$3') || ''}
                </div>
                
                <article 
                    dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
                    style={{ lineHeight: 1.8 }}
                />
                
                <footer style={{
                    marginTop: 48,
                    paddingTop: 24,
                    borderTop: '1px solid #2a2a3a',
                    textAlign: 'center',
                    color: '#6b6b7a',
                    fontSize: 13
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 8 }}>
                        <FileText size={16} />
                        立讯技术产业链分析助手
                    </div>
                    <div>Powered by AI · 仅供参考，不构成投资建议</div>
                </footer>
            </main>
            
            {/* 返回顶部 */}
            {showBackToTop && (
                <button
                    onClick={scrollToTop}
                    style={{
                        position: 'fixed',
                        bottom: 24,
                        right: 24,
                        width: 44,
                        height: 44,
                        background: '#1e293b',
                        border: '1px solid #334155',
                        borderRadius: 12,
                        color: '#a0a0b0',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                    }}
                >
                    <ChevronUp size={20} />
                </button>
            )}
        </div>
    );
}
