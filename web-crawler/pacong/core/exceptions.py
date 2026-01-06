"""
自定义异常模块
定义业务相关的异常类型
"""

from typing import Optional, Dict, Any


class PacongError(Exception):
    """基础异常类"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self):
        if self.details:
            return f"{self.message} | 详情: {self.details}"
        return self.message


class ConfigurationError(PacongError):
    """配置错误"""
    pass


class ScrapingError(PacongError):
    """爬虫错误"""
    
    def __init__(self, message: str, url: Optional[str] = None, status_code: Optional[int] = None, **kwargs):
        details = {"url": url, "status_code": status_code}
        details.update(kwargs)
        super().__init__(message, details)
        self.url = url
        self.status_code = status_code


class DataProcessingError(PacongError):
    """数据处理错误"""
    
    def __init__(self, message: str, data_source: Optional[str] = None, **kwargs):
        details = {"data_source": data_source}
        details.update(kwargs)
        super().__init__(message, details)
        self.data_source = data_source


class BrowserError(PacongError):
    """浏览器控制错误"""
    
    def __init__(self, message: str, browser_type: Optional[str] = None, **kwargs):
        details = {"browser_type": browser_type}
        details.update(kwargs)
        super().__init__(message, details)
        self.browser_type = browser_type


class ValidationError(PacongError):
    """数据验证错误"""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Optional[Any] = None, **kwargs):
        details = {"field": field, "value": value}
        details.update(kwargs)
        super().__init__(message, details)
        self.field = field
        self.value = value


class RetryExhaustedError(PacongError):
    """重试次数耗尽错误"""
    
    def __init__(self, message: str, attempts: int, last_error: Optional[Exception] = None):
        details = {"attempts": attempts, "last_error": str(last_error) if last_error else None}
        super().__init__(message, details)
        self.attempts = attempts
        self.last_error = last_error


class RateLimitError(PacongError):
    """请求频率限制错误"""
    
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        details = {"retry_after": retry_after}
        details.update(kwargs)
        super().__init__(message, details)
        self.retry_after = retry_after


class AuthenticationError(PacongError):
    """认证错误"""
    pass


class NetworkError(PacongError):
    """网络错误"""
    
    def __init__(self, message: str, timeout: Optional[float] = None, **kwargs):
        details = {"timeout": timeout}
        details.update(kwargs)
        super().__init__(message, details)
        self.timeout = timeout 