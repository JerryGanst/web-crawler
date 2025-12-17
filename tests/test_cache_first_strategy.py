# coding=utf-8
"""
测试缓存优先策略优化

验证：
1. refresh=false 时直接返回缓存（<50ms）
2. refresh=true 时立即返回缓存 + 后台异步刷新
3. 后台任务去重机制
"""

import unittest
from unittest.mock import patch, MagicMock
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCacheFirstStrategy(unittest.TestCase):
    """测试缓存优先策略"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_news_endpoint_returns_quickly(self):
        """测试新闻端点快速响应"""
        start = time.time()
        response = self.client.get("/api/news/finance")
        elapsed = time.time() - start
        
        self.assertEqual(response.status_code, 200)
        # 无缓存时也应该快速响应
        self.assertLess(elapsed, 1.0)  # 应该在1秒内响应

    def test_news_refresh_returns_immediately(self):
        """测试刷新请求立即返回"""
        start = time.time()
        response = self.client.get("/api/news/finance?refresh=true")
        elapsed = time.time() - start
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # 应该快速返回（不等待爬虫）
        self.assertLess(elapsed, 2.0)
        # 应该标记正在刷新
        self.assertIn("refreshing", data)

    def test_commodity_news_refresh(self):
        """测试大宗商品新闻刷新"""
        response = self.client.get("/api/commodity-news?refresh=true")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("refreshing", data)

    def test_supply_chain_news_refresh(self):
        """测试供应链新闻刷新"""
        response = self.client.get("/api/news/supply-chain?refresh=true")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("refreshing", data)

    def test_tariff_news_refresh(self):
        """测试关税新闻刷新"""
        response = self.client.get("/api/news/tariff?refresh=true")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("refreshing", data)

    def test_crawl_endpoint_async(self):
        """测试爬取端点异步执行"""
        start = time.time()
        response = self.client.post("/api/crawl", json={"category": "finance"})
        elapsed = time.time() - start
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # 应该立即返回
        self.assertLess(elapsed, 1.0)
        self.assertEqual(data["status"], "success")
        self.assertIn("triggered", data)

    def test_refresh_status_endpoint(self):
        """测试刷新状态端点"""
        response = self.client.get("/api/refresh-status")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("pending_tasks", data)
        self.assertIn("count", data)


class TestBackgroundRefreshDedup(unittest.TestCase):
    """测试后台刷新去重机制"""

    def test_trigger_background_refresh_dedup(self):
        """测试后台任务去重"""
        from api.routes.news import _trigger_background_refresh, _pending_refreshes
        
        # 清空 pending
        _pending_refreshes.clear()
        
        # 模拟任务函数
        mock_func = MagicMock()
        
        # 第一次触发应该成功
        result1 = _trigger_background_refresh("test:key", mock_func, "arg1")
        self.assertTrue(result1)
        self.assertIn("test:key", _pending_refreshes)
        
        # 第二次触发同一个 key 应该被跳过
        result2 = _trigger_background_refresh("test:key", mock_func, "arg1")
        self.assertFalse(result2)
        
        # 清理
        _pending_refreshes.discard("test:key")


class TestCacheReturnValues(unittest.TestCase):
    """测试缓存返回值格式"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_news_response_format(self):
        """测试新闻响应格式"""
        response = self.client.get("/api/news/finance")
        data = response.json()
        
        self.assertIn("status", data)
        self.assertIn("data", data)
        self.assertIn("cached", data)

    def test_news_refresh_response_format(self):
        """测试刷新响应格式"""
        response = self.client.get("/api/news/finance?refresh=true")
        data = response.json()
        
        self.assertIn("status", data)
        self.assertIn("refreshing", data)
        self.assertIn("message", data)


if __name__ == '__main__':
    unittest.main()
