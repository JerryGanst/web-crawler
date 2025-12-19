import React, { useEffect, useRef } from 'react';
import * as echarts from 'echarts';

const EChartsComponent = ({ data }) => {
    const chartRef = useRef(null);
    const chartInstance = useRef(null);

    useEffect(() => {
        if (chartRef.current) {
            if (!chartInstance.current) {
                chartInstance.current = echarts.init(chartRef.current);
            }

            const option = {
                tooltip: {
                    trigger: 'item',
                    formatter: '{b}: {c} ({d}%)'
                },
                legend: {
                    orient: 'horizontal',
                    bottom: 'bottom',
                    type: 'scroll'
                },
                series: [
                    {
                        name: '数据来源',
                        type: 'pie',
                        radius: ['40%', '70%'],
                        avoidLabelOverlap: false,
                        itemStyle: {
                            borderRadius: 10,
                            borderColor: '#fff',
                            borderWidth: 2
                        },
                        label: {
                            show: false,
                            position: 'center'
                        },
                        emphasis: {
                            label: {
                                show: true,
                                fontSize: '18',
                                fontWeight: 'bold'
                            }
                        },
                        labelLine: {
                            show: false
                        },
                        data: data
                    }
                ]
            };

            chartInstance.current.setOption(option);
        }

        const handleResize = () => {
            chartInstance.current?.resize();
        };
        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chartInstance.current?.dispose();
            chartInstance.current = null;
        };
    }, [data]);

    return <div ref={chartRef} style={{ width: '100%', height: '100%' }} />;
};

export default EChartsComponent;
