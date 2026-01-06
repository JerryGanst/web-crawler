# coding=utf-8
"""
消息格式化模块
为各平台生成适配的消息内容
"""

# 此模块从 main.py 迁移消息格式化相关函数
# 由于代码量较大，这里创建占位文件

from typing import Dict, List, Optional


def render_feishu_content(
    report_data: Dict, update_info: Optional[Dict] = None, mode: str = "daily"
) -> str:
    """渲染飞书内容 - 占位函数"""
    raise NotImplementedError("请使用 main.py 中的 render_feishu_content")


def render_dingtalk_content(
    report_data: Dict, update_info: Optional[Dict] = None, mode: str = "daily"
) -> str:
    """渲染钉钉内容 - 占位函数"""
    raise NotImplementedError("请使用 main.py 中的 render_dingtalk_content")


def split_content_into_batches(
    report_data: Dict,
    format_type: str,
    update_info: Optional[Dict] = None,
    max_bytes: int = None,
    mode: str = "daily",
) -> List[str]:
    """分批处理消息内容 - 占位函数"""
    raise NotImplementedError("请使用 main.py 中的 split_content_into_batches")
