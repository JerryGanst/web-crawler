import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';

// Multi-source chart component - supports multiple data series from different sources
const CommodityChart = ({
    data,              // Single source data (legacy)
    multiSourceData,   // Array of {source, color, data, url} for multi-source display
    color,
    name,
    currencySymbol,
    height = '350px',
    unit = '',
    displayUnit = ''   // Current display unit (for oz/g conversion)
}) => {
    // Use displayUnit if provided, otherwise use unit
    const displayUnitLabel = displayUnit || unit;

    // Prepare series data - support both single and multi-source
    const { dates, seriesList } = useMemo(() => {
        if (multiSourceData && multiSourceData.length > 0) {
            // Multi-source mode
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
                    symbolSize: 4,
                    lineStyle: {
                        color: source.color,
                        width: 2
                    },
                    itemStyle: {
                        color: source.color
                    },
                    data: sortedDates.map(date => dataMap[date] ?? null)
                };
            });

            return { dates: sortedDates, seriesList: series };
        } else if (data && data.length > 0) {
            // Single source mode (legacy)
            return {
                dates: data.map(item => item.date),
                seriesList: [{
                    name: name,
                    type: 'line',
                    smooth: true,
                    symbol: 'none',
                    areaStyle: {
                        color: {
                            type: 'linear',
                            x: 0, y: 0, x2: 0, y2: 1,
                            colorStops: [
                                { offset: 0, color: color },
                                { offset: 1, color: 'rgba(255, 255, 255, 0)' }
                            ]
                        },
                        opacity: 0.2
                    },
                    lineStyle: { color: color, width: 3 },
                    itemStyle: { color: color },
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
            formatter: function (params) {
                const date = params[0].name;
                const unitSuffix = displayUnitLabel ? `/${displayUnitLabel}` : '';
                let html = `<div style="font-weight:600;margin-bottom:6px">${date}</div>`;
                params.forEach(p => {
                    if (p.value !== null && p.value !== undefined) {
                        html += `<div style="display:flex;justify-content:space-between;gap:20px">`;
                        html += `${p.marker} ${p.seriesName}`;
                        html += `<b>${currencySymbol}${parseFloat(p.value).toFixed(2)}${unitSuffix}</b>`;
                        html += `</div>`;
                    }
                });
                return html;
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#e5e7eb',
            borderWidth: 1,
            padding: [10, 14],
            textStyle: { color: '#333', fontSize: 13 }
        },
        legend: hasMultiSource ? {
            show: true,
            type: 'scroll',  // Allow scrolling if too many items
            bottom: 0,
            left: 'center',
            selectedMode: 'multiple',  // Allow multiple selection (click to toggle)
            icon: 'roundRect',  // Square icon for each source
            itemWidth: 14,
            itemHeight: 14,
            itemGap: 16,
            textStyle: { 
                fontSize: 12, 
                color: '#374151',
                padding: [0, 0, 0, 4]
            },
            inactiveColor: '#d1d5db',  // Gray color when deselected
            tooltip: {
                show: true,
                formatter: (params) => `点击切换显示: ${params.name}`
            },
            emphasis: {
                selectorLabel: {
                    show: true
                }
            }
        } : { show: false },
        grid: {
            left: '3%',
            right: '4%',
            bottom: hasMultiSource ? '18%' : '3%',
            containLabel: true,
            top: '10%'
        },
        xAxis: {
            type: 'category',
            boundaryGap: false,
            data: dates,
            axisLine: { show: false },
            axisTick: { show: false },
            axisLabel: { color: '#9ca3af', fontSize: 12 }
        },
        yAxis: {
            type: 'value',
            axisLine: { show: false },
            axisTick: { show: false },
            splitLine: { lineStyle: { color: '#f3f4f6' } },
            axisLabel: {
                color: '#9ca3af',
                fontSize: 12,
                formatter: (value) => `${currencySymbol}${value.toFixed(value < 100 ? 2 : 0)}`
            },
            scale: true,
            name: displayUnitLabel ? `(${displayUnitLabel})` : '',
            nameLocation: 'end',
            nameTextStyle: { color: '#9ca3af', fontSize: 11 }
        },
        series: seriesList
    };

    return (
        <ReactECharts option={option} style={{ height: height, width: '100%' }} group="commodities" />
    );
};

export default CommodityChart;
