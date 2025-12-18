"""
财经专用爬虫
处理需要特殊解析的财经数据源
"""
import re
import json
import requests
from typing import List, Dict, Any
from datetime import datetime
from .base import BaseScraper


class SinaForexScraper(BaseScraper):
    """新浪财经外汇爬虫"""
    
    def __init__(self, name: str = "sina_forex", config: Dict = None):
        config = config or {}
        config["display_name"] = config.get("display_name", "新浪财经外汇")
        config["category"] = "finance"
        super().__init__(name, config)
        
        # 常用汇率代码
        self.forex_codes = [
            ("fx_susdcny", "美元/人民币"),
            ("fx_seurcny", "欧元/人民币"),
            ("fx_sgbpcny", "英镑/人民币"),
            ("fx_sjpycny", "日元/人民币"),
            ("fx_shkdcny", "港币/人民币"),
        ]
    
    def scrape(self) -> List[Dict[str, Any]]:
        """爬取汇率数据"""
        items = []
        
        codes = ",".join([code for code, _ in self.forex_codes])
        url = f"https://hq.sinajs.cn/list={codes}"
        
        headers = {
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": self.session.headers.get("User-Agent"),
        }
        
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = 'gbk'
            text = resp.text
            
            # 解析数据: var hq_str_fx_susdcny="...,买入价,卖出价,...";
            for code, name in self.forex_codes:
                pattern = rf'hq_str_{code}="([^"]+)"'
                match = re.search(pattern, text)
                if match:
                    data = match.group(1).split(",")
                    if len(data) >= 8:
                        buy_price = data[1]  # 买入价
                        sell_price = data[2]  # 卖出价
                        items.append({
                            "title": f"{name}: {buy_price}",
                            "url": f"https://finance.sina.com.cn/money/forex/hq/{code.replace('fx_s', '').upper()}.shtml",
                            "extra": {
                                "buy_price": buy_price,
                                "sell_price": sell_price,
                                "code": code,
                            }
                        })
        except Exception as e:
            print(f"  ❌ 新浪外汇爬取失败: {e}")
        
        return [self.standardize_item(item) for item in items]


class CoinGeckoScraper(BaseScraper):
    """CoinGecko 加密货币爬虫"""
    
    def __init__(self, name: str = "coingecko", config: Dict = None):
        config = config or {}
        config["display_name"] = config.get("display_name", "CoinGecko")
        config["category"] = "finance"
        super().__init__(name, config)
    
    def scrape(self) -> List[Dict[str, Any]]:
        """爬取加密货币数据"""
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 20,
            "page": 1,
        }
        
        resp = self.fetch(url, params=params)
        if not resp:
            return []
        
        data = self.parse_json(resp)
        if not data:
            return []
        
        items = []
        for i, coin in enumerate(data, 1):
            change = coin.get("price_change_percentage_24h", 0) or 0
            change_str = f"+{change:.2f}%" if change >= 0 else f"{change:.2f}%"
            
            items.append({
                "title": f"{coin['name']} (${coin['current_price']:,.2f}) {change_str}",
                "url": f"https://www.coingecko.com/en/coins/{coin['id']}",
                "rank": i,
                "extra": {
                    "symbol": coin["symbol"].upper(),
                    "price": coin["current_price"],
                    "change_24h": change,
                    "market_cap": coin.get("market_cap"),
                }
            })
        
        return [self.standardize_item(item) for item in items]


