import React, { useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { ArrowRightLeft } from 'lucide-react';

// Conversion constants
const GRAMS_PER_OUNCE = 31.1034768;

const CommodityChart = ({
    data,
    color,
    name,
    currencySymbol,
    height = '350px',
    unit = '',           // Original unit from data
    showUnitSwitch = true // Whether to show unit conversion switch
}) => {
    // State for chart-level unit conversion (independent of card)
    const [chartUnit, setChartUnit] = useState(unit);

    // Check if this commodity supports oz/g conversion
    const canConvert = useMemo(() => {
        return ['g', 'oz', '盎司', 'gram', 'kg'].includes(unit);
    }, [unit]);

    // Toggle between units
    const toggleChartUnit = () => {
        if (chartUnit === 'g' || chartUnit === 'gram') {
            setChartUnit('oz');
        } else if (chartUnit === 'oz' || chartUnit === '盎司') {
            setChartUnit('g');
        } else if (chartUnit === 'kg') {
            // kg can toggle between kg and oz
            setChartUnit('oz');
        }
    };

    // Convert value based on original unit and display unit
    const convertValue = (val) => {
        if (!val || !canConvert) return val;
        const numVal = parseFloat(val);

        if (unit === chartUnit) return numVal;

        // FROM 'g' TO 'oz'
        if ((unit === 'g' || unit === 'gram') && (chartUnit === 'oz' || chartUnit === '盎司')) {
            return numVal / GRAMS_PER_OUNCE;
        }

        // FROM 'oz' TO 'g'
        if ((unit === 'oz' || unit === '盎司') && (chartUnit === 'g' || chartUnit === 'gram')) {
            return numVal * GRAMS_PER_OUNCE;
        }

        // FROM 'kg' TO 'oz'
        if (unit === 'kg' && (chartUnit === 'oz' || chartUnit === '盎司')) {
            return (numVal * 1000) / GRAMS_PER_OUNCE;
        }

        return numVal;
    };

    // Get target unit text for switch button
    const getTargetUnit = () => {
        if (chartUnit === 'oz' || chartUnit === '盎司') return 'g';
        if (chartUnit === 'g' || chartUnit === 'gram' || chartUnit === 'kg') return 'oz';
        return '';
    };

    // Convert data for display
    const displayData = useMemo(() => {
        return data.map(item => ({
            ...item,
            price: convertValue(item.price)
        }));
    }, [data, chartUnit, unit]);

    const dates = displayData.map(item => item.date);
    const prices = displayData.map(item => item.price);

    // Display unit for labels
    const displayUnitLabel = chartUnit || unit;

    const option = {
        tooltip: {
            trigger: 'axis',
            formatter: function (params) {
                const date = params[0].name;
                const value = params[0].value;
                const unitSuffix = displayUnitLabel ? `/${displayUnitLabel}` : '';
                return `${date}<br/>${params[0].marker} ${name}: <b>${currencySymbol}${parseFloat(value).toFixed(2)}${unitSuffix}</b>`;
            },
            backgroundColor: 'rgba(255, 255, 255, 0.9)',
            borderColor: '#eee',
            borderWidth: 1,
            textStyle: {
                color: '#333'
            }
        },
        grid: {
            left: '3%',
            right: '4%',
            bottom: '3%',
            containLabel: true,
            top: '10%'
        },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: dates,
            axisLine: {
                show: false
            },
            axisTick: {
                show: false
            },
            axisLabel: {
                color: '#9ca3af',
                fontSize: 12
            }
        },
        yAxis: {
            type: 'value',
            axisLine: {
                show: false
            },
            axisTick: {
                show: false
            },
            splitLine: {
                lineStyle: {
                    color: '#f3f4f6'
                }
            },
            axisLabel: {
                color: '#9ca3af',
                fontSize: 12,
                formatter: (value) => `${currencySymbol}${value.toFixed(value < 100 ? 2 : 0)}`
            },
            scale: true, // Auto scale based on min/max
            name: displayUnitLabel ? `(${displayUnitLabel})` : '',
            nameLocation: 'end',
            nameTextStyle: {
                color: '#9ca3af',
                fontSize: 11
            }
        },
        series: [
            {
                name: name,
                type: 'line',
                smooth: true,
                symbol: 'none',
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0,
                        y: 0,
                        x2: 0,
                        y2: 1,
                        colorStops: [{
                            offset: 0, color: color // 0% 处的颜色
                        }, {
                            offset: 1, color: 'rgba(255, 255, 255, 0)' // 100% 处的颜色
                        }],
                        global: false // 缺省为 false
                    },
                    opacity: 0.2
                },
                lineStyle: {
                    color: color,
                    width: 3
                },
                itemStyle: {
                    color: color
                },
                data: prices
            }
        ]
    };

    return (
        <div style={{ position: 'relative', width: '100%' }}>
            {/* Unit Switch Button - positioned at top right of chart */}
            {showUnitSwitch && canConvert && (
                <div style={{
                    position: 'absolute',
                    top: '5px',
                    right: '10px',
                    zIndex: 10
                }}>
                    <button
                        onClick={toggleChartUnit}
                        style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '4px 10px',
                            borderRadius: '6px',
                            border: '1px solid #e5e7eb',
                            background: '#fff',
                            fontSize: '12px',
                            color: '#4b5563',
                            cursor: 'pointer',
                            boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                            transition: 'all 0.2s ease'
                        }}
                        onMouseOver={(e) => {
                            e.currentTarget.style.background = '#f3f4f6';
                            e.currentTarget.style.borderColor = '#0284c7';
                        }}
                        onMouseOut={(e) => {
                            e.currentTarget.style.background = '#fff';
                            e.currentTarget.style.borderColor = '#e5e7eb';
                        }}
                        title={`切换到 ${getTargetUnit()}`}
                    >
                        <ArrowRightLeft size={12} />
                        <span>{chartUnit}</span>
                        <span style={{ color: '#9ca3af' }}>→</span>
                        <span style={{ color: '#0284c7', fontWeight: '500' }}>{getTargetUnit()}</span>
                    </button>
                </div>
            )}
            <ReactECharts option={option} style={{ height: height, width: '100%' }} group="commodities" />
        </div>
    );
};

export default CommodityChart;
