"""
API 数据模型
"""
from pydantic import BaseModel
from typing import List, Dict, Optional


class CrawlRequest(BaseModel):
    """爬取请求"""
    category: str = "finance"
    webhook_url: Optional[str] = None
    include_custom: bool = True


class PushRequest(BaseModel):
    """推送请求"""
    content: str
    webhook_url: Optional[str] = None


class ReportPushRequest(BaseModel):
    """报告推送请求"""
    title: str
    content: str
    webhook_url: Optional[str] = None


class AnalysisRequest(BaseModel):
    """分析请求"""
    company_name: str = "立讯精密"
    competitors: Optional[List[str]] = None
    upstream: Optional[List[str]] = None
    downstream: Optional[List[str]] = None
    news: Optional[List[Dict]] = None
    model: Optional[str] = None  # 可选指定模型（如 gemini-3-pro-preview）
    thinking_level: Optional[str] = "high"  # Gemini 3 思考等级: low/high
