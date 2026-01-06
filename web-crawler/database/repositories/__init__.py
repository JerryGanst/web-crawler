# coding=utf-8
"""
数据仓库模块
提供各表的 CRUD 操作
"""

from .news_repo import NewsRepository, MongoNewsRepository, MongoKeywordMatchRepository
from .platform_repo import PlatformRepository, MongoPlatformRepository
from .log_repo import (
    CrawlLogRepository,
    PushRecordRepository,
    MongoCrawlLogRepository,
    MongoPushRecordRepository,
)

__all__ = [
    'NewsRepository',
    'PlatformRepository',
    'CrawlLogRepository',
    'PushRecordRepository',
    'MongoNewsRepository',
    'MongoKeywordMatchRepository',
    'MongoPlatformRepository',
    'MongoCrawlLogRepository',
    'MongoPushRecordRepository',
]
