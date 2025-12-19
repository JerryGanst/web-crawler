# coding=utf-8
"""
API 模块测试
测试 api/ 目录下的路由和缓存功能
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRedisCache(unittest.TestCase):
    """测试 Redis 缓存类"""

    def test_fallback_cache_set_get(self):
        """测试内存缓存备用方案"""
        from api.cache import RedisCache
        
        # 创建使用内存缓存的实例
        with patch('api.cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            cache = RedisCache()
            
            # 设置缓存
            result = cache.set("test_key", {"value": "test_data"}, ttl=3600)
            self.assertTrue(result)
            
            # 获取缓存
            data = cache.get("test_key")
            self.assertIsNotNone(data)
            self.assertEqual(data["value"], "test_data")
            
            # 检查存在
            self.assertTrue(cache._fallback_cache.get("test_key") is not None)
            
            # 删除缓存
            cache.delete("test_key")
            self.assertIsNone(cache._fallback_cache.get("test_key"))

    def test_key_prefix(self):
        """测试键前缀"""
        from api.cache import RedisCache, REDIS_PREFIX
        
        with patch('api.cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            cache = RedisCache()
            
            key = cache._key("my_key")
            self.assertEqual(key, f"{REDIS_PREFIX}my_key")

    def test_clear_all_fallback(self):
        """测试清除所有缓存（内存模式）"""
        from api.cache import RedisCache
        
        with patch('api.cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            cache = RedisCache()
            cache.set("key1", "value1")
            cache.set("key2", "value2")
            
            count = cache.clear_all()
            self.assertEqual(count, 2)
            self.assertEqual(len(cache._fallback_cache), 0)

    def test_get_all_keys_fallback(self):
        """测试获取所有键（内存模式）"""
        from api.cache import RedisCache
        
        with patch('api.cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            cache = RedisCache()
            cache.set("key1", "value1")
            cache.set("key2", "value2")
            
            keys = cache.get_all_keys()
            self.assertEqual(len(keys), 2)
            self.assertIn("key1", keys)
            self.assertIn("key2", keys)

    def test_get_status_fallback(self):
        """测试获取状态（内存模式）"""
        from api.cache import RedisCache
        
        with patch('api.cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            cache = RedisCache()
            cache.set("key1", "value1")
            
            status = cache.get_status()
            self.assertEqual(status["backend"], "memory")
            self.assertFalse(status["connected"])
            self.assertEqual(status["keys_count"], 1)

    def test_get_ttl_fallback(self):
        """测试获取 TTL（内存模式）"""
        from api.cache import RedisCache
        
        with patch('api.cache.redis.Redis') as mock_redis:
            mock_redis.return_value.ping.side_effect = Exception("Connection refused")
            
            cache = RedisCache()
            cache.set("test_key", "value", ttl=3600)
            
            ttl = cache.get_ttl("test_key")
            self.assertGreater(ttl, 3500)  # 应该接近 3600


class TestApiModels(unittest.TestCase):
    """测试 API 数据模型"""

    def test_crawl_request(self):
        """测试爬取请求模型"""
        from api.models import CrawlRequest
        
        request = CrawlRequest(category="finance")
        self.assertEqual(request.category, "finance")
        self.assertIsNone(request.webhook_url)
        self.assertTrue(request.include_custom)

    def test_push_request(self):
        """测试推送请求模型"""
        from api.models import PushRequest
        
        request = PushRequest(content="Test content")
        self.assertEqual(request.content, "Test content")
        self.assertIsNone(request.webhook_url)

    def test_report_push_request(self):
        """测试报告推送请求模型"""
        from api.models import ReportPushRequest
        
        request = ReportPushRequest(title="Test Title", content="Test Content")
        self.assertEqual(request.title, "Test Title")
        self.assertEqual(request.content, "Test Content")

    def test_analysis_request(self):
        """测试分析请求模型"""
        from api.models import AnalysisRequest
        
        request = AnalysisRequest(company_name="测试公司")
        self.assertEqual(request.company_name, "测试公司")
        self.assertIsNone(request.competitors)
        self.assertIsNone(request.news)


class TestApiRoutes(unittest.TestCase):
    """测试 API 路由"""

    @classmethod
    def setUpClass(cls):
        """设置测试客户端"""
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_root_endpoint(self):
        """测试根路由"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "TrendRadar API")
        # endpoints 不再是必须的，因为现在返回的是欢迎信息或 API 状态
        # self.assertIn("endpoints", data)

    def test_status_endpoint(self):
        """测试状态端点"""
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "running")
        self.assertIn("timestamp", data)
        # cache 字段已移除，现在在 endpoints 中
        # self.assertIn("cache", data)

    def test_cache_status_endpoint(self):
        """测试缓存状态端点"""
        response = self.client.get("/api/cache/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("backend", data)
        self.assertIn("keys", data)

    def test_data_sources_endpoint(self):
        """测试数据源端点"""
        response = self.client.get("/api/data/sources")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("sources", data)
        self.assertIn("cascade", data)

    def test_get_data_no_cache(self):
        """测试获取数据（无缓存）"""
        response = self.client.get("/api/data")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("data", data)
        self.assertIn("source", data)

    def test_get_commodity_news_no_cache(self):
        """测试获取商品新闻（无缓存）"""
        response = self.client.get("/api/commodity-news")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("data", data)

    def test_get_news_by_category(self):
        """测试按分类获取新闻"""
        response = self.client.get("/api/news/tech")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["category"], "tech")

    def test_get_supply_chain_news(self):
        """测试获取供应链新闻"""
        response = self.client.get("/api/news/supply-chain")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

    def test_get_tariff_news(self):
        """测试获取关税新闻"""
        response = self.client.get("/api/news/tariff")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")

    def test_list_reports(self):
        """测试获取报告列表"""
        response = self.client.get("/api/reports")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("reports", data)
        self.assertIn("total", data)

    def test_download_report_not_found(self):
        """测试下载不存在的报告"""
        response = self.client.get("/api/reports/nonexistent.md")
        self.assertEqual(response.status_code, 404)

    def test_download_report_invalid_filename(self):
        """测试非法文件名"""
        # 包含 .. 的路径应该返回 400 或 404
        response = self.client.get("/api/reports/..%2Fetc%2Fpasswd")
        self.assertIn(response.status_code, [400, 404])

    def test_price_history_endpoint(self):
        """测试价格历史端点"""
        response = self.client.get("/api/price-history")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status", data)
        self.assertIn("data", data)

    def test_delete_cache_key(self):
        """测试删除缓存键"""
        response = self.client.delete("/api/cache/test_key")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")


