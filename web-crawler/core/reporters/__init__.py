# coding=utf-8
"""
报告生成模块
提供各种格式的报告生成功能
"""

from .base import prepare_report_data, format_title_for_platform
from .html_reporter import generate_html_report, render_html_content
from .message_formatter import (
    render_feishu_content,
    render_dingtalk_content,
    split_content_into_batches,
)

__all__ = [
    'prepare_report_data',
    'format_title_for_platform',
    'generate_html_report',
    'render_html_content',
    'render_feishu_content',
    'render_dingtalk_content',
    'split_content_into_batches',
]
