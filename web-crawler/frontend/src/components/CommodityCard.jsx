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

// 农产品单位转换常数
// 蒲式耳(Bushel)是美国农产品标准单位
// 不同商品每蒲式耳重量不同:
const BUSHEL_TO_METRIC_TON = {
    wheat: 0.02721,    // 小麦: 1蒲式耳 ≈ 27.21 kg = 0.02721 吨
    corn: 0.02540,     // 玉米: 1蒲式耳 ≈ 25.40 kg = 0.02540 吨
    soybeans: 0.02722, // 大豆: 1蒲式耳 ≈ 27.22 kg = 0.02722 吨
    oats: 0.01451,     // 燕麦: 1蒲式耳 ≈ 14.51 kg = 0.01451 吨
};

// 英担(cwt - Hundredweight): 1 cwt = 45.36 kg (美国) = 0.04536 吨
const CWT_TO_METRIC_TON = 0.04536;

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
// 重要：COMEX铜以美分/磅报价，必须正确识别并转换（÷100）
const isCentsUnit = (unitStr) => {
    if (!unitStr) return false;
    const lower = unitStr.toLowerCase();
    // 检测多种美分表示方式
    return lower.includes('usc') ||
           unitStr.includes('美分') ||
           lower.includes('cent') ||
           lower.includes('¢');
};

// Check if unit contains ton (吨)
const isTonBasedUnit = (unitStr) => {
    if (!unitStr) return false;
    return unitStr.includes('吨') || unitStr.toLowerCase().includes('ton');
};

// Check if unit contains bushel (蒲式耳) - 用于美国农产品
const isBushelUnit = (unitStr) => {
    if (!unitStr) return false;
    const lower = unitStr.toLowerCase();
    return lower.includes('bushel') || lower.includes('bu') || unitStr.includes('蒲式耳');
};

// Check if unit contains hundredweight (英担/cwt) - 用于大米、牛奶
const isCwtUnit = (unitStr) => {
    if (!unitStr) return false;
    const lower = unitStr.toLowerCase();
    return lower.includes('cwt') || lower.includes('hundredweight') || unitStr.includes('英担');
};

// 工业金属列表（需要磅→吨转换）
const INDUSTRIAL_METALS = ['copper', 'aluminium', 'aluminum', 'zinc', 'nickel', 'lead', 'tin', '铜', '铝', '锌', '镍', '铅', '锡'];

// 默认汇率常量（会被props覆盖）
const DEFAULT_EXCHANGE_RATE = 7.2;

/**
 * 统一的价格格式化函数
 * 根据价格大小智能选择精度：
 * - 价格 >= 10000: 无小数位 (如 73,000)
 * - 价格 >= 100: 无小数位 (如 450)
 * - 价格 >= 1: 2位小数 (如 4.50)
 * - 价格 < 1: 4位小数 (如 0.0234)
 */
