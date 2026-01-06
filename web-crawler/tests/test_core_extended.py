# coding=utf-8
"""
Core 模块扩展测试
补充测试 core/ 目录下覆盖率不足的模块
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import tempfile
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPriceHistoryManager(unittest.TestCase):
    """测试价格历史管理器"""

    def test_init_with_redis_failure(self):
        """测试 Redis 连接失败时的初始化"""
        with patch('core.price_history.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            from core.price_history import PriceHistoryManager
            manager = PriceHistoryManager()
            
            self.assertIsNone(manager.client)

    def test_save_daily_price_no_client(self):
        """测试无客户端时保存价格"""
        with patch('core.price_history.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            from core.price_history import PriceHistoryManager
            manager = PriceHistoryManager()
            
            result = manager.save_daily_price("Gold", 2650.0)
            self.assertFalse(result)

    def test_get_history_no_client(self):
        """测试无客户端时获取历史"""
        with patch('core.price_history.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            from core.price_history import PriceHistoryManager
            manager = PriceHistoryManager()
            
            result = manager.get_history("Gold", days=7)
            self.assertEqual(result, [])

    def test_get_all_commodities_history_no_client(self):
        """测试无客户端时获取所有商品历史"""
        with patch('core.price_history.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            from core.price_history import PriceHistoryManager
            manager = PriceHistoryManager()
            
            result = manager.get_all_commodities_history(days=7)
            self.assertEqual(result, {})

    @patch('core.price_history.redis.Redis')
    def test_save_current_prices(self, mock_redis):
        """测试批量保存当前价格"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True
        mock_client.hset.return_value = True
        mock_client.hkeys.return_value = []
        
        from core.price_history import PriceHistoryManager
        manager = PriceHistoryManager()
        
        commodities = [
            {"chinese_name": "黄金", "price": 2650, "change_percent": 1.5, "source": "test"},
            {"name": "Silver", "current_price": 31, "change_percent": -0.5, "source": "test"},
            {"name": "无效数据"},  # 缺少价格
        ]
        
        saved = manager.save_current_prices(commodities)
        self.assertEqual(saved, 2)

    @patch('core.price_history.redis.Redis')
    def test_cleanup_old_data(self, mock_redis):
        """测试清理旧数据"""
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True
        
        # 模拟有一些旧数据
        old_date = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")
        mock_client.hkeys.return_value = [old_date, datetime.now().strftime("%Y-%m-%d")]
        
        from core.price_history import PriceHistoryManager
        manager = PriceHistoryManager()
        
        manager._cleanup_old_data("test_key", days=30)
        
        # 应该删除旧日期
        mock_client.hdel.assert_called()

    @patch('core.price_history.redis.Redis')
    def test_get_history_with_data(self, mock_redis):
        """测试获取历史数据"""
        import json
        mock_client = MagicMock()
        mock_redis.return_value = mock_client
        mock_client.ping.return_value = True
        
        today = datetime.now().strftime("%Y-%m-%d")
        mock_client.hgetall.return_value = {
            today: json.dumps({"price": 2650, "change_percent": 1.5, "source": "test"})
        }
        
        from core.price_history import PriceHistoryManager
        manager = PriceHistoryManager()
        
        history = manager.get_history("Gold", days=7)
        
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["price"], 2650)
        self.assertEqual(history[0]["date"], today)


