# coding=utf-8
"""
分析工具统一入口
整合所有分析功能的 AnalyticsTools 类
"""

from typing import Dict, Optional

from ...services.data_service import DataService
from ...utils.errors import MCPError, InvalidParameterError

from .trend_analyzer import TrendAnalyzer
from .platform_analyzer import PlatformAnalyzer
from .keyword_analyzer import KeywordAnalyzer


class AnalyticsTools:
    """高级数据分析工具类"""

    def __init__(self, project_root: str = None):
        """
        初始化分析工具

        Args:
            project_root: 项目根目录
        """
        self.data_service = DataService(project_root)
        self.trend_analyzer = TrendAnalyzer(self.data_service)
        self.platform_analyzer = PlatformAnalyzer(self.data_service)
        self.keyword_analyzer = KeywordAnalyzer(self.data_service)

    def analyze_data_insights_unified(
        self,
        insight_type: str = "platform_compare",
        topic: Optional[str] = None,
        date_range: Optional[Dict[str, str]] = None,
        min_frequency: int = 3,
        top_n: int = 20
    ) -> Dict:
        """
        统一数据洞察分析工具

        Args:
            insight_type: 洞察类型
            topic: 话题关键词
            date_range: 日期范围
            min_frequency: 最小共现频次
            top_n: 返回TOP N结果

        Returns:
            数据洞察分析结果字典
        """
        try:
            if insight_type not in ["platform_compare", "platform_activity", "keyword_cooccur"]:
                raise InvalidParameterError(
                    f"无效的洞察类型: {insight_type}",
                    suggestion="支持的类型: platform_compare, platform_activity, keyword_cooccur"
                )

            if insight_type == "platform_compare":
                return self.platform_analyzer.compare_platforms(
                    topic=topic,
                    date_range=date_range
                )
            elif insight_type == "platform_activity":
                return self.platform_analyzer.get_platform_activity_stats(
                    date_range=date_range
                )
            else:
                return self.keyword_analyzer.analyze_keyword_cooccurrence(
                    min_frequency=min_frequency,
                    top_n=top_n
                )

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e)}}

    def analyze_topic_trend_unified(
        self,
        topic: str,
        analysis_type: str = "trend",
        date_range: Optional[Dict[str, str]] = None,
        granularity: str = "day",
        threshold: float = 3.0,
        time_window: int = 24,
        lookahead_hours: int = 6,
        confidence_threshold: float = 0.7
    ) -> Dict:
        """
        统一话题趋势分析工具

        Args:
            topic: 话题关键词
            analysis_type: 分析类型
            date_range: 日期范围
            granularity: 时间粒度
            threshold: 热度突增倍数阈值
            time_window: 检测时间窗口
            lookahead_hours: 预测未来小时数
            confidence_threshold: 置信度阈值

        Returns:
            趋势分析结果字典
        """
        try:
            if analysis_type not in ["trend", "lifecycle", "viral", "predict"]:
                raise InvalidParameterError(
                    f"无效的分析类型: {analysis_type}",
                    suggestion="支持的类型: trend, lifecycle, viral, predict"
                )

            if analysis_type == "trend":
                return self.trend_analyzer.analyze_topic_trend(
                    topic=topic,
                    date_range=date_range,
                    granularity=granularity
                )
            elif analysis_type == "lifecycle":
                return self.trend_analyzer.analyze_topic_lifecycle(
                    topic=topic,
                    date_range=date_range
                )
            else:
                # viral 和 predict 模式使用简化实现
                return {
                    "success": True,
                    "message": f"{analysis_type} 分析功能开发中",
                    "topic": topic
                }

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e)}}

    # 保留原有方法的兼容性
    def get_topic_trend_analysis(self, topic: str, date_range=None, granularity="day"):
        return self.trend_analyzer.analyze_topic_trend(topic, date_range, granularity)

    def compare_platforms(self, topic=None, date_range=None):
        return self.platform_analyzer.compare_platforms(topic, date_range)

    def analyze_keyword_cooccurrence(self, min_frequency=3, top_n=20):
        return self.keyword_analyzer.analyze_keyword_cooccurrence(min_frequency, top_n)

    def get_platform_activity_stats(self, date_range=None):
        return self.platform_analyzer.get_platform_activity_stats(date_range)

    def analyze_topic_lifecycle(self, topic: str, date_range=None):
        return self.trend_analyzer.analyze_topic_lifecycle(topic, date_range)

    # ==================== 高级分析工具 ====================

    def compare_periods(
        self,
        period1: Dict[str, str],
        period2: Dict[str, str],
        dimensions: Optional[list] = None
    ) -> Dict:
        """
        对比两个时间段的热点差异

        Args:
            period1: 第一个时间段，格式: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            period2: 第二个时间段，格式: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
            dimensions: 对比维度列表，可选: ["topic", "platform", "frequency"]

        Returns:
            对比分析结果
        """
        try:
            from datetime import datetime, timedelta
            from collections import Counter
            from ...utils.validators import validate_date_range
            from ...utils.errors import DataNotFoundError

            # 验证日期范围
            period1_tuple = validate_date_range(period1)
            period2_tuple = validate_date_range(period2)

            if not period1_tuple or not period2_tuple:
                raise InvalidParameterError(
                    "需要提供两个有效的时间段",
                    suggestion="格式: {'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD'}"
                )

            start1, end1 = period1_tuple
            start2, end2 = period2_tuple

            # 默认对比维度
            if not dimensions:
                dimensions = ["topic", "platform"]

            # 收集两个时期的数据
            period1_keywords = Counter()
            period1_platforms = Counter()
            period2_keywords = Counter()
            period2_platforms = Counter()

            # 收集第一个时期
            current = start1
            while current <= end1:
                try:
                    all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(current)
                    for platform_id, titles in all_titles.items():
                        period1_platforms[id_to_name.get(platform_id, platform_id)] += len(titles)
                        for title in titles.keys():
                            keywords = self._extract_keywords_simple(title)
                            period1_keywords.update(keywords)
                except DataNotFoundError:
                    pass
                current += timedelta(days=1)

            # 收集第二个时期
            current = start2
            while current <= end2:
                try:
                    all_titles, id_to_name, _ = self.data_service.parser.read_all_titles_for_date(current)
                    for platform_id, titles in all_titles.items():
                        period2_platforms[id_to_name.get(platform_id, platform_id)] += len(titles)
                        for title in titles.keys():
                            keywords = self._extract_keywords_simple(title)
                            period2_keywords.update(keywords)
                except DataNotFoundError:
                    pass
                current += timedelta(days=1)

            # 分析差异
            comparison = {
                "period1": {"start": start1.strftime("%Y-%m-%d"), "end": end1.strftime("%Y-%m-%d")},
                "period2": {"start": start2.strftime("%Y-%m-%d"), "end": end2.strftime("%Y-%m-%d")}
            }

            if "topic" in dimensions:
                p1_topics = set(period1_keywords.keys())
                p2_topics = set(period2_keywords.keys())
                comparison["topics"] = {
                    "new_in_period2": list(p2_topics - p1_topics)[:20],
                    "disappeared_from_period1": list(p1_topics - p2_topics)[:20],
                    "common": list(p1_topics & p2_topics)[:20]
                }

            if "platform" in dimensions:
                comparison["platforms"] = {
                    "period1": dict(period1_platforms.most_common(10)),
                    "period2": dict(period2_platforms.most_common(10))
                }

            return {"success": True, "comparison": comparison}

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e)}}

    def aggregate_news(
        self,
        date_range: Optional[Dict[str, str]] = None,
        platforms: Optional[list] = None,
        similarity_threshold: float = 0.7,
        limit: int = 100
    ) -> Dict:
        """
        跨平台新闻去重聚合

        Args:
            date_range: 日期范围
            platforms: 平台列表
            similarity_threshold: 相似度阈值
            limit: 返回条数限制

        Returns:
            聚合后的新闻列表
        """
        try:
            from datetime import datetime
            from difflib import SequenceMatcher
            from ...utils.validators import validate_date_range, validate_platforms

            # 验证参数
            date_tuple = validate_date_range(date_range) if date_range else None
            valid_platforms = validate_platforms(platforms) if platforms else None

            # 获取新闻数据
            if date_tuple:
                start_date, end_date = date_tuple
                news_list = self.data_service.get_news_by_date_range(start_date, end_date, valid_platforms)
            else:
                news_list = self.data_service.get_latest_news(platforms=valid_platforms, limit=limit * 2)

            if not news_list:
                return {"success": True, "aggregated_news": [], "total": 0, "message": "没有找到新闻数据"}

            # 简单去重：基于标题相似度
            aggregated = []
            seen_titles = []

            for news in news_list:
                title = news.get("title", "")
                is_duplicate = False

                for seen in seen_titles:
                    ratio = SequenceMatcher(None, title, seen).ratio()
                    if ratio >= similarity_threshold:
                        is_duplicate = True
                        break

                if not is_duplicate:
                    aggregated.append(news)
                    seen_titles.append(title)

                if len(aggregated) >= limit:
                    break

            return {
                "success": True,
                "aggregated_news": aggregated,
                "total": len(aggregated),
                "original_count": len(news_list),
                "duplicates_removed": len(news_list) - len(aggregated)
            }

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e)}}

    def _extract_keywords_simple(self, title: str, min_length: int = 2) -> list:
        """简单关键词提取"""
        import re
        words = re.split(r'[\s,，。！？、：；""''【】（）\[\]《》]+', title)
        return [w for w in words if len(w) >= min_length and not w.isdigit()]
