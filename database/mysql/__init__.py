"""
MySQL 数据管道模块

Usage:
    from database.mysql import process_crawled_data, get_latest_prices, get_recent_changes
    
    # 处理爬虫数据
    result = process_crawled_data(raw_data, source='sina')
    
    # 查询最新价格
    prices = get_latest_prices(category='贵金属')
    
    # 获取变更日志 (供 LLM)
    changes = get_recent_changes(limit=50)
"""

from .connection import (
    get_connection,
    get_cursor,
    transaction,
    init_database,
    test_connection,
)

from .pipeline import (
    CommodityPipeline,
    CommodityRecord,
    ChangeRecord,
    process_crawled_data,
    get_pipeline,
    get_latest_prices,
    get_price_history,
    get_recent_changes,
    get_price_changes,
    standardize_record,
    standardize_batch,
)

__all__ = [
    # 连接管理
    'get_connection',
    'get_cursor', 
    'transaction',
    'init_database',
    'test_connection',
    
    # 数据管道
    'CommodityPipeline',
    'CommodityRecord',
    'ChangeRecord',
    'process_crawled_data',
    'get_pipeline',
    
    # 查询接口
    'get_latest_prices',
    'get_price_history',
    'get_recent_changes',
    'get_price_changes',
    
    # 标准化
    'standardize_record',
    'standardize_batch',
]
