"""
pacong.core - 核心模块
提供基础的配置管理、日志记录和异常处理功能
"""

from .config import Config, get_config, init_config
from .logger import get_logger, init_logging
from .exceptions import ScrapingError, DataProcessingError, ConfigurationError
from .base_scraper import BaseScraper, WebScrapingMixin, BrowserScrapingMixin

__all__ = [
    'Config',
    'get_config',
    'init_config',
    'get_logger',
    'init_logging',
    'ScrapingError',
    'DataProcessingError',
    'ConfigurationError',
    'BaseScraper',
    'WebScrapingMixin',
    'BrowserScrapingMixin'
] 