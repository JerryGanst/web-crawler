"""
新闻相关 API 路由

优化策略：缓存优先 + 后台异步刷新
- 用户请求时立即返回缓存数据（<50ms）
- 刷新操作在后台异步执行
- 下次请求获得新数据
"""
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..cache import cache, CACHE_TTL
from ..models import CrawlRequest

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent.parent

# 后台任务线程池
_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="news-bg")
# 在测试环境下避免启动后台线程，防止并发影响用例（通过 PYTEST_CURRENT_TEST 检测）
_TEST_ENV = "PYTEST_CURRENT_TEST" in os.environ

# 进行中的后台任务跟踪（避免重复刷新）
_pending_refreshes = set()
_refresh_lock = Lock()


# ==================== 友商关键词配置 ====================
# 18家友商分类及搜索关键词

# 光电模块友商（6家）
OPTICAL_PARTNERS = {
    "Credo": ["Credo", "Credo Technology", "CRDO"],
    "旭创科技": ["中际旭创", "旭创", "旭创科技", "300308"],
    "新易盛": ["新易盛", "300502"],
    "天孚通信": ["天孚通信", "天孚", "300394"],
    "光迅科技": ["光迅科技", "光迅", "002281"],
    "Finisar": ["Finisar", "菲尼萨", "II-VI"],
}

# 连接器友商（8家）
CONNECTOR_PARTNERS = {
    "安费诺": ["Amphenol", "安费诺", "APH"],
    "莫仕": ["Molex", "莫仕", "莫莱克斯"],
    "TE": ["TE Connectivity", "TE", "泰科电子", "TEL"],
    "中航光电": ["中航光电", "158电连接器", "002179"],
    "得意精密": ["得意精密", "得意"],
    "意华股份": ["意华股份", "意华", "002897"],
    "金信诺": ["金信诺", "300252"],
    "华丰科技": ["华丰科技", "华旗", "688100"],
}

# 电源友商（4家）
POWER_PARTNERS = {
    "奥海科技": ["奥海科技", "奥海", "002993"],
    "航嘉": ["航嘉", "航嘉驰源"],
    "赛尔康": ["赛尔康", "Salcomp"],
    "台达电子": ["台达", "台达电子", "Delta", "2308.TW"],
}
# 电源友商官网
POWER_PARTNER_SITES = {
    "奥海科技": "https://www.aohai.com",
    "航嘉": "https://www.huntkey.com",
    "赛尔康": "https://www.salcomp.com",
    "台达电子": "https://www.deltaww.com",
}
# 电源友商官网新闻/公告页
POWER_PARTNER_NEWS_PAGES = {
    "奥海科技": "https://www.aohai.com/news",
    "航嘉": "https://www.huntkey.com/category/news",
    "赛尔康": "https://www.salcomp.com/newsroom",
    "台达电子": "https://www.deltaww.com/en-US/about-delta/news",
}

# 合并所有友商关键词
def _get_partner_keywords():
    """获取所有友商关键词（扁平化）"""
    keywords = []
    for partner_dict in [OPTICAL_PARTNERS, CONNECTOR_PARTNERS, POWER_PARTNERS]:
        for company, kw_list in partner_dict.items():
            keywords.extend(kw_list)
    return keywords

PARTNER_KEYWORDS = _get_partner_keywords()

# ==================== 供应链关键词 ====================
SUPPLY_CHAIN_KEYWORDS = [
    # 核心果链/消费电子供应商
    "立讯", "歌尔", "蓝思", "富联", "富士康", "京东方", "BOE",
    "欣旺达", "德赛", "舜宇", "鹏鼎", "东山精密", "领益", "瑞声",
    # 品牌客户
    "苹果", "Apple", "iPhone", "AirPods", "Vision Pro", "iPad", "Mac",
    "华为", "Huawei", "鸿蒙", "Mate", "荣耀",
    "小米", "OPPO", "vivo", "三星", "Samsung",
    # 行业关键词
    "消费电子", "果链", "代工", "供应链", "芯片", "半导体",
    "AI", "人工智能", "算力", "GPU", "英伟达",
    # 友商关键词（自动合并）
] + PARTNER_KEYWORDS

# 关税政策关键词
TARIFF_KEYWORDS = [
    "关税", "贸易战", "中美贸易", "进口税", "出口管制",
    "实体清单", "制裁", "加征关税", "关税豁免", "贸易摩擦",
    "对华关税", "301条款", "tariff", "trade war",
    "反倾销", "反补贴", "海关", "进出口", "贸易政策",
    "关税清单", "豁免", "制裁清单", "出口禁令", "进口限制"
]

# 塑料相关关键词
PLASTICS_KEYWORDS = [
    "塑料", "PA66", "PBT", "PC", "ABS", "PP", "PE", "PVC", "HDPE", "LDPE",
    "聚丙烯", "聚乙烯", "聚氯乙烯", "尼龙", "树脂", "改性塑料", "工程塑料",
    "注塑", "塑胶", "聚酯", "聚碳酸酯", "塑料价格", "塑料原料",
    "石化", "乙烯", "丙烯", "苯乙烯", "塑料制品"
]


