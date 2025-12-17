"""
日志管理模块
提供统一的日志配置和格式
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
from .config import get_config


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""
    
    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',    # 青色
        'INFO': '\033[32m',     # 绿色
        'WARNING': '\033[33m',  # 黄色
        'ERROR': '\033[31m',    # 红色
        'CRITICAL': '\033[35m', # 紫色
        'RESET': '\033[0m'      # 重置
    }
    
    def format(self, record):
        # 添加颜色
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{log_color}{record.levelname}{self.COLORS['RESET']}"
        
        # 格式化消息
        return super().format(record)


def setup_logger(
    name: str,
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    format_string: Optional[str] = None
) -> logging.Logger:
    """设置日志记录器"""
    
    config = get_config()
    
    # 使用配置或默认值
    level = level or config.logging.level
    format_string = format_string or config.logging.format
    log_file = log_file or config.logging.file_path
    
    # 创建logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # 清除现有处理器
    logger.handlers.clear()
    
    # 控制台处理器（带颜色）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))
    
    if sys.stdout.isatty():  # 终端环境使用彩色
        console_formatter = ColoredFormatter(format_string)
    else:  # 非终端环境（如文件重定向）使用普通格式
        console_formatter = logging.Formatter(format_string)
    
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器（如果指定了文件路径）
    if log_file:
        # 确保日志目录存在
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 使用RotatingFileHandler避免日志文件过大
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=config.logging.max_file_size,
            backupCount=config.logging.backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        
        # 文件日志不使用颜色
        file_formatter = logging.Formatter(format_string)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """获取日志记录器"""
    return setup_logger(name)


# 设置根日志记录器
def init_logging():
    """初始化日志系统"""
    config = get_config()
    
    # 禁用第三方库的过多日志
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('selenium').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    # 设置根logger
    root_logger = setup_logger('pacong')
    return root_logger


# 便捷函数
def log_method_call(func):
    """装饰器：记录方法调用"""
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.debug(f"调用方法: {func.__qualname__}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"方法 {func.__qualname__} 执行成功")
            return result
        except Exception as e:
            logger.error(f"方法 {func.__qualname__} 执行失败: {e}")
            raise
    return wrapper


def log_execution_time(func):
    """装饰器：记录执行时间"""
    import time
    
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            logger.info(f"⏱️ {func.__qualname__} 执行时间: {execution_time:.2f}秒")
            return result
        except Exception as e:
            end_time = time.time()
            execution_time = end_time - start_time
            logger.error(f"❌ {func.__qualname__} 执行失败 (耗时: {execution_time:.2f}秒): {e}")
            raise
    
    return wrapper 