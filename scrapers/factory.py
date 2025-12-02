"""
爬虫工厂 - 根据配置创建爬虫实例
"""
import yaml
from typing import Dict, List, Any, Optional
from .base import BaseScraper, ConfigDrivenScraper


class ScraperFactory:
    """爬虫工厂类"""
    
    # 注册的自定义爬虫类
    _custom_scrapers: Dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str, scraper_class: type):
        """注册自定义爬虫类"""
        cls._custom_scrapers[name] = scraper_class
    
    @classmethod
    def create(cls, name: str, config: Dict[str, Any]) -> Optional[BaseScraper]:
        """
        根据配置创建爬虫实例
        
        Args:
            name: 爬虫名称
            config: 爬虫配置
        
        Returns:
            爬虫实例
        """
        # 检查是否有自定义爬虫
        if name in cls._custom_scrapers:
            return cls._custom_scrapers[name](name, config)
        
        # 使用配置驱动的通用爬虫
        return ConfigDrivenScraper(name, config)
    
    @classmethod
    def create_from_yaml(cls, yaml_path: str, category: str = None) -> List[BaseScraper]:
        """
        从 YAML 配置文件创建爬虫列表
        
        Args:
            yaml_path: 配置文件路径
            category: 可选，只创建指定分类的爬虫
        
        Returns:
            爬虫实例列表
        """
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        scrapers = []
        
        # 从 custom_scrapers 配置创建
        custom_configs = config.get("custom_scrapers", {})
        for name, scraper_config in custom_configs.items():
            if not scraper_config.get("enabled", True):
                continue
            if category and scraper_config.get("category") != category:
                continue
            
            scraper = cls.create(name, scraper_config)
            if scraper:
                scrapers.append(scraper)
        
        return scrapers
    
    @classmethod
    def list_available(cls, yaml_path: str) -> Dict[str, Dict]:
        """列出所有可用的爬虫配置"""
        with open(yaml_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        available = {}
        
        custom_configs = config.get("custom_scrapers", {})
        for name, scraper_config in custom_configs.items():
            available[name] = {
                "name": scraper_config.get("display_name", name),
                "category": scraper_config.get("category", "unknown"),
                "enabled": scraper_config.get("enabled", True),
                "urls": scraper_config.get("urls", []),
            }
        
        return available
