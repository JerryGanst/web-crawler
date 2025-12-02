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
        """从 newsnow API 爬取数据"""
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
                    time.sleep(random.uniform(2, 4))
        return []
    
    def crawl_custom(self, scraper_name: str, scraper_config: Dict) -> List[Dict]:
        """使用自定义爬虫爬取"""
        from .factory import ScraperFactory
        
        scraper = ScraperFactory.create(scraper_name, scraper_config)
        if scraper:
            return scraper.scrape()
        return []
    
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
        
        # 1. 爬取 newsnow 平台
        for p in platforms:
            pid = p["id"]
            pname = p["name"]
            print(f"  🔄 {pname} ({pid})...", end=" ")
            
            items = self.crawl_newsnow(pid)
            if items:
                # 标准化数据格式
                for item in items:
                    item["platform"] = pid
                    item["platform_name"] = pname
                    item["category"] = category
                    item["source"] = "newsnow"
                all_data.extend(items)
                print(f"✅ {len(items)} 条")
            else:
                print("❌ 失败")
            
            time.sleep(random.uniform(0.5, 1.5))
        
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
        
        print(f"\n📊 共获取 {len(all_data)} 条数据")
        return all_data
    
    def push_to_wework(self, data: List[Dict], category: str, webhook_url: str):
        """推送数据到企业微信"""
        if not webhook_url:
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
        print(f"\n📤 正在推送到企业微信（共 {len(by_source)} 批）...")
        
        success_count = 0
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
            
            resp = requests.post(webhook_url, json={
                "msgtype": "markdown",
                "markdown": {"content": message}
            })
            
            if resp.status_code == 200 and resp.json().get("errcode") == 0:
                success_count += 1
            else:
                print(f"  ❌ 第 {batch_num} 批失败")
            
            batch_num += 1
            time.sleep(1)
        
        print(f"✅ 推送完成！成功 {success_count}/{len(by_source)} 批")
