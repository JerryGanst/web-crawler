"""
数据相关 API 路由
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Optional
from pathlib import Path

from ..cache import cache, CACHE_TTL

router = APIRouter()

# 基础目录
BASE_DIR = Path(__file__).parent.parent.parent


def load_config():
    """加载配置"""
    import yaml
    config_path = BASE_DIR / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@router.get("/api/categories")
async def get_categories():
    """获取所有分类"""
    config = load_config()
    categories = config.get("categories", {})
    
    result = []
    for key, value in categories.items():
        result.append({
            "id": key,
            "name": value.get("name", key),
            "keywords": value.get("keywords", [])
        })
    
    return {"categories": result}


@router.get("/api/platforms")
async def get_platforms():
    """获取所有平台"""
    config = load_config()
    platforms = config.get("platforms", [])
    
    # 按分类分组
    by_category = {}
    for p in platforms:
        cat = p.get("category", "other")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(p)
    
    return {
        "platforms": platforms,
        "by_category": by_category,
        "total": len(platforms)
    }


@router.get("/api/data")
async def get_data(refresh: bool = False):
    """
    获取大宗商品市场数据（Redis 缓存）
    
    Args:
        refresh: 是否强制刷新
    """
    cache_key = "data:commodity"
    
    if refresh:
        try:
            print(f"🔄 用户请求刷新 commodity data...")
            from scrapers.commodity import CommodityScraper
            scraper = CommodityScraper()
            data = scraper.scrape()
            
            category_order = {'贵金属': 0, '能源': 1, '工业金属': 2, '农产品': 3, '其他': 4}
            data.sort(key=lambda x: category_order.get(x.get('category', '其他'), 4))
            
            result = {
                "data": data,
                "source": "TrendRadar Commodity",
                "timestamp": datetime.now().isoformat(),
                "cached": False,
                "categories": list(set(item.get('category', '其他') for item in data))
            }
            cache.set(cache_key, result, ttl=CACHE_TTL)
            
            # 保存价格历史
            try:
                from core.price_history import PriceHistoryManager
                history_manager = PriceHistoryManager()
                history_manager.save_prices(data)
                print(f"✅ 价格历史已保存")
            except Exception as e:
                print(f"⚠️ 保存价格历史失败: {e}")
            
            print(f"✅ commodity data 刷新完成: {len(data)} 条")
            return result
        except Exception as e:
            print(f"❌ commodity data 刷新失败: {e}")
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
        "data": [],
        "source": "TrendRadar Commodity",
        "timestamp": None,
        "cached": False,
        "categories": [],
        "message": "暂无缓存数据，请点击刷新按钮获取最新数据"
    }


@router.get("/api/price-history")
async def get_price_history(commodity: Optional[str] = None, days: int = 7):
    """获取价格历史数据"""
    try:
        from core.price_history import PriceHistoryManager
        history_manager = PriceHistoryManager()
        
        if commodity:
            history = history_manager.get_commodity_history(commodity, days)
            return {
                "status": "success",
                "commodity": commodity,
                "days": days,
                "data": history
            }
        else:
            all_history = history_manager.get_all_history(days)
            return {
                "status": "success",
                "days": days,
                "data": all_history,
                "commodities": list(all_history.keys())
            }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "data": {}
        }


@router.get("/api/data/sources")
async def get_data_sources():
    """
    获取商品数据来源信息（国家、网站级联）
    """
    # 数据源定义
    sources = {
        "US": {
            "name": "美国",
            "name_en": "United States",
            "flag": "🇺🇸",
            "websites": [
                {
                    "id": "business_insider",
                    "name": "Business Insider",
                    "url": "https://markets.businessinsider.com",
                    "commodities": ["Gold", "Silver", "Platinum", "Palladium", "WTI Crude Oil", "Brent Crude", "Natural Gas", "Copper"]
                },
                {
                    "id": "comex",
                    "name": "COMEX",
                    "url": "https://www.cmegroup.com",
                    "commodities": ["COMEX黄金", "COMEX白银", "COMEX铜"]
                }
            ]
        },
        "CN": {
            "name": "中国",
            "name_en": "China",
            "flag": "🇨🇳",
            "websites": [
                {
                    "id": "sina_futures",
                    "name": "新浪期货",
                    "url": "https://finance.sina.com.cn/futures",
                    "commodities": ["沪金", "沪银", "沪铜", "沪铝", "沪锌", "沪镍", "螺纹钢", "铁矿石"]
                },
                {
                    "id": "smm",
                    "name": "上海有色网",
                    "url": "https://www.smm.cn",
                    "commodities": ["SMM铜", "SMM铝", "SMM锌", "SMM镍", "SMM锡", "SMM铅"]
                },
                {
                    "id": "shfe",
                    "name": "上海期货交易所",
                    "url": "https://www.shfe.com.cn",
                    "commodities": ["沪金", "沪银", "沪铜", "沪铝", "沪锌", "天然橡胶"]
                }
            ]
        },
        "UK": {
            "name": "英国",
            "name_en": "United Kingdom",
            "flag": "🇬🇧",
            "websites": [
                {
                    "id": "lme",
                    "name": "伦敦金属交易所",
                    "url": "https://www.lme.com",
                    "commodities": ["LME铜", "LME铝", "LME锌", "LME镍", "LME锡", "LME铅"]
                }
            ]
        },
        "JP": {
            "name": "日本",
            "name_en": "Japan",
            "flag": "🇯🇵",
            "websites": [
                {
                    "id": "tocom",
                    "name": "东京商品交易所",
                    "url": "https://www.tocom.or.jp",
                    "commodities": ["东京黄金", "东京白银", "东京铂金"]
                }
            ]
        }
    }
    
    # 构建级联结构
    cascade = []
    for country_code, country_info in sources.items():
        country_data = {
            "code": country_code,
            "name": country_info["name"],
            "name_en": country_info["name_en"],
            "flag": country_info["flag"],
            "websites": country_info["websites"],
            "commodity_count": sum(len(w["commodities"]) for w in country_info["websites"])
        }
        cascade.append(country_data)
    
    return {
        "status": "success",
        "sources": sources,
        "cascade": cascade,
        "total_countries": len(sources),
        "total_websites": sum(len(c["websites"]) for c in sources.values())
    }


@router.get("/api/config")
async def get_config():
    """获取配置"""
    config = load_config()
    
    # 隐藏敏感信息
    if "notification" in config and "webhooks" in config["notification"]:
        webhooks = config["notification"]["webhooks"]
        for key in webhooks:
            if webhooks[key] and len(str(webhooks[key])) > 10:
                webhooks[key] = webhooks[key][:10] + "***"
    
    return config


@router.get("/api/status")
async def get_status():
    """获取系统状态"""
    return {
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "cache": cache.get_status(),
        "version": "2.0.0"
    }
