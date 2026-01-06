"""
API 模块
"""
from . import cache as cache_module
from .cache import RedisCache, CACHE_TTL
from .models import CrawlRequest, PushRequest, ReportPushRequest, AnalysisRequest

# 对外暴露缓存实例但保持 api.cache 指向模块，便于打补丁
cache_instance = cache_module.cache

__all__ = [
    'RedisCache',
    'CACHE_TTL',
    'cache_instance',
    'CrawlRequest',
    'PushRequest',
    'ReportPushRequest',
    'AnalysisRequest'
]
