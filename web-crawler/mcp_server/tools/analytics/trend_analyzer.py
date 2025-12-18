# coding=utf-8
"""
趋势分析模块
提供话题热度趋势分析和生命周期分析功能
"""

from datetime import datetime, timedelta
from typing import Dict, Optional

from ...services.data_service import DataService
from ...utils.validators import validate_keyword, validate_date_range
from ...utils.errors import MCPError, InvalidParameterError, DataNotFoundError


class TrendAnalyzer:
    """趋势分析器"""

    def __init__(self, data_service: DataService):
        self.data_service = data_service

    def analyze_topic_trend(
        self,
        topic: str,
        date_range: Optional[Dict[str, str]] = None,
        granularity: str = "day"
    ) -> Dict:
        """
        热度趋势分析 - 追踪特定话题的热度变化趋势

        Args:
            topic: 话题关键词
            date_range: 日期范围（可选）
            granularity: 时间粒度，仅支持 day

        Returns:
            趋势分析结果字典
        """
        try:
            topic = validate_keyword(topic)

            if granularity != "day":
                raise InvalidParameterError(
                    f"不支持的粒度参数: {granularity}",
                    suggestion="当前仅支持 'day' 粒度"
                )

            # 处理日期范围
            if date_range:
                date_range_tuple = validate_date_range(date_range)
                start_date, end_date = date_range_tuple
            else:
                end_date = datetime.now()
                start_date = end_date - timedelta(days=6)

            # 收集趋势数据
            trend_data = []
            current_date = start_date

            while current_date <= end_date:
                try:
                    all_titles, _, _ = self.data_service.parser.read_all_titles_for_date(
                        date=current_date
                    )

                    count = 0
                    matched_titles = []

                    for _, titles in all_titles.items():
                        for title in titles.keys():
                            if topic.lower() in title.lower():
                                count += 1
                                matched_titles.append(title)

                    trend_data.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "count": count,
                        "sample_titles": matched_titles[:3]
                    })

                except DataNotFoundError:
                    trend_data.append({
                        "date": current_date.strftime("%Y-%m-%d"),
                        "count": 0,
                        "sample_titles": []
                    })

                current_date += timedelta(days=1)

            # 计算趋势指标
            counts = [item["count"] for item in trend_data]
            total_days = (end_date - start_date).days + 1

            if len(counts) >= 2:
                first_non_zero = next((c for c in counts if c > 0), 0)
                last_count = counts[-1]

                if first_non_zero > 0:
                    change_rate = ((last_count - first_non_zero) / first_non_zero) * 100
                else:
                    change_rate = 0

                max_count = max(counts)
                peak_index = counts.index(max_count)
                peak_time = trend_data[peak_index]["date"]
            else:
                change_rate = 0
                peak_time = None
                max_count = 0

            return {
                "success": True,
                "topic": topic,
                "date_range": {
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d"),
                    "total_days": total_days
                },
                "granularity": granularity,
                "trend_data": trend_data,
                "statistics": {
                    "total_mentions": sum(counts),
                    "average_mentions": round(sum(counts) / len(counts), 2) if counts else 0,
                    "peak_count": max_count,
                    "peak_time": peak_time,
                    "change_rate": round(change_rate, 2)
                },
                "trend_direction": "上升" if change_rate > 10 else "下降" if change_rate < -10 else "稳定"
            }

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e)}}

    def analyze_topic_lifecycle(
        self,
        topic: str,
        date_range: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        话题生命周期分析 - 从出现到消失的完整周期

        Args:
            topic: 话题关键词
            date_range: 日期范围

        Returns:
            生命周期分析结果
        """
        # 复用趋势分析逻辑，添加生命周期阶段判断
        trend_result = self.analyze_topic_trend(topic, date_range)
        
        if not trend_result.get("success"):
            return trend_result

        # 添加生命周期阶段分析
        counts = [item["count"] for item in trend_result["trend_data"]]
        
        if not counts or all(c == 0 for c in counts):
            lifecycle_stage = "未出现"
        elif counts[-1] > counts[0] and counts[-1] == max(counts):
            lifecycle_stage = "上升期"
        elif counts[-1] == max(counts):
            lifecycle_stage = "高峰期"
        elif counts[-1] < max(counts) * 0.5:
            lifecycle_stage = "衰退期"
        else:
            lifecycle_stage = "稳定期"

        trend_result["lifecycle"] = {
            "stage": lifecycle_stage,
            "first_appearance": next(
                (item["date"] for item in trend_result["trend_data"] if item["count"] > 0),
                None
            ),
            "peak_date": trend_result["statistics"]["peak_time"],
            "duration_days": sum(1 for c in counts if c > 0)
        }

        return trend_result
