 #!/usr/bin/env python3
"""
网站适配器基类
定义所有网站适配器的统一接口
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class DataType(Enum):
    """数据类型枚举"""
    FOREX = "forex"          # 外汇
    COMMODITY = "commodity"  # 商品
    STOCK = "stock"         # 股票
    CRYPTO = "crypto"       # 加密货币
    BOND = "bond"           # 债券

class ScrapingMethod(Enum):
    """抓取方法枚举"""
    HTTP_REQUEST = "http_request"
    SELENIUM = "selenium"
    APPLESCRIPT = "applescript"
    API = "api"

@dataclass
class DataPoint:
    """标准化数据点"""
    symbol: str                    # 符号/代码
    name: str                     # 名称
    current_price: Optional[float] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[float] = None
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

@dataclass
class AdapterInfo:
    """适配器信息"""
    name: str                      # 适配器名称
    website_url: str              # 网站URL
    supported_data_types: List[DataType]  # 支持的数据类型
    supported_methods: List[ScrapingMethod]  # 支持的抓取方法
    priority: int = 1             # 优先级（数字越大优先级越高）
    description: str = ""         # 描述
    is_active: bool = True        # 是否激活

class BaseWebsiteAdapter(ABC):
    """网站适配器基类"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.setup_logging()
    
    def setup_logging(self):
        """设置日志"""
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    @abstractmethod
    def get_adapter_info(self) -> AdapterInfo:
        """获取适配器信息"""
        pass
    
    @abstractmethod
    def can_handle_url(self, url: str) -> bool:
        """检查是否能处理指定URL"""
        pass
    
    @abstractmethod
    def detect_data_type(self, url: str) -> Optional[DataType]:
        """检测URL对应的数据类型"""
        pass
    
    @abstractmethod
    def scrape_data(self, url: str, **kwargs) -> List[DataPoint]:
        """抓取数据的主要方法"""
        pass
    
    def validate_data(self, data_points: List[DataPoint]) -> List[DataPoint]:
        """验证和清理数据"""
        valid_points = []
        for point in data_points:
            if self._is_valid_data_point(point):
                valid_points.append(point)
            else:
                self.logger.warning(f"Invalid data point: {point}")
        return valid_points
    
    def _is_valid_data_point(self, point: DataPoint) -> bool:
        """检查数据点是否有效"""
        return bool(point.symbol and point.name)
    
    def get_health_status(self) -> Dict[str, Any]:
        """获取适配器健康状态"""
        return {
            "name": self.get_adapter_info().name,
            "status": "healthy",
            "last_check": None,
            "error_count": 0
        }
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            # 子类可以重写此方法实现具体的连接测试
            return True
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False