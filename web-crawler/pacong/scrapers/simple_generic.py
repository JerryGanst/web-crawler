"""
简化版通用配置驱动爬虫
专注于基本的配置驱动功能，避免复杂的解析逻辑
"""

import re
import json
from typing import List, Dict, Any, Optional, Union
from bs4 import BeautifulSoup, Tag

from ..core import BaseScraper, WebScrapingMixin, get_config


class SimpleGenericScraper(BaseScraper, WebScrapingMixin):
    """简化版通用配置驱动爬虫"""
    
    def __init__(self, config_name: str, **kwargs):
        super().__init__(f"simple_{config_name}", **kwargs)
        self.config_name = config_name
        self.scraper_config = self._load_scraper_config()
        
    def _load_scraper_config(self) -> Dict[str, Any]:
        """加载爬虫配置"""
        config = get_config()
        generic_configs = config._config_data.get('simple_scrapers', {})
        
        if self.config_name not in generic_configs:
            raise ValueError(f"未找到配置: {self.config_name}")
        
        return generic_configs[self.config_name]
    
    def get_data_sources(self) -> List[Dict[str, str]]:
        """获取数据源配置"""
        if not self.scraper_config.get('enabled', True):
            return []
        
        sources = []
        base_config = {
            'name': self.scraper_config.get('name', self.config_name),
            'type': self.scraper_config.get('type', 'commodity')
        }
        
        urls = self.scraper_config.get('urls', [])
        if isinstance(urls, str):
            urls = [urls]
        
        for i, url in enumerate(urls):
            source = base_config.copy()
            source['url'] = url
            source['name'] = f"{base_config['name']}_{i+1}" if len(urls) > 1 else base_config['name']
            sources.append(source)
        
        return sources
    
    def scrape_single_source(self, source: Dict[str, str]) -> List[Dict[str, Any]]:
        """爬取单个数据源"""
        url = source['url']
        method = self.scraper_config.get('method', 'requests')
        
        self.logger.info(f"开始爬取 {self.config_name}: {url}")
        
        try:
            if method == 'requests':
                content = self._scrape_with_requests(url)
            else:
                raise ValueError(f"暂不支持的爬取方法: {method}")
            
            # 简单的JSON解析
            if url.endswith('.json') or 'api' in url:
                data = self._parse_simple_json(content, url)
            else:
                data = self._parse_simple_html(content, url)
            
            self.logger.info(f"成功提取 {len(data)} 条数据")
            return data
            
        except Exception as e:
            self.logger.error(f"爬取失败 {url}: {e}")
            return []
    
    def _scrape_with_requests(self, url: str) -> str:
        """使用requests获取内容"""
        headers = self.scraper_config.get('headers', {})
        response = self.get_page(url, headers=headers)
        return response.text
    
    def _parse_simple_json(self, content: str, url: str) -> List[Dict[str, Any]]:
        """简单JSON解析"""
        try:
            data = json.loads(content)
            
            # 简单处理：假设数据是一个对象，每个键都是一个数据项
            items = []
            if isinstance(data, dict):
                for key, value in data.items():
                    if isinstance(value, dict) and 'usd' in value:
                        # 专门为CoinGecko API设计
                        item = {
                            'name': key,
                            'current_price': value.get('usd'),
                            'change_percent': 0.0,  # 添加默认的变化百分比
                            'source': self.config_name,
                            'url': url,
                            'timestamp': self._get_current_timestamp()
                        }
                        items.append(item)
            
            return items
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}")
            return []
    
    def _parse_simple_html(self, content: str, url: str) -> List[Dict[str, Any]]:
        """简单HTML解析"""
        soup = BeautifulSoup(content, 'html.parser')
        
        # 查找表格数据
        data = []
        tables = soup.find_all('table')
        
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) >= 2:
                    name = cells[0].get_text(strip=True)
                    price_text = cells[1].get_text(strip=True)
                    
                    # 提取价格
                    price_match = re.search(r'(\d+,?\d*\.?\d*)', price_text.replace(',', ''))
                    if price_match and name and not name.lower() in ['name', 'symbol', 'commodity']:
                        item = {
                            'name': name,
                            'current_price': float(price_match.group(1)),
                            'source': self.config_name,
                            'url': url,
                            'timestamp': self._get_current_timestamp()
                        }
                        data.append(item)
        
        return data
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """简单数据验证"""
        required_fields = self.scraper_config.get('required_fields', ['name', 'current_price'])
        
        for field in required_fields:
            if field not in data or data[field] is None:
                return False
        
        # 价格合理性检查
        if 'current_price' in data:
            try:
                price = float(data['current_price'])
                if price <= 0:
                    return False
            except (ValueError, TypeError):
                return False
        
        return True
    
    def clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """简单数据清洗"""
        cleaned = data.copy()
        
        # 确保价格是浮点数
        if 'current_price' in cleaned:
            try:
                cleaned['current_price'] = float(cleaned['current_price'])
            except (ValueError, TypeError):
                pass
        
        # 标准化名称
        if 'name' in cleaned:
            cleaned['name'] = str(cleaned['name']).strip()
        
        return cleaned
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now()


# 简单爬虫注册函数
def register_simple_scrapers():
    """注册所有简单通用爬虫"""
    from .factory import ScraperFactory
    
    try:
        config = get_config()
        simple_configs = config._config_data.get('simple_scrapers', {})
        
        for config_name, config_data in simple_configs.items():
            if config_data.get('enabled', False):
                class DynamicSimpleScraper(SimpleGenericScraper):
                    def __init__(self, **kwargs):
                        super().__init__(config_name, **kwargs)
                
                ScraperFactory.register_scraper(f'simple_{config_name}', DynamicSimpleScraper)
    
    except Exception as e:
        pass 