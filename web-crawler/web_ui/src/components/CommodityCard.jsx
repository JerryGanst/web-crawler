import React, { useState, useMemo } from 'react';
import CommodityChart from './CommodityChart';
import { ExternalLink } from 'lucide-react';

// Safe URL parsing helper
const safeGetHostname = (url) => {
    if (!url) return '';
    try {
        return new URL(url).hostname;
    } catch {
        return url.substring(0, 30) + (url.length > 30 ? '...' : '');
    }
};

// Conversion constants
const GRAMS_PER_OUNCE = 31.1034768;

// Extract pure weight unit from unit string - remove ALL currency markers
const extractWeightUnit = (unitStr) => {
    if (!unitStr) return '';
    // Remove all currency markers (USD, CNY, RMB, $, ¥, 美元, 人民币) and slashes
    let cleanUnit = unitStr
        .replace(/USD|CNY|RMB|美元|人民币/gi, '')
        .replace(/[$¥/]/g, '')
        .trim();
    
    // Normalize ounce variations
    if (cleanUnit === '盎司' || cleanUnit === 'ounce') {
        cleanUnit = 'oz';
    }
    return cleanUnit || unitStr;
};

// Check if unit contains ounce
const isOunceBasedUnit = (unitStr) => {
    if (!unitStr) return false;
    const lower = unitStr.toLowerCase();
    return lower.includes('oz') || unitStr.includes('盎司') || lower.includes('ounce');
};

const CommodityCard = ({
    comm,
    realItem,           // Single item (legacy)
    multiSourceItems,   // Array of items from different sources for same commodity
    currentPrice,
    unit,
    historyData,        // Single source history (legacy)
    multiSourceHistory, // Array of {source, color, data, url} for multi-source
    currencySymbol,
    formatPrice,
    isLastOdd
}) => {
    // Extract pure weight unit
    const pureUnit = extractWeightUnit(unit);
    
    // Check if this is an ounce-based commodity (only oz/盎司 needs conversion)
    const isOunceUnit = isOunceBasedUnit(unit);
    
    // State for unit display: oz or g
    const [showInGrams, setShowInGrams] = useState(false);
    
    // Current display unit
    const displayUnit = isOunceUnit ? (showInGrams ? 'g' : 'oz') : pureUnit;

    // Convert price value for display
    // Price per oz → Price per g: DIVIDE by 31.1 (1 oz = 31.1g, so per gram is cheaper)
    const convertPrice = (val) => {
        if (!val) return 0;
        const numVal = parseFloat(val);
        if (!isOunceUnit) return numVal;
        
        // Convert price/oz to price/g: divide by grams per ounce
        if (showInGrams) {
            return numVal / GRAMS_PER_OUNCE;
        }
        return numVal;
    };

    // Convert history data if showing in grams
    const convertedHistoryData = useMemo(() => {
        if (!isOunceUnit || !showInGrams) return historyData;
        return historyData?.map(item => ({
            ...item,
            price: item.price / GRAMS_PER_OUNCE  // Divide, not multiply!
        }));
    }, [historyData, showInGrams, isOunceUnit]);

    // Convert multi-source history data if showing in grams
    const convertedMultiSourceHistory = useMemo(() => {
        if (!multiSourceHistory || !isOunceUnit || !showInGrams) return multiSourceHistory;
        return multiSourceHistory.map(source => ({
            ...source,
            data: source.data.map(item => ({
                ...item,
                price: item.price / GRAMS_PER_OUNCE  // Divide, not multiply!
            }))
        }));
    }, [multiSourceHistory, showInGrams, isOunceUnit]);

    const displayedPrice = convertPrice(currentPrice);

    // Determine sources to display
    const sources = multiSourceItems || (realItem ? [realItem] : []);

    return (
        <div style={{
            background: '#fff',
            padding: '24px',
            borderRadius: '16px',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
            gridColumn: isLastOdd ? 'span 2' : 'auto',
            position: 'relative'
        }}>
            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                <div>
                    <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: comm.color }}></span>
                        {comm.name}
                    </h3>
                    {/* Multiple Sources Display */}
                    {sources.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '6px' }}>
                            {sources.map((item, idx) => (
                                <a
                                    key={idx}
                                    href={item.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    style={{
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: '3px',
                                        fontSize: '11px',
                                        color: '#6b7280',
                                        textDecoration: 'none',
                                        padding: '2px 6px',
                                        background: '#f3f4f6',
                                        borderRadius: '4px'
                                    }}
                                    title={item.url}
                                >
                                    <ExternalLink size={10} />
                                    {safeGetHostname(item.url)}
                                </a>
                            ))}
                        </div>
                    )}
                </div>

                <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '20px', fontWeight: '700', color: '#111827' }}>
                        {currencySymbol}{formatPrice(displayedPrice)}
                        <span style={{ fontSize: '14px', color: '#6b7280', marginLeft: '4px', fontWeight: '500' }}>
                            /{displayUnit}
                        </span>
                    </div>

                    {/* Unit Switch Toggle - only for oz units */}
                    {isOunceUnit && (
                        <div style={{ 
                            display: 'inline-flex', 
                            alignItems: 'center', 
                            gap: '6px',
                            marginTop: '8px',
                            padding: '4px',
                            background: '#fef3c7',
                            borderRadius: '8px',
                            border: '1px solid #fcd34d'
                        }}>
                            <button
                                onClick={() => setShowInGrams(false)}
                                style={{
                                    padding: '4px 12px',
                                    borderRadius: '6px',
                                    border: 'none',
                                    background: !showInGrams ? '#92400e' : 'transparent',
                                    color: !showInGrams ? '#fff' : '#92400e',
                                    fontSize: '12px',
                                    fontWeight: '600',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s'
                                }}
                            >
                                oz
                            </button>
                            <button
                                onClick={() => setShowInGrams(true)}
                                style={{
                                    padding: '4px 12px',
                                    borderRadius: '6px',
                                    border: 'none',
                                    background: showInGrams ? '#92400e' : 'transparent',
                                    color: showInGrams ? '#fff' : '#92400e',
                                    fontSize: '12px',
                                    fontWeight: '600',
                                    cursor: 'pointer',
                                    transition: 'all 0.2s'
                                }}
                            >
                                g
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* Chart */}
            <div style={{ height: multiSourceHistory ? '320px' : '300px' }}>
                <CommodityChart
                    data={convertedHistoryData}
                    multiSourceData={convertedMultiSourceHistory}
                    color={comm.color}
                    name={comm.name}
                    currencySymbol={currencySymbol}
                    unit={pureUnit}
                    displayUnit={displayUnit}
                />
            </div>
        </div>
    );
};

export default CommodityCard;
