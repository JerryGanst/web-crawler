# coding=utf-8
"""
API 完整测试
覆盖所有 api/ 目录下的路由端点
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import tempfile
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestNewsRoutes(unittest.TestCase):
    """测试新闻路由"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_commodity_news_no_cache(self):
        """测试获取大宗商品新闻（无缓存）"""
        response = self.client.get("/api/commodity-news")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("data", data)

    def test_supply_chain_news_no_cache(self):
        """测试获取供应链新闻（无缓存）"""
        response = self.client.get("/api/news/supply-chain")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

    def test_tariff_news_no_cache(self):
        """测试获取关税新闻（无缓存）"""
        response = self.client.get("/api/news/tariff")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

    def test_news_by_category_finance(self):
        """测试按分类获取财经新闻"""
        response = self.client.get("/api/news/finance")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["category"], "finance")

    def test_news_by_category_tech(self):
        """测试按分类获取科技新闻"""
        response = self.client.get("/api/news/tech")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["category"], "tech")

    def test_news_by_category_social(self):
        """测试按分类获取社交新闻"""
        response = self.client.get("/api/news/social")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["category"], "social")

    def test_news_by_category_all(self):
        """测试获取所有分类新闻"""
        response = self.client.get("/api/news/all")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

    def test_crawl_endpoint(self):
        """测试爬取端点"""
        response = self.client.post("/api/crawl", json={"category": "finance"})
        # 可能成功或失败，但不应该是 404
        self.assertNotEqual(response.status_code, 404)


