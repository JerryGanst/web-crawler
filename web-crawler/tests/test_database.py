# coding=utf-8
"""
数据库模块测试
"""

import unittest
import tempfile
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDatabaseConnection(unittest.TestCase):
    """测试数据库连接"""
    
    def setUp(self):
        """创建临时数据库"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        os.environ["DB_PATH"] = self.db_path
        
        # 重置单例
        from database.connection import DatabaseManager
        DatabaseManager._instance = None
    
    def tearDown(self):
        """清理临时文件"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if "DB_PATH" in os.environ:
            del os.environ["DB_PATH"]
    
    def test_database_initialization(self):
        """测试数据库初始化"""
        from database.connection import get_db
        
        db = get_db(self.db_path)
        self.assertTrue(Path(self.db_path).exists())
        
        # 检查健康状态
        health = db.health_check()
        self.assertEqual(health["status"], "healthy")
        self.assertIn("news", health["tables"])
        self.assertIn("platforms", health["tables"])
    
    def test_execute_query(self):
        """测试执行查询"""
        from database.connection import get_db
        
        db = get_db(self.db_path)
        
        # 插入测试数据
        db.execute(
            "INSERT INTO platforms (id, name) VALUES (?, ?)",
            ("test_platform", "测试平台")
        )
        
        # 查询数据
        row = db.fetch_one(
            "SELECT * FROM platforms WHERE id = ?",
            ("test_platform",)
        )
        
        self.assertIsNotNone(row)
        self.assertEqual(row["name"], "测试平台")


class TestNewsRepository(unittest.TestCase):
    """测试新闻数据仓库"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        os.environ["DB_PATH"] = self.db_path
        
        from database.connection import DatabaseManager
        DatabaseManager._instance = None
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if "DB_PATH" in os.environ:
            del os.environ["DB_PATH"]
    
    def test_insert_news(self):
        """测试插入新闻"""
        from database.connection import get_db
        from database.models import News, Platform
        from database.repositories.news_repo import NewsRepository
        from database.repositories.platform_repo import PlatformRepository
        
        db = get_db(self.db_path)
        
        # 先插入平台
        platform_repo = PlatformRepository(db)
        platform = Platform(id="zhihu", name="知乎", category="social")
        platform_repo.insert(platform)
        
        # 插入新闻
        news_repo = NewsRepository(db)
        news = News(
            platform_id="zhihu",
            title="测试新闻标题",
            url="http://example.com",
            current_rank=1,
            ranks_history=[1],
            category="social"
        )
        
        news_id = news_repo.insert(news)
        self.assertIsNotNone(news_id)
        self.assertGreater(news_id, 0)
        
        # 查询验证
        saved_news = news_repo.find_by_id(news_id)
        self.assertIsNotNone(saved_news)
        self.assertEqual(saved_news.title, "测试新闻标题")
        self.assertEqual(saved_news.platform_id, "zhihu")
    
    def test_insert_or_update(self):
        """测试插入或更新"""
        from database.connection import get_db
        from database.models import News, Platform
        from database.repositories.news_repo import NewsRepository
        from database.repositories.platform_repo import PlatformRepository
        
        db = get_db(self.db_path)
        
        platform_repo = PlatformRepository(db)
        platform_repo.insert(Platform(id="weibo", name="微博"))
        
        news_repo = NewsRepository(db)
        news = News(
            platform_id="weibo",
            title="重复测试新闻",
            current_rank=5
        )
        
        # 第一次插入
        news_id1, is_new1 = news_repo.insert_or_update(news)
        self.assertTrue(is_new1)
        
        # 第二次应该更新
        news.current_rank = 3
        news_id2, is_new2 = news_repo.insert_or_update(news)
        self.assertFalse(is_new2)
        self.assertEqual(news_id1, news_id2)
    
    def test_find_by_date(self):
        """测试按日期查询"""
        from database.connection import get_db
        from database.models import News, Platform
        from database.repositories.news_repo import NewsRepository
        from database.repositories.platform_repo import PlatformRepository
        
        db = get_db(self.db_path)
        
        platform_repo = PlatformRepository(db)
        platform_repo.insert(Platform(id="toutiao", name="头条"))
        
        news_repo = NewsRepository(db)
        today = datetime.now().strftime("%Y-%m-%d")
        
        # 插入多条新闻
        for i in range(5):
            news = News(
                platform_id="toutiao",
                title=f"测试新闻 {i}",
                current_rank=i + 1,
                crawl_date=today
            )
            news_repo.insert(news)
        
        # 查询今日新闻
        results = news_repo.find_by_date(today, platform_id="toutiao")
        self.assertEqual(len(results), 5)


class TestPlatformRepository(unittest.TestCase):
    """测试平台配置仓库"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        os.environ["DB_PATH"] = self.db_path
        
        from database.connection import DatabaseManager
        DatabaseManager._instance = None
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_sync_from_config(self):
        """测试从配置同步平台"""
        from database.connection import get_db
        from database.repositories.platform_repo import PlatformRepository
        
        db = get_db(self.db_path)
        repo = PlatformRepository(db)
        
        config = [
            {"id": "zhihu", "name": "知乎", "category": "social"},
            {"id": "weibo", "name": "微博", "category": "social"},
            {"id": "toutiao", "name": "头条", "category": "news"},
        ]
        
        count = repo.sync_from_config(config)
        self.assertEqual(count, 3)
        
        # 验证
        platforms = repo.find_all()
        self.assertEqual(len(platforms), 3)


