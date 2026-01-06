"""
爬虫工厂模块
提供统一的爬虫创建接口
"""

from typing import Dict, Type, List, Optional
from ..core import BaseScraper, get_logger


class ScraperRegistry:
    """爬虫注册表"""
    
    def __init__(self):
        self._scrapers: Dict[str, Type[BaseScraper]] = {}
        self.logger = get_logger(__name__)
    
    def register(self, name: str, scraper_class: Type[BaseScraper]):
        """注册爬虫"""
        self._scrapers[name] = scraper_class
        self.logger.info(f"注册爬虫: {name} -> {scraper_class.__name__}")
    
    def get_scraper_class(self, name: str) -> Optional[Type[BaseScraper]]:
        """获取爬虫类"""
        return self._scrapers.get(name)
    
    def list_scrapers(self) -> List[str]:
        """列出所有可用爬虫"""
        return list(self._scrapers.keys())
    
    def create_scraper(self, name: str, **kwargs) -> Optional[BaseScraper]:
        """创建爬虫实例"""
        scraper_class = self.get_scraper_class(name)
        if scraper_class:
            return scraper_class(**kwargs)
        return None


# 全局爬虫注册表
_scraper_registry = ScraperRegistry()


class ScraperFactory:
    """爬虫工厂"""
    
    @staticmethod
    def register_scraper(name: str, scraper_class: Type[BaseScraper]):
        """注册爬虫"""
        _scraper_registry.register(name, scraper_class)
    
    @staticmethod
    def create_scraper(name: str, **kwargs) -> Optional[BaseScraper]:
        """创建爬虫实例"""
        return _scraper_registry.create_scraper(name, **kwargs)
    
    @staticmethod
    def list_available_scrapers() -> List[str]:
        """列出可用爬虫"""
        return _scraper_registry.list_scrapers()
    
    @staticmethod
    def create_all_scrapers(**kwargs) -> List[BaseScraper]:
        """创建所有已注册的爬虫"""
        scrapers = []
        for name in _scraper_registry.list_scrapers():
            scraper = _scraper_registry.create_scraper(name, **kwargs)
            if scraper:
                scrapers.append(scraper)
        return scrapers


# 自动注册可用的爬虫
def _auto_register_scrapers():
    """自动注册爬虫"""
    try:
        from .business_insider import BusinessInsiderScraper
        ScraperFactory.register_scraper('business_insider', BusinessInsiderScraper)
    except ImportError:
        pass
    
    try:
        from .sina_finance import SinaFinanceScraper
        ScraperFactory.register_scraper('sina_finance', SinaFinanceScraper)
    except ImportError:
        pass
    
    try:
        from .worldbank import WorldBankScraper
        ScraperFactory.register_scraper('worldbank', WorldBankScraper)
    except ImportError:
        pass
    
    # 注册通用配置驱动爬虫
    try:
        from .generic_scraper import register_generic_scrapers
        register_generic_scrapers()
    except ImportError:
        pass
    
    # 注册简化版通用爬虫
    try:
        from .simple_generic import register_simple_scrapers
        register_simple_scrapers()
    except ImportError:
        pass


# 自动注册
_auto_register_scrapers() 