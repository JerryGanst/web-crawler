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
const POUNDS_PER_TON = 2204.62;  // 1 吨 = 2204.62 磅
const CENTS_TO_DOLLARS = 100;   // 100 美分 = 1 美元

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

// Check if unit contains pound (磅)
const isPoundBasedUnit = (unitStr) => {
    if (!unitStr) return false;
    const lower = unitStr.toLowerCase();
    return lower.includes('pound') || lower.includes('lb') || unitStr.includes('磅');
};

// Check if unit is in cents (美分/USc)
const isCentsUnit = (unitStr) => {
    if (!unitStr) return false;
    const lower = unitStr.toLowerCase();
    return lower.includes('usc') || unitStr.includes('美分') || lower.includes('cent');
};

// Check if unit contains ton (吨)
const isTonBasedUnit = (unitStr) => {
    if (!unitStr) return false;
    return unitStr.includes('吨') || unitStr.toLowerCase().includes('ton');
};

// 工业金属列表（需要磅→吨转换）
const INDUSTRIAL_METALS = ['copper', 'aluminium', 'aluminum', 'zinc', 'nickel', 'lead', 'tin', '铜', '铝', '锌', '镍', '铅', '锡'];

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
    const isPoundUnit = isPoundBasedUnit(unit);
    const isTonUnit = isTonBasedUnit(unit);

    // 判断是否为工业金属（需要统一显示为吨）
    const isIndustrialMetal = INDUSTRIAL_METALS.some(m =>
        comm.name?.toLowerCase().includes(m) || comm.id?.toLowerCase().includes(m)
    );

    const [showInGrams, setShowInGrams] = useState(false);
    // 工业金属默认显示吨，磅单位的数据需要转换
    const [showInTons, setShowInTons] = useState(isIndustrialMetal);

    // 计算显示单位
    const getDisplayUnit = () => {
        if (isOunceUnit) {
            return showInGrams ? 'g' : 'oz';
        }
        if (isPoundUnit && showInTons) {
            return '吨';
        }
        if (isTonUnit) {
            return '吨';
        }
        return pureUnit;
    };
    const displayUnit = getDisplayUnit();

    // 判断原始价格是否为人民币（根据单位判断）
    const isOriginalCNY = unit && (unit.includes('元') || unit.includes('CNY') || unit.includes('RMB'));

    // 货币转换函数
    const convertPrice = (val, itemUnit = unit) => {
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

        // 单位转换（磅转吨）- 价格 × 2204.62
        // 例如: $6/磅 × 2204.62 = $13,227.72/吨
        const isItemPound = isPoundBasedUnit(itemUnit);
        if (isItemPound && showInTons) {
            numVal = numVal * POUNDS_PER_TON;
        }

        return numVal;
    };

    // 判断数据源是否为人民币来源
    // 优化：优先使用数据的 unit/price_unit 字段，其次才是来源名称
    const isCNYSource = (source, itemUnit = null) => {
        // 优先检查单位字段
        if (itemUnit) {
            if (itemUnit.includes('元') || itemUnit.includes('CNY') || itemUnit.includes('RMB') || itemUnit.includes('￥')) {
                return true;
            }
            if (itemUnit.includes('USD') || itemUnit.includes('$') || itemUnit.includes('美元')) {
                return false;
            }
        }

        // 回退到来源名称判断（保留兼容性）
        if (!source) return false;
        const cnySources = ['上海有色网', 'SMM', '中塑在线', '21cp'];
        return cnySources.some(s => source.toLowerCase().includes(s.toLowerCase()) || s.includes(source));
    };

    // 转换历史数据价格（根据来源判断是否需要货币转换）
    const convertedHistoryData = useMemo(() => {
        if (!historyData) return historyData;
        return historyData.map(item => {
            let price = parseFloat(item.price) || 0;

            // 根据历史数据的来源和单位判断原始货币
            const itemUnit = item.unit || item.price_unit || '';

            // 1. 美分→美元转换
            if (isCentsUnit(itemUnit)) {
                price = price / CENTS_TO_DOLLARS;
            }

            // 2. 货币转换（根据数据来源而非商品单位）
            const isItemCNY = isCNYSource(item.source, itemUnit);
            if (currency === 'CNY' && !isItemCNY) {
                price = price * exchangeRate;
            } else if (currency === 'USD' && isItemCNY) {
                price = price / exchangeRate;
            }

            // 3. 单位转换（盎司转克）
            if (isOunceUnit && showInGrams) {
                price = price / GRAMS_PER_OUNCE;
            }

            // 4. 单位转换（磅转吨）
            // 重要：只有当数据项自身有明确的磅单位时才转换，不要回退到组件默认unit
            const weightUnit = item.unit || item.weight_unit || '';
            if (weightUnit && isPoundBasedUnit(weightUnit) && showInTons) {
                price = price * POUNDS_PER_TON;
            }

            return { ...item, price };
        });
    }, [historyData, showInGrams, isOunceUnit, showInTons, currency, exchangeRate, unit]);

    // 转换多来源历史数据（根据来源判断是否需要货币转换）
    const convertedMultiSourceHistory = useMemo(() => {
        if (!multiSourceHistory) return multiSourceHistory;
        return multiSourceHistory.map(sourceObj => {
            // 获取来源的单位 - 只使用数据源自身的单位，不回退到组件默认unit
            const sourceUnit = sourceObj.unit || sourceObj.price_unit || '';
            // 根据来源名称和单位判断货币类型
            const isSourceCNY = isCNYSource(sourceObj.source, sourceUnit);
            const isSourcePound = isPoundBasedUnit(sourceUnit);
            const isSourceCents = isCentsUnit(sourceUnit);

            return {
                ...sourceObj,
                data: sourceObj.data.map(item => {
                    let price = parseFloat(item.price) || 0;

                    // 1. 美分→美元转换
                    if (isSourceCents) {
                        price = price / CENTS_TO_DOLLARS;
                    }

                    // 2. 货币转换（根据来源和单位）
                    if (currency === 'CNY' && !isSourceCNY) {
                        price = price * exchangeRate;
                    } else if (currency === 'USD' && isSourceCNY) {
                        price = price / exchangeRate;
                    }

                    // 3. 单位转换（盎司转克）
                    if (isOunceUnit && showInGrams) {
                        price = price / GRAMS_PER_OUNCE;
                    }

                    // 4. 单位转换（磅转吨）
                    // 使用外层 sourceUnit（来源的单位），因为历史数据点通常没有 unit 字段
                    if (sourceUnit && isSourcePound && showInTons) {
                        price = price * POUNDS_PER_TON;
                    }

                    return { ...item, price };
                })
            };
        });
    }, [multiSourceHistory, showInGrams, isOunceUnit, showInTons, currency, exchangeRate]);

    // 计算多来源商品的平均价格（根据来源判断货币转换）
    const calculateAveragePrice = () => {
        const sources = multiSourceItems || [];
        if (sources.length === 0) {
            // 无来源数据，使用传入的默认值，但需要做货币转换
            let price = parseFloat(currentPrice) || 0;

            // 1. 美分→美元转换
            if (unit && isCentsUnit(unit)) {
                price = price / CENTS_TO_DOLLARS;
            }

            // 2. 货币转换
            if (currency === 'CNY' && !isOriginalCNY) {
                price = price * exchangeRate;
            } else if (currency === 'USD' && isOriginalCNY) {
                price = price / exchangeRate;
            }

            // 3. 磅转吨 - 只有明确知道是磅单位时才转换
            if (unit && isPoundBasedUnit(unit) && showInTons) {
                price = price * POUNDS_PER_TON;
            }
            return price;
        }

        if (sources.length === 1) {
            let price = parseFloat(sources[0].price || sources[0].current_price || currentPrice);
            // 重要：只使用数据项自身的单位，不要回退到组件默认unit
            const sourceUnit = sources[0].unit || sources[0].price_unit || '';

            // 1. 美分→美元转换
            if (isCentsUnit(sourceUnit)) {
                price = price / CENTS_TO_DOLLARS;
            }

            // 2. 使用改进的 isCNYSource 函数，优先检查单位字段
            const isSourceCNY = isCNYSource(sources[0].source, sourceUnit);

            if (currency === 'CNY' && !isSourceCNY) {
                price = price * exchangeRate;
            } else if (currency === 'USD' && isSourceCNY) {
                price = price / exchangeRate;
            }

            // 3. 磅转吨 - 只有当数据项自身有明确的磅单位时才转换
            if (sourceUnit && isPoundBasedUnit(sourceUnit) && showInTons) {
                price = price * POUNDS_PER_TON;
            }

            return price;
        }

        // 多来源：计算平均值（根据每个来源的货币类型进行转换）
        // 注意：不同来源可能使用不同单位（磅 vs 吨，美分 vs 美元），需要统一后再求平均
        let total = 0;
        let count = 0;

        sources.forEach(item => {
            let price = parseFloat(item.price || item.current_price);
            if (!isNaN(price) && price > 0) {
                const itemUnit = item.unit || item.price_unit || '';

                // 1. 首先处理美分→美元转换（COMEX铜等以美分报价的商品）
                if (isCentsUnit(itemUnit)) {
                    price = price / CENTS_TO_DOLLARS;
                }

                // 2. 使用改进的 isCNYSource 函数，优先检查单位字段
                const isItemCNY = isCNYSource(item.source, itemUnit);

                let convertedPrice = price;
                if (currency === 'CNY' && !isItemCNY) {
                    convertedPrice = price * exchangeRate;
                } else if (currency === 'USD' && isItemCNY) {
                    convertedPrice = price / exchangeRate;
                }

                // 3. 磅转吨（统一单位后再求平均）
                // 重要：只有当数据项自身有明确的磅单位时才转换
                if (itemUnit && isPoundBasedUnit(itemUnit) && showInTons) {
                    // 磅→吨: 价格 × 2204.62
                    convertedPrice = convertedPrice * POUNDS_PER_TON;
                }
                // 吨单位的数据无需转换

                total += convertedPrice;
                count++;
            }
        });

        return count > 0 ? total / count : currentPrice;
    };

    const avgPrice = calculateAveragePrice();
    // 单位转换（盎司→克）在求平均值之后完成
    // 注意：磅→吨转换已在 calculateAveragePrice 中完成
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

                    {/* Unit Switch - for pound/ton units (industrial metals) */}
                    {isPoundUnit && isIndustrialMetal && (
                        <div className="unit-toggle" style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            marginTop: '8px',
                            padding: '3px',
                            background: '#dbeafe',
                            borderRadius: '6px',
                            border: '1px solid #93c5fd'
                        }}>
                            <button
                                onClick={() => setShowInTons(false)}
                                style={{
                                    padding: '3px 10px',
                                    borderRadius: '4px',
                                    border: 'none',
                                    background: !showInTons ? '#1e40af' : 'transparent',
                                    color: !showInTons ? '#fff' : '#1e40af',
                                    fontSize: '11px',
                                    fontWeight: '600',
                                    cursor: 'pointer',
                                    transition: 'all 0.15s ease'
                                }}
                            >
                                磅
                            </button>
                            <button
                                onClick={() => setShowInTons(true)}
                                style={{
                                    padding: '3px 10px',
                                    borderRadius: '4px',
                                    border: 'none',
                                    background: showInTons ? '#1e40af' : 'transparent',
                                    color: showInTons ? '#fff' : '#1e40af',
                                    fontSize: '11px',
                                    fontWeight: '600',
                                    cursor: 'pointer',
                                    transition: 'all 0.15s ease'
                                }}
                            >
                                吨
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
