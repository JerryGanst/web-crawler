# coding=utf-8
"""
数据仓库模块
提供各表的 CRUD 操作
"""

from .news_repo import NewsRepository
from .platform_repo import PlatformRepository
from .log_repo import CrawlLogRepository, PushRecordRepository

__all__ = [
    'NewsRepository',
    'PlatformRepository',
    'CrawlLogRepository',
    'PushRecordRepository',
]
