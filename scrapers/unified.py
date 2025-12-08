"""
统一数据源管理器
整合 newsnow API 和自定义爬虫，提供统一的爬取接口
"""
import yaml
import time
import random
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


class UnifiedDataSource:
    """统一数据源管理器"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
        
        # 注册自定义爬虫
        from .finance import register_finance_scrapers
        register_finance_scrapers()
    
    def _load_config(self) -> Dict:
        """加载配置"""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def get_platforms_by_category(self, category: str) -> List[Dict]:
        """获取指定分类的平台列表"""
        platforms = self.config.get("platforms", [])
        if category == "all":
            return platforms
        return [p for p in platforms if p.get("category") == category]
    
    def get_categories(self) -> Dict:
        """获取所有分类"""
        return self.config.get("categories", {})
    
    def crawl_newsnow(self, platform_id: str) -> List[Dict]:
        """从 newsnow API 爬取数据（单平台）"""
        url = f"https://newsnow.busiyi.world/api/s?id={platform_id}&latest"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
        }
        
        for retry in range(3):
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                
                if data.get("status") in ["success", "cache"]:
                    items = data.get("items", [])
                    return items
            except Exception:
                if retry < 2:
                    time.sleep(random.uniform(0.5, 1.5))
        return []
    
    def crawl_custom(self, scraper_name: str, scraper_config: Dict = None) -> List[Dict]:
        """使用自定义爬虫爬取，自动从 YAML 加载配置"""
        from .factory import ScraperFactory
        
        # 如果没传配置，从 YAML 加载
        if not scraper_config:
            scraper_config = self._load_scraper_config(scraper_name)
        
        scraper = ScraperFactory.create(scraper_name, scraper_config)
        if scraper:
            return scraper.scrape()
        return []
    
    def _load_scraper_config(self, scraper_name: str) -> Dict:
        """从 scrapers.yaml 加载指定爬虫的配置"""
        try:
            yaml_path = "config/scrapers.yaml"
            with open(yaml_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            custom_scrapers = config.get("custom_scrapers", {})
            return custom_scrapers.get(scraper_name, {})
        except Exception as e:
            print(f"⚠️ 加载爬虫配置失败 {scraper_name}: {e}")
            return {}
    
    def crawl_category(self, category: str, include_custom: bool = True) -> List[Dict]:
        """
        爬取指定分类的所有数据
        
        Args:
            category: 分类名称 (finance, news, social, tech, all)
            include_custom: 是否包含自定义爬虫的数据
        
        Returns:
            统一格式的数据列表
        """
        all_data = []
        platforms = self.get_platforms_by_category(category)
        category_info = self.get_categories().get(category, {})
        category_name = category_info.get("name", category)
        
        print(f"\n📂 正在爬取【{category_name}】分类")
        print("=" * 50)
        
        # 1. 并发爬取 newsnow 平台
        max_workers = min(8, max(1, len(platforms)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self.crawl_newsnow, p["id"]): p for p in platforms
            }

            for future in as_completed(future_map):
                p = future_map[future]
                pid = p["id"]
                pname = p["name"]
                try:
                    items = future.result()
                    if items:
                        for item in items:
                            item["platform"] = pid
                            item["platform_name"] = pname
                            item["category"] = category
                            item["source"] = "newsnow"
                        all_data.extend(items)
                        print(f"  ✅ {pname} ({pid}) {len(items)} 条")
                    else:
                        print(f"  ❌ {pname} ({pid}) 无数据")
                except Exception as e:
                    print(f"  ❌ {pname} ({pid}) 失败: {e}")
        
        # 2. 爬取自定义数据源（如果启用）
        if include_custom and category == "finance":
            print(f"\n  📊 自定义财经数据源:")
            
            # 新浪外汇
            print(f"  🔄 新浪外汇...", end=" ")
            forex_data = self.crawl_custom("sina_forex", {})
            if forex_data:
                for item in forex_data:
                    item["source"] = "custom"
                all_data.extend(forex_data)
                print(f"✅ {len(forex_data)} 条")
            else:
                print("❌ 失败")
            
            # CoinGecko
            print(f"  🔄 CoinGecko 加密货币...", end=" ")
            crypto_data = self.crawl_custom("coingecko", {})
            if crypto_data:
                for item in crypto_data:
                    item["source"] = "custom"
                all_data.extend(crypto_data)
                print(f"✅ {len(crypto_data)} 条")
            else:
                print("❌ 失败")
            
            # 东方财富供应链企业动态
            print(f"  🔄 东方财富供应链动态...", end=" ")
            supply_chain_data = self.crawl_custom("eastmoney_supply_chain", {})
            if supply_chain_data:
                for item in supply_chain_data:
                    item["source"] = "custom"
                    item["platform_name"] = "东方财富"
                all_data.extend(supply_chain_data)
                print(f"✅ {len(supply_chain_data)} 条")
            else:
                print("❌ 失败")
        
        if include_custom and category == "tech":
            print(f"\n  📊 自定义科技数据源:")
            
            # Hacker News
            print(f"  🔄 Hacker News...", end=" ")
            hn_data = self.crawl_custom("hackernews", {})
            if hn_data:
                for item in hn_data:
                    item["source"] = "custom"
                all_data.extend(hn_data)
                print(f"✅ {len(hn_data)} 条")
            else:
                print("❌ 失败")
        
        # 3. 爬取大宗商品数据源
        if include_custom and category == "commodity":
            print(f"\n  📊 自定义大宗商品数据源:")
            
            # 上海有色金属网
            print(f"  🔄 上海有色网...", end=" ")
            smm_data = self.crawl_custom("smm_news", {})
            if smm_data:
                for item in smm_data:
                    item["source"] = "custom"
                    item["platform"] = "smm"
                    item["platform_name"] = "上海有色网"
                    item["category"] = "commodity"
                all_data.extend(smm_data)
                print(f"✅ {len(smm_data)} 条")
            else:
                print("❌ 失败")

            # Plasway 行业消息（塑料/大宗）
            print(f"  🔄 Plasway行业消息...", end=" ")
            plasway_data = self.crawl_custom("plasway_industry")
            if plasway_data:
                for item in plasway_data:
                    item["source"] = "custom"
                    item["platform"] = "plasway"
                    item["platform_name"] = "Plasway"
                    item["category"] = "commodity"
                all_data.extend(plasway_data)
                print(f"✅ {len(plasway_data)} 条")
            else:
                print("❌ 失败")
        
        print(f"\n📊 共获取 {len(all_data)} 条数据")
        return all_data
    
    def push_to_wework(self, data: List[Dict], category: str, webhook_url):
        """推送数据到企业微信（支持字符串或列表 URL）"""
        if isinstance(webhook_url, list):
            webhook_urls = webhook_url
        elif isinstance(webhook_url, str) and webhook_url:
            webhook_urls = [webhook_url]
        else:
            print("❌ 未配置企业微信 webhook")
            return

        if not data:
            print("❌ 没有数据可推送")
            return
        
        category_info = self.get_categories().get(category, {})
        category_name = category_info.get("name", category)
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 按平台/来源分组
        by_source = {}
        for item in data:
            source_name = item.get("platform_name", item.get("platform", "未知"))
            if source_name not in by_source:
                by_source[source_name] = []
            by_source[source_name].append(item)
        
        # 分批发送
        print(f"\n📤 正在推送到企业微信（共 {len(by_source)} 批，{len(webhook_urls)} 个 webhook）...")
        
        batch_num = 1
        
        for source_name, items in by_source.items():
            lines = [f"## 📊 {category_name}热点 ({now}) [{batch_num}]\n"]
            lines.append(f"### 📰 {source_name}")
            
            for i, item in enumerate(items[:10], 1):
                title = item.get("title", "")
                url = item.get("url", "")
                if url:
                    lines.append(f"{i}. [{title}]({url})")
                else:
                    lines.append(f"{i}. {title}")
            
            message = "\n".join(lines)
            
            for wurl in webhook_urls:
                try:
                    resp = requests.post(wurl, json={
                        "msgtype": "markdown",
                        "markdown": {"content": message}
                    })
                    if resp.status_code != 200 or resp.json().get("errcode") != 0:
                        print(f"  ❌ {source_name} 发送失败 ({wurl[:20]}...)")
                except Exception as e:
                    print(f"  ❌ {source_name} 发送异常: {e}")
            
            batch_num += 1
            time.sleep(1)