class TestCacheManager(unittest.TestCase):
    """测试缓存管理器"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        os.environ["DB_PATH"] = self.db_path
        
        from database.connection import DatabaseManager
        DatabaseManager._instance = None
        
        from database import cache
        cache._cache_manager = None
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_sqlite_cache(self):
        """测试 SQLite 缓存"""
        from database.cache import get_cache
        
        cache = get_cache(use_redis=False)
        
        # 设置缓存
        result = cache.set("test_key", {"data": "test_value"}, ttl_seconds=3600)
        self.assertTrue(result)
        
        # 获取缓存
        value = cache.get("test_key")
        self.assertIsNotNone(value)
        self.assertEqual(value["data"], "test_value")
        
        # 检查存在
        self.assertTrue(cache.exists("test_key"))
        
        # 删除缓存
        cache.delete("test_key")
        self.assertFalse(cache.exists("test_key"))


class TestLogRepositories(unittest.TestCase):
    """测试日志仓库"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        os.environ["DB_PATH"] = self.db_path
        
        from database.connection import DatabaseManager
        DatabaseManager._instance = None
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_crawl_log(self):
        """测试爬取日志"""
        from database.connection import get_db
        from database.repositories.log_repo import CrawlLogRepository
        
        db = get_db(self.db_path)
        repo = CrawlLogRepository(db)
        
        # 创建任务
        log = repo.create_task()
        log.status = "running"
        log.platforms_crawled = ["zhihu", "weibo"]
        
        # 插入日志
        log_id = repo.insert(log)
        self.assertGreater(log_id, 0)
        
        # 更新状态
        repo.update_status(log.task_id, "success", total_news=100, new_news=20)
        
        # 查询验证
        saved_log = repo.find_by_task_id(log.task_id)
        self.assertEqual(saved_log.status, "success")
        self.assertEqual(saved_log.total_news, 100)
    
    def test_push_record(self):
        """测试推送记录"""
        from database.connection import get_db
        from database.models import PushRecord
        from database.repositories.log_repo import PushRecordRepository
        
        db = get_db(self.db_path)
        repo = PushRecordRepository(db)
        
        # 创建推送记录
        record = PushRecord(
            channel="feishu",
            status="success",
            report_type="当日汇总",
            news_count=50
        )
        
        record_id = repo.insert(record)
        self.assertGreater(record_id, 0)
        
        # 检查今日是否已推送
        has_pushed = repo.has_pushed_today("feishu")
        self.assertTrue(has_pushed)


if __name__ == '__main__':
    unittest.main()
