# coding=utf-8
"""
平台分析模块
提供平台对比和活跃度统计功能
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional

from ...services.data_service import DataService
from ...utils.validators import validate_keyword, validate_date_range
from ...utils.errors import MCPError, DataNotFoundError


class PlatformAnalyzer:
    """平台分析器"""

    def __init__(self, data_service: DataService):
        self.data_service = data_service

    def compare_platforms(
        self,
        topic: Optional[str] = None,
        date_range: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        平台对比分析 - 对比不同平台对同一话题的关注度

        Args:
            topic: 话题关键词（可选）
            date_range: 日期范围

        Returns:
            平台对比分析结果
        """
        try:
            if topic:
                topic = validate_keyword(topic)
            date_range_tuple = validate_date_range(date_range)

            if date_range_tuple:
                start_date, end_date = date_range_tuple
            else:
                start_date = end_date = datetime.now()

            platform_stats = defaultdict(lambda: {
                "total_news": 0,
                "topic_mentions": 0,
                "unique_titles": set(),
                "top_keywords": Counter()
            })

            current_date = start_date
            while current_date <= end_date:
                try:
                    all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(
                        date=current_date
                    )

                    for platform_id, titles in all_titles.items():
                        platform_name = id_to_name.get(platform_id, platform_id)

                        for title in titles.keys():
                            platform_stats[platform_name]["total_news"] += 1
                            platform_stats[platform_name]["unique_titles"].add(title)

                            if topic and topic.lower() in title.lower():
                                platform_stats[platform_name]["topic_mentions"] += 1

                            keywords = self._extract_keywords(title)
                            platform_stats[platform_name]["top_keywords"].update(keywords)

                except DataNotFoundError:
                    pass

                current_date += timedelta(days=1)

            result_stats = {}
            for platform, stats in platform_stats.items():
                coverage_rate = 0
                if stats["total_news"] > 0:
                    coverage_rate = (stats["topic_mentions"] / stats["total_news"]) * 100

                result_stats[platform] = {
                    "total_news": stats["total_news"],
                    "topic_mentions": stats["topic_mentions"],
                    "unique_titles": len(stats["unique_titles"]),
                    "coverage_rate": round(coverage_rate, 2),
                    "top_keywords": [
                        {"keyword": k, "count": v}
                        for k, v in stats["top_keywords"].most_common(5)
                    ]
                }

            return {
                "success": True,
                "topic": topic,
                "date_range": {
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                },
                "platform_stats": result_stats,
                "total_platforms": len(result_stats)
            }

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e)}}

    def get_platform_activity_stats(
        self,
        date_range: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        平台活跃度统计

        Args:
            date_range: 日期范围

        Returns:
            平台活跃度统计结果
        """
        return self.compare_platforms(topic=None, date_range=date_range)

    def _extract_keywords(self, title: str) -> list:
        """从标题中提取关键词（简单分词）"""
        import re
        # 简单的中文分词：按标点和空格分割，过滤短词
        words = re.split(r'[\s,，。！？、：；""''【】（）\[\]《》]+', title)
        keywords = [w.strip() for w in words if len(w.strip()) >= 2]
        return keywords[:5]  # 限制每个标题最多5个关键词
