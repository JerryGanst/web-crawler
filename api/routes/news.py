"""
新闻相关 API 路由

优化策略：缓存优先 + 后台异步刷新
- 用户请求时立即返回缓存数据（<50ms）
- 刷新操作在后台异步执行
- 下次请求获得新数据
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from datetime import datetime
from typing import Dict
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

from ..cache import cache, CACHE_TTL
from ..models import CrawlRequest

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent.parent

# 后台任务线程池
_executor = ThreadPoolExecutor(max_workers=3)

# 进行中的后台任务跟踪（避免重复刷新）
_pending_refreshes = set()

# 供应链关键词
SUPPLY_CHAIN_KEYWORDS = [
    "立讯", "歌尔", "蓝思", "富联", "富士康", "京东方", "BOE",
    "欣旺达", "德赛", "舜宇", "鹏鼎", "东山精密", "领益", "瑞声",
    "苹果", "Apple", "iPhone", "AirPods", "Vision Pro", "iPad", "Mac",
    "华为", "Huawei", "鸿蒙", "Mate", "荣耀",
    "小米", "OPPO", "vivo", "三星", "Samsung",
    "消费电子", "果链", "代工", "供应链", "芯片", "半导体",
    "AI", "人工智能", "算力", "GPU", "英伟达"
]

# 关税政策关键词
TARIFF_KEYWORDS = [
    "关税", "贸易战", "中美贸易", "进口税", "出口管制",
    "实体清单", "制裁", "加征关税", "关税豁免", "贸易摩擦",
    "对华关税", "301条款", "tariff", "trade war",
    "反倾销", "反补贴", "海关", "进出口", "贸易政策",
    "关税清单", "豁免", "制裁清单", "出口禁令", "进口限制"
]


def _crawl_news(category: str, include_custom: bool = True) -> Dict:
    """执行新闻爬取"""
    from scrapers.unified import UnifiedDataSource
    
    unified = UnifiedDataSource()
    data = unified.crawl_category(category, include_custom=include_custom)
    
    return {
        "status": "success",
        "category": category,
        "data": data,
        "timestamp": datetime.now().isoformat(),
        "total": len(data)
    }


def _background_crawl_news(cache_key: str, category: str, include_custom: bool = True):
    """后台爬取新闻并更新缓存"""
    try:
        print(f"🔄 [后台] 开始爬取 {category}...")
        result = _crawl_news(category, include_custom)
        result["cached"] = False
        result["background_refresh"] = True
        cache.set(cache_key, result, ttl=CACHE_TTL)
        print(f"✅ [后台] {category} 爬取完成: {result['total']} 条")
    except Exception as e:
        print(f"❌ [后台] {category} 爬取失败: {e}")
    finally:
        _pending_refreshes.discard(cache_key)


def _background_fetch_realtime(cache_key: str, keywords: list, category: str = None):
    """后台拓取实时新闻并更新缓存"""
    try:
        from .analysis import fetch_realtime_news
        print(f"🔄 [后台] 开始拓取 {cache_key}...")
        news = fetch_realtime_news(keywords)
        result = {
            "status": "success",
            "data": news,
            "timestamp": datetime.now().isoformat(),
            "total": len(news),
            "cached": False,
            "background_refresh": True
        }
        if category:
            result["category"] = category
        cache.set(cache_key, result, ttl=CACHE_TTL)
        print(f"✅ [后台] {cache_key} 拓取完成: {len(news)} 条")
    except Exception as e:
        print(f"❌ [后台] {cache_key} 拓取失败: {e}")
    finally:
        _pending_refreshes.discard(cache_key)


def _trigger_background_refresh(cache_key: str, task_func, *args):
    """触发后台刷新任务（去重）"""
    if cache_key in _pending_refreshes:
        print(f"⏳ {cache_key} 已有后台任务进行中，跳过")
        return False
    _pending_refreshes.add(cache_key)
    _executor.submit(task_func, cache_key, *args)
    return True


@router.get("/api/commodity-news")
async def get_commodity_news(refresh: bool = False):
    """
    获取大宗商品新闻
    
    优化策略：
    - refresh=false: 直接返回缓存（<50ms）
    - refresh=true: 立即返回缓存 + 后台异步刷新
    """
    cache_key = "news:commodity"
    cached = cache.get(cache_key)
    
    if refresh:
        # 触发后台刷新
        triggered = _trigger_background_refresh(cache_key, _background_crawl_news, "commodity", True)
        
        # 立即返回现有缓存
        if cached:
            cached["cached"] = True
            cached["refreshing"] = triggered
            cached["message"] = "数据正在后台刷新，稍后重新加载获取最新数据" if triggered else "刷新任务已在进行中"
            return cached
        
        # 无缓存时返回空数据 + 刷新状态
        return {
            "status": "success",
            "category": "commodity",
            "data": [],
            "timestamp": None,
            "cached": False,
            "total": 0,
            "refreshing": triggered,
            "message": "数据正在后台加载，请稍后刷新页面"
        }
    
    # 正常请求：直接返回缓存
    if cached:
        cached["cached"] = True
        cached["cache_ttl"] = cache.get_ttl(cache_key)
        return cached
    
    return {
        "status": "success",
        "category": "commodity",
        "data": [],
        "timestamp": None,
        "cached": False,
        "total": 0,
        "message": "暂无缓存数据，请点击刷新按钮获取最新数据"
    }


@router.get("/api/news/supply-chain")
async def get_supply_chain_news(refresh: bool = False):
    """
    获取供应链相关新闻
    
    优化策略：缓存优先 + 后台异步刷新
    """
    cache_key = "news:supply-chain"
    cached = cache.get(cache_key)
    
    if refresh:
        triggered = _trigger_background_refresh(cache_key, _background_fetch_realtime, SUPPLY_CHAIN_KEYWORDS, None)
        
        if cached:
            cached["cached"] = True
            cached["refreshing"] = triggered
            cached["message"] = "数据正在后台刷新" if triggered else "刷新任务已在进行中"
            return cached
        
        return {
            "status": "success",
            "data": [],
            "timestamp": None,
            "cached": False,
            "total": 0,
            "refreshing": triggered,
            "message": "数据正在后台加载"
        }
    
    if cached:
        cached["cached"] = True
        cached["cache_ttl"] = cache.get_ttl(cache_key)
        return cached
    
    return {
        "status": "success",
        "data": [],
        "timestamp": None,
        "cached": False,
        "total": 0,
        "message": "暂无缓存数据，请点击刷新按钮获取最新数据"
    }


@router.get("/api/news/tariff")
async def get_tariff_news(refresh: bool = False):
    """
    获取关税政策相关新闻
    
    优化策略：缓存优先 + 后台异步刷新
    """
    cache_key = "news:tariff"
    cached = cache.get(cache_key)
    
    if refresh:
        triggered = _trigger_background_refresh(cache_key, _background_fetch_realtime, TARIFF_KEYWORDS, "tariff")
        
        if cached:
            cached["cached"] = True
            cached["refreshing"] = triggered
            cached["message"] = "数据正在后台刷新" if triggered else "刷新任务已在进行中"
            return cached
        
        return {
            "status": "success",
            "category": "tariff",
            "data": [],
            "timestamp": None,
            "cached": False,
            "total": 0,
            "refreshing": triggered,
            "message": "数据正在后台加载"
        }
    
    if cached:
        cached["cached"] = True
        cached["cache_ttl"] = cache.get_ttl(cache_key)
        return cached
    
    return {
        "status": "success",
        "category": "tariff",
        "data": [],
        "timestamp": None,
        "cached": False,
        "total": 0,
        "message": "暂无关税政策缓存数据，请点击刷新按钮获取最新数据"
    }


@router.get("/api/news/{category}")
async def get_news(category: str, include_custom: bool = True, refresh: bool = False):
    """
    获取指定分类的新闻
    
    优化策略：缓存优先 + 后台异步刷新
    响应时间：<50ms（从缓存读取）
    """
    cache_key = f"news:{category}"
    cached = cache.get(cache_key)
    
    if refresh:
        triggered = _trigger_background_refresh(cache_key, _background_crawl_news, category, include_custom)
        
        if cached:
            cached["cached"] = True
            cached["refreshing"] = triggered
            cached["message"] = f"{category} 数据正在后台刷新" if triggered else "刷新任务已在进行中"
            return cached
        
        return {
            "status": "success",
            "category": category,
            "data": [],
            "timestamp": None,
            "cached": False,
            "total": 0,
            "refreshing": triggered,
            "message": f"{category} 数据正在后台加载"
        }
    
    if cached:
        cached["cached"] = True
        cached["cache_ttl"] = cache.get_ttl(cache_key)
        return cached
    
    return {
        "status": "success",
        "category": category,
        "data": [],
        "timestamp": None,
        "cached": False,
        "total": 0,
        "message": f"暂无 {category} 缓存数据，请点击刷新按钮获取最新数据"
    }


@router.post("/api/crawl")
async def trigger_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    """
    触发爬取任务（后台异步执行）
    
    立即返回响应，爬取在后台进行
    """
    if request.category in ["supply-chain", "supply_chain"]:
        cache_key = "news:supply-chain"
        triggered = _trigger_background_refresh(cache_key, _background_fetch_realtime, SUPPLY_CHAIN_KEYWORDS, None)
    else:
        cache_key = f"news:{request.category}"
        triggered = _trigger_background_refresh(cache_key, _background_crawl_news, request.category, request.include_custom)
    
    return {
        "status": "success",
        "category": request.category,
        "triggered": triggered,
        "message": f"{request.category} 爬取任务已提交后台执行" if triggered else f"{request.category} 爬取任务已在进行中"
    }


@router.get("/api/refresh-status")
async def get_refresh_status():
    """获取后台刷新任务状态"""
    return {
        "pending_tasks": list(_pending_refreshes),
        "count": len(_pending_refreshes)
    }