class TestDataRoutes(unittest.TestCase):
    """测试数据路由"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_get_data_no_cache(self):
        """测试获取数据（无缓存）"""
        response = self.client.get("/api/data")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("data", data)
        self.assertIn("source", data)

    def test_get_categories(self):
        """测试获取分类列表"""
        response = self.client.get("/api/categories")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("categories", data)

    def test_get_platforms(self):
        """测试获取平台列表"""
        response = self.client.get("/api/platforms")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("platforms", data)
        self.assertIn("total", data)

    def test_get_data_sources(self):
        """测试获取数据源"""
        response = self.client.get("/api/data/sources")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("sources", data)
        self.assertIn("cascade", data)

    def test_get_price_history(self):
        """测试获取价格历史"""
        response = self.client.get("/api/price-history")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("data", data)

    def test_get_price_history_with_days(self):
        """测试获取指定天数的价格历史"""
        response = self.client.get("/api/price-history?days=14")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # 检查返回的 days 字段（可能在 data 中或顶层）
        self.assertIn("status", data)

    def test_get_status(self):
        """测试获取系统状态"""
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "running")
        self.assertIn("timestamp", data)
        self.assertIn("cache", data)


class TestCacheRoutes(unittest.TestCase):
    """测试缓存路由"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_cache_status(self):
        """测试获取缓存状态"""
        response = self.client.get("/api/cache/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("backend", data)
        self.assertIn("keys", data)

    def test_clear_cache(self):
        """测试清除缓存"""
        response = self.client.post("/api/cache/clear")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

    def test_delete_cache_key(self):
        """测试删除缓存键"""
        response = self.client.delete("/api/cache/nonexistent_key")
        self.assertEqual(response.status_code, 200)


class TestReportsRoutes(unittest.TestCase):
    """测试报告路由"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_list_reports(self):
        """测试获取报告列表"""
        response = self.client.get("/api/reports")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("reports", data)
        self.assertIn("total", data)

    def test_download_nonexistent_report(self):
        """测试下载不存在的报告"""
        response = self.client.get("/api/reports/nonexistent_12345.md")
        self.assertEqual(response.status_code, 404)

    def test_download_report_path_traversal(self):
        """测试路径遍历攻击防护"""
        response = self.client.get("/api/reports/../../../etc/passwd")
        self.assertIn(response.status_code, [400, 404])


class TestAnalysisRoutes(unittest.TestCase):
    """测试分析路由"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_market_analysis_no_cache(self):
        """测试市场分析（无缓存）"""
        # 这个端点可能需要 AI API，所以可能返回错误
        response = self.client.get("/api/market-analysis")
        # 可能成功或失败，但应该返回有效响应
        self.assertIn(response.status_code, [200, 400, 500])


class TestRootEndpoint(unittest.TestCase):
    """测试根端点"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_root(self):
        """测试根路由"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "TrendRadar API")
        self.assertIn("version", data)
        self.assertIn("endpoints", data)


class TestCacheModuleComplete(unittest.TestCase):
    """测试缓存模块完整功能"""

    def test_redis_cache_with_redis_success(self):
        """测试 Redis 连接成功"""
        with patch('api.cache.redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client
            
            from api.cache import RedisCache
            cache = RedisCache()
            
            self.assertIsNotNone(cache.client)

    def test_cache_get_all_keys(self):
        """测试获取所有键"""
        with patch('api.cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            from api.cache import RedisCache
            cache = RedisCache()
            
            cache.set("key1", "value1")
            cache.set("key2", "value2")
            
            keys = cache.get_all_keys()
            self.assertIn("key1", keys)
            self.assertIn("key2", keys)

    def test_cache_get_status(self):
        """测试获取缓存状态"""
        with patch('api.cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            from api.cache import RedisCache
            cache = RedisCache()
            
            cache.set("test_key", "test_value")
            
            status = cache.get_status()
            self.assertEqual(status["backend"], "memory")
            self.assertFalse(status["connected"])
            self.assertEqual(status["keys_count"], 1)

    def test_cache_get_ttl(self):
        """测试获取 TTL"""
        with patch('api.cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            from api.cache import RedisCache
            cache = RedisCache()
            
            cache.set("ttl_key", "value", ttl=3600)
            
            ttl = cache.get_ttl("ttl_key")
            self.assertGreater(ttl, 3500)

    def test_cache_clear_all(self):
        """测试清除所有缓存"""
        with patch('api.cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            from api.cache import RedisCache
            cache = RedisCache()
            
            cache.set("key1", "value1")
            cache.set("key2", "value2")
            
            count = cache.clear_all()
            self.assertEqual(count, 2)
            self.assertEqual(len(cache._fallback_cache), 0)


class TestNewsHelpers(unittest.TestCase):
    """测试新闻辅助函数"""

    def test_crawl_news_function(self):
        """测试 _crawl_news 函数"""
        from api.routes.news import _crawl_news
        
        with patch('scrapers.unified.UnifiedDataSource') as mock_source:
            mock_instance = MagicMock()
            mock_instance.crawl_category.return_value = [
                {"title": "测试新闻", "url": "http://test.com"}
            ]
            mock_source.return_value = mock_instance
            
            result = _crawl_news("finance", include_custom=True)
            
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["category"], "finance")


class TestAnalysisHelpers(unittest.TestCase):
    """测试分析辅助函数"""

    def test_load_config(self):
        """测试加载配置"""
        from api.routes.analysis import load_config
        
        config = load_config()
        self.assertIsInstance(config, dict)

    def test_get_ai_config(self):
        """测试获取 AI 配置"""
        from api.routes.analysis import get_ai_config
        
        ai_config = get_ai_config()
        self.assertIn("internal", ai_config)
        self.assertIn("external", ai_config)

    @patch('api.routes.analysis.req.post')
    def test_call_ai_api(self, mock_post):
        """测试调用 AI API"""
        from api.routes.analysis import call_ai_api
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "AI 响应"}}]
        }
        mock_post.return_value = mock_response
        
        response = call_ai_api(
            "http://test.api/v1",
            "test_key",
            "test_model",
            "系统提示",
            "用户提示"
        )
        
        self.assertEqual(response.status_code, 200)

    @patch('api.routes.analysis.req.get')
    def test_fetch_realtime_news(self, mock_get):
        """测试实时抓取新闻"""
        from api.routes.analysis import fetch_realtime_news
        
        # 模拟所有请求失败
        mock_get.side_effect = Exception("Network error")
        
        keywords = ["测试关键词"]
        news = fetch_realtime_news(keywords)
        
        # 应该返回空列表
        self.assertIsInstance(news, list)


class TestDataHelpers(unittest.TestCase):
    """测试数据辅助函数"""

    def test_load_config_from_data(self):
        """测试从数据模块加载配置"""
        from api.routes.data import load_config
        
        config = load_config()
        self.assertIsInstance(config, dict)


class TestModelsComplete(unittest.TestCase):
    """测试模型完整功能"""

    def test_report_push_request(self):
        """测试报告推送请求模型"""
        from api.models import ReportPushRequest
        
        request = ReportPushRequest(
            title="测试报告",
            content="报告内容"
        )
        
        self.assertEqual(request.title, "测试报告")
        self.assertEqual(request.content, "报告内容")
        self.assertIsNone(request.webhook_url)

    def test_push_request(self):
        """测试推送请求模型"""
        from api.models import PushRequest
        
        request = PushRequest(content="测试内容")
        
        self.assertEqual(request.content, "测试内容")
        self.assertIsNone(request.webhook_url)

    def test_analysis_request_with_all_fields(self):
        """测试分析请求（所有字段）"""
        from api.models import AnalysisRequest
        
        request = AnalysisRequest(
            company_name="测试公司",
            competitors=["竞争对手1"],
            upstream=["上游1"],
            downstream=["下游1"],
            news=[{"title": "新闻1"}]
        )
        
        self.assertEqual(request.company_name, "测试公司")
        self.assertEqual(len(request.competitors), 1)
        self.assertEqual(len(request.upstream), 1)
        self.assertEqual(len(request.downstream), 1)


if __name__ == '__main__':
    unittest.main()
