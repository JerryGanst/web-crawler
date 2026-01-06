"""
通用配置驱动爬虫
通过配置文件定义爬取规则，无需为每个新网站编写代码
"""

import re
import json
from typing import List, Dict, Any, Optional, Union
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup, Tag

from ..core import BaseScraper, WebScrapingMixin, BrowserScrapingMixin, get_config
from ..data import CommodityData, ForexData


class GenericScraper(BaseScraper, WebScrapingMixin, BrowserScrapingMixin):
    """通用配置驱动爬虫"""
    
    def __init__(self, config_name: str, **kwargs):
        """
        初始化通用爬虫
        
        Args:
            config_name: 配置文件中的配置名称
        """
        super().__init__(f"generic_{config_name}", **kwargs)
        self.config_name = config_name
        self.scraper_config = self._load_scraper_config()
        
    def _load_scraper_config(self) -> Dict[str, Any]:
        """加载爬虫配置"""
        config = get_config()
        generic_configs = config._config_data.get('generic_scrapers', {})
        
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
        
        # 支持单个URL或多个URL
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
            # 获取页面内容
            if method == 'requests':
                content = self._scrape_with_requests(url)
            elif method == 'selenium':
                content = self._scrape_with_selenium(url)
            elif method == 'applescript':
                content = self._scrape_with_applescript(url)
            else:
                raise ValueError(f"不支持的爬取方法: {method}")
            
            # 解析数据
            data = self._parse_content(content, url)
            
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
    
    def _scrape_with_selenium(self, url: str) -> str:
        """使用Selenium获取内容"""
        from ..browser.selenium_controller import SeleniumController
        
        controller = SeleniumController(headless=True)
        try:
            controller.setup_driver()
            content = controller.get_page(url)
            
            # 等待动态内容加载
            wait_time = self.scraper_config.get('wait_time', 3)
            controller.driver.implicitly_wait(wait_time)
            
            return content
        finally:
            if controller.driver:
                controller.close()
    
    def _scrape_with_applescript(self, url: str) -> str:
        """使用AppleScript获取内容"""
        from ..browser.applescript import chrome_applescript_scraper
        
        try:
            result = chrome_applescript_scraper(url)
            return result.get('content', '')
        except Exception as e:
            self.logger.error(f"AppleScript爬取失败: {e}")
            return ""
    
    def _parse_content(self, content: str, url: str) -> List[Dict[str, Any]]:
        """解析页面内容"""
        parser_type = self.scraper_config.get('parser', 'html')
        
        if parser_type == 'html':
            return self._parse_html(content, url)
        elif parser_type == 'json':
            return self._parse_json(content, url)
        elif parser_type == 'regex':
            return self._parse_regex(content, url)
        else:
            raise ValueError(f"不支持的解析器: {parser_type}")
    
    def _parse_html(self, content: str, url: str) -> List[Dict[str, Any]]:
        """解析HTML内容"""
        soup = BeautifulSoup(content, 'html.parser')
        data = []
        
        # 获取数据提取规则
        extraction_rules = self.scraper_config.get('extraction', {})
        
        # 查找数据容器
        container_selector = extraction_rules.get('container')
        if container_selector:
            containers = soup.select(container_selector)
        else:
            # 默认查找表格行
            containers = soup.find_all(['tr', 'div', 'li'])
        
        # 提取数据字段
        field_rules = extraction_rules.get('fields', {})
        
        for container in containers:
            item_data = self._extract_item_data(container, field_rules, url)
            if item_data:
                data.append(item_data)
        
        return data
    
    def _extract_item_data(self, container: Tag, field_rules: Dict[str, Any], url: str) -> Optional[Dict[str, Any]]:
        """从容器中提取数据项"""
        item_data = {
            'source': self.config_name,
            'url': url,
            'timestamp': self._get_current_timestamp()
        }
        
        try:
            for field_name, rule in field_rules.items():
                value = self._extract_field_value(container, rule)
                if value:
                    item_data[field_name] = value
            
            # 验证必需字段
            required_fields = self.scraper_config.get('required_fields', ['name'])
            if all(field in item_data for field in required_fields):
                return item_data
            
        except Exception as e:
            self.logger.debug(f"提取数据项失败: {e}")
        
        return None
    
    def _extract_field_value(self, container: Tag, rule: Union[str, Dict[str, Any]]) -> Optional[str]:
        """根据规则提取字段值"""
        if isinstance(rule, str):
            # 简单选择器
            element = container.select_one(rule)
            return element.get_text(strip=True) if element else None
        
        elif isinstance(rule, dict):
            selector = rule.get('selector')
            attribute = rule.get('attribute')
            regex_pattern = rule.get('regex')
            transform = rule.get('transform')
            
            # 查找元素
            if selector:
                element = container.select_one(selector)
                if not element:
                    return None
            else:
                element = container
            
            # 获取值
            if attribute:
                value = element.get(attribute)
            else:
                value = element.get_text(strip=True)
            
            if not value:
                return None
            
            # 正则提取
            if regex_pattern:
                match = re.search(regex_pattern, str(value))
                value = match.group(1) if match else None
            
            # 数据转换
            if value and transform:
                value = self._transform_value(value, transform)
            
            return value
        
        return None
    
    def _transform_value(self, value: str, transform: str) -> str:
        """数据转换"""
        if transform == 'float':
            # 提取数字
            numbers = re.findall(r'[\d.,]+', value.replace(',', ''))
            return numbers[0] if numbers else value
        elif transform == 'lowercase':
            return value.lower()
        elif transform == 'uppercase':
            return value.upper()
        elif transform == 'strip_currency':
            return re.sub(r'[^\d.,]', '', value)
        
        return value
    
    def _parse_json(self, content: str, url: str) -> List[Dict[str, Any]]:
        """解析JSON内容"""
        try:
            data = json.loads(content)
            
            # 获取数据路径
            data_path = self.scraper_config.get('json_path', '')
            if data_path:
                for key in data_path.split('.'):
                    data = data.get(key, {})
            
            if isinstance(data, list):
                return [self._transform_json_item(item, url) for item in data]
            elif isinstance(data, dict):
                # 检查是否是嵌套结构（如 CoinGecko API）
                field_mapping = self.scraper_config.get('field_mapping', {})
                if not any(key in field_mapping.values() for key in data.keys()):
                    # 嵌套结构，每个键值对是一个数据项
                    items = []
                    for coin_id, coin_data in data.items():
                        if isinstance(coin_data, dict):
                            coin_item = {
                                'source': self.config_name,
                                'url': url,
                                'timestamp': self._get_current_timestamp(),
                                'name': coin_id
                            }
                            
                            # 映射其他字段
                            for target_field, source_field in field_mapping.items():
                                if target_field != 'name' and source_field in coin_data:
                                    coin_item[target_field] = coin_data[source_field]
                            
                            # Debug: 打印实际获取的数据
                            self.logger.debug(f"币种 {coin_id} 原始数据: {coin_data}")
                            self.logger.debug(f"处理后数据: {coin_item}")
                            
                            items.append(coin_item)
                    return items
                else:
                    # 标准单项结构
                    return [self._transform_json_item(data, url)]
            
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {e}")
        
        return []
    
    def _transform_json_item(self, item: Dict[str, Any], url: str) -> Dict[str, Any]:
        """转换JSON数据项"""
        # 字段映射
        field_mapping = self.scraper_config.get('field_mapping', {})
        
        transformed = {
            'source': self.config_name,
            'url': url,
            'timestamp': self._get_current_timestamp()
        }
        
        # 标准映射
        for target_field, source_field in field_mapping.items():
            if source_field in item:
                transformed[target_field] = item[source_field]
        
        return transformed
    
    def _parse_regex(self, content: str, url: str) -> List[Dict[str, Any]]:
        """使用正则表达式解析内容"""
        patterns = self.scraper_config.get('regex_patterns', {})
        data = []
        
        for pattern_name, pattern_config in patterns.items():
            pattern = pattern_config.get('pattern')
            fields = pattern_config.get('fields', [])
            
            matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
            
            for match in matches:
                item_data = {
                    'source': self.config_name,
                    'url': url,
                    'timestamp': self._get_current_timestamp()
                }
                
                for i, field_name in enumerate(fields):
                    try:
                        item_data[field_name] = match.group(i + 1)
                    except IndexError:
                        continue
                
                if len(item_data) > 3:  # 除了基础字段还有其他数据
                    data.append(item_data)
        
        return data
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """验证数据"""
        # 使用配置中的验证规则
        validation_rules = self.scraper_config.get('validation', {})
        
        # 检查必需字段
        required_fields = validation_rules.get('required_fields', ['name'])
        if not all(field in data for field in required_fields):
            return False
        
        # 检查数据格式
        format_rules = validation_rules.get('formats', {})
        for field, format_type in format_rules.items():
            if field in data:
                if not self._validate_format(data[field], format_type):
                    return False
        
        return True
    
    def _validate_format(self, value: Any, format_type: str) -> bool:
        """验证数据格式"""
        if format_type == 'number':
            try:
                float(str(value).replace(',', ''))
                return True
            except ValueError:
                return False
        elif format_type == 'url':
            return bool(urlparse(str(value)).netloc)
        elif format_type == 'non_empty':
            return bool(str(value).strip())
        
        return True
    
    def clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """清洗单个数据项"""
        if not isinstance(data, dict):
            return data
        
        cleaning_rules = self.scraper_config.get('cleaning', {})
        cleaned_item = data.copy()
        
        # 字段清理
        for field, clean_type in cleaning_rules.get('fields', {}).items():
            if field in cleaned_item:
                cleaned_item[field] = self._clean_field_value(
                    cleaned_item[field], 
                    clean_type
                )
        
        # 数据转换
        transforms = cleaning_rules.get('transforms', {})
        for field, transform_type in transforms.items():
            if field in cleaned_item:
                cleaned_item[field] = self._transform_value(
                    str(cleaned_item[field]), 
                    transform_type
                )
        
        return cleaned_item
    
    def _clean_field_value(self, value: Any, clean_type: str) -> Any:
        """清理字段值"""
        value_str = str(value).strip()
        
        if clean_type == 'remove_currency':
            return re.sub(r'[^\d.,]', '', value_str)
        elif clean_type == 'normalize_whitespace':
            return ' '.join(value_str.split())
        elif clean_type == 'remove_html':
            return BeautifulSoup(value_str, 'html.parser').get_text()
        
        return value
    
    def _get_current_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


# 爬虫注册函数
def register_generic_scrapers():
    """注册所有配置的通用爬虫"""
    from .factory import ScraperFactory
    
    try:
        config = get_config()
        generic_configs = config._config_data.get('generic_scrapers', {})
        
        for config_name, config_data in generic_configs.items():
            # 只注册启用的爬虫
            if config_data.get('enabled', False):
                # 使用闭包确保正确捕获config_name
                def create_scraper_class(name):
                    class DynamicGenericScraper(GenericScraper):
                        def __init__(self, **kwargs):
                            super().__init__(name, **kwargs)
                    return DynamicGenericScraper
                
                scraper_class = create_scraper_class(config_name)
                ScraperFactory.register_scraper(f'generic_{config_name}', scraper_class)
    
    except Exception as e:
        # 如果配置加载失败，不影响其他爬虫
        pass 