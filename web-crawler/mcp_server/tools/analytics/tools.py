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
