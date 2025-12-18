# coding=utf-8
"""
新闻权重计算模块
计算新闻的综合权重分数
"""

from typing import Dict


def calculate_news_weight(news_data: Dict, rank_threshold: int = 5) -> float:
    """
    计算新闻权重（用于排序）

    基于 main.py 的权重算法实现，综合考虑：
    - 排名权重 (60%)：新闻在榜单中的排名
    - 频次权重 (30%)：新闻出现的次数
    - 热度权重 (10%)：高排名出现的比例

    Args:
        news_data: 新闻数据字典，包含 ranks 和 count 字段
        rank_threshold: 高排名阈值，默认5

    Returns:
        权重分数（0-100之间的浮点数）
    """
    ranks = news_data.get("ranks", [])
    if not ranks:
        return 0.0

    count = news_data.get("count", len(ranks))

    # 权重配置（与 config.yaml 保持一致）
    RANK_WEIGHT = 0.6
    FREQUENCY_WEIGHT = 0.3
    HOTNESS_WEIGHT = 0.1

    # 1. 排名权重：Σ(11 - min(rank, 10)) / 出现次数
    rank_scores = []
    for rank in ranks:
        score = 11 - min(rank, 10)
        rank_scores.append(score)

    rank_weight = sum(rank_scores) / len(ranks) if ranks else 0

    # 2. 频次权重：min(出现次数, 10) × 10
    frequency_weight = min(count, 10) * 10

    # 3. 热度加成：高排名次数 / 总出现次数 × 100
    high_rank_count = sum(1 for rank in ranks if rank <= rank_threshold)
    hotness_ratio = high_rank_count / len(ranks) if ranks else 0
    hotness_weight = hotness_ratio * 100

    # 综合权重
    total_weight = (
        rank_weight * RANK_WEIGHT
        + frequency_weight * FREQUENCY_WEIGHT
        + hotness_weight * HOTNESS_WEIGHT
    )

    return total_weight
