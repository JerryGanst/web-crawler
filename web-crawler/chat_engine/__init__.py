# coding=utf-8
"""
数据洞察聊天引擎

基于 LangGraph + Vertex AI 实现的智能对话系统。
支持：
- 滑动窗口 + 摘要的记忆策略
- MCP 工具集成（新闻查询、趋势分析等）
- MongoDB 持久化存储
"""

from .graph import ChatEngine, get_chat_engine
from .tools import DataInsightTools
from .hybrid_query import HybridQueryRouter, get_hybrid_router, hybrid_query

__all__ = [
    'ChatEngine', 
    'get_chat_engine', 
    'DataInsightTools',
    'HybridQueryRouter',
    'get_hybrid_router',
    'hybrid_query'
]
