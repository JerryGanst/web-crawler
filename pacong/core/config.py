"""
配置管理模块
统一管理所有配置参数，支持环境变量和配置文件
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class BrowserConfig:
    """浏览器配置"""
    selenium_timeout: int = 30
    applescript_timeout: int = 60
    cdp_debug_port: int = 9222
    chrome_path: str = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    headless: bool = True


@dataclass
class ScrapingConfig:
    """爬虫配置"""
    request_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    rate_limit_delay: float = 2.0
    max_concurrent_requests: int = 5


@dataclass
class OutputConfig:
    """输出配置"""
    reports_dir: str = "reports"
    data_dir: str = "data"
    charts_dir: str = "charts"
    encoding: str = "utf-8-sig"
    timestamp_format: str = "%Y%m%d_%H%M%S"


@dataclass
class LoggingConfig:
    """日志配置"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


class Config:
    """统一配置管理器"""
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = config_file or self._find_config_file()
        self._config_data = self._load_config()
        
        # 初始化各模块配置
        self.browser = BrowserConfig(**self._config_data.get('browser', {}))
        self.scraping = ScrapingConfig(**self._config_data.get('scraping', {}))
        self.output = OutputConfig(**self._config_data.get('output', {}))
        self.logging = LoggingConfig(**self._config_data.get('logging', {}))
        
        # API密钥等敏感信息
        self.api_keys = self._config_data.get('api_keys', {})
        
        # 数据源配置
        self.data_sources = self._config_data.get('data_sources', {})
    
    def _find_config_file(self) -> str:
        """查找配置文件"""
        possible_paths = [
            "config/settings.yaml",
            "pacong/config/settings.yaml",
            os.path.expanduser("~/.pacong/settings.yaml"),
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        
        # 如果没有找到配置文件，返回默认路径
        return "config/settings.yaml"
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}
            
            # 从环境变量覆盖配置
            self._load_from_env(config)
            return config
            
        except Exception as e:
            print(f"警告: 加载配置文件失败 {self.config_file}: {e}")
            return {}
    
    def _load_from_env(self, config: Dict[str, Any]):
        """从环境变量加载配置"""
        env_mappings = {
            'PACONG_LOG_LEVEL': ['logging', 'level'],
            'PACONG_REPORTS_DIR': ['output', 'reports_dir'],
            'PACONG_CHROME_PATH': ['browser', 'chrome_path'],
            'PACONG_REQUEST_TIMEOUT': ['scraping', 'request_timeout'],
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value:
                # 导航到配置路径并设置值
                current = config
                for key in config_path[:-1]:
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                
                # 尝试转换类型
                try:
                    if config_path[-1] in ['request_timeout', 'retry_attempts']:
                        value = int(value)
                    elif config_path[-1] in ['retry_delay', 'rate_limit_delay']:
                        value = float(value)
                except ValueError:
                    pass
                
                current[config_path[-1]] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置值"""
        keys = key.split('.')
        current = self._config_data
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        
        return current
    
    def set(self, key: str, value: Any):
        """设置配置值"""
        keys = key.split('.')
        current = self._config_data
        
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]
        
        current[keys[-1]] = value
    
    def save(self, file_path: Optional[str] = None):
        """保存配置到文件"""
        file_path = file_path or self.config_file
        
        # 确保目录存在
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(self._config_data, f, default_flow_style=False, allow_unicode=True)


# 全局配置实例
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置实例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def init_config(config_file: Optional[str] = None) -> Config:
    """初始化配置"""
    global _config_instance
    _config_instance = Config(config_file)
    return _config_instance 