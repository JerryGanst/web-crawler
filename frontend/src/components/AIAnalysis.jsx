import React, { useState, useEffect, useCallback } from 'react';
import { Bot, Sparkles, RefreshCw, Clock, Loader2, AlertCircle } from 'lucide-react';
import api from '../services/api';

const AIAnalysis = () => {
    const [analysisText, setAnalysisText] = useState('');
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [lastUpdate, setLastUpdate] = useState(null);
    const [cached, setCached] = useState(false);
    const [apiSource, setApiSource] = useState('');

    const fetchAnalysis = useCallback(async (refresh = false) => {
        setLoading(true);
        setError(null);
        try {
            const response = await api.getMarketAnalysis(refresh);
            const data = response.data;
            
            if (data.status === 'success') {
                setAnalysisText(data.content);
                setLastUpdate(new Date(data.timestamp));
                setCached(data.cached || false);
                setApiSource(data.api_source || '');
            } else {
                throw new Error('获取分析失败');
            }
        } catch (err) {
            console.error('获取市场分析失败:', err);
            setError(err.message || '获取分析失败，请稍后重试');
            // 显示默认内容
            setAnalysisText(`**市场概况**
今日市场数据正在加载中...

**重点关注**
* 请点击刷新按钮获取最新 AI 分析

**操作建议**
等待数据加载完成。`);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAnalysis();
    }, [fetchAnalysis]);

    const handleRefresh = () => {
        fetchAnalysis(true);
    };

    const renderContent = (text) => {
        return text.split('\n').map((line, index) => {
            // 标题 (加粗)
            if (line.startsWith('**') && line.endsWith('**')) {
                return <h4 key={index} style={{ margin: '12px 0 6px', color: '#111827', fontWeight: '600' }}>{line.replace(/\*\*/g, '')}</h4>;
            }
            // 列表项 (以 * 或 - 开头)
            if (line.match(/^[\*\-]\s/)) {
                return <li key={index} style={{ marginLeft: '20px', marginBottom: '4px', color: '#4b5563', listStyleType: 'disc' }}>{line.replace(/^[\*\-]\s/, '').trim()}</li>;
            }
            // 分隔线
            if (line.startsWith('---')) {
                return <hr key={index} style={{ border: 'none', borderTop: '1px solid #e5e7eb', margin: '12px 0' }} />;
            }
            // 斜体文本 (时间戳等)
            if (line.startsWith('*') && line.endsWith('*') && !line.startsWith('**')) {
                return <p key={index} style={{ margin: '8px 0', fontSize: '12px', color: '#9ca3af', fontStyle: 'italic' }}>{line.replace(/\*/g, '')}</p>;
            }
            // 空行
            if (line.trim() === '') return null;
            // 普通段落
            return <p key={index} style={{ margin: '0 0 8px', lineHeight: '1.6', color: '#4b5563' }}>{line}</p>;
        });
    };

    const formatTime = (date) => {
        if (!date) return '';
        return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    };

    return (
        <div style={{ 
            background: 'linear-gradient(135deg, #f0f9ff 0%, #e0e7ff 100%)', 
            padding: '24px', 
            borderRadius: '16px', 
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)', 
            marginBottom: '20px',
            position: 'relative'
        }}>
            {/* 标题栏 */}
            <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center', 
                marginBottom: '15px' 
            }}>
                <h3 style={{ 
                    margin: 0, 
                    fontSize: '18px', 
                    fontWeight: '600', 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '8px', 
                    color: '#1e40af' 
                }}>
                    <Bot size={20} />
                    AI 市场分析
                    <Sparkles size={16} color="#f59e0b" />
                </h3>
                
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    {/* 状态标签 */}
                    {apiSource && !loading && (
                        <span style={{
                            fontSize: '11px',
                            padding: '2px 8px',
                            borderRadius: '10px',
                            background: cached ? '#e0e7ff' : '#dcfce7',
                            color: cached ? '#3730a3' : '#166534'
                        }}>
                            {cached ? '缓存' : 'AI 生成'} · {apiSource}
                        </span>
                    )}
                    
                    {/* 更新时间 */}
                    {lastUpdate && !loading && (
                        <span style={{ 
                            fontSize: '12px', 
                            color: '#6b7280', 
                            display: 'flex', 
                            alignItems: 'center', 
                            gap: '4px' 
                        }}>
                            <Clock size={12} />
                            {formatTime(lastUpdate)}
                        </span>
                    )}
                    
                    {/* 刷新按钮 */}
                    <button
                        onClick={handleRefresh}
                        disabled={loading}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '6px 12px',
                            fontSize: '12px',
                            background: loading ? '#e5e7eb' : '#3b82f6',
                            color: loading ? '#9ca3af' : 'white',
                            border: 'none',
                            borderRadius: '8px',
                            cursor: loading ? 'not-allowed' : 'pointer',
                            transition: 'all 0.2s'
                        }}
                    >
                        {loading ? (
                            <>
                                <Loader2 size={14} style={{ animation: 'spin 1s linear infinite' }} />
                                分析中...
                            </>
                        ) : (
                            <>
                                <RefreshCw size={14} />
                                刷新
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* 错误提示 */}
            {error && (
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '10px 14px',
                    marginBottom: '12px',
                    background: '#fef2f2',
                    borderRadius: '8px',
                    color: '#dc2626',
                    fontSize: '13px'
                }}>
                    <AlertCircle size={16} />
                    {error}
                </div>
            )}

            {/* 加载状态 */}
            {loading && !analysisText && (
                <div style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '40px 20px',
                    color: '#6b7280'
                }}>
                    <Loader2 size={32} style={{ animation: 'spin 1s linear infinite', marginBottom: '12px' }} />
                    <p style={{ margin: 0, fontSize: '14px' }}>AI 正在分析市场数据...</p>
                </div>
            )}

            {/* 分析内容 */}
            {analysisText && (
                <div style={{ 
                    fontSize: '14px',
                    opacity: loading ? 0.6 : 1,
                    transition: 'opacity 0.2s'
                }}>
                    {renderContent(analysisText)}
                </div>
            )}

            {/* 加载动画样式 */}
            <style>{`
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    );
};

export default AIAnalysis;
