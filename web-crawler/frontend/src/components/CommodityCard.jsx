import React, { useState, useMemo } from 'react';
import CommodityChart from './CommodityChart';
import { ExternalLink, TrendingUp, TrendingDown } from 'lucide-react';

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

// Extract pure weight unit from unit string
const extractWeightUnit = (unitStr) => {
    if (!unitStr) return '';
    let cleanUnit = unitStr
        .replace(/USD|CNY|RMB|美元|人民币/gi, '')
        .replace(/[$¥/]/g, '')
        .trim();

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

// 默认汇率常量（会被props覆盖）
const DEFAULT_EXCHANGE_RATE = 7.2;

const CommodityCard = ({
    comm,
    realItem,
    multiSourceItems,
    currentPrice,
    unit,
    historyData,
    multiSourceHistory,
    currencySymbol,
    formatPrice,
    isLastOdd,
    currency = 'USD',
    exchangeRate = DEFAULT_EXCHANGE_RATE
}) => {
    const pureUnit = extractWeightUnit(unit);
    const isOunceUnit = isOunceBasedUnit(unit);
    const [showInGrams, setShowInGrams] = useState(false);
    const displayUnit = isOunceUnit ? (showInGrams ? 'g' : 'oz') : pureUnit;

    // 判断原始价格是否为人民币（根据单位判断）
    const isOriginalCNY = unit && (unit.includes('元') || unit.includes('CNY') || unit.includes('RMB'));

    // 货币转换函数
    const convertPrice = (val) => {
        if (!val) return 0;
        let numVal = parseFloat(val);

        // 货币转换逻辑:
        // - 如果原始价格是CNY（元），目标是USD：除以汇率
        // - 如果原始价格是USD，目标是CNY：乘以汇率
        if (currency === 'CNY' && !isOriginalCNY) {
            // 原价是USD，转换为CNY
            numVal = numVal * exchangeRate;
        } else if (currency === 'USD' && isOriginalCNY) {
            // 原价是CNY，转换为USD
            numVal = numVal / exchangeRate;
        }

        // 单位转换（盎司转克）
        if (isOunceUnit && showInGrams) {
            numVal = numVal / GRAMS_PER_OUNCE;
        }
        return numVal;
    };

    // 转换历史数据价格（同时进行货币转换和单位转换）
    const convertedHistoryData = useMemo(() => {
        if (!historyData) return historyData;
        return historyData.map(item => {
            let price = parseFloat(item.price) || 0;

            // 货币转换
            if (currency === 'CNY' && !isOriginalCNY) {
                price = price * exchangeRate;
            } else if (currency === 'USD' && isOriginalCNY) {
                price = price / exchangeRate;
            }

            // 单位转换（盎司转克）
            if (isOunceUnit && showInGrams) {
                price = price / GRAMS_PER_OUNCE;
            }
            return { ...item, price };
        });
    }, [historyData, showInGrams, isOunceUnit, currency, exchangeRate, isOriginalCNY]);

    const convertedMultiSourceHistory = useMemo(() => {
        if (!multiSourceHistory) return multiSourceHistory;
        return multiSourceHistory.map(source => ({
            ...source,
            data: source.data.map(item => {
                let price = parseFloat(item.price) || 0;

                // 货币转换
                if (currency === 'CNY' && !isOriginalCNY) {
                    price = price * exchangeRate;
                } else if (currency === 'USD' && isOriginalCNY) {
                    price = price / exchangeRate;
                }

                // 单位转换
                if (isOunceUnit && showInGrams) {
                    price = price / GRAMS_PER_OUNCE;
                }
                return { ...item, price };
            })
        }));
    }, [multiSourceHistory, showInGrams, isOunceUnit, currency, exchangeRate, isOriginalCNY]);

    // 计算多来源商品的平均价格（在货币转换之前）
    const calculateAveragePrice = () => {
        const sources = multiSourceItems || [];
        if (sources.length === 0) {
            return currentPrice; // 无来源数据，使用传入的默认值
        }

        if (sources.length === 1) {
            return sources[0].price || sources[0].current_price || currentPrice;
        }

        // 多来源：计算平均值
        let total = 0;
        let count = 0;

        sources.forEach(item => {
            const price = parseFloat(item.price || item.current_price);
            if (!isNaN(price) && price > 0) {
                // 判断该来源的原始货币
                const itemUnit = item.unit || '';
                const isItemCNY = itemUnit.includes('元') || itemUnit.includes('CNY') || itemUnit.includes('RMB');

                // 根据目标货币进行转换后累加
                let convertedPrice = price;
                if (currency === 'CNY' && !isItemCNY) {
                    convertedPrice = price * exchangeRate;
                } else if (currency === 'USD' && isItemCNY) {
                    convertedPrice = price / exchangeRate;
                }

                total += convertedPrice;
                count++;
            }
        });

        return count > 0 ? total / count : currentPrice;
    };

    const avgPrice = calculateAveragePrice();
    // 单位转换（盎司→克）在求平均值之后完成
    const displayedPrice = isOunceUnit && showInGrams
        ? avgPrice / GRAMS_PER_OUNCE
        : avgPrice;
    // 为 Oil (WTI) 注入固定来源 URL
    let computedSources = multiSourceItems || (realItem ? [realItem] : []);
    if (comm.name.includes('WTI') || comm.name.includes('原油')) {
        // 创建一个 Map 以便按名称更新或添加来源
        const sourceMap = new Map();

        // 1. 初始化现有来源
        computedSources.forEach(s => {
            const host = safeGetHostname(s.url) || s.source || 'Unknown';
            sourceMap.set(s.source || host, { ...s });
        });

        // 2. 注入或更新特定来源
        // 中塑在线
        if (!sourceMap.has('中塑在线')) {
            sourceMap.set('中塑在线', {
                source: '中塑在线',
                url: 'https://quote.21cp.com/crude_centre/list/158651161505726464--.html'
            });
        }

        // 新浪期货
        if (!sourceMap.has('新浪期货')) {
            sourceMap.set('新浪期货', {
                source: '新浪期货',
                url: 'https://finance.sina.com.cn/futures/quotes/hf_CL.shtml'
            });
        } else {
            // 确保 URL 正确
            const existing = sourceMap.get('新浪期货');
            if (!existing.url) existing.url = 'https://finance.sina.com.cn/futures/quotes/hf_CL.shtml';
        }

        // Business Insider
        // 查找现有的 Business Insider 条目（可能是 hostname）
        let biKey = Array.from(sourceMap.keys()).find(k => k.includes('businessinsider'));
        if (!biKey) {
            sourceMap.set('Business Insider', {
                source: 'Business Insider',
                url: 'https://markets.businessinsider.com/commodities/oil-(brent)'
            });
        } else {
            // 如果存在，确保 url 正确（如果原 url 为空）
            const existing = sourceMap.get(biKey);
            if (!existing.url) existing.url = 'https://markets.businessinsider.com/commodities/oil-(brent)';
        }

        // 重新转换为数组
        computedSources = Array.from(sourceMap.values());
    }

    const sources = computedSources;
    const change = comm.change || realItem?.change || realItem?.change_percent || 0;
    const isUp = parseFloat(change) >= 0;

    // Debug logging for Palladium/Platinum
    if (comm.id === 'palladium' || comm.id === 'platinum') {
        console.log(`🃏 [Card:${comm.id}] Props:`, {
            hasHistoryData: !!historyData,
            historyDataLength: historyData?.length,
            hasMultiSourceHistory: !!multiSourceHistory,
            multiSourceHistoryLength: multiSourceHistory?.length,
            pureUnit,
            displayUnit
        });
        if (multiSourceHistory && multiSourceHistory.length > 0) {
            console.log(`🃏 [Card:${comm.id}] First Source Data Sample:`, multiSourceHistory[0].data?.slice(0, 3));
        }
    }

    return (
        <div className="commodity-card-wrapper" style={{
            background: '#fff',
            padding: '20px',
            borderRadius: '12px',
            boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
            border: '1px solid #f3f4f6',
            gridColumn: isLastOdd ? 'span 2' : 'auto',
            position: 'relative',
            transition: 'box-shadow 0.2s ease'
        }}>
            {/* Header */}
            <div className="card-header" style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                marginBottom: '16px',
                gap: '12px'
            }}>
                <div className="title-container" style={{ flex: 1, minWidth: 0 }}>
                    <div className="title-row" style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                        <span style={{
                            width: '10px',
                            height: '10px',
                            borderRadius: '50%',
                            background: comm.color,
                            flexShrink: 0
                        }}></span>
                        <h3 style={{
                            margin: 0,
                            fontSize: '15px',
                            fontWeight: '600',
                            color: '#111827',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis'
                        }}>
                            {comm.name}
                        </h3>
                        {/* 涨跌指示 */}
                        <span style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '2px',
                            fontSize: '11px',
                            fontWeight: '600',
                            color: isUp ? '#10b981' : '#ef4444',
                            background: isUp ? '#d1fae5' : '#fee2e2',
                            padding: '2px 6px',
                            borderRadius: '4px'
                        }}>
                            {isUp ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                            {isUp ? '+' : ''}{parseFloat(change).toFixed(2)}%
                        </span>
                    </div>

                    {/* Sources */}
                    {sources.length > 0 && (
                        <div className="sources-container" style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                            {sources.slice(0, 3).map((item, idx) => (
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
                                        background: '#f9fafb',
                                        borderRadius: '4px',
                                        border: '1px solid #f3f4f6',
                                        transition: 'all 0.15s ease'
                                    }}
                                    title={item.url}
                                    onMouseEnter={e => {
                                        e.currentTarget.style.background = '#f3f4f6';
                                        e.currentTarget.style.color = '#374151';
                                    }}
                                    onMouseLeave={e => {
                                        e.currentTarget.style.background = '#f9fafb';
                                        e.currentTarget.style.color = '#6b7280';
                                    }}
                                >
                                    <ExternalLink size={9} />
                                    {safeGetHostname(item.url)}
                                </a>
                            ))}
                            {sources.length > 3 && (
                                <span style={{
                                    fontSize: '11px',
                                    color: '#9ca3af',
                                    padding: '2px 4px'
                                }}>
                                    +{sources.length - 3}
                                </span>
                            )}
                        </div>
                    )}
                </div>

                {/* Price & Unit Toggle */}
                <div className="price-section" style={{ textAlign: 'right', flexShrink: 0 }}>
                    <div className="price-display" style={{
                        fontSize: '20px',
                        fontWeight: '700',
                        color: '#111827',
                        lineHeight: 1.2
                    }}>
                        {currencySymbol}{displayedPrice.toFixed(2)}
                        <span style={{
                            fontSize: '12px',
                            color: '#6b7280',
                            marginLeft: '4px',
                            fontWeight: '500'
                        }}>
                            /{displayUnit}
                        </span>
                    </div>

                    {/* Unit Switch - only for oz units */}
                    {isOunceUnit && (
                        <div className="unit-toggle" style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            marginTop: '8px',
                            padding: '3px',
                            background: '#fef3c7',
                            borderRadius: '6px',
                            border: '1px solid #fcd34d'
                        }}>
                            <button
                                onClick={() => setShowInGrams(false)}
                                style={{
                                    padding: '3px 10px',
                                    borderRadius: '4px',
                                    border: 'none',
                                    background: !showInGrams ? '#92400e' : 'transparent',
                                    color: !showInGrams ? '#fff' : '#92400e',
                                    fontSize: '11px',
                                    fontWeight: '600',
                                    cursor: 'pointer',
                                    transition: 'all 0.15s ease'
                                }}
                            >
                                oz
                            </button>
                            <button
                                onClick={() => setShowInGrams(true)}
                                style={{
                                    padding: '3px 10px',
                                    borderRadius: '4px',
                                    border: 'none',
                                    background: showInGrams ? '#92400e' : 'transparent',
                                    color: showInGrams ? '#fff' : '#92400e',
                                    fontSize: '11px',
                                    fontWeight: '600',
                                    cursor: 'pointer',
                                    transition: 'all 0.15s ease'
                                }}
                            >
                                g
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* Chart */}
            <div className="chart-container" style={{ height: multiSourceHistory ? '260px' : '240px' }}>
                <CommodityChart
                    data={convertedHistoryData}
                    multiSourceData={convertedMultiSourceHistory}
                    color={comm.color}
                    name={comm.name}
                    currencySymbol={currencySymbol}
                    unit={pureUnit}
                    displayUnit={displayUnit}
                    currency={currency}
                    height={multiSourceHistory ? '260px' : '240px'}
                />
            </div>
        </div>
    );
};

export default CommodityCard;