class HackerNewsScraper(BaseScraper):
    """Hacker News 爬虫"""
    
    def __init__(self, name: str = "hackernews", config: Dict = None):
        config = config or {}
        config["display_name"] = config.get("display_name", "Hacker News")
        config["category"] = "tech"
        super().__init__(name, config)
    
    def scrape(self) -> List[Dict[str, Any]]:
        """爬取 HN 热门"""
        # 获取热门 story ID 列表
        resp = self.fetch("https://hacker-news.firebaseio.com/v0/topstories.json")
        if not resp:
            return []
        
        story_ids = self.parse_json(resp)
        if not story_ids:
            return []
        
        # 获取前20个 story 详情
        items = []
        for i, story_id in enumerate(story_ids[:20], 1):
            detail_resp = self.fetch(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
            if not detail_resp:
                continue
            
            story = self.parse_json(detail_resp)
            if not story or story.get("type") != "story":
                continue
            
            items.append({
                "title": story.get("title", ""),
                "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                "rank": i,
                "extra": {
                    "score": story.get("score", 0),
                    "comments": story.get("descendants", 0),
                }
            })
        
        return [self.standardize_item(item) for item in items]


class SupplyChainNewsScraper(BaseScraper):
    """供应链企业新闻爬虫 - 从多个财经源筛选相关新闻"""
    
    def __init__(self, name: str = "eastmoney_supply_chain", config: Dict = None):
        config = config or {}
        config["display_name"] = config.get("display_name", "供应链企业动态")
        config["category"] = "finance"
        super().__init__(name, config)
        
        # 监控的供应链企业关键词
        self.keywords = {
            "立讯精密": ["立讯", "002475"],
            "歌尔股份": ["歌尔", "002241"],
            "蓝思科技": ["蓝思", "300433"],
            "工业富联": ["富联", "富士康", "601138"],
            "京东方A": ["京东方", "BOE", "000725"],
            "欣旺达": ["欣旺达", "300207"],
            "鹏鼎控股": ["鹏鼎", "002938"],
            "东山精密": ["东山精密", "002384"],
            "舜宇光学": ["舜宇", "02382"],
            "德赛电池": ["德赛", "000049"],
            "苹果": ["苹果", "Apple", "iPhone", "AirPods", "Vision Pro"],
            "华为": ["华为", "Huawei", "HUAWEI", "鸿蒙"],
        }
        
        # newsnow 财经平台列表
        self.finance_platforms = [
            "wallstreetcn-hot",
            "wallstreetcn-news", 
            "cls-hot",
            "cls-telegraph",
            "gelonghui",
            "jin10",
        ]
    
    def scrape(self) -> List[Dict[str, Any]]:
        """从财经新闻中筛选供应链相关新闻"""
        all_items = []
        
        # 从多个财经平台获取新闻
        for platform_id in self.finance_platforms:
            try:
                items = self._fetch_newsnow(platform_id)
                all_items.extend(items)
            except Exception as e:
                pass
        
        # 筛选与供应链企业相关的新闻
        supply_chain_news = []
        seen_titles = set()
        
        for item in all_items:
            title = item.get("title", "")
            if not title or title in seen_titles:
                continue
            
            # 检查是否匹配任何关键词
            for company, keywords in self.keywords.items():
                if any(kw in title for kw in keywords):
                    seen_titles.add(title)
                    supply_chain_news.append(self.standardize_item({
                        "title": f"[{company}] {title}",
                        "url": item.get("url", ""),
                        "extra": {
                            "company": company,
                            "original_platform": item.get("platform_name", ""),
                        }
                    }))
                    break
        
        return supply_chain_news[:30]
    
    def _fetch_newsnow(self, platform_id: str) -> List[Dict]:
        """从 newsnow API 获取数据"""
        url = f"https://newsnow.busiyi.world/api/s?id={platform_id}&latest"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json()
            if data.get("status") in ["success", "cache"]:
                items = data.get("items", [])
                for item in items:
                    item["platform_name"] = platform_id
                return items
        except Exception:
            pass
        return []


# 注册自定义爬虫
def register_finance_scrapers():
    """注册所有财经爬虫到工厂"""
    from .factory import ScraperFactory
    from .smm import SMMScraper
    from .plasway import PlaswaySectionScraper
    
    ScraperFactory.register("sina_forex", SinaForexScraper)
    ScraperFactory.register("coingecko", CoinGeckoScraper)
    ScraperFactory.register("hackernews", HackerNewsScraper)
    ScraperFactory.register("eastmoney_supply_chain", SupplyChainNewsScraper)
    ScraperFactory.register("smm_news", SMMScraper)
    ScraperFactory.register("plasway_industry", PlaswaySectionScraper)