def _crawl_news(category: str, include_custom: bool = True) -> Dict:
    """执行新闻爬取"""
    from scrapers.unified import UnifiedDataSource
    
    unified = UnifiedDataSource()
    data = unified.crawl_category(category, include_custom=include_custom)
    
    # 统计数据来源分布
    sources = {}
    for item in data:
        # 按照优先级提取来源：platform_name > source > platform > 未知
        # 修复逻辑：优先取 platform_name 或 source，避免取到 newsnow
        source_name = item.get('platform_name') or item.get('source') or item.get('platform') or '未知'
        sources[source_name] = sources.get(source_name, 0) + 1
    
    return {
        "status": "success",
        "category": category,
        "data": data,
        "timestamp": datetime.now().isoformat(),
        "total": len(data),
        "sources": sources  # 添加来源统计
    }


def _extract_text_from_html(html_text: str, limit: int = 1200) -> str:
    """简易正文抽取：去掉标签/脚本，压缩空白"""
    import re, html as html_lib
    if not html_text:
        return ""
    cleaned = re.sub(r"(?is)<script.*?>.*?</script>", " ", html_text)
    cleaned = re.sub(r"(?is)<style.*?>.*?</style>", " ", cleaned)
    cleaned = re.sub(r"(?s)<[^>]+>", " ", cleaned)
    cleaned = html_lib.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:limit]


def _fetch_power_partner_news(max_per_company: int = 4) -> list:
    """
    针对电源友商的定向抓取（Google News RSS），并尝试提取正文。
    过滤掉雪球/百度，避免噪声。
    """
    import requests as req
    import xml.etree.ElementTree as ET
    
    results = []
    seen_titles = set()
    
    headers = {"User-Agent": "Mozilla/5.0 (TrendRadar/1.0)"}
    
    for company, keywords in POWER_PARTNERS.items():
        # 取公司名称作为搜索关键词
        keyword = company
        feed_url = f"https://news.google.com/rss/search?q={quote(keyword)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        try:
            resp = req.get(feed_url, timeout=10, headers=headers)
            if resp.status_code != 200 or not resp.content:
                continue
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")[:max_per_company]
            for item in items:
                title = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                pub = item.findtext("pubDate", "").strip()
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)
                
                content = ""
                try:
                    article = req.get(link, timeout=8, headers=headers)
                    if article.status_code == 200:
                        content = _extract_text_from_html(article.text)
                except Exception:
                    content = ""
                
                results.append({
                    "title": title,
                    "url": link,
                    "source": f"{company} 相关",
                    "publish_time": pub,
                    "content": content
                })
        except Exception:
            continue

    return results


def _fetch_power_official_announcements(max_per_company: int = 5) -> list:
    """
    抓取电源友商官网公告/新闻页内容
    """
    import re
    import requests as req
    from urllib.parse import urljoin

    headers = {"User-Agent": "Mozilla/5.0 (TrendRadar/1.0)"}
    results = []

    for company, page_url in POWER_PARTNER_NEWS_PAGES.items():
        try:
            resp = req.get(page_url, timeout=12, headers=headers)
            if resp.status_code != 200 or not resp.text:
                continue
            html = resp.text

            links = []
            try:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(html, "html.parser")
                links = [(a.get_text(" ", strip=True), a.get("href")) for a in soup.find_all("a", href=True)]
            except Exception:
                raw_links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.I | re.S)
                for href, text in raw_links:
                    clean_text = re.sub(r"<[^>]+>", " ", text)
                    clean_text = re.sub(r"\s+", " ", clean_text).strip()
                    links.append((clean_text, href))

            seen_titles = set()
            seen_urls = set()
            for text, href in links:
                if not href or not text or len(text) < 5:
                    continue
                if href.startswith("#") or href.lower().startswith("javascript"):
                    continue
                lower_href = href.lower()
                if not any(k in lower_href for k in ["news", "press", "media", "info", "article", "xinwen", "gonggao"]) and not any(tag in text for tag in ["新闻", "公告", "动态", "资讯", "媒体"]):
                    continue
                full_url = urljoin(page_url, href)
                if text in seen_titles or full_url in seen_urls:
                    continue
                seen_titles.add(text)
                seen_urls.add(full_url)
                results.append({
                    "title": text[:180],
                    "url": full_url,
                    "source": f"{company} 官网",
                    "publish_time": "",
                    "content": ""
                })
                if len(seen_titles) >= max_per_company:
                    break
        except Exception:
            continue

    return results


