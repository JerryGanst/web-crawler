import React, { useState } from 'react';
import CommodityChart from './CommodityChart';
import { ExternalLink, ArrowRightLeft } from 'lucide-react';

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

    // Check if this commodity supports oz/g conversion (Gold/Silver usually)
    // We assume if the unit is 'g' or 'oz', it supports conversion.
    // Also 'kg' for Silver might want to convert to oz? 
    // The requirement specifically mentions "Oz and Gram conversion".
    const canConvert = ['g', 'oz', '盎司', 'gram'].includes(unit) || (unit === 'kg' && comm.id === 'silver');

    const toggleUnit = () => {
        if (displayUnit === 'g' || displayUnit === 'gram') {
            setDisplayUnit('oz');
        } else if (displayUnit === 'oz' || displayUnit === '盎司') {
            setDisplayUnit('g');
        } else if (displayUnit === 'kg') {
            setDisplayUnit('oz'); // Special case for Silver if it comes in kg
        }
    };

    // Helper to convert value based on current displayUnit vs original unit
    const convertValue = (val) => {
        if (!val) return 0;
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

        // Convert FROM 'kg' TO 'oz' (1 kg = 1000 g = 32.1507 oz)
        if (unit === 'kg' && (displayUnit === 'oz' || displayUnit === '盎司')) {
            return (numVal * 1000) / GRAMS_PER_OUNCE;
        }

        return numVal;
    };

    const displayedPrice = convertValue(currentPrice);
    const displayedHistory = historyData.map(item => ({
        ...item,
        price: convertValue(item.price)
    }));

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
                        >
                            <ExternalLink size={12} />
                            {new URL(realItem.url).hostname}
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

                    {/* Unit Switch */}
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
                        >
                            <ArrowRightLeft size={10} />
                            Switch to {displayUnit === 'oz' ? 'g' : 'oz'}
                        </button>
                    )}
                </div>
            </div>

            <div style={{ height: '350px' }}>
                <CommodityChart
                    data={displayedHistory}
                    color={comm.color}
                    name={comm.name}
                    currencySymbol={currencySymbol}
                />
            </div>
        </div>
    );
};

export default CommodityCard;
