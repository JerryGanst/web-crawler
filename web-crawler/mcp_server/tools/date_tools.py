# coding=utf-8
"""
日期工具

提供自然语言日期解析功能。
"""

import re
from datetime import datetime, timedelta
from typing import Dict, Optional


class DateTools:
    """日期解析工具类"""

    # 中文数字映射
    CN_NUMBERS = {
        '零': 0, '一': 1, '二': 2, '三': 3, '四': 4,
        '五': 5, '六': 6, '七': 7, '八': 8, '九': 9,
        '十': 10, '两': 2
    }

    def resolve_date_range(self, expression: str) -> Dict:
        """
        将自然语言日期表达式转换为标准日期范围

        支持的表达式：
        - 今天、昨天、前天
        - 本周、上周、这周
        - 本月、上个月、上月
        - 最近N天、过去N天
        - N天前、N天内
        - 2025年1月、一月份、1月
        - YYYY-MM-DD 格式

        Args:
            expression: 自然语言日期表达式

        Returns:
            解析结果字典 {
                "success": bool,
                "start": "YYYY-MM-DD",
                "end": "YYYY-MM-DD",
                "expression": str,
                "description": str
            }
        """
        today = datetime.now().date()
        expression = expression.strip()
        original_expression = expression

        try:
            # 1. 精确日期匹配 (YYYY-MM-DD)
            if re.match(r'^\d{4}-\d{2}-\d{2}$', expression):
                date = datetime.strptime(expression, "%Y-%m-%d").date()
                return self._success(date, date, original_expression, "指定日期")

            # 2. 今天/昨天/前天
            if expression in ['今天', 'today', '今日']:
                return self._success(today, today, original_expression, "今天")

            if expression in ['昨天', 'yesterday', '昨日']:
                yesterday = today - timedelta(days=1)
                return self._success(yesterday, yesterday, original_expression, "昨天")

            if expression in ['前天']:
                day_before = today - timedelta(days=2)
                return self._success(day_before, day_before, original_expression, "前天")

            # 3. 本周/上周
            if expression in ['本周', '这周', 'this week']:
                start = today - timedelta(days=today.weekday())
                return self._success(start, today, original_expression, "本周")

            if expression in ['上周', 'last week']:
                start = today - timedelta(days=today.weekday() + 7)
                end = start + timedelta(days=6)
                return self._success(start, end, original_expression, "上周")

            # 4. 本月/上月
            if expression in ['本月', '这个月', 'this month']:
                start = today.replace(day=1)
                return self._success(start, today, original_expression, "本月")

            if expression in ['上月', '上个月', 'last month']:
                first_of_month = today.replace(day=1)
                last_month_end = first_of_month - timedelta(days=1)
                last_month_start = last_month_end.replace(day=1)
                return self._success(last_month_start, last_month_end, original_expression, "上个月")

            # 5. 最近N天 / 过去N天
            match = re.match(r'(?:最近|过去|近)(\d+|[一二三四五六七八九十两]+)[天日]', expression)
            if match:
                days = self._parse_chinese_number(match.group(1))
                start = today - timedelta(days=days - 1)
                return self._success(start, today, original_expression, f"最近{days}天")

            # 6. N天前
            match = re.match(r'(\d+|[一二三四五六七八九十两]+)[天日]前', expression)
            if match:
                days = self._parse_chinese_number(match.group(1))
                target = today - timedelta(days=days)
                return self._success(target, target, original_expression, f"{days}天前")

            # 7. N天内
            match = re.match(r'(\d+|[一二三四五六七八九十两]+)[天日]内', expression)
            if match:
                days = self._parse_chinese_number(match.group(1))
                start = today - timedelta(days=days - 1)
                return self._success(start, today, original_expression, f"{days}天内")

            # 8. 最近一周/一个月
            if expression in ['最近一周', '近一周']:
                start = today - timedelta(days=6)
                return self._success(start, today, original_expression, "最近一周")

            if expression in ['最近一个月', '近一个月']:
                start = today - timedelta(days=29)
                return self._success(start, today, original_expression, "最近一个月")

            # 9. YYYY年MM月
            match = re.match(r'(\d{4})年(\d{1,2})月', expression)
            if match:
                year = int(match.group(1))
                month = int(match.group(2))
                start = datetime(year, month, 1).date()
                # 计算该月最后一天
                if month == 12:
                    end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
                else:
                    end = datetime(year, month + 1, 1).date() - timedelta(days=1)
                return self._success(start, end, original_expression, f"{year}年{month}月")

            # 10. N月 / N月份 (当年)
            match = re.match(r'(\d{1,2}|[一二三四五六七八九十]+)月(?:份)?$', expression)
            if match:
                month = self._parse_chinese_number(match.group(1))
                if 1 <= month <= 12:
                    year = today.year
                    start = datetime(year, month, 1).date()
                    if month == 12:
                        end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
                    else:
                        end = datetime(year, month + 1, 1).date() - timedelta(days=1)
                    # 如果指定月份在未来，使用去年
                    if start > today:
                        year -= 1
                        start = datetime(year, month, 1).date()
                        if month == 12:
                            end = datetime(year + 1, 1, 1).date() - timedelta(days=1)
                        else:
                            end = datetime(year, month + 1, 1).date() - timedelta(days=1)
                    return self._success(start, end, original_expression, f"{year}年{month}月")

            # 11. 日期范围 YYYY-MM-DD 到 YYYY-MM-DD
            match = re.match(
                r'(\d{4}-\d{2}-\d{2})\s*(?:到|至|-|~)\s*(\d{4}-\d{2}-\d{2})',
                expression
            )
            if match:
                start = datetime.strptime(match.group(1), "%Y-%m-%d").date()
                end = datetime.strptime(match.group(2), "%Y-%m-%d").date()
                return self._success(start, end, original_expression, "指定日期范围")

            # 无法解析
            return {
                "success": False,
                "expression": original_expression,
                "error": "无法解析日期表达式",
                "suggestion": "支持的格式: 今天、昨天、本周、上周、本月、上月、最近N天、N天前、YYYY-MM-DD 等"
            }

        except Exception as e:
            return {
                "success": False,
                "expression": original_expression,
                "error": f"解析错误: {str(e)}"
            }

    def _success(
        self,
        start,
        end,
        expression: str,
        description: str
    ) -> Dict:
        """构建成功响应"""
        return {
            "success": True,
            "start": start.strftime("%Y-%m-%d"),
            "end": end.strftime("%Y-%m-%d"),
            "expression": expression,
            "description": description,
            "total_days": (end - start).days + 1
        }

    def _parse_chinese_number(self, s: str) -> int:
        """
        解析中文或阿拉伯数字

        Args:
            s: 数字字符串

        Returns:
            整数
        """
        if s.isdigit():
            return int(s)

        # 简单中文数字解析
        if s in self.CN_NUMBERS:
            return self.CN_NUMBERS[s]

        # 处理 "十X" 格式
        if s.startswith('十'):
            if len(s) == 1:
                return 10
            return 10 + self.CN_NUMBERS.get(s[1], 0)

        # 处理 "X十" 格式
        if s.endswith('十'):
            return self.CN_NUMBERS.get(s[0], 1) * 10

        # 处理 "X十X" 格式
        if '十' in s:
            parts = s.split('十')
            tens = self.CN_NUMBERS.get(parts[0], 1)
            ones = self.CN_NUMBERS.get(parts[1], 0) if parts[1] else 0
            return tens * 10 + ones

        return 7  # 默认返回7天

    def get_preset_ranges(self) -> Dict:
        """
        获取预设的日期范围

        Returns:
            预设日期范围字典
        """
        today = datetime.now().date()

        presets = {
            "today": {
                "name": "今天",
                "start": today.strftime("%Y-%m-%d"),
                "end": today.strftime("%Y-%m-%d")
            },
            "yesterday": {
                "name": "昨天",
                "start": (today - timedelta(days=1)).strftime("%Y-%m-%d"),
                "end": (today - timedelta(days=1)).strftime("%Y-%m-%d")
            },
            "this_week": {
                "name": "本周",
                "start": (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d"),
                "end": today.strftime("%Y-%m-%d")
            },
            "last_7_days": {
                "name": "最近7天",
                "start": (today - timedelta(days=6)).strftime("%Y-%m-%d"),
                "end": today.strftime("%Y-%m-%d")
            },
            "this_month": {
                "name": "本月",
                "start": today.replace(day=1).strftime("%Y-%m-%d"),
                "end": today.strftime("%Y-%m-%d")
            },
            "last_30_days": {
                "name": "最近30天",
                "start": (today - timedelta(days=29)).strftime("%Y-%m-%d"),
                "end": today.strftime("%Y-%m-%d")
            }
        }

        return {
            "success": True,
            "presets": presets,
            "current_date": today.strftime("%Y-%m-%d")
        }