def _background_crawl_news(cache_key: str, category: str, include_custom: bool = True):
    """后台爬取新闻并更新缓存"""
    try:
        print(f"🔄 [后台] 开始爬取 {category}...")
        result = _crawl_news(category, include_custom)
        result["cached"] = False
        result["background_refresh"] = True
        
        # 1. 先同步写入 MongoDB 历史归档（确保数据先入库，这样 _try_get_from_mongodb_daily 才能查到最新）
        try:
            from database.manager import db_manager
            if db_manager.mongodb_enabled:
                if result.get("data"):
                    from database.models import News
                    news_objects = []
                    for item in result["data"]:
                        # 处理时间
                        p_time = item.get("time") or item.get("publish_time")
                        published_at = None
                        if p_time:
                            try:
                                if isinstance(p_time, str):
                                    # 尝试处理不同格式
                                    try:
                                        published_at = datetime.fromisoformat(p_time.replace('Z', '+00:00'))
                                    except:
                                        # 尝试解析 "YYYY-MM-DD HH:MM" 格式
                                        published_at = datetime.strptime(p_time, "%Y-%m-%d %H:%M")
                                else:
                                    published_at = p_time
                            except:
                                published_at = datetime.now()
                        else:
                            published_at = datetime.now()

                        news_objects.append(News(
                            platform_id=item.get("platform", "unknown"),
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            published_at=published_at,
                            category=category,
                            extra_data=item,
                            source=item.get("source", ""),
                            platform_name=item.get("platform_name") or item.get("source", ""),
                            summary=item.get("summary", "") or item.get("content", "")[:200]
                        ))
                    
                    inserted, updated = db_manager.news_repo.insert_batch(news_objects)
                    print(f"✅ [后台] {category} 归档到 MongoDB: 新增 {inserted}, 更新 {updated}")
        except Exception as e:
            print(f"⚠️ [后台] MongoDB 归档失败: {e}")
        
        # 默认先设置当前抓取结果为缓存
        final_result = result
        
        # 2. 尝试从 MongoDB 获取最近 7 天的全量数据（此时已经包含了刚刚入库的数据）
        daily_data = _try_get_from_mongodb_daily(category)
        if daily_data and daily_data.get("total", 0) > len(result.get("data", [])):
            print(f"🔄 [后台] {category} 使用 MongoDB 最近7天全量数据更新缓存 ({daily_data.get('total')} 条)")
            final_result = daily_data
        
        # 3. 写入 MongoDB 快照 (使用全量数据)
        try:
            if db_manager.mongodb_enabled:
                db_manager.news_repo.save_snapshot(cache_key, final_result)
                print(f"✅ [后台] {category} 快照已保存到 MongoDB (包含 {final_result.get('total', 0)} 条)")
        except Exception as e:
            print(f"⚠️ [后台] MongoDB 快照保存失败: {e}")

        # 4. 最后写入 Redis (使用全量数据)
        cache.set(cache_key, final_result, ttl=CACHE_TTL)
            
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
        # 过滤不需要的来源
        news = [n for n in news if n.get("source") not in ["雪球", "百度"]]
        
        # 补全 platform_name (确保入库和缓存都有该字段)
        for item in news:
            if not item.get("platform_name") and item.get("source"):
                item["platform_name"] = item["source"]
        
        # 针对 supply-chain 增补电源友商定向抓取（带正文）
        if category == "supply-chain":
            power_news = _fetch_power_partner_news()
            official_news = _fetch_power_official_announcements()
            # 去重（按标题）
            seen = {n.get("title") for n in news}
            for item in power_news + official_news:
                if item.get("title") and item["title"] not in seen:
                    seen.add(item["title"])
                    news.append(item)
        
        # 统计数据来源分布
        sources = {}
        for item in news:
            # 按照优先级提取来源：platform_name > source > platform > 未知
            # 修复逻辑：优先取 platform_name 或 source，避免取到 newsnow
            source_name = item.get('platform_name') or item.get('source') or item.get('platform') or '未知'
            sources[source_name] = sources.get(source_name, 0) + 1
        
        # 1. 写入 MongoDB
        try:
            from database.manager import db_manager
            if db_manager.mongodb_enabled and category:
                from database.models import News
                news_objects = []
                for item in news:
                    # 处理时间
                    p_time = item.get("time")
                    published_at = None
                    if p_time:
                        try:
                            if isinstance(p_time, str):
                                published_at = datetime.fromisoformat(p_time.replace('Z', '+00:00'))
                            else:
                                published_at = p_time
                        except:
                            published_at = datetime.now()
                    else:
                        published_at = datetime.now()

                    news_objects.append(News(
                        platform_id=item.get("platform", "unknown"),
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        published_at=published_at,
                        category=category,
                        extra_data=item,
                        source=item.get("source", ""),
                        platform_name=item.get("platform_name", ""),
                        summary=item.get("summary", "") or item.get("content", "")[:200]
                    ))
                
                inserted, updated = db_manager.news_repo.insert_batch(news_objects)
                print(f"✅ [后台] {category} (实时) 归档到 MongoDB: 新增 {inserted}, 更新 {updated}")
        except Exception as e:
            print(f"⚠️ [后台] MongoDB 归档失败: {e}")

        result = {
            "status": "success",
            "data": news,
            "timestamp": datetime.now().isoformat(),
            "total": len(news),
            "sources": sources,  # 添加来源统计
            "cached": False,
            "background_refresh": True
        }
        if category:
            result["category"] = category
        
        # 默认先设置当前抓取结果为缓存
        final_result = result
        
        # 2. 尝试从 MongoDB 获取最近 7 天的全量数据（此时已经包含了刚刚入库的数据）
        daily_data = _try_get_from_mongodb_daily(category, keywords)
        if daily_data and daily_data.get("total", 0) > len(news):
            print(f"🔄 [后台] {cache_key} 使用 MongoDB 最近7天全量数据更新缓存 ({daily_data.get('total')} 条)")
            final_result = daily_data
        
        # 3. 写入 MongoDB 快照 (使用全量数据)
        try:
            if db_manager.mongodb_enabled:
                db_manager.news_repo.save_snapshot(cache_key, final_result)
                print(f"✅ [后台] {cache_key} 快照已保存到 MongoDB (包含 {final_result.get('total', 0)} 条)")
        except Exception as e:
            print(f"⚠️ [后台] MongoDB 快照保存失败: {e}")

        # 4. 最后写入 Redis (使用全量数据)
        cache.set(cache_key, final_result, ttl=CACHE_TTL)
        print(f"✅ [后台] {cache_key} 拓取完成: {len(news)} 条 (最终缓存: {final_result.get('total')} 条)")
                    
    except Exception as e:
        print(f"❌ [后台] {cache_key} 拓取失败: {e}")
    finally:
        with _refresh_lock:
            _pending_refreshes.discard(cache_key)


