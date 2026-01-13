# coding=utf-8
"""
RSS 功能集成测试

测试 TrendRadar v4.0+ RSS 功能融合。
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestRSSModels:
    """RSS 数据模型测试"""

    def test_rss_feed_creation(self):
        """测试 RSSFeed 模型创建"""
        from database.models import RSSFeed

        feed = RSSFeed(
            id="36kr-rss",
            name="36氪",
            url="https://36kr.com/feed",
            category="tech",
            enabled=True,
            max_items=30
        )

        assert feed.id == "36kr-rss"
        assert feed.name == "36氪"
        assert feed.url == "https://36kr.com/feed"
        assert feed.category == "tech"
        assert feed.enabled is True
        assert feed.max_items == 30
        assert feed.created_at is not None

    def test_rss_feed_from_config(self):
        """测试从配置创建 RSSFeed"""
        from database.models import RSSFeed

        config = {
            "id": "huxiu-rss",
            "name": "虎嗅",
            "url": "https://www.huxiu.com/rss/0.xml",
            "category": "tech",
            "enabled": True,
            "max_items": 20
        }

        feed = RSSFeed.from_config(config)

        assert feed.id == "huxiu-rss"
        assert feed.name == "虎嗅"
        assert feed.category == "tech"

    def test_rss_item_creation(self):
        """测试 RSSItem 模型创建"""
        from database.models import RSSItem

        item = RSSItem(
            feed_id="36kr-rss",
            title="OpenAI 发布 GPT-5",
            url="https://36kr.com/p/123456",
            summary="OpenAI 发布了最新的 GPT-5 模型...",
            author="张三",
            published_at=datetime.now(),
            feed_name="36氪",
            category="tech",
            tags=["AI", "GPT"]
        )

        assert item.feed_id == "36kr-rss"
        assert item.title == "OpenAI 发布 GPT-5"
        assert item.author == "张三"
        assert len(item.tags) == 2
        assert item.crawl_date == datetime.now().strftime("%Y-%m-%d")

    def test_rss_item_title_hash(self):
        """测试标题哈希生成"""
        from database.models import RSSItem

        item = RSSItem(
            feed_id="test",
            title="测试标题"
        )

        assert item.title_hash is not None
        assert len(item.title_hash) == 32  # MD5 hash length

    def test_rss_item_to_dict(self):
        """测试 RSSItem 转字典"""
        from database.models import RSSItem

        item = RSSItem(
            feed_id="test",
            title="测试标题",
            url="https://example.com",
            summary="摘要内容"
        )

        data = item.to_dict()

        assert isinstance(data, dict)
        assert data["feed_id"] == "test"
        assert data["title"] == "测试标题"


class TestDateTools:
    """日期解析工具测试"""

    def test_resolve_today(self):
        """测试解析 '今天'"""
        from mcp_server.tools.date_tools import DateTools

        tools = DateTools()
        result = tools.resolve_date_range("今天")

        assert result["success"] is True
        assert result["start"] == datetime.now().strftime("%Y-%m-%d")
        assert result["end"] == datetime.now().strftime("%Y-%m-%d")

    def test_resolve_yesterday(self):
        """测试解析 '昨天'"""
        from mcp_server.tools.date_tools import DateTools

        tools = DateTools()
        result = tools.resolve_date_range("昨天")

        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        assert result["success"] is True
        assert result["start"] == yesterday
        assert result["end"] == yesterday

    def test_resolve_last_7_days(self):
        """测试解析 '最近7天'"""
        from mcp_server.tools.date_tools import DateTools

        tools = DateTools()
        result = tools.resolve_date_range("最近7天")

        today = datetime.now().date()
        start = (today - timedelta(days=6)).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")

        assert result["success"] is True
        assert result["start"] == start
        assert result["end"] == end
        assert result["total_days"] == 7

    def test_resolve_this_week(self):
        """测试解析 '本周'"""
        from mcp_server.tools.date_tools import DateTools

        tools = DateTools()
        result = tools.resolve_date_range("本周")

        assert result["success"] is True
        assert result["description"] == "本周"

    def test_resolve_this_month(self):
        """测试解析 '本月'"""
        from mcp_server.tools.date_tools import DateTools

        tools = DateTools()
        result = tools.resolve_date_range("本月")

        today = datetime.now().date()
        first_of_month = today.replace(day=1).strftime("%Y-%m-%d")

        assert result["success"] is True
        assert result["start"] == first_of_month

    def test_resolve_standard_date(self):
        """测试解析标准日期格式"""
        from mcp_server.tools.date_tools import DateTools

        tools = DateTools()
        result = tools.resolve_date_range("2025-01-15")

        assert result["success"] is True
        assert result["start"] == "2025-01-15"
        assert result["end"] == "2025-01-15"

    def test_resolve_chinese_number(self):
        """测试中文数字解析"""
        from mcp_server.tools.date_tools import DateTools

        tools = DateTools()
        result = tools.resolve_date_range("最近三天")

        assert result["success"] is True
        assert result["total_days"] == 3

    def test_resolve_invalid_expression(self):
        """测试无效表达式"""
        from mcp_server.tools.date_tools import DateTools

        tools = DateTools()
        result = tools.resolve_date_range("随便什么")

        assert result["success"] is False
        assert "error" in result

    def test_get_preset_ranges(self):
        """测试获取预设日期范围"""
        from mcp_server.tools.date_tools import DateTools

        tools = DateTools()
        result = tools.get_preset_ranges()

        assert result["success"] is True
        assert "presets" in result
        assert "today" in result["presets"]
        assert "yesterday" in result["presets"]
        assert "last_7_days" in result["presets"]


class TestRSSFetcher:
    """RSS 爬虫测试"""

    def test_fetcher_initialization(self):
        """测试 RSS 爬虫初始化"""
        from scrapers.rss_scraper import RSSFetcher

        config = {
            "rss": {
                "enabled": True,
                "request_interval": 2,
                "default_max_items": 20,
                "feeds": [
                    {
                        "id": "test-feed",
                        "name": "测试源",
                        "url": "https://example.com/feed",
                        "enabled": True
                    }
                ]
            }
        }

        fetcher = RSSFetcher(config=config)

        assert fetcher.is_enabled() is True
        assert len(fetcher.feeds) == 1
        assert fetcher.feeds[0].id == "test-feed"

    def test_fetcher_disabled(self):
        """测试 RSS 功能禁用"""
        from scrapers.rss_scraper import RSSFetcher

        config = {
            "rss": {
                "enabled": False,
                "feeds": []
            }
        }

        fetcher = RSSFetcher(config=config)

        assert fetcher.is_enabled() is False

    def test_get_feed_info(self):
        """测试获取 RSS 源信息"""
        from scrapers.rss_scraper import RSSFetcher

        config = {
            "rss": {
                "enabled": True,
                "feeds": [
                    {
                        "id": "test1",
                        "name": "源1",
                        "url": "https://example1.com/feed",
                        "category": "tech",
                        "enabled": True
                    },
                    {
                        "id": "test2",
                        "name": "源2",
                        "url": "https://example2.com/feed",
                        "category": "finance",
                        "enabled": True
                    }
                ]
            }
        }

        fetcher = RSSFetcher(config=config)
        info = fetcher.get_feed_info()

        assert len(info) == 2
        assert info[0]["id"] == "test1"
        assert info[1]["category"] == "finance"


class TestRSSRepository:
    """RSS 仓库测试（Mock MongoDB）"""

    @pytest.fixture
    def mock_mongo_db(self):
        """创建 Mock MongoDB 数据库"""
        db = MagicMock()
        db["rss_items"] = MagicMock()
        db["rss_feeds"] = MagicMock()
        return db

    def test_save_rss_batch(self, mock_mongo_db):
        """测试批量保存 RSS 文章"""
        from database.repositories.rss_repo import MongoRSSRepository
        from database.models import RSSItem

        # 模拟 bulk_write 返回
        mock_result = MagicMock()
        mock_result.upserted_count = 2
        mock_result.modified_count = 0
        mock_mongo_db["rss_items"].bulk_write.return_value = mock_result

        repo = MongoRSSRepository(mock_mongo_db)

        items = [
            RSSItem(feed_id="test", title="文章1"),
            RSSItem(feed_id="test", title="文章2")
        ]

        inserted, updated = repo.save_rss_batch(items)

        assert inserted == 2
        assert updated == 0
        mock_mongo_db["rss_items"].bulk_write.assert_called_once()

    def test_get_latest_rss(self, mock_mongo_db):
        """测试获取最新 RSS"""
        from database.repositories.rss_repo import MongoRSSRepository

        # 模拟查询返回
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = [
            {
                "_id": "1",
                "feed_id": "test",
                "title": "文章1",
                "url": "https://example.com/1"
            }
        ]
        mock_mongo_db["rss_items"].find.return_value = mock_cursor

        repo = MongoRSSRepository(mock_mongo_db)
        items = repo.get_latest_rss(limit=10)

        assert len(items) == 1
        assert items[0].title == "文章1"

    def test_search_rss(self, mock_mongo_db):
        """测试搜索 RSS"""
        from database.repositories.rss_repo import MongoRSSRepository

        # 模拟查询返回
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = mock_cursor
        mock_cursor.limit.return_value = [
            {
                "_id": "1",
                "feed_id": "test",
                "title": "人工智能新突破",
                "summary": "AI 领域的最新进展..."
            }
        ]
        mock_mongo_db["rss_items"].find.return_value = mock_cursor

        repo = MongoRSSRepository(mock_mongo_db)
        items = repo.search_rss(keyword="人工智能", days=7)

        assert len(items) == 1
        assert "人工智能" in items[0].title

    def test_get_rss_count(self, mock_mongo_db):
        """测试获取 RSS 统计"""
        from database.repositories.rss_repo import MongoRSSRepository

        # 模拟聚合返回
        mock_mongo_db["rss_items"].aggregate.return_value = [
            {"_id": "feed1", "count": 10},
            {"_id": "feed2", "count": 5}
        ]

        repo = MongoRSSRepository(mock_mongo_db)
        stats = repo.get_rss_count(days=7)

        assert stats["total"] == 15
        assert stats["by_feed"]["feed1"] == 10
        assert stats["by_feed"]["feed2"] == 5


class TestDataQueryRSSTools:
    """数据查询工具 RSS 方法测试"""

    def test_get_latest_rss_no_repo(self):
        """测试 RSS 仓库不可用时的处理"""
        from mcp_server.tools.data_query import DataQueryTools

        tools = DataQueryTools()

        # Mock _get_rss_repository 返回 None
        with patch.object(tools, '_get_rss_repository', return_value=None):
            result = tools.get_latest_rss()

        assert result["success"] is False
        assert result["error"]["code"] == "RSS_NOT_CONFIGURED"

    def test_search_rss_no_repo(self):
        """测试 RSS 搜索仓库不可用时的处理"""
        from mcp_server.tools.data_query import DataQueryTools

        tools = DataQueryTools()

        with patch.object(tools, '_get_rss_repository', return_value=None):
            result = tools.search_rss(keyword="测试")

        assert result["success"] is False
        assert result["error"]["code"] == "RSS_NOT_CONFIGURED"


class TestAnalyticsNewTools:
    """新增分析工具测试"""

    def test_compare_periods_invalid_input(self):
        """测试时期对比无效输入"""
        from mcp_server.tools.analytics import AnalyticsTools

        tools = AnalyticsTools()

        # 无效的日期格式
        result = tools.compare_periods(
            period1={"start": "invalid", "end": "invalid"},
            period2={"start": "2025-01-08", "end": "2025-01-14"}
        )

        # 应该返回错误或空结果
        assert "error" in result or result.get("success") is False

    def test_aggregate_news_empty_result(self):
        """测试新闻聚合无数据情况"""
        from mcp_server.tools.analytics import AnalyticsTools

        tools = AnalyticsTools()

        # 使用一个不可能有数据的日期范围
        result = tools.aggregate_news(
            date_range={"start": "1990-01-01", "end": "1990-01-07"}
        )

        assert result.get("success") is True
        assert result.get("total", 0) == 0


class TestSearchAllTool:
    """联合搜索工具测试"""

    def test_search_all_hotlist_only(self):
        """测试仅搜索热搜"""
        from mcp_server.tools.search_tools import SearchTools

        tools = SearchTools()

        # Mock search_news_unified
        with patch.object(tools, 'search_news_unified') as mock_search:
            mock_search.return_value = {
                "success": True,
                "results": [{"title": "测试新闻"}],
                "summary": {"total_found": 1}
            }

            result = tools.search_all(
                query="测试",
                include_hotlist=True,
                include_rss=False
            )

        assert result["success"] is True
        assert result["total_hotlist"] == 1
        assert result["total_rss"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
