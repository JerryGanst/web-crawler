"""
新闻相关 API 路由
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from datetime import datetime
from typing import Dict
from pathlib import Path

from ..cache import cache, CACHE_TTL
from ..models import CrawlRequest

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent.parent

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


@router.get("/api/commodity-news")
async def get_commodity_news(refresh: bool = False):
    """获取大宗商品新闻"""
    cache_key = "news:commodity"
    
    if refresh:
        try:
            print(f"🔄 用户请求刷新 commodity news...")
            result = _crawl_news("commodity", include_custom=True)
            result["cached"] = False
            cache.set(cache_key, result, ttl=CACHE_TTL)
            print(f"✅ commodity news 刷新完成: {result['total']} 条")
            return result
        except Exception as e:
            print(f"❌ commodity news 刷新失败: {e}")
            cached = cache.get(cache_key)
            if cached:
                cached["cached"] = True
                cached["error"] = str(e)
                return cached
            raise HTTPException(status_code=500, detail=f"爬取失败: {str(e)}")
    
    cached = cache.get(cache_key)
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
    """获取供应链相关新闻"""
    from .analysis import fetch_realtime_news
    
    cache_key = "news:supply-chain"
    
    if refresh:
        try:
            print(f"🔄 用户请求刷新 supply-chain...")
            news = fetch_realtime_news(SUPPLY_CHAIN_KEYWORDS)
            result = {
                "status": "success",
                "data": news,
                "timestamp": datetime.now().isoformat(),
                "total": len(news),
                "cached": False
            }
            cache.set(cache_key, result, ttl=CACHE_TTL)
            print(f"✅ supply-chain 刷新完成: {len(news)} 条")
            return result
        except Exception as e:
            print(f"❌ supply-chain 刷新失败: {e}")
            cached = cache.get(cache_key)
            if cached:
                cached["cached"] = True
                cached["error"] = str(e)
                return cached
            raise HTTPException(status_code=500, detail=f"爬取失败: {str(e)}")
    
    cached = cache.get(cache_key)
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


@router.get("/api/news/{category}")
async def get_news(category: str, include_custom: bool = True, refresh: bool = False):
    """获取指定分类的新闻"""
    cache_key = f"news:{category}"
    
    if refresh:
        try:
            print(f"🔄 用户请求刷新 {category}...")
            result = _crawl_news(category, include_custom)
            result["cached"] = False
            cache.set(cache_key, result, ttl=CACHE_TTL)
            print(f"✅ {category} 刷新完成: {result['total']} 条")
            return result
        except Exception as e:
            print(f"❌ {category} 刷新失败: {e}")
            cached = cache.get(cache_key)
            if cached:
                cached["cached"] = True
                cached["error"] = str(e)
                return cached
            raise HTTPException(status_code=500, detail=f"爬取失败: {str(e)}")
    
    cached = cache.get(cache_key)
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
    """触发爬取任务"""
    from scrapers.unified import UnifiedDataSource
    
    try:
        unified = UnifiedDataSource()
        
        if request.category in ["supply-chain", "supply_chain"]:
            from .analysis import fetch_realtime_news
            keywords = SUPPLY_CHAIN_KEYWORDS
            data = fetch_realtime_news(keywords)
            
            cache.set("news:supply-chain", {
                "status": "success",
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "total": len(data)
            }, ttl=CACHE_TTL)
            
            return {
                "status": "success",
                "category": request.category,
                "total": len(data),
                "message": f"已爬取 {len(data)} 条数据"
            }
        
        data = unified.crawl_category(request.category, request.include_custom)
        
        cache.set(f"news:{request.category}", {
            "status": "success",
            "category": request.category,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "total": len(data)
        }, ttl=CACHE_TTL)
        
        return {
            "status": "success",
            "category": request.category,
            "total": len(data),
            "message": f"已爬取 {len(data)} 条数据"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