def _trigger_background_refresh(cache_key: str, task_func, *args):
    """触发后台刷新任务（去重）"""
    with _refresh_lock:
        if cache_key in _pending_refreshes:
            print(f"⏳ {cache_key} 已有后台任务进行中，跳过")
            return False
        _pending_refreshes.add(cache_key)
    
    # 在测试环境下跳过真实的后台线程，避免占用 mock side effect、减小干扰
    if _TEST_ENV:
        return True
    _executor.submit(task_func, cache_key, *args)
    return True


def _try_get_from_snapshot(cache_key: str, category: str) -> Dict:
    """
    尝试从 MongoDB 快照获取数据 (快照回源)
    如果成功，会自动回写到 Redis
    """
    try:
        from database.manager import db_manager
        if db_manager.mongodb_enabled:
            # 优先尝试读取快照
            snapshot = db_manager.news_repo.get_snapshot(cache_key)
            if snapshot and snapshot.get("data"):
                print(f"🔄 [API] {category} Redis Miss，从 MongoDB 快照恢复")
                result = snapshot["data"]
                
                # 修复: 确保 snapshot 格式正确
                if isinstance(result, list):
                    result = {
                        "status": "success",
                        "category": category,
                        "data": result,
                        "timestamp": datetime.now().isoformat(),
                        "total": len(result),
                        "cached": False,
                        "from_snapshot": True
                    }
                else:
                    result["from_snapshot"] = True
                    result["cached"] = False
                
                # 补充 sources 统计
                if "sources" not in result or not result["sources"]:
                    sources = {}
                    for item in result.get("data", []):
                        # 补全 platform_name
                        if not item.get("platform_name") and item.get("source"):
                            item["platform_name"] = item["source"]
                            
                        source_name = item.get('platform_name') or item.get('source') or item.get('platform') or '未知'
                        sources[source_name] = sources.get(source_name, 0) + 1
                    result["sources"] = sources
                else:
                    # 即使 sources 存在，也检查一遍 data 中的 platform_name
                    if result.get("data"):
                        for item in result["data"]:
                            if not item.get("platform_name") and item.get("source"):
                                item["platform_name"] = item["source"]
                
                # 回写 Redis
                try:
                    cache.set(cache_key, result, ttl=CACHE_TTL)
                    print(f"✅ [API] {category} 快照数据已回写 Redis")
                except Exception as redis_err:
                    print(f"⚠️ [API] 快照回写 Redis 失败: {redis_err}")
                    
                return result
            else:
                 print(f"⚠️ [API] {category} MongoDB 快照不存在或为空")
    except Exception as e:
        print(f"⚠️ [API] MongoDB 快照恢复失败: {e}")
    return None


