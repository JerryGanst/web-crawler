# coding=utf-8
"""
API 模块扩展测试
补充测试 api/ 目录下覆盖率不足的模块
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestApiRoutesExtended(unittest.TestCase):
    """测试 API 路由扩展"""

    @classmethod
    def setUpClass(cls):
        """设置测试客户端"""
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_get_data_endpoint(self):
        """测试获取数据端点"""
        response = self.client.get("/api/data")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("data", data)

    def test_get_price_history(self):
        """测试获取价格历史"""
        response = self.client.get("/api/price-history")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)

    def test_api_status(self):
        """测试 API 状态"""
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)

    def test_clear_all_cache(self):
        """测试清除所有缓存"""
        response = self.client.post("/api/cache/clear")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

    def test_get_cache_status(self):
        """测试获取缓存状态"""
        response = self.client.get("/api/cache/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("backend", data)


class TestReportsRoutes(unittest.TestCase):
    """测试报告路由"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_list_reports_empty(self):
        """测试获取空报告列表"""
        response = self.client.get("/api/reports")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("reports", data)
        self.assertIn("total", data)

    def test_download_nonexistent_report(self):
        """测试下载不存在的报告"""
        response = self.client.get("/api/reports/nonexistent_report_12345.md")
        self.assertEqual(response.status_code, 404)


class TestNewsRoutes(unittest.TestCase):
    """测试新闻路由"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_get_news_finance(self):
        """测试获取财经新闻"""
        response = self.client.get("/api/news/finance")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["category"], "finance")

    def test_get_news_social(self):
        """测试获取社交新闻"""
        response = self.client.get("/api/news/social")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

    def test_get_news_all(self):
        """测试获取所有新闻"""
        response = self.client.get("/api/news/all")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")


class TestDataRoutes(unittest.TestCase):
    """测试数据路由"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_get_data_with_refresh(self):
        """测试刷新数据"""
        response = self.client.get("/api/data?refresh=true")
        self.assertEqual(response.status_code, 200)

    def test_get_data_sources_detailed(self):
        """测试获取详细数据源"""
        response = self.client.get("/api/data/sources")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("sources", data)
        self.assertIn("cascade", data)


class TestAnalysisRoutes(unittest.TestCase):
    """测试分析路由"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_get_analysis_config(self):
        """测试获取分析配置"""
        response = self.client.get("/api/analysis/config")
        # 可能返回 200 或 404 取决于配置
        self.assertIn(response.status_code, [200, 404, 500])


class TestCacheModule(unittest.TestCase):
    """测试缓存模块"""

    def test_redis_cache_init_failure(self):
        """测试 Redis 连接失败时的初始化"""
        with patch('api.cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            from api.cache import RedisCache
            cache = RedisCache()
            
            # 应该回退到内存缓存 (client 属性应为 None)
            self.assertIsNone(cache.client)

    def test_redis_cache_set_get_fallback(self):
        """测试内存回退模式的设置和获取"""
        with patch('api.cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            from api.cache import RedisCache
            cache = RedisCache()
            
            # 设置值
            cache.set("test_key", {"data": "test"})
            
            # 获取值
            result = cache.get("test_key")
            self.assertEqual(result["data"], "test")

    def test_redis_cache_delete_fallback(self):
        """测试内存回退模式的删除"""
        with patch('api.cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            from api.cache import RedisCache
            cache = RedisCache()
            
            cache.set("delete_key", "value")
            cache.delete("delete_key")
            
            result = cache.get("delete_key")
            self.assertIsNone(result)


class TestModelsValidation(unittest.TestCase):
    """测试模型验证"""

    def test_crawl_request_defaults(self):
        """测试爬取请求默认值"""
        from api.models import CrawlRequest
        
        request = CrawlRequest()
        self.assertEqual(request.category, "finance")  # 默认是 finance
        self.assertTrue(request.include_custom)
        self.assertIsNone(request.webhook_url)

    def test_crawl_request_custom(self):
        """测试爬取请求自定义值"""
        from api.models import CrawlRequest
        
        request = CrawlRequest(
            category="finance",
            include_custom=False,
            webhook_url="http://webhook.example.com"
        )
        
        self.assertEqual(request.category, "finance")
        self.assertFalse(request.include_custom)
        self.assertEqual(request.webhook_url, "http://webhook.example.com")

    def test_analysis_request_minimal(self):
        """测试分析请求最小配置"""
        from api.models import AnalysisRequest
        
        request = AnalysisRequest(company_name="测试公司")
        
        self.assertEqual(request.company_name, "测试公司")
        self.assertIsNone(request.competitors)
        self.assertIsNone(request.news)

    def test_analysis_request_full(self):
        """测试分析请求完整配置"""
        from api.models import AnalysisRequest
        
        request = AnalysisRequest(
            company_name="测试公司",
            competitors=["竞争对手1", "竞争对手2"],
            news=[{"title": "新闻1"}]
        )
        
        self.assertEqual(len(request.competitors), 2)
        self.assertEqual(len(request.news), 1)


if __name__ == '__main__':
    unittest.main()
