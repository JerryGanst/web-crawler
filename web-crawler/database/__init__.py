# coding=utf-8
"""
TrendRadar 数据库模块
提供 SQLite 持久化存储和可选的 Redis 缓存
"""

from .connection import DatabaseManager, get_db
from .models import News, Platform, KeywordMatch, CrawlLog, PushRecord

__all__ = [
    'DatabaseManager',
    'get_db',
    'News',
    'Platform',
    'KeywordMatch',
    'CrawlLog',
    'PushRecord',
]