def _try_get_from_mongodb_daily(category: str, keywords: list = None, days: int = 7) -> Dict:
    """
    尝试从 MongoDB news 集合查询最近 N 天的数据
    """
    try:
        from database.manager import db_manager
        if db_manager.mongodb_enabled:
            print(f"🔄 [API] {category} 尝试查询 MongoDB 最近 {days} 天数据...")
            
            # 获取起始时间（最近 N 天的零点）
            start_date = (datetime.now() - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
            
            # 构建查询条件
            query = {
                "category": category,
                "published_at": {"$gte": start_date}
            }
            
            # 如果提供了关键词，可以增加标题匹配（可选，视需求而定，这里暂时只按 category 查）
            # if keywords:
            #     query["title"] = {"$regex": "|".join(keywords)}

            # 查询数据，按时间倒序，限制 500 条
            news_items = list(db_manager.news_repo._col.find(
                query, 
                {"_id": 0}  # 不返回 _id
            ).sort("published_at", -1).limit(500))  # 扩大限制以容纳多天数据
            
            if news_items:
                print(f"✅ [API] {category} 从 MongoDB 查到 {len(news_items)} 条最近数据")
                
                # 格式化数据以匹配 API 返回格式
                data = []
                seen_titles = set()  # 用于去重
                sources = {}
                
                for item in news_items:
                    # 去重逻辑
                    title = item.get("title", "")
                    if title in seen_titles:
                        continue
                    seen_titles.add(title)

                    # 转换 datetime 对象为 ISO 格式字符串
                    if isinstance(item.get("published_at"), datetime):
                        item["published_at"] = item["published_at"].isoformat()
                    
                    # 补全 platform_name
                    extra_data = item.get('extra_data', {}) or {}  # 确保 extra_data 是字典
                    platform_name = item.get('platform_name') or extra_data.get('platform_name')
                    source = item.get('source') or extra_data.get('source')
                     
                    if not platform_name and source:
                        platform_name = source
                    
                    if platform_name:
                        item["platform_name"] = platform_name
                    

                    data.append(item)
                    
                    # 统计来源
                    source_name = item.get('platform_name') or item.get('source') or item.get('platform') or '未知'
                    sources[source_name] = sources.get(source_name, 0) + 1
                
                result = {
                    "status": "success",
                    "category": category,
                    "data": data,
                    "timestamp": datetime.now().isoformat(),
                    "total": len(data),
                    "sources": sources,
                    "cached": False,
                    "from_mongodb_daily": True
                }
                return result
            else:
                print(f"⚠️ [API] {category} MongoDB 当日无数据")
    except Exception as e:
        print(f"⚠️ [API] MongoDB 当日数据查询失败: {e}")
    return None


@router.get("/api/commodity-news")
def get_commodity_news(refresh: bool = False):
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
            "sources": {},
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

        # 检查并补全 platform_name
        if cached.get("data"):
            for item in cached["data"]:
                if not item.get("platform_name") and item.get("source"):
                    item["platform_name"] = item["source"]

        return cached
    
    # 缓存未命中，尝试从 MongoDB 快照获取最新数据 (快照回源)
    snapshot_data = _try_get_from_snapshot(cache_key, "commodity")
    if snapshot_data:
        return snapshot_data
    
    # 无缓存且未强制刷新时，自动触发后台刷新
    triggered = _trigger_background_refresh(cache_key, _background_crawl_news, "commodity", True)
    
    return {
        "status": "success",
        "category": "commodity",
        "data": [],
        "sources": {},
        "timestamp": None,
        "cached": False,
        "total": 0,
        "refreshing": triggered,
        "message": "暂无缓存数据，正在后台获取..." if triggered else "数据正在后台加载"
    }


@router.get("/api/news/supply-chain")
def get_supply_chain_news(refresh: bool = False):
    """
    获取供应链相关新闻
    
    优化策略：缓存优先 + 后台异步刷新
    """
    cache_key = "news:supply-chain"
    cached = cache.get(cache_key)
    
    if refresh:
        triggered = _trigger_background_refresh(cache_key, _background_fetch_realtime, SUPPLY_CHAIN_KEYWORDS, "supply-chain")
        
        if cached:
            cached["cached"] = True
            cached["refreshing"] = triggered
            cached["message"] = "数据正在后台刷新" if triggered else "刷新任务已在进行中"
            
            # 补全 platform_name
            if cached.get("data"):
                for item in cached["data"]:
                    extra = item.get("extra_data", {}) or {}
                    p_name = item.get("platform_name") or extra.get("platform_name")
                    src = item.get("source") or extra.get("source")
                    if not p_name and src:
                        p_name = src
                    if p_name:
                        item["platform_name"] = p_name

            return cached
        
        return {
            "status": "success",
            "data": [],
            "sources": {},
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

    # 缓存未命中，尝试从 MongoDB 快照获取最新数据 (快照回源)
    snapshot_data = _try_get_from_snapshot(cache_key, "supply-chain")
    if snapshot_data:
        return snapshot_data
    
    return {
        "status": "success",
        "data": [],
        "sources": {},
        "timestamp": None,
        "cached": False,
        "total": 0,
        "message": "暂无缓存数据，请点击刷新按钮获取最新数据"
    }


@router.get("/api/news/tariff")
def get_tariff_news(refresh: bool = False):
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
            "sources": {},
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

    # 缓存未命中，尝试从 MongoDB 快照获取最新数据 (快照回源)
    snapshot_data = _try_get_from_snapshot(cache_key, "tariff")
    if snapshot_data:
        return snapshot_data
    
    return {
        "status": "success",
        "category": "tariff",
        "data": [],
        "sources": {},
        "timestamp": None,
        "cached": False,
        "total": 0,
        "message": "暂无关税政策缓存数据，请点击刷新按钮获取最新数据"
    }


@router.get("/api/news/plastics")
def get_plastics_news(refresh: bool = False):
    """
    获取塑料相关新闻
    
    优化策略：缓存优先 + 后台异步刷新
    """
    cache_key = "news:plastics"
    cached = cache.get(cache_key)
    
    if refresh:
        triggered = _trigger_background_refresh(cache_key, _background_fetch_realtime, PLASTICS_KEYWORDS, "plastics")
        
        if cached:
            cached["cached"] = True
            cached["refreshing"] = triggered
            cached["message"] = "数据正在后台刷新" if triggered else "刷新任务已在进行中"
            
            # 补全 platform_name
            if cached.get("data"):
                for item in cached["data"]:
                    extra = item.get("extra_data", {}) or {}
                    p_name = item.get("platform_name") or extra.get("platform_name")
                    src = item.get("source") or extra.get("source")
                    if not p_name and src:
                        p_name = src
                    if p_name:
                        item["platform_name"] = p_name

            return cached
        
        return {
            "status": "success",
            "category": "plastics",
            "data": [],
            "sources": {},
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
    
    # 从 MongoDB 查询当日数据
    daily_data = _try_get_from_mongodb_daily("plastics", PLASTICS_KEYWORDS)
    if daily_data:
        # 回写 Redis
        cache.set(cache_key, daily_data, ttl=CACHE_TTL)
        return daily_data

    # 无缓存且未强制刷新时，自动触发后台刷新
    triggered = _trigger_background_refresh(cache_key, _background_fetch_realtime, PLASTICS_KEYWORDS, "plastics")
    
    return {
        "status": "success",
        "category": "plastics",
        "data": [],
        "sources": {},
        "timestamp": None,
        "cached": False,
        "total": 0,
        "refreshing": triggered,
        "message": "暂无缓存数据，正在后台获取..." if triggered else "数据正在后台加载"
    }


@router.get("/api/news/{category}")
def get_news(category: str, include_custom: bool = True, refresh: bool = False):
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
            "sources": {},  # 添加空sources字段
            "timestamp": None,
            "cached": False,
            "total": 0,
            "refreshing": triggered,
            "message": f"{category} 数据正在后台加载"
        }
    
    if cached:
        cached["cached"] = True
        cached["cache_ttl"] = cache.get_ttl(cache_key)
        
        # 补全 platform_name (防止缓存数据缺失)
        if cached.get("data"):
            for item in cached["data"]:
                extra = item.get("extra_data", {}) or {}
                p_name = item.get("platform_name") or extra.get("platform_name")
                src = item.get("source") or extra.get("source")
                if not p_name and src:
                    p_name = src
                if p_name:
                    item["platform_name"] = p_name
        
        return cached
    
    # 缓存未命中，尝试从 MongoDB 快照获取最新数据 (快照回源)
    snapshot_data = _try_get_from_snapshot(cache_key, category)
    if snapshot_data:
        return snapshot_data

    # 无缓存且未强制刷新时，自动触发后台刷新
    triggered = _trigger_background_refresh(cache_key, _background_crawl_news, category, include_custom)
    
    return {
        "status": "success",
        "category": category,
        "data": [],
        "sources": {},  # 添加空sources字段
        "timestamp": None,
        "cached": False,
        "total": 0,
        "refreshing": triggered,
        "message": f"暂无 {category} 缓存数据，正在后台获取..." if triggered else f"{category} 数据正在后台加载"
    }


@router.post("/api/crawl")
def trigger_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    """
    触发爬取任务（后台异步执行）
    
    立即返回响应，爬取在后台进行
    """
    if request.category in ["supply-chain", "supply_chain"]:
        cache_key = "news:supply-chain"
        triggered = _trigger_background_refresh(cache_key, _background_fetch_realtime, SUPPLY_CHAIN_KEYWORDS, None)
    elif request.category == "tariff":
        cache_key = "news:tariff"
        triggered = _trigger_background_refresh(cache_key, _background_fetch_realtime, TARIFF_KEYWORDS, "tariff")
    elif request.category == "plastics":
        cache_key = "news:plastics"
        triggered = _trigger_background_refresh(cache_key, _background_fetch_realtime, PLASTICS_KEYWORDS, "plastics")
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
def get_refresh_status():
    """获取后台刷新任务状态"""
    return {
        "pending_tasks": list(_pending_refreshes),
        "count": len(_pending_refreshes)
    }


# ==================== 客户配置 ====================
CUSTOMERS = {
    "苹果": ["苹果", "Apple", "iPhone", "AirPods", "Apple Watch", "Vision Pro", "iPad", "Mac", "AAPL"],
    "华为": ["华为", "Huawei", "鸿蒙", "Mate", "荣耀", "Honor"],
    "Meta": ["Meta", "Quest", "VR", "Facebook", "Oculus"],
    "小米": ["小米", "Xiaomi", "红米", "Redmi"],
    "OPPO": ["OPPO", "一加", "OnePlus", "realme"],
    "vivo": ["vivo", "iQOO"],
    "三星": ["三星", "Samsung", "Galaxy"],
    "奇瑞汽车": ["奇瑞", "Chery", "星途", "捷途"],
    "特斯拉": ["特斯拉", "Tesla", "Model"],
    "比亚迪": ["比亚迪", "BYD", "仰望", "腾势"],
}

# ==================== 供应商配置 ====================
SUPPLIERS = {
    "IC芯片": {
        "Marvell": ["Marvell", "迈威尔"],
        "Broadcom": ["Broadcom", "博通"],
        "ADI": ["ADI", "亚德诺", "Analog Devices"],
        "TI": ["TI", "德州仪器", "Texas Instruments"],
        "ST": ["ST", "意法半导体", "STMicroelectronics"],
    },
    "PCB": {
        "鹏鼎控股": ["鹏鼎", "002938"],
        "东山精密": ["东山精密", "002384"],
        "深南电路": ["深南电路", "002916"],
    },
    "被动元件": {
        "村田": ["村田", "Murata"],
        "国巨": ["国巨", "Yageo"],
        "风华高科": ["风华高科", "000636"],
    },
    "注塑/压铸": {
        "领益智造": ["领益智造", "002600"],
        "长盈精密": ["长盈精密", "300115"],
    },
}

# ==================== 物料品类配置 ====================
MATERIALS = {
    "IC/芯片": ["IC", "芯片", "MCU", "CPU", "GPU", "SoC", "FPGA", "存储", "内存"],
    "PCB/电路板": ["PCB", "电路板", "FPC", "柔性电路", "HDI"],
    "连接器": ["连接器", "接插件", "端子", "FFC", "FPC连接器"],
    "被动元件": ["电阻", "电容", "电感", "MLCC", "贴片电阻"],
    "传感器": ["传感器", "摄像头", "CIS", "陀螺仪", "加速度计"],
    "电池": ["电池", "锂电", "电芯", "BMS", "充电"],
    "显示屏": ["显示屏", "LCD", "OLED", "AMOLED", "面板"],
    "结构件": ["结构件", "外壳", "中框", "散热", "压铸", "注塑"],
}


def _match_news(news_list, entity_config, website_map=None):
    """通用新闻匹配函数"""
    stats = {}
    for name, keywords in entity_config.items():
        count = 0
        matched_news = []
        for news in news_list:
            title = news.get("title", "")
            summary = news.get("summary", "") or news.get("content", "")
            text = f"{title} {summary}"
            
            for kw in keywords:
                if kw in text:
                    count += 1
                    matched_news.append({
                        "title": title,
                        "url": news.get("url", ""),
                        "source": news.get("source", ""),
                        "publish_time": news.get("publish_time", ""),
                        "matched_keyword": kw
                    })
                    break
        
        # 按发布时间排序（最新在前）
        matched_news.sort(key=lambda x: x.get("publish_time", ""), reverse=True)
        
        stats[name] = {
            "keywords": keywords,
            "news_count": count,
            "news": matched_news[:10],  # 最多返回10条
            "website": (website_map or {}).get(name)
        }
    return stats


@router.get("/api/partner-news-stats")
def get_partner_news_stats():
    """获取友商新闻统计"""
    cached = cache.get("news:supply-chain")
    news_list = cached.get("data", []) if cached else []
    
    categories = {
        "光电模块": OPTICAL_PARTNERS,
        "连接器": CONNECTOR_PARTNERS,
        "电源": POWER_PARTNERS,
    }
    
    stats = {}
    for category_name, partners in categories.items():
        website_map = POWER_PARTNER_SITES if category_name == "电源" else None
        stats[category_name] = _match_news(news_list, partners, website_map)
    
    total_partners = sum(len(p) for p in categories.values())
    partners_with_news = sum(
        1 for cat in stats.values() 
        for p in cat.values() 
        if p["news_count"] > 0
    )
    
    # 计算匹配的新闻总数
    matched_total = sum(
        p["news_count"] for cat in stats.values() for p in cat.values()
    )
    
    return {
        "status": "success",
        "total_news": matched_total,
        "total_partners": total_partners,
        "partners_with_news": partners_with_news,
        "stats": stats
    }


@router.get("/api/customer-news-stats")
def get_customer_news_stats():
    """获取客户新闻统计"""
    cached = cache.get("news:supply-chain")
    news_list = cached.get("data", []) if cached else []
    
    stats = _match_news(news_list, CUSTOMERS)
    
    customers_with_news = sum(1 for c in stats.values() if c["news_count"] > 0)
    matched_total = sum(c["news_count"] for c in stats.values())
    
    return {
        "status": "success",
        "total_news": matched_total,
        "total_customers": len(CUSTOMERS),
        "customers_with_news": customers_with_news,
        "stats": stats
    }


@router.get("/api/supplier-news-stats")
def get_supplier_news_stats():
    """获取供应商新闻统计"""
    cached = cache.get("news:supply-chain")
    news_list = cached.get("data", []) if cached else []
    
    stats = {}
    for category, suppliers in SUPPLIERS.items():
        stats[category] = _match_news(news_list, suppliers)
    
    total_suppliers = sum(len(s) for s in SUPPLIERS.values())
    suppliers_with_news = sum(
        1 for cat in stats.values()
        for s in cat.values()
        if s["news_count"] > 0
    )
    matched_total = sum(
        s["news_count"] for cat in stats.values() for s in cat.values()
    )
    
    return {
        "status": "success",
        "total_news": matched_total,
        "total_suppliers": total_suppliers,
        "suppliers_with_news": suppliers_with_news,
        "stats": stats
    }


@router.get("/api/material-news-stats")
def get_material_news_stats():
    """获取物料品类新闻统计"""
    cached = cache.get("news:supply-chain")
    news_list = cached.get("data", []) if cached else []
    
    stats = _match_news(news_list, MATERIALS)
    
    materials_with_news = sum(1 for m in stats.values() if m["news_count"] > 0)
    matched_total = sum(m["news_count"] for m in stats.values())
    
    return {
        "status": "success",
        "total_news": matched_total,
        "total_materials": len(MATERIALS),
        "materials_with_news": materials_with_news,
        "stats": stats
    }


@router.get("/api/tariff-news-stats")
def get_tariff_news_stats():
    """获取关税政策新闻统计（AI智能分类）"""
    cached = cache.get("news:tariff")
    news_list = cached.get("data", []) if cached else []
    
    # 智能分类规则
    categories = {
        "中美关税": ["中美", "美国", "特朗普", "拜登", "301", "贸易战", "美中"],
        "欧盟政策": ["欧盟", "欧洲", "CBAM", "碳关税", "碳边境"],
        "出口管制": ["出口管制", "实体清单", "制裁", "禁令", "管制"],
        "进口关税": ["进口", "加征", "关税", "税率", "海关"],
        "自贸协定": ["自贸", "FTA", "RCEP", "协定", "减免"],
        "其他政策": []  # 兜底分类
    }
    
    stats = {}
    used_news = set()
    
    for cat_name, keywords in categories.items():
        matched_news = []
        for news in news_list:
            if id(news) in used_news:
                continue
            title = news.get("title", "")
            
            if keywords:  # 有关键词的分类
                if any(kw in title for kw in keywords):
                    matched_news.append({
                        "title": title,
                        "url": news.get("url", ""),
                        "source": news.get("source", ""),
                        "publish_time": news.get("publish_time", "")
                    })
                    used_news.add(id(news))
            else:  # "其他政策" 兜底
                matched_news.append({
                    "title": title,
                    "url": news.get("url", ""),
                    "source": news.get("source", ""),
                    "publish_time": news.get("publish_time", "")
                })
        
        # 按发布时间排序（最新在前）
        matched_news.sort(key=lambda x: x.get("publish_time", ""), reverse=True)
        
        stats[cat_name] = {
            "news_count": len(matched_news),
            "news": matched_news[:10]
        }
    
    matched_total = sum(s["news_count"] for s in stats.values())
    
    return {
        "status": "success",
        "total_news": matched_total,
        "stats": stats
    }


@router.get("/api/reader/{news_id}")
def read_news_article(news_id: str):
    """
    新闻阅读器 - 显示保存的文章内容
    
    用于需要登录的外部网站（如 Plasway），直接显示已爬取的内容
    """
    from fastapi.responses import HTMLResponse
    
    # 直接使用全局缓存获取内容
    # cache.get 会自动处理 key 前缀 (trendradar:) 和 JSON 解析
    news = cache.get(f"reader:{news_id}")
    
    if not news:
        raise HTTPException(status_code=404, detail="文章内容不可用或已过期")
    
    # 返回美化的 HTML 页面
    html_template = f"""
        <!DOCTYPE html>
        <html lang="zh-CN">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{news.get('title', '文章阅读')}</title>
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{ 
                    max-width: 800px; 
                    margin: 0 auto; 
                    padding: 40px 20px;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                    line-height: 1.8;
                    background: #f9fafb;
                    color: #1f2937;
                }}
                .container {{
                    background: white;
                    border-radius: 12px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                    padding: 40px;
                }}
                .header {{
                    border-bottom: 2px solid #e5e7eb;
                    padding-bottom: 24px;
                    margin-bottom: 32px;
                }}
                h1 {{ 
                    font-size: 28px; 
                    font-weight: 700;
                    margin-bottom: 16px;
                    color: #111827;
                    line-height: 1.4;
                }}
                .meta {{ 
                    color: #6b7280; 
                    font-size: 14px;
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    flex-wrap: wrap;
                }}
                .source-badge {{
                    display: inline-block;
                    background: linear-gradient(135deg, #3b82f6, #2563eb);
                    color: white;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                    font-weight: 500;
                }}
                .section-badge {{
                    display: inline-block;
                    background: #f3f4f6;
                    color: #4b5563;
                    padding: 4px 12px;
                    border-radius: 20px;
                    font-size: 12px;
                }}
                .content {{
                    font-size: 17px;
                    color: #374151;
                    white-space: pre-wrap;
                }}
                .content p {{
                    margin-bottom: 16px;
                }}
                .footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid #e5e7eb;
                    font-size: 13px;
                    color: #9ca3af;
                    text-align: center;
                }}
                .footer a {{
                    color: #3b82f6;
                    text-decoration: none;
                }}
                .footer a:hover {{
                    text-decoration: underline;
                }}
                .back-btn {{
                    display: inline-flex;
                    align-items: center;
                    gap: 6px;
                    color: #3b82f6;
                    text-decoration: none;
                    font-size: 14px;
                    margin-bottom: 20px;
                }}
                .back-btn:hover {{
                    text-decoration: underline;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <a href="javascript:history.back()" class="back-btn">
                    ← 返回列表
                </a>
                <div class="header">
                    <h1>{news.get('title', '')}</h1>
                    <div class="meta">
                        <span class="source-badge">{news.get('source', 'Plasway')}</span>
                        <span class="section-badge">{news.get('section', '行业资讯')}</span>
                        <span>{news.get('timestamp', '')[:10] if news.get('timestamp') else ''}</span>
                    </div>
                </div>
                <div class="content">
                    {news.get('content', '内容加载中...')}
                </div>
                <div class="footer">
                    内容来源：<a href="{news.get('original_url', '#')}" target="_blank" rel="noopener">原文链接</a>
                    <br>
                    由 TrendRadar 自动抓取并缓存
                </div>
            </div>
        </body>
        </html>
        """
        
    return HTMLResponse(content=html_template)
