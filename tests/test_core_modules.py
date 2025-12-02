# coding=utf-8
"""
核心模块单元测试
测试 core/ 目录下的模块功能
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestUtils(unittest.TestCase):
    """测试工具函数"""

    def test_clean_title(self):
        """测试标题清理"""
        from core.utils import clean_title
        
        # 测试换行符清理
        self.assertEqual(clean_title("标题\n换行"), "标题 换行")
        
        # 测试多空格合并
        self.assertEqual(clean_title("标题   多空格"), "标题 多空格")
        
        # 测试首尾空格
        self.assertEqual(clean_title("  标题  "), "标题")
        
        # 测试非字符串输入
        self.assertEqual(clean_title(123), "123")
        
    def test_html_escape(self):
        """测试 HTML 转义"""
        from core.utils import html_escape
        
        self.assertEqual(html_escape("<script>"), "&lt;script&gt;")
        self.assertEqual(html_escape("a & b"), "a &amp; b")
        self.assertEqual(html_escape('"quoted"'), "&quot;quoted&quot;")

    def test_format_date_folder(self):
        """测试日期文件夹格式化"""
        from core.utils import format_date_folder
        
        result = format_date_folder()
        # 应该返回类似 "2025年12月02日" 的格式
        self.assertRegex(result, r"\d{4}年\d{2}月\d{2}日")

    def test_strip_markdown(self):
        """测试 Markdown 语法去除"""
        from core.utils import strip_markdown
        
        # 测试粗体
        self.assertEqual(strip_markdown("**bold**"), "bold")
        
        # 测试链接
        self.assertEqual(strip_markdown("[text](url)"), "text url")
        
        # 测试标题符号
        self.assertEqual(strip_markdown("# 标题"), "标题")


class TestStatistics(unittest.TestCase):
    """测试统计模块"""

    def test_calculate_news_weight(self):
        """测试新闻权重计算"""
        from core.statistics import calculate_news_weight
        
        # 测试高排名新闻
        high_rank_news = {"ranks": [1, 2, 3], "count": 3}
        weight = calculate_news_weight(high_rank_news, rank_threshold=5)
        self.assertGreater(weight, 0)
        
        # 测试低排名新闻
        low_rank_news = {"ranks": [50, 60, 70], "count": 3}
        low_weight = calculate_news_weight(low_rank_news, rank_threshold=5)
        
        # 高排名应该权重更高
        self.assertGreater(weight, low_weight)
        
        # 测试空排名
        empty_news = {"ranks": [], "count": 0}
        self.assertEqual(calculate_news_weight(empty_news), 0.0)

    def test_matches_word_groups(self):
        """测试词组匹配"""
        from core.statistics import matches_word_groups
        
        word_groups = [
            {"required": [], "normal": ["AI", "人工智能"], "group_key": "AI"}
        ]
        filter_words = ["广告"]
        
        # 测试正常匹配
        self.assertTrue(matches_word_groups("AI发展趋势", word_groups, filter_words))
        
        # 测试过滤词
        self.assertFalse(matches_word_groups("AI广告推广", word_groups, filter_words))
        
        # 测试不匹配
        self.assertFalse(matches_word_groups("天气预报", word_groups, filter_words))
        
        # 测试空词组（应匹配所有）
        self.assertTrue(matches_word_groups("任何内容", [], []))

    def test_format_rank_display(self):
        """测试排名显示格式化"""
        from core.statistics import format_rank_display
        
        # 测试单一排名
        result = format_rank_display([3], 5, "feishu")
        self.assertIn("3", result)
        
        # 测试范围排名
        result = format_rank_display([1, 5, 10], 5, "feishu")
        self.assertIn("1", result)
        self.assertIn("10", result)
        
        # 测试空排名
        self.assertEqual(format_rank_display([], 5, "feishu"), "")


class TestDataProcessor(unittest.TestCase):
    """测试数据处理模块"""

    def test_load_frequency_words(self):
        """测试加载频率词配置"""
        from core.data_processor import load_frequency_words
        import tempfile
        import os
        
        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("AI\n人工智能\n\n比特币\n加密货币\n!广告")
            temp_file = f.name
        
        try:
            word_groups, filter_words = load_frequency_words(temp_file)
            
            # 应该有2个词组
            self.assertEqual(len(word_groups), 2)
            
            # 应该有1个过滤词
            self.assertEqual(len(filter_words), 1)
            self.assertIn("广告", filter_words)
            
        finally:
            os.unlink(temp_file)


class TestPushRecord(unittest.TestCase):
    """测试推送记录管理"""

    @patch('core.push_record.CONFIG')
    def test_push_record_manager(self, mock_config):
        """测试推送记录管理器"""
        mock_config.__getitem__ = MagicMock(return_value={
            "RECORD_RETENTION_DAYS": 7
        })
        
        from core.push_record import PushRecordManager
        
        # 创建管理器实例
        manager = PushRecordManager()
        
        # 测试记录目录是否创建
        self.assertTrue(manager.record_dir.exists())


class TestDataFetcher(unittest.TestCase):
    """测试数据获取模块"""

    @patch('core.data_fetcher.requests.get')
    def test_fetch_data_success(self, mock_get):
        """测试成功获取数据"""
        from core.data_fetcher import DataFetcher
        
        # Mock 响应
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"status": "success", "items": []}'
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        fetcher = DataFetcher()
        result, id_value, alias = fetcher.fetch_data("test_id")
        
        self.assertIsNotNone(result)
        self.assertEqual(id_value, "test_id")

    @patch('core.data_fetcher.requests.get')
    def test_fetch_data_failure(self, mock_get):
        """测试获取数据失败"""
        from core.data_fetcher import DataFetcher
        
        mock_get.side_effect = Exception("Network error")
        
        fetcher = DataFetcher()
        result, id_value, alias = fetcher.fetch_data("test_id", max_retries=0)
        
        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
