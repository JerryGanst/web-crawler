# coding=utf-8
"""
MCP Services 模块测试
测试 mcp_server/services/ 目录下的服务
"""

import unittest
from unittest.mock import patch, MagicMock
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCacheService(unittest.TestCase):
    """测试缓存服务"""

    def setUp(self):
        """每个测试前重置缓存"""
        from mcp_server.services.cache_service import CacheService
        self.cache = CacheService()

    def test_set_and_get(self):
        """测试设置和获取缓存"""
        self.cache.set("test_key", {"data": "test_value"})
        result = self.cache.get("test_key")
        
        self.assertEqual(result["data"], "test_value")

    def test_get_nonexistent(self):
        """测试获取不存在的键"""
        result = self.cache.get("nonexistent_key")
        self.assertIsNone(result)

    def test_get_expired(self):
        """测试获取过期的缓存"""
        self.cache.set("expiring_key", "value")
        # 模拟时间流逝
        self.cache._timestamps["expiring_key"] = time.time() - 1000
        
        result = self.cache.get("expiring_key", ttl=900)
        self.assertIsNone(result)

    def test_delete_existing(self):
        """测试删除存在的键"""
        self.cache.set("delete_key", "value")
        result = self.cache.delete("delete_key")
        
        self.assertTrue(result)
        self.assertIsNone(self.cache.get("delete_key"))

    def test_delete_nonexistent(self):
        """测试删除不存在的键"""
        result = self.cache.delete("nonexistent")
        self.assertFalse(result)

    def test_clear(self):
        """测试清空缓存"""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        
        self.cache.clear()
        
        self.assertIsNone(self.cache.get("key1"))
        self.assertIsNone(self.cache.get("key2"))

    def test_cleanup_expired(self):
        """测试清理过期缓存"""
        self.cache.set("fresh_key", "fresh")
        self.cache.set("old_key", "old")
        # 模拟 old_key 过期
        self.cache._timestamps["old_key"] = time.time() - 1000
        
        count = self.cache.cleanup_expired(ttl=900)
        
        self.assertEqual(count, 1)
        self.assertIsNotNone(self.cache.get("fresh_key"))

    def test_get_stats_empty(self):
        """测试空缓存的统计"""
        stats = self.cache.get_stats()
        
        self.assertEqual(stats["total_entries"], 0)
        self.assertEqual(stats["oldest_entry_age"], 0)

    def test_get_stats_with_data(self):
        """测试有数据时的统计"""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        
        stats = self.cache.get_stats()
        
        self.assertEqual(stats["total_entries"], 2)
        self.assertGreaterEqual(stats["oldest_entry_age"], 0)


class TestGlobalCache(unittest.TestCase):
    """测试全局缓存实例"""

    def test_get_cache_singleton(self):
        """测试获取全局缓存是单例"""
        from mcp_server.services.cache_service import get_cache
        
        cache1 = get_cache()
        cache2 = get_cache()
        
        self.assertIs(cache1, cache2)


class TestParserService(unittest.TestCase):
    """测试解析服务"""

    def test_init_default_root(self):
        """测试默认项目根目录初始化"""
        from mcp_server.services.parser_service import ParserService
        
        parser = ParserService()
        self.assertIsNotNone(parser.project_root)

    def test_init_custom_root(self):
        """测试自定义项目根目录初始化"""
        from mcp_server.services.parser_service import ParserService
        
        parser = ParserService("/custom/path")
        self.assertEqual(parser.project_root, Path("/custom/path"))

    def test_clean_title(self):
        """测试清理标题"""
        from mcp_server.services.parser_service import ParserService
        
        # 测试移除多余空白
        result = ParserService.clean_title("  Hello   World  ")
        self.assertEqual(result, "Hello World")

    def test_clean_title_empty(self):
        """测试清理空标题"""
        from mcp_server.services.parser_service import ParserService
        
        result = ParserService.clean_title("   ")
        self.assertEqual(result, "")

    @patch('mcp_server.services.parser_service.Path.exists')
    def test_parse_txt_file_not_exists(self, mock_exists):
        """测试解析不存在的文件"""
        from mcp_server.services.parser_service import ParserService
        from mcp_server.utils.errors import FileParseError
        
        mock_exists.return_value = False
        
        parser = ParserService()
        with self.assertRaises(FileParseError):
            parser.parse_txt_file(Path("/nonexistent/file.txt"))


class TestDataService(unittest.TestCase):
    """测试数据服务"""

    @patch('mcp_server.services.data_service.ParserService')
    @patch('mcp_server.services.data_service.get_cache')
    def test_init(self, mock_cache, mock_parser):
        """测试初始化"""
        from mcp_server.services.data_service import DataService
        
        service = DataService()
        
        self.assertIsNotNone(service.parser)
        self.assertIsNotNone(service.cache)

    @patch('mcp_server.services.data_service.ParserService')
    @patch('mcp_server.services.data_service.get_cache')
    def test_get_latest_news_from_cache(self, mock_cache, mock_parser):
        """测试从缓存获取最新新闻"""
        from mcp_server.services.data_service import DataService
        
        mock_cache_instance = MagicMock()
        mock_cache_instance.get.return_value = [{"title": "cached news"}]
        mock_cache.return_value = mock_cache_instance
        
        service = DataService()
        result = service.get_latest_news(limit=10)
        
        self.assertEqual(result, [{"title": "cached news"}])


class TestAnalyticsPlatformAnalyzer(unittest.TestCase):
    """测试平台分析器"""

    def test_import_platform_analyzer(self):
        """测试导入平台分析器"""
        from mcp_server.tools.analytics.platform_analyzer import PlatformAnalyzer
        
        self.assertIsNotNone(PlatformAnalyzer)


class TestAnalyticsTrendAnalyzer(unittest.TestCase):
    """测试趋势分析器"""

    def test_import_trend_analyzer(self):
        """测试导入趋势分析器"""
        from mcp_server.tools.analytics.trend_analyzer import TrendAnalyzer
        
        self.assertIsNotNone(TrendAnalyzer)


if __name__ == '__main__':
    unittest.main()
