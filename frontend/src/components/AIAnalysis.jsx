import React from 'react';
import { Bot, Sparkles } from 'lucide-react';

const AIAnalysis = () => {
    const analysisText = `**市场概况**
今日市场整体表现平稳，汇率波动较小。

**重点关注**
* 美元/人民币汇率维持在 7.09 附近
* 加密货币市场有所回升，BTC 突破 87000
* 关注今晚美联储议息会议结果

**操作建议**
保持观望，等待更明确的市场信号。`;

    const renderContent = (text) => {
        return text.split('\n').map((line, index) => {
            if (line.startsWith('**')) {
                return <h4 key={index} style={{ margin: '10px 0 5px', color: '#111827' }}>{line.replace(/\*\*/g, '')}</h4>;
            }
            if (line.startsWith('*')) {
                return <li key={index} style={{ marginLeft: '20px', marginBottom: '4px', color: '#4b5563' }}>{line.replace('*', '').trim()}</li>;
            }
            if (line.trim() === '') return null;
            return <p key={index} style={{ margin: '0 0 8px', lineHeight: '1.5', color: '#4b5563' }}>{line}</p>;
        });
    };

    return (
        <div style={{ background: 'linear-gradient(135deg, #f0f9ff 0%, #e0e7ff 100%)', padding: '24px', borderRadius: '16px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)', marginBottom: '20px' }}>
            <h3 style={{ margin: '0 0 15px 0', fontSize: '18px', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '8px', color: '#1e40af' }}>
                <Bot size={20} />
                AI 市场分析
                <Sparkles size={16} color="#f59e0b" />
            </h3>
            <div style={{ fontSize: '14px' }}>
                {renderContent(analysisText)}
            </div>
        </div>
    );
};

export default AIAnalysis;
