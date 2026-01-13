"""
数据相关 API 路由

优化策略：缓存优先 + 后台异步刷新
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from ..cache import cache, CACHE_TTL
from database.manager import db_manager
from database.mysql.connection import get_connection, get_cursor
import pymysql

router = APIRouter()

# 基础目录
BASE_DIR = Path(__file__).parent.parent.parent

# 后台任务
_executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="data-bg")
_pending_refreshes = set()
_refresh_lock = Lock()


def _transform_mysql_to_api_format(data: List[Dict]) -> List[Dict]:
    """
    将 MySQL commodity_latest 数据转换为 API 格式
    
    转换内容：
    1. 合并 price_unit 和 weight_unit 为 unit
    2. 添加 current_price 字段
    3. 确保 url 字段存在
    4. 删除 MySQL 专用字段
    """
    for item in data:
        # 1. 合并 price_unit 和 weight_unit 为 unit
        price_unit = item.get('price_unit', '')
        weight_unit = item.get('weight_unit', '')
        if price_unit and weight_unit:
            item['unit'] = f"{price_unit}/{weight_unit}"
        elif price_unit:
            item['unit'] = price_unit
        elif weight_unit:
            item['unit'] = weight_unit
        else:
            item['unit'] = 'USD'
        
        # 2. current_price = price (前端兼容)
        if 'price' in item and 'current_price' not in item:
            item['current_price'] = item['price']
        
        # 3. 确保 url 字段存在
        if 'url' not in item or not item['url']:
            item['url'] = item.get('source_url', '')
        
        # 4. 删除前端不需要的字段
        item.pop('id', None)
        item.pop('price_unit', None)
        item.pop('weight_unit', None)
        item.pop('version_ts', None)
        item.pop('source_url', None)
    
    return data


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
def get_platforms():
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


def _background_fetch_commodity_data(cache_key: str):
    """后台爬取商品数据并从 MySQL commodity_latest 读取去重后的数据写入 Redis"""
    try:
        print(f"🔄 [后台] 开始爬取商品数据...")
        from scrapers.commodity import CommodityScraper
        scraper = CommodityScraper()
        raw_data = scraper.scrape()
        print(f"✅ [后台] 爬取完成: {len(raw_data)} 条原始数据")
        
        # 写入 MySQL（Pipeline 会自动去重），按来源分组
        try:
            stats_by_source = {}
            sources = set(item.get("source", "unknown") for item in raw_data)
            for src in sources:
                src_records = [item for item in raw_data if item.get("source", "unknown") == src]
                if not src_records:
                    continue
                db_stats = db_manager.write_commodity(src_records, source=src)
                if db_stats:
                    stats_by_source[src] = db_stats
            if stats_by_source:
                print(f"✅ [后台] MySQL 入库完成: {stats_by_source}")
        except Exception as e:
            print(f"⚠️ MySQL 入库失败: {e}")
        
        # 从 MySQL commodity_latest 读取去重后的数据（以 MySQL 为准）
        try:
            latest_data = db_manager.get_commodity_latest()
            if not latest_data:
                print("⚠️ MySQL commodity_latest 为空，使用原始数据")
                latest_data = raw_data
            else:
                print(f"✅ [后台] 从 MySQL commodity_latest 读取: {len(latest_data)} 条去重数据")
                # 字段映射：MySQL → API 格式
                latest_data = _transform_mysql_to_api_format(latest_data)
        except Exception as e:
            print(f"⚠️ 从 MySQL 读取失败: {e}，使用原始数据")
            latest_data = raw_data
        
        # 排序并写入 Redis
        category_order = {'贵金属': 0, '能源': 1, '工业金属': 2, '农产品': 3, '其他': 4}
        latest_data.sort(key=lambda x: category_order.get(x.get('category', '其他'), 4))
        
        result = {
            "data": latest_data,
            "source": "TrendRadar Commodity",
            "timestamp": datetime.now().isoformat(),
            "cached": False,
            "background_refresh": True,
            "from_mysql": True,
            "categories": list(set(item.get('category', '其他') for item in latest_data)),
            "total": len(latest_data)
        }
        
        print(f"✅ [后台] 写入 Redis 缓存: {len(latest_data)} 条")
        cache.set(cache_key, result, ttl=CACHE_TTL)
    except Exception as e:
        print(f"❌ [后台] 商品数据失败: {e}")
    finally:
        with _refresh_lock:
            _pending_refreshes.discard(cache_key)


@router.get("/api/data")
async def get_data(refresh: bool = False, sync: bool = False):
    """
    获取大宗商品市场数据

    优化策略：
    - refresh=false: 直接返回缓存（<50ms）
    - refresh=true: 立即返回缓存 + 后台异步刷新
    - refresh=true&sync=true: 同步刷新，等待新数据返回
    """
    cache_key = "data:commodity"
    cached = cache.get(cache_key)

    if refresh:
        if sync:
            # 同步刷新：直接爬取新数据并返回
            print(f"🔄 商品数据同步刷新开始...")
            try:
                from scrapers.commodity import CommodityScraper
                scraper = CommodityScraper()
                raw_data = scraper.scrape()
                print(f"✅ 同步爬取完成: {len(raw_data)} 条原始数据")

                # 写入 MySQL
                try:
                    stats_by_source = {}
                    sources = set(item.get("source", "unknown") for item in raw_data)
                    for src in sources:
                        src_records = [item for item in raw_data if item.get("source", "unknown") == src]
                        if src_records:
                            db_stats = db_manager.write_commodity(src_records, source=src)
                            if db_stats:
                                stats_by_source[src] = db_stats
                    print(f"✅ MySQL 入库完成: {stats_by_source}")
                except Exception as e:
                    print(f"⚠️ MySQL 入库失败: {e}")

                # 从 MySQL 读取去重后的数据
                latest_data = db_manager.get_commodity_latest() or raw_data
                latest_data = _transform_mysql_to_api_format(latest_data)

                # 排序
                category_order = {'贵金属': 0, '能源': 1, '工业金属': 2, '农产品': 3, '其他': 4}
                latest_data.sort(key=lambda x: category_order.get(x.get('category', '其他'), 4))

                result = {
                    "data": latest_data,
                    "source": "TrendRadar Commodity (Sync Refresh)",
                    "timestamp": datetime.now().isoformat(),
                    "cached": False,
                    "refreshing": False,
                    "sync_refresh": True,
                    "from_mysql": True,
                    "categories": list(set(item.get('category', '其他') for item in latest_data)),
                    "total": len(latest_data)
                }

                cache.set(cache_key, result, ttl=CACHE_TTL)
                return result

            except Exception as e:
                print(f"❌ 同步刷新失败: {e}")
                # 失败时返回缓存数据
                if cached:
                    cached["error"] = str(e)
                    return cached
                return {"data": [], "error": str(e), "timestamp": None}

        # 异步刷新：触发后台刷新
        triggered = False
        with _refresh_lock:
            if cache_key not in _pending_refreshes:
                _pending_refreshes.add(cache_key)
                _executor.submit(_background_fetch_commodity_data, cache_key)
                triggered = True
                print(f"🔄 商品数据后台刷新已触发")

        # 立即返回现有缓存
        if cached:
            cached["cached"] = True
            cached["refreshing"] = triggered
            cached["message"] = "数据正在后台刷新" if triggered else "刷新任务已在进行中"
            return cached

        return {
            "data": [],
            "source": "TrendRadar Commodity",
            "timestamp": None,
            "cached": False,
            "refreshing": triggered,
            "categories": [],
            "message": "数据正在后台加载"
        }
    
    if cached:
        cached["cached"] = True
        return cached

    # 缓存未命中，尝试从 MySQL 快照 (commodity_latest) 获取
    try:
        from database.manager import db_manager
        latest_data = db_manager.get_commodity_latest()
        
        if latest_data:
            print("🔄 [API] Redis Miss -> 从 MySQL 快照 (commodity_latest) 恢复")
            
            # 字段映射：MySQL → API 格式（与后台刷新逻辑保持一致）
            latest_data = _transform_mysql_to_api_format(latest_data)
            
            # 排序
            category_order = {'贵金属': 0, '能源': 1, '工业金属': 2, '农产品': 3, '其他': 4}
            latest_data.sort(key=lambda x: category_order.get(x.get('category', '其他'), 4))
            
            # 构建标准响应
            result = {
                "data": latest_data,
                "source": "TrendRadar MySQL Snapshot",
                "timestamp": datetime.now().isoformat(),
                "cached": False,
                "from_snapshot": True,
                "from_mysql": True,
                "categories": list(set(item.get('category', '其他') for item in latest_data)),
                "total": len(latest_data)
            }
            cache.set(cache_key, result, ttl=CACHE_TTL)
            return result
            
    except Exception as e:
        print(f"⚠️ [API] MySQL 快照恢复失败: {e}")

    # 快照缺失，尝试从历史归档 (commodity_history) 获取当天数据
    try:
        from database.mysql.pipeline import get_commodities_by_date
        today_data = get_commodities_by_date(datetime.now())
        
        if today_data:
            print("🔄 [API] MySQL 快照缺失 -> 从历史归档 (commodity_history) 加载今日数据")
            
            # 兼容处理: 历史表字段转为前端需要的格式 (如果字段名有差异)
            # 目前 commodity_history 与 latest 字段基本一致
            
            result = {
                "data": today_data,
                "source": "TrendRadar MySQL History",
                "timestamp": datetime.now().isoformat(),
                "cached": False,
                "from_archive": True,
                "categories": list(set(item.get('category', '其他') for item in today_data))
            }
            cache.set(cache_key, result, ttl=CACHE_TTL)
            return result
            
    except Exception as e:
        print(f"⚠️ [API] MySQL 历史归档读取失败: {e}")
    
    # 缓存未命中且DB无数据，触发后台爬取
    _background_fetch_commodity_data(cache_key)


@router.get("/api/price-history")
async def get_price_history(commodity: Optional[str] = None, days: int = 7):
    """
    获取价格历史数据（从 commodity_history 表）
    
    优化：使用缓存（价格历史不常变）
    """
    cache_key = f"price-history:{commodity or 'all'}:{days}"
    
    # 检查缓存
    cached = cache.get(cache_key)
    if cached:
        cached["cached"] = True
        return cached
    
    try:
        from core.price_history import PriceHistoryManager
        history_manager = PriceHistoryManager()
        
        if commodity:
            history = history_manager.get_history(commodity, days)
            result = {
                "status": "success",
                "commodity": commodity,
                "days": days,
                "data": history,
                "cached": False
            }
        else:
            all_history = history_manager.get_all_commodities_history(days)
            result = {
                "status": "success",
                "days": days,
                "data": all_history,
                "commodities": list(all_history.keys()),
                "cached": False
            }
        
        # 缓存 五分钟
        cache.set(cache_key, result, ttl=300)
        return result
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e),
            "data": {},
            "cached": False
        }


@router.post("/api/price-history/init-plastics")
async def init_plastics_history(days: int = 30):
    """
    初始化塑料历史数据（从中塑在线拉取历史记录）
    
    Args:
        days: 拉取最近多少天的历史数据，默认30天
    """
    try:
        from scrapers.plastic21cp import Plastic21CPScraper
        from core.price_history import PriceHistoryManager
        from datetime import datetime, timedelta
        
        scraper = Plastic21CPScraper()
        history_manager = PriceHistoryManager()
        
        # 计算日期范围
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        total_saved = 0
        products_processed = []
        
        for product_key in scraper.list_products():
            try:
                # 获取历史数据
                records = scraper.fetch(product_key, start_date=start_date, end_date=end_date)
                
                # 保存到历史记录
                for record in records:
                    name = record.get("chinese_name") or record.get("name")
                    price = record.get("price")
                    change = record.get("change_percent", 0)
                    source = record.get("source", "中塑在线")
                    date = record.get("price_date")
                    
                    if name and price and date:
                        history_manager.save_daily_price(name, price, change, source, date)
                        total_saved += 1
                
                products_processed.append({
                    "product": product_key,
                    "records": len(records)
                })
                
            except Exception as e:
                products_processed.append({
                    "product": product_key,
                    "error": str(e)
                })
        
        return {
            "status": "success",
            "message": f"已初始化 {total_saved} 条塑料历史数据",
            "date_range": {"start": start_date, "end": end_date},
            "products": products_processed
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
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
                },
                {
                    "id": "21cp",
                    "name": "中塑在线",
                    "url": "https://quote.21cp.com",
                    "commodities": [
                        "ABS(华南)", "ABS(华东)", "ABS(华北)",
                        "PP(华东)", "PP(华南)", "PP(华北)",
                        "PE(华东)", "PE(华南)", "PE(华北)",
                        "GPPS(华东)", "GPPS(华南)", "GPPS低端(华东)", "GPPS低端(华南)",
                        "HIPS(华东)", "HIPS(华南)", "HIPS低端(华东)", "HIPS低端(华南)",
                        "WTI原油"
                    ]
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
            val = webhooks[key]
            if isinstance(val, list):
                # 如果是列表（如 wework_url），处理每个元素
                masked_list = []
                for item in val:
                    if item and isinstance(item, str) and len(item) > 10:
                        masked_list.append(item[:10] + "***")
                    else:
                        masked_list.append(item)
                webhooks[key] = masked_list
            elif val and isinstance(val, str) and len(val) > 10:
                webhooks[key] = val[:10] + "***"
    
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



def _create_exchange_rate_table():
    sql = """
    CREATE TABLE IF NOT EXISTS exchange_rates (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        base_currency VARCHAR(3) NOT NULL COMMENT '基础货币 (如 USD)',
        target_currency VARCHAR(3) NOT NULL COMMENT '目标货币 (如 CNY)',
        rate DECIMAL(10, 6) NOT NULL COMMENT '汇率值',
        source VARCHAR(64) COMMENT '数据来源 (如 api.exchangerate-api.com)',
        timestamp DATETIME(3) COMMENT '数据时间戳 (来源提供的时间)',
        created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
        INDEX idx_currency_pair (base_currency, target_currency),
        INDEX idx_created_at (created_at DESC)
    ) ENGINE=InnoDB COMMENT='汇率历史表';
    """
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql)
            conn.commit()
            print("✅ Created exchange_rates table")
    except Exception as e:
        print(f"❌ Failed to create exchange_rates table: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def _save_exchange_rate_to_mysql(data: dict):
    sql = """
        INSERT INTO exchange_rates 
        (base_currency, target_currency, rate, source, timestamp)
        VALUES (%s, %s, %s, %s, %s)
    """
    # 处理 timestamp 格式，确保 MySQL 能识别
    ts = data['timestamp']
    if 'T' in ts:
        ts = ts.replace('T', ' ')
        
    params = (
        data['base'],
        data['target'],
        data['rate'],
        data['source'],
        ts
    )
    
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            conn.commit()
            print(f"✅ Exchange rate saved to MySQL: {data['rate']}")
    except pymysql.err.ProgrammingError as e:
        if e.args[0] == 1146: # Table doesn't exist
            print("⚠️ Table exchange_rates does not exist, creating...")
            _create_exchange_rate_table()
            # Retry once
            if conn: conn.close()
            conn = get_connection()
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                conn.commit()
                print(f"✅ Exchange rate saved to MySQL (after create): {data['rate']}")
        else:
            raise
    except Exception as e:
        print(f"❌ MySQL Error: {e}")
    finally:
        if conn:
            conn.close()

@router.get("/api/exchange-rate")

def get_exchange_rate(refresh: bool = False):
    """
    获取实时汇率（USD/CNY）
    
    优化策略：
    - 缓存优先：默认从 Redis 获取缓存数据
    - 缓存有效期：20分钟 (1200秒)
    - refresh=true: 强制刷新缓存
    """
    cache_key = "data:exchange_rate:usd_cny"
    
    # 1. 尝试读取缓存
    if not refresh:
        cached_data = cache.get(cache_key)
        if cached_data:
            cached_data["cached"] = True
            return cached_data
    
    import requests
    
    # 尝试多个汇率源
    sources = [
        # ExchangeRate-API (免费)
        ("https://api.exchangerate-api.com/v4/latest/USD", lambda d: d.get("rates", {}).get("CNY")),
        # Open Exchange Rates (备用)
        ("https://open.er-api.com/v6/latest/USD", lambda d: d.get("rates", {}).get("CNY")),
    ]
    
    for url, extractor in sources:
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                rate = extractor(data)
                if rate:
                    result = {
                        "status": "success",
                        "base": "USD",
                        "target": "CNY",
                        "rate": round(float(rate), 4),
                        "timestamp": datetime.now().isoformat(),
                        "source": url.split("/")[2],
                        "cached": False
                    }
                    
                    # 写入 MySQL (缓存前)
                    _save_exchange_rate_to_mysql(result)
                    
                    # 写入缓存 (20分钟 = 1200秒)
                    cache.set(cache_key, result, ttl=1200)
                    return result
        except Exception:
            continue
    
    # 默认备用汇率
    fallback_result = {
        "status": "fallback",
        "base": "USD",
        "target": "CNY",
        "rate": 7.2,
        "timestamp": datetime.now().isoformat(),
        "source": "default",
        "cached": False
    }
    
    # 写入 MySQL (缓存前)
    _save_exchange_rate_to_mysql(fallback_result)

    # 备用数据也缓存较短时间 (5分钟)
    cache.set(cache_key, fallback_result, ttl=300)
    return fallback_result
