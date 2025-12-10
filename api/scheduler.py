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
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="scheduler")
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
            
            result = {
                "status": "success",
                "category": category,
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "total": len(data),
                "cached": False,
                "scheduled_refresh": True
            }
            cache.set(f"news:{category}", result, ttl=CACHE_TTL)
            print(f"⏰ [定时] {category} 完成: {len(data)} 条")
        except Exception as e:
            print(f"⏰ [定时] {category} 失败: {e}")
    
    def _crawl_commodity_data(self):
        """爬取大宗商品数据"""
        try:
            from scrapers.commodity import CommodityScraper
            
            print(f"⏰ [定时] 开始爬取大宗商品数据...")
            scraper = CommodityScraper()
            data = scraper.scrape()
            
            category_order = {'贵金属': 0, '能源': 1, '工业金属': 2, '农产品': 3, '其他': 4}
            data.sort(key=lambda x: category_order.get(x.get('category', '其他'), 4))
            
            result = {
                "data": data,
                "source": "TrendRadar Commodity",
                "timestamp": datetime.now().isoformat(),
                "cached": False,
                "scheduled_refresh": True,
                "categories": list(set(item.get('category', '其他') for item in data))
            }
            cache.set("data:commodity", result, ttl=CACHE_TTL)
            
            # 保存价格历史
            try:
                from core.price_history import PriceHistoryManager
                history_manager = PriceHistoryManager()
                history_manager.save_current_prices(data)
            except Exception as e:
                print(f"⚠️ [定时] 保存价格历史失败: {e}")
            
            print(f"⏰ [定时] 大宗商品数据完成: {len(data)} 条")
        except Exception as e:
            print(f"⏰ [定时] 大宗商品数据失败: {e}")
    
    def _fetch_realtime_news(self, cache_key: str, keywords: list, category: str = None):
        """抓取实时新闻"""
        try:
            from api.routes.analysis import fetch_realtime_news
            
            print(f"⏰ [定时] 开始抓取 {cache_key}...")
            news = fetch_realtime_news(keywords)
            
            result = {
                "status": "success",
                "data": news,
                "timestamp": datetime.now().isoformat(),
                "total": len(news),
                "cached": False,
                "scheduled_refresh": True
            }
            if category:
                result["category"] = category
            cache.set(cache_key, result, ttl=CACHE_TTL)
            print(f"⏰ [定时] {cache_key} 完成: {len(news)} 条")
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
            ("供应链新闻", lambda: self._fetch_realtime_news("news:supply-chain", supply_chain_keywords)),
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
                    "func": lambda: self._fetch_realtime_news("news:supply-chain", supply_chain_keywords)
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
