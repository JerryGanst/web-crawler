import React from 'react';
import { Newspaper, ExternalLink } from 'lucide-react';
import { MOCK_NEWS } from '../services/mockData';

const NewsFeed = () => {
    return (
        <div style={{ background: '#fff', padding: '24px', borderRadius: '16px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)', height: '100%' }}>
            <h3 style={{ margin: '0 0 15px 0', fontSize: '18px', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Newspaper size={20} color="#f59e0b" />
                市场快讯 (Market News)
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                {MOCK_NEWS.map((news) => (
                    <div key={news.id} style={{ borderBottom: '1px solid #f3f4f6', paddingBottom: '10px', lastChild: { borderBottom: 'none' } }}>
                        <div style={{ fontSize: '14px', fontWeight: '500', color: '#374151', marginBottom: '4px' }}>
                            {news.title}
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#9ca3af' }}>
                            <span>{news.source}</span>
                            <span>{news.time}</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default NewsFeed;
