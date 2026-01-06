import React, { useState, useEffect } from 'react';
import { Building2, Clock, TrendingUp, Activity } from 'lucide-react';

const ExchangeStatus = () => {
    const [status, setStatus] = useState({
        shanghai: 'Open',
        london: 'Closed',
        newyork: 'Closed',
        volatility: 'Low'
    });

    useEffect(() => {
        // Simple mock time-based status
        const updateStatus = () => {
            const hour = new Date().getHours();
            setStatus({
                shanghai: (hour >= 9 && hour < 15) ? 'Open' : 'Closed',
                london: (hour >= 16 || hour < 1) ? 'Open' : 'Closed',
                newyork: (hour >= 21 || hour < 4) ? 'Open' : 'Closed',
                volatility: Math.random() > 0.7 ? 'High' : 'Moderate'
            });
        };

        updateStatus();
        const interval = setInterval(updateStatus, 60000);
        return () => clearInterval(interval);
    }, []);

    const getStatusColor = (s) => s === 'Open' ? '#059669' : '#9ca3af';

    return (
        <div style={{ background: '#fff', padding: '24px', borderRadius: '16px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)', marginBottom: '20px' }}>
            <h3 style={{ margin: '0 0 15px 0', fontSize: '18px', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Building2 size={20} color="#6366f1" />
                交易所状态 (Exchange Status)
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '15px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ padding: '8px', background: '#f3f4f6', borderRadius: '8px' }}>
                        <Clock size={16} color="#4b5563" />
                    </div>
                    <div>
                        <div style={{ fontSize: '12px', color: '#6b7280' }}>SGE (Shanghai)</div>
                        <div style={{ fontSize: '14px', fontWeight: '600', color: getStatusColor(status.shanghai) }}>{status.shanghai}</div>
                    </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ padding: '8px', background: '#f3f4f6', borderRadius: '8px' }}>
                        <Clock size={16} color="#4b5563" />
                    </div>
                    <div>
                        <div style={{ fontSize: '12px', color: '#6b7280' }}>LME (London)</div>
                        <div style={{ fontSize: '14px', fontWeight: '600', color: getStatusColor(status.london) }}>{status.london}</div>
                    </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ padding: '8px', background: '#f3f4f6', borderRadius: '8px' }}>
                        <Clock size={16} color="#4b5563" />
                    </div>
                    <div>
                        <div style={{ fontSize: '12px', color: '#6b7280' }}>COMEX (NY)</div>
                        <div style={{ fontSize: '14px', fontWeight: '600', color: getStatusColor(status.newyork) }}>{status.newyork}</div>
                    </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ padding: '8px', background: '#fff1f2', borderRadius: '8px' }}>
                        <Activity size={16} color="#e11d48" />
                    </div>
                    <div>
                        <div style={{ fontSize: '12px', color: '#6b7280' }}>Market Volatility</div>
                        <div style={{ fontSize: '14px', fontWeight: '600', color: '#e11d48' }}>{status.volatility}</div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ExchangeStatus;