const smartFormatPrice = (price, options = {}) => {
    if (!isFinite(price)) return '0.00';

    const { forceDecimals, minDecimals = 0, maxDecimals = 4 } = options;
    const absPrice = Math.abs(price);

    let decimals;
    if (forceDecimals !== undefined) {
        decimals = forceDecimals;
    } else if (absPrice >= 10000) {
        decimals = 0;
    } else if (absPrice >= 100) {
        decimals = 0;
    } else if (absPrice >= 1) {
        decimals = 2;
    } else if (absPrice >= 0.01) {
        decimals = 4;
    } else {
        decimals = maxDecimals;
    }

    decimals = Math.max(minDecimals, Math.min(maxDecimals, decimals));
    return price.toFixed(decimals);
};

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
    // 确保汇率有效（防止传入 null 导致 NaN）
    const effectiveExchangeRate = exchangeRate || DEFAULT_EXCHANGE_RATE;

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

    /**
     * 统一价格转换函数
     *
     * 转换顺序（按用户要求）：
     * 1. 美分→美元：如果是美分(USc)，÷100
     * 2. 磅→吨：如果是磅，×2204.62（工业金属默认显示吨）
     * 3. 货币转换：CNY→USD 或 USD→CNY
     *
     * 最终目标：默认展示 USD/吨
     */
    const convertPrice = (val, itemUnit = unit) => {
        if (!val) return 0;
        let numVal = parseFloat(val);

        // 判断原始单位
        const isItemCents = isCentsUnit(itemUnit);
        const isItemPound = isPoundBasedUnit(itemUnit);
        const isItemCNY = itemUnit && (itemUnit.includes('元') || itemUnit.includes('CNY') || itemUnit.includes('RMB'));

        // ===== 步骤1: 美分→美元（÷100）=====
        // COMEX铜报价是 USc/磅，需要先转成 USD/磅
        if (isItemCents) {
            numVal = numVal / CENTS_TO_DOLLARS;
        }

        // ===== 步骤2: 磅→吨（×2204.62）=====
        // 工业金属默认显示吨，所有磅单位都要转换
        if (isItemPound && showInTons) {
            numVal = numVal * POUNDS_PER_TON;
        }

        // ===== 步骤3: 货币转换 =====
        // 默认展示美金，人民币需要除以汇率转USD
        // 如果用户选择CNY，USD需要乘以汇率转CNY
        if (currency === 'CNY' && !isItemCNY) {
            // 原价是USD，目标是CNY：乘汇率
            numVal = numVal * effectiveExchangeRate;
        } else if (currency === 'USD' && isItemCNY) {
            // 原价是CNY，目标是USD：除汇率
            numVal = numVal / effectiveExchangeRate;
        }

        // ===== 步骤4: 盎司→克（贵金属可选）=====
        if (isOunceUnit && showInGrams) {
            numVal = numVal / GRAMS_PER_OUNCE;
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

    // 转换历史数据价格
    // 转换顺序：1.美分→美元 2.磅→吨 3.货币转换 4.盎司→克
    const convertedHistoryData = useMemo(() => {
        if (!historyData) return historyData;
        return historyData.map(item => {
            let price = parseFloat(item.price) || 0;
            const itemUnit = item.unit || item.price_unit || '';

            // ===== 步骤1: 美分→美元（÷100）=====
            if (isCentsUnit(itemUnit)) {
                price = price / CENTS_TO_DOLLARS;
            }

            // ===== 步骤2: 磅→吨（×2204.62）=====
            const weightUnit = item.unit || item.weight_unit || '';
            if (weightUnit && isPoundBasedUnit(weightUnit) && showInTons) {
                price = price * POUNDS_PER_TON;
            }

            // ===== 步骤3: 货币转换 =====
            const isItemCNY = isCNYSource(item.source, itemUnit);
            if (currency === 'CNY' && !isItemCNY) {
                price = price * effectiveExchangeRate;
            } else if (currency === 'USD' && isItemCNY) {
                price = price / effectiveExchangeRate;
            }

            // ===== 步骤4: 盎司→克 =====
            if (isOunceUnit && showInGrams) {
                price = price / GRAMS_PER_OUNCE;
            }

            return { ...item, price };
        });
    }, [historyData, showInGrams, isOunceUnit, showInTons, currency, exchangeRate, unit]);

    // 转换多来源历史数据
    // 如果数据已在 Dashboard 中预转换（isConverted: true），则跳过转换
    // 否则执行转换顺序：1.美分→美元 2.磅→吨 3.货币转换 4.盎司→克
    const convertedMultiSourceHistory = useMemo(() => {
        if (!multiSourceHistory) return multiSourceHistory;
        return multiSourceHistory.map(sourceObj => {
            // 如果数据已在 Dashboard 中预转换，直接返回
            if (sourceObj.isConverted) {
                return sourceObj;
            }

            const sourceUnit = sourceObj.unit || sourceObj.price_unit || '';
            const isSourceCNY = isCNYSource(sourceObj.source, sourceUnit);
            const isSourcePound = isPoundBasedUnit(sourceUnit);
            const isSourceCents = isCentsUnit(sourceUnit);

            return {
                ...sourceObj,
                data: sourceObj.data.map(item => {
                    let price = parseFloat(item.price) || 0;

                    // ===== 步骤1: 美分→美元（÷100）=====
                    if (isSourceCents) {
                        price = price / CENTS_TO_DOLLARS;
                    }

                    // ===== 步骤2: 磅→吨（×2204.62）=====
                    if (sourceUnit && isSourcePound && showInTons) {
                        price = price * POUNDS_PER_TON;
                    }

                    // ===== 步骤3: 货币转换 =====
                    if (currency === 'CNY' && !isSourceCNY) {
                        price = price * effectiveExchangeRate;
                    } else if (currency === 'USD' && isSourceCNY) {
                        price = price / effectiveExchangeRate;
                    }

                    // ===== 步骤4: 盎司→克 =====
                    if (isOunceUnit && showInGrams) {
                        price = price / GRAMS_PER_OUNCE;
                    }

                    return { ...item, price };
                })
            };
        });
    }, [multiSourceHistory, showInGrams, isOunceUnit, showInTons, currency, exchangeRate]);

    // 计算多来源商品的平均价格
    // 转换顺序：1.美分→美元 2.磅→吨 3.货币转换
    const calculateAveragePrice = () => {
        const sources = multiSourceItems || [];
        if (sources.length === 0) {
            let price = parseFloat(currentPrice) || 0;

            // ===== 步骤1: 美分→美元（÷100）=====
            if (unit && isCentsUnit(unit)) {
                price = price / CENTS_TO_DOLLARS;
            }

            // ===== 步骤2: 磅→吨（×2204.62）=====
            if (unit && isPoundBasedUnit(unit) && showInTons) {
                price = price * POUNDS_PER_TON;
            }

            // ===== 步骤3: 货币转换 =====
            if (currency === 'CNY' && !isOriginalCNY) {
                price = price * effectiveExchangeRate;
            } else if (currency === 'USD' && isOriginalCNY) {
                price = price / effectiveExchangeRate;
            }

            return price;
        }

        if (sources.length === 1) {
            let price = parseFloat(sources[0].price || sources[0].current_price || currentPrice);
            const sourceUnit = sources[0].unit || sources[0].price_unit || '';

            // ===== 步骤1: 美分→美元（÷100）=====
            if (isCentsUnit(sourceUnit)) {
                price = price / CENTS_TO_DOLLARS;
            }

            // ===== 步骤2: 磅→吨（×2204.62）=====
            if (sourceUnit && isPoundBasedUnit(sourceUnit) && showInTons) {
                price = price * POUNDS_PER_TON;
            }

            // ===== 步骤3: 货币转换 =====
            const isSourceCNY = isCNYSource(sources[0].source, sourceUnit);
            if (currency === 'CNY' && !isSourceCNY) {
                price = price * effectiveExchangeRate;
            } else if (currency === 'USD' && isSourceCNY) {
                price = price / effectiveExchangeRate;
            }

            return price;
        }

        // 多来源：计算平均值
        // 转换顺序：1.美分→美元 2.磅→吨 3.货币转换
        let total = 0;
        let count = 0;

        sources.forEach(item => {
            let price = parseFloat(item.price || item.current_price);
            if (!isNaN(price) && price > 0) {
                const itemUnit = item.unit || item.price_unit || '';
                const priceUnit = item.price_unit || '';

                // 铜价调试日志
                const isCopper = comm.name?.toLowerCase().includes('copper') ||
                                 comm.name?.includes('铜') ||
                                 comm.id?.toLowerCase().includes('copper');
                if (isCopper) {
                    console.log(`[铜价调试] 商品: ${item.name || comm.name}, 原始价格: ${price}, 单位: ${itemUnit}, 来源: ${item.source}`);
                }

                // ===== 步骤1: 美分→美元（÷100）=====
                const needCentsConversion = isCentsUnit(itemUnit) || isCentsUnit(priceUnit);
                if (needCentsConversion) {
                    if (isCopper) {
                        console.log(`[铜价调试] 美分→美元: ${price} ÷ 100 = ${price / CENTS_TO_DOLLARS}`);
                    }
                    price = price / CENTS_TO_DOLLARS;
                }

                // ===== 步骤2: 磅→吨（×2204.62）=====
                if (itemUnit && isPoundBasedUnit(itemUnit) && showInTons) {
                    if (isCopper) {
                        console.log(`[铜价调试] 磅→吨: ${price} × ${POUNDS_PER_TON} = ${price * POUNDS_PER_TON}`);
                    }
                    price = price * POUNDS_PER_TON;
                }

                // ===== 步骤3: 货币转换 =====
                const isItemCNY = isCNYSource(item.source, itemUnit);
                let convertedPrice = price;
                if (currency === 'CNY' && !isItemCNY) {
                    convertedPrice = price * effectiveExchangeRate;
                    if (isCopper) {
                        console.log(`[铜价调试] USD→CNY: ${price} × ${effectiveExchangeRate} = ${convertedPrice}`);
                    }
                } else if (currency === 'USD' && isItemCNY) {
                    convertedPrice = price / effectiveExchangeRate;
                    if (isCopper) {
                        console.log(`[铜价调试] CNY→USD: ${price} ÷ ${effectiveExchangeRate} = ${convertedPrice}`);
                    }
                }

                if (isCopper) {
                    console.log(`[铜价调试] 最终价格: ${convertedPrice}`);
                }

                total += convertedPrice;
                count++;
            }
        });

        // 安全返回：确保不返回 undefined 或 NaN
        if (count > 0) {
            const avgValue = total / count;
            return isFinite(avgValue) ? avgValue : 0;
        }
        // currentPrice 可能为 undefined，需要安全处理
        const fallbackPrice = parseFloat(currentPrice);
        return isFinite(fallbackPrice) ? fallbackPrice : 0;
    };

    const avgPrice = calculateAveragePrice();
    // 单位转换（盎司→克）在求平均值之后完成
    // 注意：磅→吨转换已在 calculateAveragePrice 中完成
    const displayedPrice = isOunceUnit && showInGrams
        ? (isFinite(avgPrice) ? avgPrice / GRAMS_PER_OUNCE : 0)
        : (isFinite(avgPrice) ? avgPrice : 0);
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
                            {isUp ? '+' : ''}{smartFormatPrice(parseFloat(change), { forceDecimals: 2 })}%
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
                        {currencySymbol}{smartFormatPrice(displayedPrice)}
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

// 导出工具函数供其他组件使用
export { smartFormatPrice, isCentsUnit, isPoundBasedUnit, isOunceBasedUnit, isTonBasedUnit };
