"""
API 路由模块
"""
from fastapi import APIRouter

# 创建主路由
router = APIRouter()

# 导入子路由
from . import data, news, reports, analysis_v4, cache as cache_routes

# 注册子路由
router.include_router(data.router, tags=["数据"])
router.include_router(news.router, tags=["新闻"])
router.include_router(reports.router, tags=["报告"])
router.include_router(analysis_v4.router, tags=["分析"])
router.include_router(cache_routes.router, tags=["缓存"])
