"""
基础爬虫抽象类
定义所有爬虫的通用接口和行为
"""

import requests
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from pathlib import Path

from .config import get_config
from .logger import get_logger, log_execution_time
from .exceptions import ScrapingError, ConfigurationError


class BaseScraper(ABC):
    """基础爬虫抽象类"""
    
    def __init__(self, name: str, **kwargs):
        self.name = name
        self.config = get_config()
        self.logger = get_logger(f"scraper.{name}")
        
        # 输出目录
        self.output_dir = Path(self.config.output.reports_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # 爬虫配置
        self.request_timeout = kwargs.get('timeout', self.config.scraping.request_timeout)
        self.retry_attempts = kwargs.get('retry_attempts', self.config.scraping.retry_attempts)
        self.rate_limit_delay = kwargs.get('rate_limit_delay', self.config.scraping.rate_limit_delay)
        
        # 状态跟踪
        self._start_time: Optional[datetime] = None
        self._end_time: Optional[datetime] = None
        self._scraped_count = 0
        self._error_count = 0
        
        self.logger.info(f"🚀 初始化爬虫: {self.name}")
    
    @abstractmethod
    def get_data_sources(self) -> List[Dict[str, str]]:
        """
        获取数据源列表
        返回格式: [{"name": "数据源名称", "url": "URL", "type": "数据类型"}]
        """
        pass
    
    @abstractmethod
    def scrape_single_source(self, source: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        爬取单个数据源
        
        Args:
            source: 数据源信息
            
        Returns:
            List[Dict]: 爬取到的数据列表
        """
        pass
    
    @abstractmethod
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        验证单条数据的有效性
        
        Args:
            data: 待验证的数据
            
        Returns:
            bool: 数据是否有效
        """
        pass
    
    def clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        清洗单条数据（可重写）
        
        Args:
            data: 原始数据
            
        Returns:
            Dict: 清洗后的数据
        """
        # 默认实现：添加时间戳和数据源
        cleaned_data = data.copy()
        cleaned_data.setdefault('timestamp', datetime.now())
        cleaned_data.setdefault('source', self.name)
        return cleaned_data
    
    @log_execution_time
    def scrape_all(self) -> List[Dict[str, Any]]:
        """
        爬取所有数据源
        
        Returns:
            List[Dict]: 所有爬取到的数据
        """
        self._start_time = datetime.now()
        self._scraped_count = 0
        self._error_count = 0
        
        self.logger.info(f"📊 开始爬取数据源: {self.name}")
        
        all_data = []
        data_sources = self.get_data_sources()
        
        self.logger.info(f"📋 发现 {len(data_sources)} 个数据源")
        
        for i, source in enumerate(data_sources, 1):
            try:
                self.logger.info(f"🔍 [{i}/{len(data_sources)}] 爬取: {source.get('name', source.get('url'))}")
                
                # 速率限制
                if i > 1:
                    import time
                    time.sleep(self.rate_limit_delay)
                
                source_data = self.scrape_single_source(source)
                
                if source_data:
                    # 数据验证和清洗
                    valid_data = []
                    for item in source_data:
                        if self.validate_data(item):
                            cleaned_item = self.clean_data(item)
                            valid_data.append(cleaned_item)
                        else:
                            self.logger.warning(f"⚠️ 数据验证失败: {item}")
                    
                    all_data.extend(valid_data)
                    self._scraped_count += len(valid_data)
                    
                    self.logger.info(f"✅ 获取 {len(valid_data)} 条有效数据")
                else:
                    self.logger.warning(f"⚠️ 数据源无数据: {source.get('name')}")
                    
            except Exception as e:
                self._error_count += 1
                self.logger.error(f"❌ 爬取失败: {source.get('name')} - {e}")
                continue
        
        self._end_time = datetime.now()
        execution_time = (self._end_time - self._start_time).total_seconds()
        
        self.logger.info(f"🎉 爬取完成: 成功 {self._scraped_count} 条, 错误 {self._error_count} 次, 耗时 {execution_time:.2f}秒")
        
        return all_data
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取爬取统计信息"""
        return {
            'scraper_name': self.name,
            'start_time': self._start_time,
            'end_time': self._end_time,
            'execution_time': (self._end_time - self._start_time).total_seconds() if self._start_time and self._end_time else None,
            'scraped_count': self._scraped_count,
            'error_count': self._error_count,
            'success_rate': self._scraped_count / (self._scraped_count + self._error_count) if (self._scraped_count + self._error_count) > 0 else 0
        }
    
    def save_raw_data(self, data: List[Dict[str, Any]], filename: Optional[str] = None) -> Path:
        """保存原始数据"""
        import json
        
        if not filename:
            timestamp = datetime.now().strftime(self.config.output.timestamp_format)
            filename = f"{self.name}_raw_{timestamp}.json"
        
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"💾 原始数据已保存: {filepath}")
        return filepath
    
    def __enter__(self):
        """上下文管理器支持"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器清理"""
        if hasattr(self, 'cleanup'):
            self.cleanup()


class WebScrapingMixin:
    """网页爬虫混入类"""
    
    def setup_http_session(self):
        """设置HTTP会话"""
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        self.session = requests.Session()
        
        # 重试策略
        retry_strategy = Retry(
            total=self.retry_attempts,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # 默认头部
        self.session.headers.update({
            'User-Agent': self.config.browser.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
    
    def get_page(self, url: str, **kwargs) -> requests.Response:
        """获取网页内容"""
        if not hasattr(self, 'session'):
            self.setup_http_session()
        
        try:
            response = self.session.get(url, timeout=self.request_timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            raise ScrapingError(f"请求失败: {url}", url=url) from e
    
    def cleanup(self):
        """清理HTTP会话"""
        if hasattr(self, 'session'):
            self.session.close()


class BrowserScrapingMixin:
    """浏览器控制爬虫混入类"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.browser = None
        self.browser_type = kwargs.get('browser_type', 'selenium')
    
    def setup_browser(self):
        """设置浏览器驱动"""
        if self.browser_type == 'selenium':
            self._setup_selenium()
        elif self.browser_type == 'applescript':
            self._setup_applescript()
        elif self.browser_type == 'cdp':
            self._setup_cdp()
        else:
            raise ConfigurationError(f"不支持的浏览器类型: {self.browser_type}")
    
    def _setup_selenium(self):
        """设置Selenium驱动"""
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.chrome.options import Options
            
            options = Options()
            if self.config.get('browser.headless', True):
                options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(f"--user-agent={self.config.browser.user_agent}")
            
            self.browser = uc.Chrome(options=options)
            self.browser.set_page_load_timeout(self.config.browser.selenium_timeout)
            
        except ImportError:
            raise ConfigurationError("需要安装 undetected-chromedriver: pip install undetected-chromedriver")
        except Exception as e:
            raise ConfigurationError(f"Selenium初始化失败: {e}")
    
    def _setup_applescript(self):
        """设置AppleScript控制"""
        # AppleScript不需要特殊初始化
        self.browser = 'applescript'
    
    def _setup_cdp(self):
        """设置Chrome DevTools Protocol"""
        # CDP连接会在使用时建立
        self.browser = 'cdp'
    
    def get_page_content(self, url: str) -> str:
        """获取页面内容"""
        if not self.browser:
            self.setup_browser()
        
        if self.browser_type == 'selenium':
            return self._get_content_selenium(url)
        elif self.browser_type == 'applescript':
            return self._get_content_applescript(url)
        elif self.browser_type == 'cdp':
            return self._get_content_cdp(url)
    
    def _get_content_selenium(self, url: str) -> str:
        """通过Selenium获取内容"""
        self.browser.get(url)
        return self.browser.page_source
    
    def _get_content_applescript(self, url: str) -> str:
        """通过AppleScript获取内容"""
        from ..browser.applescript import execute_applescript
        
        script = f'''
        tell application "Google Chrome"
            set URL of active tab of front window to "{url}"
            delay 5
            execute active tab of front window javascript "document.documentElement.outerHTML"
        end tell
        '''
        
        return execute_applescript(script)
    
    def _get_content_cdp(self, url: str) -> str:
        """通过CDP获取内容"""
        # CDP实现会更复杂，这里是基本框架
        raise NotImplementedError("CDP支持待实现")
    
    def cleanup(self):
        """清理浏览器资源"""
        if self.browser and self.browser_type == 'selenium':
            try:
                self.browser.quit()
            except:
                pass 