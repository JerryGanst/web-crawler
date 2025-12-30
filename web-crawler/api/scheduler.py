# coding=utf-8
"""
后台定时任务调度器

功能：
1. 服务启动时自动预热缓存
2. 定期刷新各分类数据
3. 避免用户等待爬虫

调度策略：
- 启动时：预热所有分类缓存
- 每 30 分钟：刷新财经、科技、新闻
- 每 15 分钟：刷新大宗商品数据
- 每 10 分钟：刷新供应链、关税新闻
"""

import asyncio
import os
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List

from .cache import cache, CACHE_TTL


class BackgroundScheduler:
    """后台任务调度器"""
    
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="scheduler")
        self._running = False
        self._tasks: Dict[str, dict] = {}
        self._test_env = "PYTEST_CURRENT_TEST" in os.environ
    
    def _crawl_category(self, category: str, include_custom: bool = True):
        """爬取指定分类"""
        try:
            from scrapers.unified import UnifiedDataSource
            
            print(f"⏰ [定时] 开始爬取 {category}...")
            unified = UnifiedDataSource()
            data = unified.crawl_category(category, include_custom=include_custom)
            
            # 1. 写入 MongoDB
            try:
                from database.manager import db_manager
                if db_manager.mongodb_enabled:
                    # 将普通字典转换为 News 对象
                    from database.models import News
                    news_objects = []
                    for item in data:
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
                            platform_name=item.get("platform_name") or item.get("source", ""),
                            summary=item.get("summary", "") or item.get("content", "")[:200]
                        ))
                    
                    inserted, updated = db_manager.news_repo.insert_batch(news_objects)
                    print(f"✅ [定时] {category} 归档到 MongoDB: 新增 {inserted}, 更新 {updated}")
            except Exception as e:
                print(f"⚠️ [定时] MongoDB 归档失败: {e}")

            result = {
                "status": "success",
                "category": category,
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "total": len(data),
                "cached": False,
                "scheduled_refresh": True
            }
            
            # 默认先设置当前抓取结果为缓存
            final_result = result
            cache_key = f"news:{category}"

            # 尝试从 MongoDB 获取最近 7 天的全量数据
            # 只要启用了 MongoDB，就尝试合并历史数据，确保展示完整
            from api.routes.news import _try_get_from_mongodb_daily
            daily_data = _try_get_from_mongodb_daily(category)
            
            if daily_data and daily_data.get("total", 0) > len(data):
                print(f"🔄 [定时] {category} 使用 MongoDB 最近7天全量数据更新缓存 ({daily_data.get('total')} 条)")
                final_result = daily_data
            
            # 2. 写入 MongoDB 快照 (作为 Redis 的持久化备份)
            try:
                from database.manager import db_manager
                if db_manager.mongodb_enabled:
                    # 快照也使用 final_result (全量数据)
                    db_manager.news_repo.save_snapshot(cache_key, final_result)
                    print(f"✅ [定时] {category} 快照已保存到 MongoDB (包含 {final_result.get('total', 0)} 条)")
            except Exception as e:
                print(f"⚠️ [定时] MongoDB 快照保存失败: {e}")
            
            # 3. 写入 Redis
            cache.set(cache_key, final_result, ttl=CACHE_TTL)
                
            print(f"⏰ [定时] {category} 完成: {len(data)} 条 (最终缓存: {final_result.get('total', 0)} 条)")
        except Exception as e:
            print(f"⏰ [定时] {category} 失败: {e}")
    
    def _crawl_commodity_data(self):
        """爬取大宗商品数据"""
        try:
            from scrapers.commodity import CommodityScraper
            from database.manager import db_manager
            
            print(f"⏰ [定时] 开始爬取大宗商品数据...")
            scraper = CommodityScraper()
            raw_data = scraper.scrape()
            print(f"✅ [Scheduler] Scraped {len(raw_data)} commodity items")
            
            # 1. 写入 MySQL（Pipeline 会自动去重），按来源分组
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
                    print(f"✅ [定时] MySQL 入库完成: {stats_by_source}")
            except Exception as e:
                print(f"⚠️ [定时] MySQL 入库失败: {e}")

            # 2. 从 MySQL commodity_latest 读取去重后的数据（以 MySQL 为准）
            try:
                latest_data = db_manager.get_commodity_latest()
                if not latest_data:
                    print("⚠️ [定时] MySQL commodity_latest 为空，使用原始数据")
                    latest_data = raw_data
                else:
                    print(f"✅ [定时] 从 MySQL 读取: {len(latest_data)} 条去重数据")
                    # 字段映射：MySQL → API 格式 (内联实现，避免循环依赖)
                    for item in latest_data:
                        # 1. 合并 unit
                        price_unit = item.get('price_unit', '')
                        weight_unit = item.get('weight_unit', '')
                        if price_unit and weight_unit:
                            item['unit'] = f"{price_unit}/{weight_unit}"
                        else:
                            item['unit'] = price_unit or weight_unit or 'USD'
                        
                        # 2. current_price
                        if 'price' in item and 'current_price' not in item:
                            item['current_price'] = item['price']
                        
                        # 3. url
                        if 'url' not in item or not item['url']:
                            item['url'] = item.get('source_url', '')

                        # 4. cleanup
                        for k in ['id', 'price_unit', 'weight_unit', 'version_ts', 'source_url']:
                            item.pop(k, None)

            except Exception as e:
                print(f"⚠️ [定时] 从 MySQL 读取失败: {e}，使用原始数据")
                latest_data = raw_data
            
            # 3. 排序
            category_order = {'贵金属': 0, '能源': 1, '工业金属': 2, '农产品': 3, '其他': 4}
            latest_data.sort(key=lambda x: category_order.get(x.get('category', '其他'), 4))
            
            # 4. 写入 Redis
            result = {
                "data": latest_data,
                "source": "TrendRadar Commodity",
                "timestamp": datetime.now().isoformat(),
                "cached": False,
                "scheduled_refresh": True,
                "from_mysql": True,
                "categories": list(set(item.get('category', '其他') for item in latest_data)),
                "total": len(latest_data)
            }
            cache.set("data:commodity", result, ttl=CACHE_TTL)
            
            print(f"⏰ [定时] 大宗商品数据完成: {len(latest_data)} 条")
        except Exception as e:
            print(f"⏰ [定时] 大宗商品数据失败: {e}")
    
    def _fetch_realtime_news(self, cache_key: str, keywords: list, category: str = None):
        """抓取实时新闻"""
        try:
            from api.routes.analysis import fetch_realtime_news
            from api.routes.news import _fetch_power_partner_news, _fetch_power_official_announcements
            
            print(f"⏰ [定时] 开始抓取 {cache_key}...")
            news = fetch_realtime_news(keywords)
            if category == "supply-chain":
                power_news = _fetch_power_partner_news()
                official_news = _fetch_power_official_announcements()
                seen = {n.get("title") for n in news}
                for item in power_news + official_news:
                    if item.get("title") and item["title"] not in seen:
                        seen.add(item["title"])
                        news.append(item)
            
            # 补全 platform_name (确保入库和缓存都有该字段)
            for item in news:
                if not item.get("platform_name") and item.get("source"):
                    item["platform_name"] = item["source"]
            
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
                            # source removed
                            published_at=published_at,
                            category=category,
                            extra_data=item,
                            source=item.get("source", ""),
                            platform_name=item.get("platform_name", ""),
                            summary=item.get("summary", "") or item.get("content", "")[:200]
                        ))
                    
                    inserted, updated = db_manager.news_repo.insert_batch(news_objects)
                    print(f"✅ [定时] {category} (实时) 归档到 MongoDB: 新增 {inserted}, 更新 {updated}")
            except Exception as e:
                print(f"⚠️ [定时] MongoDB 归档失败: {e}")
            
            result = {
                "status": "success",
                "data": news,
                "timestamp": datetime.now().isoformat(),
                "total": len(news),
                "sources": sources,  # 添加 sources 统计
                "cached": False,
                "scheduled_refresh": True
            }

            # 尝试从 MongoDB 获取最近 7 天的全量数据
            # 只要启用了 MongoDB，就尝试合并历史数据，确保展示完整
            from api.routes.news import _try_get_from_mongodb_daily
            daily_data = _try_get_from_mongodb_daily(category, keywords) # keywords 可能为空，但在 _try_get_from_mongodb_daily 内部处理了
            
            if daily_data and daily_data.get("total", 0) > len(news):
                print(f"🔄 [定时] {cache_key} 使用 MongoDB 最近7天全量数据更新缓存 ({daily_data.get('total')} 条)")
                final_result = daily_data
            
            # 2. 写入 MongoDB 快照 (作为 Redis 的持久化备份)
            try:
                from database.manager import db_manager
                if db_manager.mongodb_enabled:
                    # 快照也使用 final_result (全量数据)
                    db_manager.news_repo.save_snapshot(cache_key, final_result)
                    print(f"✅ [定时] {cache_key} 快照已保存到 MongoDB (包含 {final_result.get('total', 0)} 条)")
            except Exception as e:
                print(f"⚠️ [定时] MongoDB 快照保存失败: {e}")

            # 3. 写入 Redis
            cache.set(cache_key, final_result, ttl=CACHE_TTL)
            
            print(f"⏰ [定时] {cache_key} 完成: {len(news)} 条 (最终缓存: {final_result.get('total', 0)} 条)")
        except Exception as e:
            print(f"⏰ [定时] {cache_key} 失败: {e}")
    
    def warmup_cache(self):
        """预热缓存（启动时调用）"""
        if self._test_env:
            print("🔥 跳过测试环境下的预热任务")
            return
        print("🔥 开始预热缓存...")
        
        # 从 news.py 导入统一的关键词配置
        from .routes.news import SUPPLY_CHAIN_KEYWORDS, TARIFF_KEYWORDS, PLASTICS_KEYWORDS
        supply_chain_keywords = SUPPLY_CHAIN_KEYWORDS
        tariff_keywords = TARIFF_KEYWORDS
        plastics_keywords = PLASTICS_KEYWORDS
        
        # 预热任务列表
        warmup_tasks = [
            ("大宗商品数据", self._crawl_commodity_data),
            ("财经新闻", lambda: self._crawl_category("finance")),
            ("科技新闻", lambda: self._crawl_category("tech")),
            ("供应链新闻", lambda: self._fetch_realtime_news("news:supply-chain", supply_chain_keywords, "supply-chain")),
            ("关税新闻", lambda: self._fetch_realtime_news("news:tariff", tariff_keywords, "tariff")),
            ("塑料新闻", lambda: self._fetch_realtime_news("news:plastics", plastics_keywords, "plastics")),
            ("大宗商品新闻", lambda: self._crawl_category("commodity")),
        ]
        
        for name, task in warmup_tasks:
            try:
                self._executor.submit(task)
                print(f"  📌 已提交: {name}")
            except Exception as e:
                print(f"  ❌ 提交失败 {name}: {e}")
        
        print("🔥 预热任务已全部提交")
    
    def start_scheduled_tasks(self):
        """启动定时任务（非阻塞）"""
        if self._running:
            return
        
        self._running = True
        if self._test_env:
            # 测试环境不启动后台循环，避免干扰其它用例的 mock
            return
        
        def scheduler_loop():
            """调度循环"""
            # 从 news.py 导入统一的关键词配置
            from .routes.news import SUPPLY_CHAIN_KEYWORDS, TARIFF_KEYWORDS
            supply_chain_keywords = SUPPLY_CHAIN_KEYWORDS
            tariff_keywords = TARIFF_KEYWORDS
            
            # 任务配置：(间隔秒数, 上次执行时间, 任务函数)
            tasks = {
                "commodity_data": {
                    "interval": 15 * 60,  # 15分钟
                    "last_run": 0,
                    "func": self._crawl_commodity_data
                },
                "finance_news": {
                    "interval": 30 * 60,  # 30分钟
                    "last_run": 0,
                    "func": lambda: self._crawl_category("finance")
                },
                "tech_news": {
                    "interval": 30 * 60,
                    "last_run": 0,
                    "func": lambda: self._crawl_category("tech")
                },
                "supply_chain": {
                    "interval": 10 * 60,  # 10分钟
                    "last_run": 0,
                    "func": lambda: self._fetch_realtime_news("news:supply-chain", supply_chain_keywords, "supply-chain")
                },
                "tariff": {
                    "interval": 10 * 60,
                    "last_run": 0,
                    "func": lambda: self._fetch_realtime_news("news:tariff", tariff_keywords, "tariff")
                }
            }
            
            import time
            while self._running:
                now = time.time()
                
                for name, config in tasks.items():
                    if now - config["last_run"] >= config["interval"]:
                        try:
                            self._executor.submit(config["func"])
                            config["last_run"] = now
                            print(f"⏰ [调度] 已触发: {name}")
                        except Exception as e:
                            print(f"⏰ [调度] 触发失败 {name}: {e}")
                
                # 每分钟检查一次
                time.sleep(60)
        
        # 在后台线程运行调度循环
        thread = threading.Thread(target=scheduler_loop, daemon=True, name="scheduler-main")
        thread.start()
        print("⏰ 定时任务调度器已启动")
    
    def stop(self):
        """停止调度器"""
        self._running = False
        self._executor.shutdown(wait=False)
        print("⏰ 定时任务调度器已停止")


# 全局调度器实例
scheduler = BackgroundScheduler()
