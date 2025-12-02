"""
TrendRadar 爬虫模块
支持配置驱动的网页数据爬取
"""
from .base import BaseScraper
from .factory import ScraperFactory

__all__ = ['BaseScraper', 'ScraperFactory']
