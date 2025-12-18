# coding=utf-8
"""
高级数据分析工具模块
提供热度趋势分析、平台对比、关键词共现、情感分析等高级分析功能
"""

from .trend_analyzer import TrendAnalyzer
from .platform_analyzer import PlatformAnalyzer
from .keyword_analyzer import KeywordAnalyzer
from .weight_calculator import calculate_news_weight
from .tools import AnalyticsTools

__all__ = [
    'TrendAnalyzer',
    'PlatformAnalyzer', 
    'KeywordAnalyzer',
    'calculate_news_weight',
    'AnalyticsTools',
]
