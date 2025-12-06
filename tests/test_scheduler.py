# coding=utf-8
"""
测试后台调度器

验证：
1. 调度器初始化
2. 预热缓存功能
3. 定时任务启停
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestBackgroundScheduler(unittest.TestCase):
    """测试后台调度器"""

    def test_scheduler_import(self):
        """测试调度器导入"""
        from api.scheduler import scheduler, BackgroundScheduler
        
        self.assertIsInstance(scheduler, BackgroundScheduler)

    def test_scheduler_init(self):
        """测试调度器初始化"""
        from api.scheduler import BackgroundScheduler
        
        s = BackgroundScheduler()
        self.assertFalse(s._running)
        self.assertIsNotNone(s._executor)

    def test_scheduler_warmup_cache(self):
        """测试预热缓存"""
        from api.scheduler import BackgroundScheduler
        
        s = BackgroundScheduler()
        # 预热应该不抛出异常
        try:
            s.warmup_cache()
        except Exception as e:
            self.fail(f"warmup_cache raised exception: {e}")

    def test_scheduler_start_stop(self):
        """测试调度器启停"""
        from api.scheduler import BackgroundScheduler
        
        s = BackgroundScheduler()
        
        # 启动
        s.start_scheduled_tasks()
        self.assertTrue(s._running)
        
        # 重复启动应该无效
        s.start_scheduled_tasks()
        self.assertTrue(s._running)
        
        # 停止
        s.stop()
        self.assertFalse(s._running)


class TestSchedulerIntegration(unittest.TestCase):
    """测试调度器与服务集成"""

    @classmethod
    def setUpClass(cls):
        from fastapi.testclient import TestClient
        from server import app
        cls.client = TestClient(app)

    def test_server_starts_with_scheduler(self):
        """测试服务启动时集成调度器"""
        # 服务启动后应该能正常响应
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_cache_prewarmed(self):
        """测试缓存预热后有数据"""
        import time
        # 等待预热任务完成
        time.sleep(2)
        
        # 检查缓存状态
        response = self.client.get("/api/cache/status")
        self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    unittest.main()
