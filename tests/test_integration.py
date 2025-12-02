# coding=utf-8
"""
集成测试
测试模块间的协作和完整流程
"""

import unittest
from unittest.mock import patch, MagicMock
import tempfile
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCoreIntegration(unittest.TestCase):
    """核心模块集成测试"""

    def test_config_loading(self):
        """测试配置加载"""
        from core.config import CONFIG, VERSION
        
        # 验证配置已加载
        self.assertIsNotNone(CONFIG)
        self.assertIn("PLATFORMS", CONFIG)
        self.assertIn("REPORT_MODE", CONFIG)
        
        # 验证版本号
        self.assertIsNotNone(VERSION)
        self.assertRegex(VERSION, r"\d+\.\d+\.\d+")

    def test_statistics_with_real_data(self):
        """测试统计模块与真实数据结构"""
        from core.statistics import count_word_frequency, calculate_news_weight
        
        # 模拟真实数据结构
        test_results = {
            "zhihu": {
                "AI发展趋势分析": {"ranks": [1, 2], "url": "http://example.com", "mobileUrl": ""},
                "人工智能新突破": {"ranks": [3], "url": "http://example.com", "mobileUrl": ""},
            },
            "weibo": {
                "AI技术应用": {"ranks": [5, 6], "url": "http://example.com", "mobileUrl": ""},
            }
        }
        
        word_groups = [
            {"required": [], "normal": ["AI", "人工智能"], "group_key": "AI 人工智能", "max_count": 0}
        ]
        
        id_to_name = {"zhihu": "知乎", "weibo": "微博"}
        
        stats, total = count_word_frequency(
            test_results,
            word_groups,
            filter_words=[],
            id_to_name=id_to_name,
            title_info=None,
            rank_threshold=5,
            new_titles=None,
            mode="daily"
        )
        
        # 验证返回结构
        self.assertIsInstance(stats, list)
        self.assertGreater(total, 0)
        
        if stats:
            self.assertIn("word", stats[0])
            self.assertIn("count", stats[0])
            self.assertIn("titles", stats[0])

    def test_data_processor_flow(self):
        """测试数据处理流程"""
        from core.data_processor import save_titles_to_file, parse_file_titles
        from core.utils import ensure_directory_exists
        
        # 创建测试数据
        test_results = {
            "test_platform": {
                "测试标题1": {"ranks": [1], "url": "http://test.com", "mobileUrl": ""},
                "测试标题2": {"ranks": [2], "url": "http://test.com", "mobileUrl": ""},
            }
        }
        id_to_name = {"test_platform": "测试平台"}
        failed_ids = []
        
        # 保存文件
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.getcwd()
            try:
                os.chdir(temp_dir)
                ensure_directory_exists("output")
                
                file_path = save_titles_to_file(test_results, id_to_name, failed_ids)
                
                # 验证文件已创建
                self.assertTrue(Path(file_path).exists())
                
                # 解析文件
                titles_by_id, parsed_id_to_name = parse_file_titles(Path(file_path))
                
                # 验证解析结果
                self.assertIn("test_platform", titles_by_id)
                self.assertEqual(len(titles_by_id["test_platform"]), 2)
                
            finally:
                os.chdir(original_dir)


class TestAnalyticsIntegration(unittest.TestCase):
    """分析模块集成测试"""

    def test_weight_calculator(self):
        """测试权重计算器"""
        from mcp_server.tools.analytics.weight_calculator import calculate_news_weight
        
        # 测试高权重新闻
        high_weight_news = {
            "ranks": [1, 1, 2, 3],
            "count": 4
        }
        weight1 = calculate_news_weight(high_weight_news)
        
        # 测试低权重新闻
        low_weight_news = {
            "ranks": [50],
            "count": 1
        }
        weight2 = calculate_news_weight(low_weight_news)
        
        # 高排名新闻权重应更高
        self.assertGreater(weight1, weight2)

    @patch('mcp_server.tools.analytics.trend_analyzer.DataService')
    def test_trend_analyzer_structure(self, mock_data_service):
        """测试趋势分析器结构"""
        from mcp_server.tools.analytics.trend_analyzer import TrendAnalyzer
        
        mock_service = MagicMock()
        analyzer = TrendAnalyzer(mock_service)
        
        # 验证方法存在
        self.assertTrue(hasattr(analyzer, 'analyze_topic_trend'))
        self.assertTrue(hasattr(analyzer, 'analyze_topic_lifecycle'))


class TestEndToEndFlow(unittest.TestCase):
    """端到端流程测试"""

    def test_analyzer_initialization(self):
        """测试分析器初始化"""
        from core.analyzer import NewsAnalyzer
        
        # 测试分析器可以正常创建
        analyzer = NewsAnalyzer()
        
        # 验证基本属性
        self.assertIsNotNone(analyzer.request_interval)
        self.assertIsNotNone(analyzer.report_mode)
        self.assertIsNotNone(analyzer.rank_threshold)
        self.assertIsNotNone(analyzer.data_fetcher)

    def test_mode_strategies(self):
        """测试模式策略配置"""
        from core.analyzer import NewsAnalyzer
        
        analyzer = NewsAnalyzer()
        
        # 测试各模式策略
        for mode in ["incremental", "current", "daily"]:
            strategy = analyzer.MODE_STRATEGIES.get(mode)
            self.assertIsNotNone(strategy)
            self.assertIn("mode_name", strategy)
            self.assertIn("description", strategy)
            self.assertIn("summary_report_type", strategy)


class TestReportersIntegration(unittest.TestCase):
    """报告生成模块集成测试"""

    def test_prepare_report_data(self):
        """测试报告数据准备"""
        from core.reporters.base import prepare_report_data
        
        # 模拟统计数据
        stats = [
            {
                "word": "AI",
                "count": 5,
                "percentage": 25.0,
                "titles": [
                    {
                        "title": "AI新闻标题",
                        "source_name": "知乎",
                        "time_display": "10时00分",
                        "count": 1,
                        "ranks": [1],
                        "rank_threshold": 5,
                        "url": "http://example.com",
                        "mobileUrl": "",
                        "is_new": False
                    }
                ]
            }
        ]
        
        report_data = prepare_report_data(
            stats=stats,
            failed_ids=[],
            new_titles=None,
            id_to_name={"zhihu": "知乎"},
            mode="daily"
        )
        
        # 验证返回结构
        self.assertIn("stats", report_data)
        self.assertIn("new_titles", report_data)
        self.assertIn("failed_ids", report_data)
        self.assertIn("total_new_count", report_data)

    def test_format_title_for_platform(self):
        """测试平台标题格式化"""
        from core.reporters.base import format_title_for_platform
        
        title_data = {
            "title": "测试标题",
            "source_name": "测试平台",
            "ranks": [1],
            "rank_threshold": 5,
            "url": "http://example.com",
            "mobile_url": "",
            "time_display": "10:00",
            "count": 2,
            "is_new": True
        }
        
        # 测试飞书格式
        feishu_result = format_title_for_platform("feishu", title_data)
        self.assertIn("测试标题", feishu_result)
        self.assertIn("🆕", feishu_result)  # 新标记
        
        # 测试钉钉格式
        dingtalk_result = format_title_for_platform("dingtalk", title_data)
        self.assertIn("测试标题", dingtalk_result)


if __name__ == '__main__':
    unittest.main()