class TestPushRecordManager(unittest.TestCase):
    """测试推送记录管理器"""

    def setUp(self):
        """创建临时目录"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        os.makedirs("output/.push_records", exist_ok=True)

    def tearDown(self):
        """清理临时目录"""
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('core.push_record.CONFIG')
    @patch('core.push_record.get_beijing_time')
    def test_has_pushed_today_false(self, mock_time, mock_config):
        """测试今天未推送"""
        mock_config.__getitem__ = MagicMock(return_value={"RECORD_RETENTION_DAYS": 7})
        mock_time.return_value = datetime(2025, 12, 6, 10, 0, 0)
        
        from core.push_record import PushRecordManager
        manager = PushRecordManager()
        
        result = manager.has_pushed_today()
        self.assertFalse(result)

    @patch('core.push_record.CONFIG')
    @patch('core.push_record.get_beijing_time')
    def test_record_push(self, mock_time, mock_config):
        """测试记录推送"""
        mock_config.__getitem__ = MagicMock(return_value={"RECORD_RETENTION_DAYS": 7})
        mock_time.return_value = datetime(2025, 12, 6, 10, 0, 0)
        
        from core.push_record import PushRecordManager
        manager = PushRecordManager()
        
        manager.record_push("当日汇总")
        
        # 检查记录是否已保存
        self.assertTrue(manager.has_pushed_today())

    @patch('core.push_record.CONFIG')
    @patch('core.push_record.get_beijing_time')
    def test_is_in_time_range(self, mock_time, mock_config):
        """测试时间范围判断"""
        mock_config.__getitem__ = MagicMock(return_value={"RECORD_RETENTION_DAYS": 7})
        mock_time.return_value = datetime(2025, 12, 6, 10, 30, 0)
        
        from core.push_record import PushRecordManager
        manager = PushRecordManager()
        
        # 在时间范围内
        self.assertTrue(manager.is_in_time_range("09:00", "11:00"))
        
        # 不在时间范围内
        self.assertFalse(manager.is_in_time_range("11:00", "12:00"))

    @patch('core.push_record.CONFIG')
    @patch('core.push_record.get_beijing_time')
    def test_ensure_record_dir(self, mock_time, mock_config):
        """测试确保记录目录存在"""
        mock_config.__getitem__ = MagicMock(return_value={"RECORD_RETENTION_DAYS": 7})
        mock_time.return_value = datetime(2025, 12, 6, 10, 0, 0)
        
        from core.push_record import PushRecordManager
        manager = PushRecordManager()
        
        self.assertTrue(manager.record_dir.exists())

    @patch('core.push_record.CONFIG')
    @patch('core.push_record.get_beijing_time')
    def test_get_today_record_file(self, mock_time, mock_config):
        """测试获取今日记录文件路径"""
        mock_config.__getitem__ = MagicMock(return_value={"RECORD_RETENTION_DAYS": 7})
        mock_time.return_value = datetime(2025, 12, 6, 10, 0, 0)
        
        from core.push_record import PushRecordManager
        manager = PushRecordManager()
        
        record_file = manager.get_today_record_file()
        self.assertIn("push_record_20251206", str(record_file))


class TestConfigModule(unittest.TestCase):
    """测试配置模块"""

    def test_config_loaded(self):
        """测试配置已加载"""
        from core.config import CONFIG, VERSION
        
        self.assertIsNotNone(CONFIG)
        self.assertIsNotNone(VERSION)
        self.assertIn("PLATFORMS", CONFIG)

    def test_version_format(self):
        """测试版本号格式"""
        from core.config import VERSION
        
        import re
        self.assertRegex(VERSION, r"\d+\.\d+\.\d+")


class TestUtilsExtended(unittest.TestCase):
    """测试工具函数扩展"""

    def test_get_beijing_time(self):
        """测试获取北京时间"""
        from core.utils import get_beijing_time
        
        result = get_beijing_time()
        self.assertIsInstance(result, datetime)

    def test_ensure_directory_exists(self):
        """测试确保目录存在"""
        from core.utils import ensure_directory_exists
        
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = os.path.join(temp_dir, "new_dir")
            ensure_directory_exists(test_path)
            self.assertTrue(os.path.exists(test_path))

    def test_strip_markdown(self):
        """测试去除 Markdown 格式"""
        from core.utils import strip_markdown
        
        # 测试粗体
        result = strip_markdown("**bold text**")
        self.assertEqual(result, "bold text")
        
        # 测试链接
        result = strip_markdown("[link text](http://example.com)")
        self.assertIn("link text", result)
        
        # 测试标题
        result = strip_markdown("# Heading")
        self.assertEqual(result.strip(), "Heading")

    def test_check_version_update(self):
        """测试版本检查"""
        from core.utils import check_version_update
        from unittest.mock import patch, MagicMock
        
        with patch('core.utils.requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.text = "2.0.0"
            mock_response.raise_for_status = MagicMock()
            mock_get.return_value = mock_response
            
            need_update, new_version = check_version_update("1.0.0", "http://test.com/version")
            self.assertTrue(need_update)
            self.assertEqual(new_version, "2.0.0")


class TestDataFetcherExtended(unittest.TestCase):
    """测试数据获取器扩展"""

    @patch('core.data_fetcher.requests.get')
    def test_fetch_data_with_custom_params(self, mock_get):
        """测试使用自定义参数获取数据"""
        from core.data_fetcher import DataFetcher
        
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
    def test_fetch_data_retry(self, mock_get):
        """测试获取数据重试"""
        from core.data_fetcher import DataFetcher
        
        # 第一次失败，第二次成功
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.text = '{"status": "success"}'
        mock_response_success.raise_for_status = MagicMock()
        
        mock_get.side_effect = [
            Exception("Network error"),
            mock_response_success
        ]
        
        fetcher = DataFetcher()
        result, id_value, alias = fetcher.fetch_data("test_id", max_retries=2)
        
        self.assertIsNotNone(result)


class TestStatisticsExtended(unittest.TestCase):
    """测试统计模块扩展"""

    def test_calculate_news_weight_with_boost(self):
        """测试带加权的新闻权重计算"""
        from core.statistics import calculate_news_weight
        
        news = {"ranks": [1, 1, 1], "count": 3}
        weight = calculate_news_weight(news, rank_threshold=5)
        
        # 多次出现在 top 排名应该有更高权重
        self.assertGreater(weight, 0)

    def test_format_rank_display_various_modes(self):
        """测试不同模式的排名显示"""
        from core.statistics import format_rank_display
        
        ranks = [1, 3, 5, 10]
        
        # 飞书格式
        feishu_result = format_rank_display(ranks, 5, "feishu")
        self.assertIn("1", feishu_result)
        
        # 钉钉格式
        dingtalk_result = format_rank_display(ranks, 5, "dingtalk")
        self.assertIn("1", dingtalk_result)


class TestAnalyzer(unittest.TestCase):
    """测试分析器"""

    def test_analyzer_init(self):
        """测试分析器初始化"""
        from core.analyzer import NewsAnalyzer
        
        analyzer = NewsAnalyzer()
        
        self.assertIsNotNone(analyzer.data_fetcher)
        self.assertIn(analyzer.report_mode, ["incremental", "current", "daily"])

    def test_mode_strategies_exist(self):
        """测试模式策略存在"""
        from core.analyzer import NewsAnalyzer
        
        analyzer = NewsAnalyzer()
        
        # 检查 MODE_STRATEGIES 存在
        self.assertTrue(hasattr(analyzer, 'MODE_STRATEGIES'))
        self.assertIsInstance(analyzer.MODE_STRATEGIES, dict)
        
        # 至少有一个策略
        self.assertGreater(len(analyzer.MODE_STRATEGIES), 0)


class TestDataProcessorExtended(unittest.TestCase):
    """测试数据处理器扩展"""

    def test_load_frequency_words_empty_file(self):
        """测试加载空频率词文件"""
        from core.data_processor import load_frequency_words
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("")
            temp_file = f.name
        
        try:
            word_groups, filter_words = load_frequency_words(temp_file)
            self.assertEqual(len(word_groups), 0)
            self.assertEqual(len(filter_words), 0)
        finally:
            os.unlink(temp_file)

    def test_load_frequency_words_with_required(self):
        """测试加载带必需词的频率词"""
        from core.data_processor import load_frequency_words
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("+必需词\n普通词\n\n+另一必需词\n另一普通词")
            temp_file = f.name
        
        try:
            word_groups, filter_words = load_frequency_words(temp_file)
            self.assertEqual(len(word_groups), 2)
            
            # 检查必需词
            self.assertIn("必需词", word_groups[0]["required"])
            self.assertIn("另一必需词", word_groups[1]["required"])
        finally:
            os.unlink(temp_file)


class TestReportersBase(unittest.TestCase):
    """测试报告生成器基础模块"""

    def test_prepare_report_data(self):
        """测试准备报告数据"""
        from core.reporters.base import prepare_report_data
        
        stats = [
            {
                "word": "测试关键词",
                "count": 5,
                "percentage": 25.0,
                "titles": []
            }
        ]
        
        # new_titles 的正确格式: {source_id: {title: title_data}}
        new_titles = {
            "test": {
                "新标题1": {"ranks": [1], "url": "http://test.com", "mobileUrl": ""},
                "新标题2": {"ranks": [2], "url": "http://test2.com", "mobileUrl": ""}
            }
        }
        
        # 测试基本调用
        report_data = prepare_report_data(
            stats=stats,
            failed_ids=["failed_id"],
            new_titles=new_titles,
            id_to_name={"test": "测试平台"},
            mode="daily"
        )
        
        # 检查结构
        self.assertIsInstance(report_data, dict)
        self.assertIn("stats", report_data)
        self.assertIn("failed_ids", report_data)

    def test_format_title_for_platform_without_url(self):
        """测试无 URL 的标题格式化"""
        from core.reporters.base import format_title_for_platform
        
        title_data = {
            "title": "测试标题",
            "source_name": "测试平台",
            "ranks": [1],
            "rank_threshold": 5,
            "url": "",
            "mobile_url": "",
            "time_display": "10:00",
            "count": 1,
            "is_new": False
        }
        
        result = format_title_for_platform("feishu", title_data)
        self.assertIn("测试标题", result)


if __name__ == '__main__':
    unittest.main()
