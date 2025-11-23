import React from 'react';
import ReactECharts from 'echarts-for-react';

const CommodityChart = ({ data, color, name, currencySymbol, height = '350px' }) => {
    const dates = data.map(item => item.date);
    const prices = data.map(item => item.price);

    const option = {
        tooltip: {
            trigger: 'axis',
            formatter: function (params) {
                const date = params[0].name;
                const value = params[0].value;
                return `${date}<br/>${params[0].marker} ${name}: <b>${currencySymbol}${parseFloat(value).toFixed(2)}</b>`;
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
                formatter: (value) => `${currencySymbol}${value}`
            },
            scale: true // Auto scale based on min/max
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

    return <ReactECharts option={option} style={{ height: height, width: '100%' }} group="commodities" />;
};

export default CommodityChart;
