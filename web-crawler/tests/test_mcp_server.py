# coding=utf-8
"""
MCP Server 模块测试
测试 mcp_server/ 目录下的工具和服务
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDateParser(unittest.TestCase):
    """测试日期解析器"""

    def test_parse_today_cn(self):
        """测试解析中文'今天'"""
        from mcp_server.utils.date_parser import DateParser
        
        result = DateParser.parse_date_query("今天")
        self.assertEqual(result.date(), datetime.now().date())

    def test_parse_yesterday_cn(self):
        """测试解析中文'昨天'"""
        from mcp_server.utils.date_parser import DateParser
        
        result = DateParser.parse_date_query("昨天")
        expected = (datetime.now() - timedelta(days=1)).date()
        self.assertEqual(result.date(), expected)

    def test_parse_qiantian_cn(self):
        """测试解析中文'前天'"""
        from mcp_server.utils.date_parser import DateParser
        
        result = DateParser.parse_date_query("前天")
        expected = (datetime.now() - timedelta(days=2)).date()
        self.assertEqual(result.date(), expected)

    def test_parse_today_en(self):
        """测试解析英文'today'"""
        from mcp_server.utils.date_parser import DateParser
        
        result = DateParser.parse_date_query("today")
        self.assertEqual(result.date(), datetime.now().date())

    def test_parse_yesterday_en(self):
        """测试解析英文'yesterday'"""
        from mcp_server.utils.date_parser import DateParser
        
        result = DateParser.parse_date_query("yesterday")
        expected = (datetime.now() - timedelta(days=1)).date()
        self.assertEqual(result.date(), expected)

    def test_parse_n_days_ago_cn(self):
        """测试解析'N天前'"""
        from mcp_server.utils.date_parser import DateParser
        
        result = DateParser.parse_date_query("5天前")
        expected = (datetime.now() - timedelta(days=5)).date()
        self.assertEqual(result.date(), expected)

    def test_parse_n_days_ago_en(self):
        """测试解析'N days ago'"""
        from mcp_server.utils.date_parser import DateParser
        
        result = DateParser.parse_date_query("3 days ago")
        expected = (datetime.now() - timedelta(days=3)).date()
        self.assertEqual(result.date(), expected)

    def test_parse_iso_date(self):
        """测试解析 ISO 日期格式"""
        from mcp_server.utils.date_parser import DateParser
        
        result = DateParser.parse_date_query("2025-10-15")
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 10)
        self.assertEqual(result.day, 15)

    def test_parse_cn_date(self):
        """测试解析中文日期格式"""
        from mcp_server.utils.date_parser import DateParser
        
        result = DateParser.parse_date_query("2025年10月15日")
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 10)
        self.assertEqual(result.day, 15)

    def test_parse_cn_date_no_year(self):
        """测试解析无年份的中文日期"""
        from mcp_server.utils.date_parser import DateParser
        
        result = DateParser.parse_date_query("6月15日")
        self.assertEqual(result.month, 6)
        self.assertEqual(result.day, 15)

    def test_parse_slash_date(self):
        """测试解析斜杠日期格式"""
        from mcp_server.utils.date_parser import DateParser
        
        result = DateParser.parse_date_query("2025/10/15")
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 10)
        self.assertEqual(result.day, 15)

    def test_parse_weekday_cn(self):
        """测试解析中文星期"""
        from mcp_server.utils.date_parser import DateParser
        
        result = DateParser.parse_date_query("上周一")
        self.assertIsInstance(result, datetime)

    def test_parse_weekday_en(self):
        """测试解析英文星期"""
        from mcp_server.utils.date_parser import DateParser
        
        result = DateParser.parse_date_query("last monday")
        self.assertIsInstance(result, datetime)

    def test_parse_invalid_date(self):
        """测试解析无效日期"""
        from mcp_server.utils.date_parser import DateParser
        from mcp_server.utils.errors import InvalidParameterError
        
        with self.assertRaises(InvalidParameterError):
            DateParser.parse_date_query("无效日期格式xyz")

    def test_parse_empty_date(self):
        """测试解析空日期"""
        from mcp_server.utils.date_parser import DateParser
        from mcp_server.utils.errors import InvalidParameterError
        
        with self.assertRaises(InvalidParameterError):
            DateParser.parse_date_query("")

    def test_parse_too_many_days(self):
        """测试解析过大天数"""
        from mcp_server.utils.date_parser import DateParser
        from mcp_server.utils.errors import InvalidParameterError
        
        with self.assertRaises(InvalidParameterError):
            DateParser.parse_date_query("500天前")

    def test_format_date_folder(self):
        """测试日期格式化为文件夹名"""
        from mcp_server.utils.date_parser import DateParser
        
        date = datetime(2025, 10, 15)
        result = DateParser.format_date_folder(date)
        self.assertEqual(result, "2025年10月15日")

    def test_validate_date_not_future(self):
        """测试验证日期不在未来"""
        from mcp_server.utils.date_parser import DateParser
        from mcp_server.utils.errors import InvalidParameterError
        
        future_date = datetime.now() + timedelta(days=10)
        with self.assertRaises(InvalidParameterError):
            DateParser.validate_date_not_future(future_date)

    def test_validate_date_not_too_old(self):
        """测试验证日期不太久远"""
        from mcp_server.utils.date_parser import DateParser
        from mcp_server.utils.errors import InvalidParameterError
        
        old_date = datetime.now() - timedelta(days=400)
        with self.assertRaises(InvalidParameterError):
            DateParser.validate_date_not_too_old(old_date, max_days=365)


class TestValidators(unittest.TestCase):
    """测试验证器"""

    def test_validate_limit_default(self):
        """测试默认限制值"""
        from mcp_server.utils.validators import validate_limit
        
        result = validate_limit(None, default=20)
        self.assertEqual(result, 20)

    def test_validate_limit_valid(self):
        """测试有效限制值"""
        from mcp_server.utils.validators import validate_limit
        
        result = validate_limit(50, default=20)
        self.assertEqual(result, 50)

    def test_validate_limit_zero(self):
        """测试零限制值"""
        from mcp_server.utils.validators import validate_limit
        from mcp_server.utils.errors import InvalidParameterError
        
        with self.assertRaises(InvalidParameterError):
            validate_limit(0, default=20)

    def test_validate_limit_negative(self):
        """测试负数限制值"""
        from mcp_server.utils.validators import validate_limit
        from mcp_server.utils.errors import InvalidParameterError
        
        with self.assertRaises(InvalidParameterError):
            validate_limit(-10, default=20)

    def test_validate_limit_exceed_max(self):
        """测试超过最大限制"""
        from mcp_server.utils.validators import validate_limit
        from mcp_server.utils.errors import InvalidParameterError
        
        with self.assertRaises(InvalidParameterError):
            validate_limit(2000, default=20, max_limit=1000)

    def test_validate_date_valid(self):
        """测试有效日期"""
        from mcp_server.utils.validators import validate_date
        
        result = validate_date("2025-10-15")
        self.assertEqual(result.year, 2025)
        self.assertEqual(result.month, 10)
        self.assertEqual(result.day, 15)

    def test_validate_date_invalid(self):
        """测试无效日期"""
        from mcp_server.utils.validators import validate_date
        from mcp_server.utils.errors import InvalidParameterError
        
        with self.assertRaises(InvalidParameterError):
            validate_date("invalid-date")

    def test_validate_keyword_valid(self):
        """测试有效关键词"""
        from mcp_server.utils.validators import validate_keyword
        
        result = validate_keyword("  测试关键词  ")
        self.assertEqual(result, "测试关键词")

    def test_validate_keyword_empty(self):
        """测试空关键词"""
        from mcp_server.utils.validators import validate_keyword
        from mcp_server.utils.errors import InvalidParameterError
        
        with self.assertRaises(InvalidParameterError):
            validate_keyword("")

    def test_validate_keyword_too_long(self):
        """测试过长关键词"""
        from mcp_server.utils.validators import validate_keyword
        from mcp_server.utils.errors import InvalidParameterError
        
        long_keyword = "a" * 150
        with self.assertRaises(InvalidParameterError):
            validate_keyword(long_keyword)

    def test_validate_top_n(self):
        """测试 TOP N 验证"""
        from mcp_server.utils.validators import validate_top_n
        
        result = validate_top_n(30, default=10)
        self.assertEqual(result, 30)

    def test_validate_mode_valid(self):
        """测试有效模式"""
        from mcp_server.utils.validators import validate_mode
        
        result = validate_mode("daily", ["daily", "weekly"], "daily")
        self.assertEqual(result, "daily")

    def test_validate_mode_invalid(self):
        """测试无效模式"""
        from mcp_server.utils.validators import validate_mode
        from mcp_server.utils.errors import InvalidParameterError
        
        with self.assertRaises(InvalidParameterError):
            validate_mode("invalid", ["daily", "weekly"], "daily")

    def test_validate_config_section(self):
        """测试配置节验证"""
        from mcp_server.utils.validators import validate_config_section
        
        result = validate_config_section("crawler")
        self.assertEqual(result, "crawler")

    def test_validate_date_range_valid(self):
        """测试有效日期范围"""
        from mcp_server.utils.validators import validate_date_range
        
        date_range = {"start": "2025-01-01", "end": "2025-01-10"}
        result = validate_date_range(date_range)
        self.assertIsNotNone(result)
        self.assertEqual(result[0].day, 1)
        self.assertEqual(result[1].day, 10)

    def test_validate_date_range_none(self):
        """测试 None 日期范围"""
        from mcp_server.utils.validators import validate_date_range
        
        result = validate_date_range(None)
        self.assertIsNone(result)

    def test_validate_date_range_invalid_order(self):
        """测试无效日期顺序"""
        from mcp_server.utils.validators import validate_date_range
        from mcp_server.utils.errors import InvalidParameterError
        
        date_range = {"start": "2025-01-10", "end": "2025-01-01"}
        with self.assertRaises(InvalidParameterError):
            validate_date_range(date_range)


class TestMCPErrors(unittest.TestCase):
    """测试 MCP 错误类"""

    def test_mcp_error_basic(self):
        """测试基础 MCP 错误"""
        from mcp_server.utils.errors import MCPError
        
        error = MCPError("测试错误", code="TEST_ERROR", suggestion="测试建议")
        
        self.assertEqual(error.message, "测试错误")
        self.assertEqual(error.code, "TEST_ERROR")
        self.assertEqual(error.suggestion, "测试建议")

    def test_mcp_error_to_dict(self):
        """测试错误转字典"""
        from mcp_server.utils.errors import MCPError
        
        error = MCPError("测试错误", code="TEST_ERROR", suggestion="测试建议")
        error_dict = error.to_dict()
        
        self.assertEqual(error_dict["code"], "TEST_ERROR")
        self.assertEqual(error_dict["message"], "测试错误")
        self.assertEqual(error_dict["suggestion"], "测试建议")

    def test_data_not_found_error(self):
        """测试数据不存在错误"""
        from mcp_server.utils.errors import DataNotFoundError
        
        error = DataNotFoundError("数据不存在")
        self.assertEqual(error.code, "DATA_NOT_FOUND")

    def test_invalid_parameter_error(self):
        """测试参数无效错误"""
        from mcp_server.utils.errors import InvalidParameterError
        
        error = InvalidParameterError("参数错误")
        self.assertEqual(error.code, "INVALID_PARAMETER")

    def test_configuration_error(self):
        """测试配置错误"""
        from mcp_server.utils.errors import ConfigurationError
        
        error = ConfigurationError("配置错误")
        self.assertEqual(error.code, "CONFIGURATION_ERROR")

    def test_platform_not_supported_error(self):
        """测试平台不支持错误"""
        from mcp_server.utils.errors import PlatformNotSupportedError
        
        error = PlatformNotSupportedError("unknown_platform")
        self.assertEqual(error.code, "PLATFORM_NOT_SUPPORTED")
        self.assertIn("unknown_platform", error.message)

    def test_crawl_task_error(self):
        """测试爬取任务错误"""
        from mcp_server.utils.errors import CrawlTaskError
        
        error = CrawlTaskError("爬取失败")
        self.assertEqual(error.code, "CRAWL_TASK_ERROR")

    def test_file_parse_error(self):
        """测试文件解析错误"""
        from mcp_server.utils.errors import FileParseError
        
        error = FileParseError("/path/to/file.txt", "格式错误")
        self.assertEqual(error.code, "FILE_PARSE_ERROR")
        self.assertIn("/path/to/file.txt", error.message)


class TestKeywordAnalyzer(unittest.TestCase):
    """测试关键词分析器"""

    def test_extract_keywords(self):
        """测试关键词提取"""
        from mcp_server.tools.analytics.keyword_analyzer import KeywordAnalyzer
        
        analyzer = KeywordAnalyzer(MagicMock())
        
        title = "人工智能发展迅速，大模型应用落地"
        keywords = analyzer._extract_keywords(title)
        
        self.assertIsInstance(keywords, list)
        self.assertTrue(len(keywords) > 0)

    def test_extract_keywords_short_words_filtered(self):
        """测试过滤短词"""
        from mcp_server.tools.analytics.keyword_analyzer import KeywordAnalyzer
        
        analyzer = KeywordAnalyzer(MagicMock())
        
        title = "我 是 一个 测试标题"
        keywords = analyzer._extract_keywords(title)
        
        # 单字符应该被过滤
        for kw in keywords:
            self.assertGreaterEqual(len(kw), 2)


class TestWeightCalculator(unittest.TestCase):
    """测试权重计算器"""

    def test_calculate_news_weight_basic(self):
        """测试基础权重计算"""
        from mcp_server.tools.analytics.weight_calculator import calculate_news_weight
        
        news_data = {
            "ranks": [1, 2, 3],
            "count": 3
        }
        weight = calculate_news_weight(news_data)
        
        self.assertGreater(weight, 0)

    def test_calculate_news_weight_empty(self):
        """测试空数据权重计算"""
        from mcp_server.tools.analytics.weight_calculator import calculate_news_weight
        
        news_data = {"ranks": [], "count": 0}
        weight = calculate_news_weight(news_data)
        
        self.assertEqual(weight, 0.0)

    def test_calculate_news_weight_high_ranks(self):
        """测试高排名权重"""
        from mcp_server.tools.analytics.weight_calculator import calculate_news_weight
        
        # 高排名新闻
        high_rank = {"ranks": [1, 1, 1], "count": 3}
        # 低排名新闻
        low_rank = {"ranks": [10, 10, 10], "count": 3}
        
        high_weight = calculate_news_weight(high_rank)
        low_weight = calculate_news_weight(low_rank)
        
        self.assertGreater(high_weight, low_weight)


class TestAnalyticsTools(unittest.TestCase):
    """测试分析工具"""

    def test_import_tools(self):
        """测试导入工具模块"""
        from mcp_server.tools.analytics import tools
        
        self.assertIsNotNone(tools)


if __name__ == '__main__':
    unittest.main()
