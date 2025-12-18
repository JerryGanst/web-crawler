"""
基础爬虫类 - 提供通用的爬取能力
参考 web-crawler/pacong/core/base_scraper.py 设计
"""
import requests
import time
import random
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime


class BaseScraper(ABC):
    """爬虫基类"""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        self.name = name
        self.config = config or {}
        self.rate_limit_delay = self.config.get("rate_limit_delay", 0)
        self.session = requests.Session()
        self._setup_session()
    
    def _setup_session(self):
        """配置请求会话"""
        default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        # 合并自定义 headers
        custom_headers = self.config.get("headers", {})
        default_headers.update(custom_headers)
        self.session.headers.update(default_headers)
    
    def fetch(self, url: str, method: str = "GET", **kwargs) -> Optional[requests.Response]:
        """
        执行 HTTP 请求，支持重试
        """
        max_retries = self.config.get("max_retries", 3)
        timeout = self.config.get("timeout", 15)
        
        for retry in range(max_retries):
            try:
                # 轻量级速率限制：每次请求前等待配置的延迟（含抖动）
                if self.rate_limit_delay > 0:
                    jitter = random.uniform(0, 0.3)
                    time.sleep(self.rate_limit_delay + jitter)

                if method.upper() == "GET":
                    resp = self.session.get(url, timeout=timeout, **kwargs)
                else:
                    resp = self.session.post(url, timeout=timeout, **kwargs)
                
                # 429/403 特殊处理：指数退避
                if resp.status_code in (429, 403):
                    backoff = random.uniform(5, 10) * (2 ** retry)
                    print(f"  ⚠️ {self.name} 被限流 ({resp.status_code})，等待 {backoff:.1f}s 后重试...")
                    time.sleep(backoff)
                    continue
                
                resp.raise_for_status()
                return resp
                
            except requests.exceptions.HTTPError as e:
                # 非 429/403 的 HTTP 错误
                if retry < max_retries - 1:
                    wait = random.uniform(2, 4) + retry * 2
                    time.sleep(wait)
                else:
                    print(f"  ❌ {self.name} 请求失败: {e}")
                    return None
            except Exception as e:
                if retry < max_retries - 1:
                    wait = random.uniform(2, 4) + retry * 2
                    time.sleep(wait)
                else:
                    print(f"  ❌ {self.name} 请求失败: {e}")
                    return None
        return None
    
    @abstractmethod
    def scrape(self) -> List[Dict[str, Any]]:
        """
        执行爬取，返回数据列表
        子类必须实现此方法
        """
        pass
    
    def parse_json(self, response: requests.Response) -> Any:
        """解析 JSON 响应"""
        try:
            return response.json()
        except Exception as e:
            print(f"  ❌ JSON 解析失败: {e}")
            return None
    
    def standardize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        标准化数据项格式，确保与 TrendRadar 兼容
        """
        return {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "platform": self.name,
            "platform_name": self.config.get("display_name", self.name),
            "category": self.config.get("category", "finance"),
            "rank": item.get("rank", 0),
            "timestamp": datetime.now().isoformat(),
            "extra": item.get("extra", {}),
        }


class ConfigDrivenScraper(BaseScraper):
    """
    配置驱动的通用爬虫
    通过 YAML 配置即可爬取不同网站
    """
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.urls = config.get("urls", [])
        if isinstance(self.urls, str):
            self.urls = [self.urls]
        self.method = config.get("method", "requests")
        self.parser = config.get("parser", "json")  # json / html
        self.json_path = config.get("json_path", None)  # 如 "data.items"
        self.field_mapping = config.get("field_mapping", {})
    
    def scrape(self) -> List[Dict[str, Any]]:
        """执行爬取"""
        all_items = []
        
        for url in self.urls:
            resp = self.fetch(url)
            if not resp:
                continue
            
            if self.parser == "json":
                items = self._parse_json_response(resp)
            else:
                items = self._parse_html_response(resp)
            
            all_items.extend(items)
        
        # 标准化所有数据项
        return [self.standardize_item(item) for item in all_items]
    
    def _parse_json_response(self, resp: requests.Response) -> List[Dict]:
        """解析 JSON 响应"""
        data = self.parse_json(resp)
        if not data:
            return []
        
        # 按 json_path 提取数据
        if self.json_path:
            for key in self.json_path.split("."):
                if isinstance(data, dict):
                    data = data.get(key, [])
                else:
                    break
        
        # 确保是列表
        if not isinstance(data, list):
            data = [data]
        
        # 字段映射
        items = []
        for item in data:
            mapped = {}
            for target_field, source_field in self.field_mapping.items():
                if isinstance(source_field, str) and source_field in item:
                    mapped[target_field] = item[source_field]
            # 保留原始字段
            for k, v in item.items():
                if k not in mapped:
                    mapped[k] = v
            items.append(mapped)
        
        return items
    
    def _parse_html_response(self, resp: requests.Response) -> List[Dict]:
        """解析 HTML 响应（需要 BeautifulSoup）"""
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            extraction = self.config.get("extraction", {})
            container = extraction.get("container", "")
            fields = extraction.get("fields", {})
            
            items = []
            elements = soup.select(container) if container else [soup]
            
            for elem in elements:
                item = {}
                for field_name, field_config in fields.items():
                    selector = field_config.get("selector", "") if isinstance(field_config, dict) else field_config
                    selected = elem.select_one(selector)
                    if selected:
                        item[field_name] = selected.get_text(strip=True)
                if item:
                    items.append(item)
            
            return items
            
        except ImportError:
            print("  ⚠️ 需要安装 beautifulsoup4: pip install beautifulsoup4")
            return []
        except Exception as e:
            print(f"  ❌ HTML 解析失败: {e}")
            return []
