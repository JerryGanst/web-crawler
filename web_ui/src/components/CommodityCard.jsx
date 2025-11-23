import React, { useState } from 'react';
import CommodityChart from './CommodityChart';
import { ExternalLink, ArrowRightLeft } from 'lucide-react';

// Safe URL parsing helper
const safeGetHostname = (url) => {
    if (!url) return '';
    try {
        return new URL(url).hostname;
    } catch {
        return url.substring(0, 30) + (url.length > 30 ? '...' : '');
    }
};

const CommodityCard = ({
    comm,
    realItem,
    currentPrice,
    unit,
    historyData,
    currencySymbol,
    formatPrice,
    isLastOdd
}) => {
    // State for unit conversion
    // Default to the unit provided by the data
    const [displayUnit, setDisplayUnit] = useState(unit);

    // Conversion constants
    const GRAMS_PER_OUNCE = 31.1034768;

    // Check if this commodity supports oz/g conversion
    // Supports: g, oz, 盎司, gram, kg (for precious metals like silver)
    const canConvert = ['g', 'oz', '盎司', 'gram', 'kg'].includes(unit);

    // Fixed toggle logic - supports full cycle conversion
    const toggleUnit = () => {
        if (displayUnit === 'g' || displayUnit === 'gram') {
            setDisplayUnit('oz');
        } else if (displayUnit === 'oz' || displayUnit === '盎司') {
            // If original was kg, allow going back to kg; otherwise go to g
            if (unit === 'kg') {
                setDisplayUnit('kg');
            } else {
                setDisplayUnit('g');
            }
        } else if (displayUnit === 'kg') {
            setDisplayUnit('oz');
        }
    };

    // Get target unit text for switch button
    const getTargetUnit = () => {
        if (displayUnit === 'oz' || displayUnit === '盎司') {
            return unit === 'kg' ? 'kg' : 'g';
        }
        return 'oz';
    };

    // Helper to convert value based on current displayUnit vs original unit
    const convertValue = (val) => {
        if (!val || !canConvert) return val || 0;
        const numVal = parseFloat(val);

        if (unit === displayUnit) return numVal;

        // Convert FROM 'g' TO 'oz'
        if ((unit === 'g' || unit === 'gram') && (displayUnit === 'oz' || displayUnit === '盎司')) {
            return numVal / GRAMS_PER_OUNCE;
        }

        // Convert FROM 'oz' TO 'g'
        if ((unit === 'oz' || unit === '盎司') && (displayUnit === 'g' || displayUnit === 'gram')) {
            return numVal * GRAMS_PER_OUNCE;
        }

        // Convert FROM 'kg' TO 'oz' (1 kg = 1000 g ≈ 32.15 oz)
        if (unit === 'kg' && (displayUnit === 'oz' || displayUnit === '盎司')) {
            return (numVal * 1000) / GRAMS_PER_OUNCE;
        }

        // Convert FROM 'oz' TO 'kg' (reverse)
        if ((unit === 'oz' || unit === '盎司') && displayUnit === 'kg') {
            return (numVal * GRAMS_PER_OUNCE) / 1000;
        }

        return numVal;
    };

    // Converted price for header display (card-level conversion)
    const displayedPrice = convertValue(currentPrice);

    return (
        <div style={{
            background: '#fff',
            padding: '24px',
            borderRadius: '16px',
            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)',
            gridColumn: isLastOdd ? 'span 2' : 'auto',
            position: 'relative'
        }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
                <div>
                    <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ width: '12px', height: '12px', borderRadius: '50%', background: comm.color }}></span>
                        {comm.name}
                    </h3>
                    {/* URL Display */}
                    {realItem && realItem.url && (
                        <a
                            href={realItem.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '4px',
                                fontSize: '12px',
                                color: '#6b7280',
                                marginTop: '4px',
                                textDecoration: 'none'
                            }}
                            title={realItem.url}
                        >
                            <ExternalLink size={12} />
                            {safeGetHostname(realItem.url)}
                        </a>
                    )}
                </div>

                <div style={{ textAlign: 'right' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '8px' }}>
                        <span style={{ fontSize: '20px', fontWeight: '700', color: '#111827' }}>
                            {currencySymbol}{formatPrice(displayedPrice)}
                            <span style={{ fontSize: '14px', color: '#6b7280', marginLeft: '4px', fontWeight: '500' }}>
                                /{displayUnit}
                            </span>
                        </span>
                    </div>

                    {/* Unit Switch for header price display */}
                    {canConvert && (
                        <button
                            onClick={toggleUnit}
                            style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                marginTop: '4px',
                                padding: '2px 8px',
                                borderRadius: '4px',
                                border: '1px solid #e5e7eb',
                                background: '#f9fafb',
                                fontSize: '11px',
                                color: '#4b5563',
                                cursor: 'pointer'
                            }}
                            title="切换价格显示单位"
                        >
                            <ArrowRightLeft size={10} />
                            切换到 {getTargetUnit()}
                        </button>
                    )}
                </div>
            </div>

            <div style={{ height: '350px' }}>
                <CommodityChart
                    data={historyData}
                    color={comm.color}
                    name={comm.name}
                    currencySymbol={currencySymbol}
                    unit={unit}
                    showUnitSwitch={canConvert}
                />
            </div>
        </div>
    );
};

export default CommodityCard;