class TestAnalysisHelpers(unittest.TestCase):
    """测试分析模块辅助函数"""

    def test_get_ai_config(self):
        """测试获取 AI 配置"""
        from api.routes.analysis import get_ai_config
        
        with patch('api.routes.analysis.load_config') as mock_config:
            mock_config.return_value = {
                "ai": {
                    "internal": {
                        "api_key": "internal_key",
                        "api_base": "http://internal.api",
                        "model": "internal_model"
                    },
                    "external": {
                        "api_key": "external_key",
                        "api_base": "http://external.api",
                        "model": "external_model"
                    }
                }
            }
            
            config = get_ai_config()
            
            self.assertEqual(config["internal"]["api_key"], "internal_key")
            self.assertEqual(config["external"]["api_key"], "external_key")

    def test_call_ai_api(self):
        """测试调用 AI API"""
        from api.routes.analysis import call_ai_api
        
        with patch('api.routes.analysis.req.post') as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Test response"}}]
            }
            mock_post.return_value = mock_response
            
            response = call_ai_api(
                "http://test.api",
                "test_key",
                "test_model",
                "system prompt",
                "user prompt",
                timeout=30
            )
            
            self.assertEqual(response.status_code, 200)
            mock_post.assert_called_once()

    @patch('api.routes.analysis.req.get')
    def test_fetch_realtime_news(self, mock_get):
        """测试实时抓取新闻"""
        from api.routes.analysis import fetch_realtime_news
        
        # Mock 所有请求都失败
        mock_get.side_effect = Exception("Network error")
        
        keywords = ["AI", "供应链"]
        news = fetch_realtime_news(keywords)
        
        # 应该返回空列表
        self.assertIsInstance(news, list)


class TestCrawlEndpoint(unittest.TestCase):
    """测试爬取端点"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_trigger_crawl_endpoint_exists(self):
        """测试爬取端点存在"""
        # 发送请求并检查端点存在（不一定成功，但不应该是 404）
        response = self.client.post("/api/crawl", json={"category": "test"})
        # 应该返回 200 或 500（爬取失败），但不是 404
        self.assertNotEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()
