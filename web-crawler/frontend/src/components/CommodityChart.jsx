import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';

// Multi-source chart component - supports multiple data series from different sources
const CommodityChart = ({
    data,              // Single source data (legacy)
    multiSourceData,   // Array of {source, color, data, url} for multi-source display
    color,
    name,
    currencySymbol,
    height = '280px',
    unit = '',
    displayUnit = '',
    currency = 'USD'
}) => {
    const displayUnitLabel = displayUnit || unit;

    // Prepare series data
    const { dates, seriesList, minValue, maxValue } = useMemo(() => {
        let allValues = [];

        if (multiSourceData && multiSourceData.length > 0) {
            const allDates = new Set();
            multiSourceData.forEach(source => {
                source.data.forEach(item => {
                    allDates.add(item.date);
                    if (item.price && !isNaN(item.price)) {
                        allValues.push(item.price);
                    }
                });
            });
            const sortedDates = Array.from(allDates).sort();

            const series = multiSourceData.map((source, idx) => {
                const dataMap = {};
                source.data.forEach(item => {
                    if (item.date) {
                        dataMap[item.date] = parseFloat(item.price);
                    }
                });

                // Debug log
                if (name && (name.includes('palladium') || name.includes('platinum') || name.includes('钯') || name.includes('铂'))) {
                    console.log(`📈 [Chart:${name}] Source ${idx} data points:`, source.data.length);
                }

                return {
                    name: source.source || `来源${idx + 1}`,
                    type: 'line',
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 5,
                    showSymbol: false,
                    emphasis: {
                        focus: 'series',
                        itemStyle: {
                            shadowBlur: 10,
                            shadowColor: 'rgba(0, 0, 0, 0.3)'
                        }
                    },
                    lineStyle: {
                        color: source.color,
                        width: 2.5
                    },
                    itemStyle: {
                        color: source.color,
                        borderWidth: 2,
                        borderColor: '#fff'
                    },
                    areaStyle: {
                        color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [
                                { offset: 0, color: source.color + '30' },
                                { offset: 1, color: source.color + '05' }
                            ]
                        }
                    },
                    data: sortedDates.map(date => {
                        const val = dataMap[date];
                        return val !== undefined && !isNaN(val) ? val : null;
                    })
                };
            });

            const min = allValues.length > 0 ? Math.min(...allValues) : 0;
            const max = allValues.length > 0 ? Math.max(...allValues) : 100;

            return { dates: sortedDates, seriesList: series, minValue: min, maxValue: max };
        } else if (data && data.length > 0) {
            data.forEach(item => {
                if (item.price && !isNaN(item.price)) {
                    allValues.push(item.price);
                }
            });

            const min = allValues.length > 0 ? Math.min(...allValues) : 0;
            const max = allValues.length > 0 ? Math.max(...allValues) : 100;

            return {
                dates: data.map(item => item.date),
                seriesList: [{
                    name: name,
                    type: 'line',
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 5,
                    showSymbol: false,
                    emphasis: {
                        focus: 'series',
                        itemStyle: {
                            shadowBlur: 10,
                            shadowColor: 'rgba(0, 0, 0, 0.3)'
                        }
                    },
                    lineStyle: {
                        color: color,
                        width: 3,
                        shadowColor: 'rgba(0, 0, 0, 0.1)',
                        shadowBlur: 10,
                        shadowOffsetY: 5
                    },
                    itemStyle: {
                        color: color,
                        borderWidth: 2,
                        borderColor: '#fff'
                    },
                    areaStyle: {
                        color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [
                                { offset: 0, color: color + '40' },
                                { offset: 1, color: color + '05' }
                            ]
                        }
                    },
                    data: data.map(item => item.price)
                }],
                minValue: min,
                maxValue: max
            };
        }

        // Default return for empty data
        return {
            dates: [],
            seriesList: [],
            minValue: 0,
            maxValue: 100
        };
    }, [data, multiSourceData, color, name]);

    const hasMultiSource = multiSourceData && multiSourceData.length > 1;

    // 计算Y轴范围，增加10%的padding
    const yAxisPadding = (maxValue - minValue) * 0.1 || 1;
    const yMin = Math.max(0, minValue - yAxisPadding);
    const yMax = maxValue + yAxisPadding;

    const option = {
        animation: true,
        animationDuration: 500,
        tooltip: {
            trigger: 'axis',
            backgroundColor: 'rgba(255, 255, 255, 0.98)',
            borderColor: '#e5e7eb',
            borderWidth: 1,
            padding: [12, 16],
            textStyle: {
                color: '#374151',
                fontSize: 12
            },
            formatter: function (params) {
                if (!params || params.length === 0) return '';
                let date = params[0].axisValue;
                // Format date if it's long ISO string
                if (date && typeof date === 'string' && date.length > 10) {
                    date = date.substring(0, 10);
                }

                const unitSuffix = displayUnitLabel ? `/${displayUnitLabel}` : '';
                let html = `<div style="font-weight:600;margin-bottom:8px;color:#111827;font-size:13px">${date}</div>`;
                params.forEach(p => {
                    if (p.value !== null && p.value !== undefined && !isNaN(p.value)) {
                        html += `<div style="display:flex;justify-content:space-between;align-items:center;gap:24px;margin:4px 0">`;
                        html += `<span style="display:flex;align-items:center;gap:6px">${p.marker}<span style="color:#6b7280">${p.seriesName}</span></span>`;
                        html += `<span style="font-weight:600;color:#111827">${currencySymbol}${parseFloat(p.value).toFixed(2)}${unitSuffix}</span>`;
                        html += `</div>`;
                    }
                });
                return html;
            },
            axisPointer: {
                type: 'cross',
                crossStyle: {
                    color: '#9ca3af'
                },
                lineStyle: {
                    color: '#e5e7eb',
                    width: 1,
                    type: 'dashed'
                }
            }
        },
        legend: hasMultiSource ? {
            show: true,
            type: 'scroll',
            bottom: 0,
            left: 'center',
            selectedMode: 'multiple',
            icon: 'circle',
            itemWidth: 10,
            itemHeight: 10,
            itemGap: 20,
            textStyle: {
                fontSize: 11,
                color: '#6b7280',
                padding: [0, 0, 0, 4]
            },
            inactiveColor: '#d1d5db'
        } : { show: false },
        grid: {
            left: '8px',
            right: '16px',
            bottom: hasMultiSource ? '40px' : '8px',
            top: '16px',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: dates,
            axisLine: {
                show: true,
                lineStyle: {
                    color: '#f3f4f6'
                }
            },
            axisTick: { show: false },
            axisLabel: {
                color: '#9ca3af',
                fontSize: 11,
                margin: 12,
                formatter: (value) => {
                    // Format date to YYYY-MM-DD
                    if (value && typeof value === 'string' && value.length > 10) {
                        return value.substring(0, 10);
                    }
                    return value;
                }
            }
        },
        yAxis: {
            type: 'value',
            min: yMin,
            max: yMax,
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine: {
                lineStyle: {
                    color: '#f3f4f6',
                    type: 'dashed'
                }
            },
            axisLabel: {
                color: '#9ca3af',
                fontSize: 11,
                formatter: (value) => {
                    if (value >= 10000) {
                        return `${currencySymbol}${(value / 1000).toFixed(0)}k`;
                    } else if (value >= 1000) {
                        return `${currencySymbol}${value.toFixed(0)}`;
                    } else if (value >= 100) {
                        return `${currencySymbol}${value.toFixed(0)}`;
                    } else if (value >= 1) {
                        return `${currencySymbol}${value.toFixed(1)}`;
                    } else {
                        return `${currencySymbol}${value.toFixed(2)}`;
                    }
                }
            },
            scale: false
        },
        series: seriesList
    };

    // 如果没有数据，显示空状态
    if (seriesList.length === 0 || dates.length === 0) {
        return (
            <div style={{
                height: height,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#9ca3af',
                fontSize: '13px',
                background: '#fafafa',
                borderRadius: '8px'
            }}>
                暂无数据
            </div>
        );
    }

    return (
        <ReactECharts
            option={option}
            style={{ height: height, width: '100%' }}
            group="commodities"
            notMerge={true}
            lazyUpdate={true}
        />
    );
};

export default CommodityChart;
