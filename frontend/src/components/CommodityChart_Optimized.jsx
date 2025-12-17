import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';

const CommodityChart = ({
    data,
    multiSourceData,
    color,
    name,
    currencySymbol,
    height = '360px',
    unit = '',
    displayUnit = '',
    currency = 'USD'
}) => {
    const displayUnitLabel = displayUnit || unit;

    const { dates, seriesList } = useMemo(() => {
        if (multiSourceData && multiSourceData.length > 0) {
            const allDates = new Set();
            multiSourceData.forEach(source => {
                source.data.forEach(item => allDates.add(item.date));
            });
            const sortedDates = Array.from(allDates).sort();

            const series = multiSourceData.map((source, idx) => {
                const dataMap = {};
                source.data.forEach(item => {
                    dataMap[item.date] = item.price;
                });
                return {
                    name: source.source || `来源${idx + 1}`,
                    type: 'line',
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 6,
                    lineStyle: {
                        color: source.color,
                        width: 3
                    },
                    itemStyle: {
                        color: source.color
                    },
                    emphasis: {
                        focus: 'series',
                        lineStyle: {
                            width: 4
                        },
                        itemStyle: {
                            borderColor: source.color,
                            borderWidth: 2,
                            shadowBlur: 10,
                            shadowColor: source.color
                        }
                    },
                    data: sortedDates.map(date => dataMap[date] ?? null)
                };
            });

            return { dates: sortedDates, seriesList: series };
        } else if (data && data.length > 0) {
            return {
                dates: data.map(item => item.date),
                seriesList: [{
                    name: name,
                    type: 'line',
                    smooth: true,
                    symbol: 'circle',
                    symbolSize: 0,
                    areaStyle: {
                        color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [
                                { offset: 0, color: color + 'dd' },
                                { offset: 1, color: color + '00' }
                            ]
                        },
                        opacity: 0.3
                    },
                    lineStyle: { 
                        color: color, 
                        width: 3
                    },
                    itemStyle: { 
                        color: color 
                    },
                    emphasis: {
                        lineStyle: {
                            width: 4
                        },
                        itemStyle: {
                            borderColor: color,
                            borderWidth: 2,
                            shadowBlur: 10,
                            shadowColor: color,
                            symbolSize: 8
                        }
                    },
                    data: data.map(item => item.price)
                }]
            };
        }
        return { dates: [], seriesList: [] };
    }, [data, multiSourceData, name, color]);

    const hasMultiSource = multiSourceData && multiSourceData.length > 1;

    const option = {
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'cross',
                crossStyle: {
                    color: '#999'
                },
                lineStyle: {
                    type: 'dashed',
                    color: '#aaa'
                }
            },
            formatter: function (params) {
                const date = params[0].name;
                const unitSuffix = displayUnitLabel ? `/${displayUnitLabel}` : '';
                let html = `<div style="font-weight:700;margin-bottom:8px;font-size:14px;color:#111">${date}</div>`;
                params.forEach(p => {
                    if (p.value !== null && p.value !== undefined) {
                        html += `<div style="display:flex;justify-content:space-between;gap:24px;margin-top:6px">`;
                        html += `<span style="display:flex;align-items:center;gap:6px;font-size:13px;font-weight:500">${p.marker} ${p.seriesName}</span>`;
                        html += `<b style="font-size:14px;color:#111">${currencySymbol}${parseFloat(p.value).toFixed(2)}${unitSuffix}</b>`;
                        html += `</div>`;
                    }
                });
                return html;
            },
            backgroundColor: 'rgba(255, 255, 255, 0.96)',
            borderColor: '#e5e7eb',
            borderWidth: 1,
            padding: [12, 16],
            textStyle: { 
                color: '#333', 
                fontSize: 13 
            },
            shadowBlur: 10,
            shadowColor: 'rgba(0, 0, 0, 0.1)'
        },
        legend: hasMultiSource ? {
            show: true,
            type: 'scroll',
            bottom: 0,
            left: 'center',
            selectedMode: 'multiple',
            icon: 'roundRect',
            itemWidth: 16,
            itemHeight: 16,
            itemGap: 18,
            textStyle: { 
                fontSize: 13, 
                color: '#374151',
                padding: [0, 0, 0, 6],
                fontWeight: '500'
            },
            inactiveColor: '#d1d5db',
            tooltip: {
                show: true,
                formatter: (params) => `点击切换显示: ${params.name}`
            },
            emphasis: {
                selectorLabel: {
                    show: true
                }
            },
            pageButtonItemGap: 5,
            pageIconColor: '#0284c7',
            pageIconInactiveColor: '#d1d5db',
            pageTextStyle: {
                color: '#6b7280',
                fontSize: 12
            }
        } : { show: false },
        grid: {
            left: '3%',
            right: '4%',
            bottom: hasMultiSource ? '18%' : '5%',
            top: '12%',
            containLabel: true
        },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: dates,
            axisLine: { 
                show: true,
                lineStyle: {
                    color: '#e5e7eb'
                }
            },
            axisTick: { 
                show: false 
            },
            axisLabel: { 
                color: '#9ca3af', 
                fontSize: 13,
                fontWeight: '500',
                margin: 12
            },
            splitLine: {
                show: false
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
                    color: '#f3f4f6',
                    type: 'dashed'
                } 
            },
            axisLabel: {
                color: '#9ca3af',
                fontSize: 13,
                fontWeight: '500',
                formatter: (value) => {
                    if (value >= 1000000) {
                        return `${currencySymbol}${(value / 1000000).toFixed(1)}M`;
                    } else if (value >= 1000) {
                        return `${currencySymbol}${(value / 1000).toFixed(1)}K`;
                    } else if (value < 100) {
                        return `${currencySymbol}${value.toFixed(2)}`;
                    } else {
                        return `${currencySymbol}${value.toFixed(0)}`;
                    }
                }
            },
            scale: true,
            name: displayUnitLabel ? `单位: ${displayUnitLabel}` : '',
            nameLocation: 'end',
            nameGap: 12,
            nameTextStyle: { 
                color: '#9ca3af', 
                fontSize: 12,
                fontWeight: '600',
                padding: [0, 0, 6, 0]
            }
        },
        series: seriesList,
        animationDuration: 800,
        animationEasing: 'cubicOut'
    };

    return (
        <ReactECharts 
            option={option} 
            style={{ height: height, width: '100%' }} 
            group="commodities"
            opts={{ 
                renderer: 'canvas',
                locale: 'ZH'
            }}
        />
    );
};

export default CommodityChart;
