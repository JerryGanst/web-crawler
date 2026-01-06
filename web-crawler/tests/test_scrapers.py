# coding=utf-8
"""
Scrapers 模块测试
测试 scrapers/ 目录下的爬虫类
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestBaseScraper(unittest.TestCase):
    """测试基础爬虫类"""

    def test_init(self):
        """测试初始化"""
        from scrapers.base import ConfigDrivenScraper
        
        config = {
            "urls": ["http://test.com/api"],
            "display_name": "测试爬虫"
        }
        scraper = ConfigDrivenScraper("test_scraper", config)
        
        self.assertEqual(scraper.name, "test_scraper")
        self.assertEqual(scraper.urls, ["http://test.com/api"])

    def test_init_single_url(self):
        """测试单个 URL 初始化"""
        from scrapers.base import ConfigDrivenScraper
        
        config = {
            "urls": "http://test.com/api",  # 字符串而非列表
        }
        scraper = ConfigDrivenScraper("test_scraper", config)
        
        self.assertEqual(scraper.urls, ["http://test.com/api"])

    def test_setup_session(self):
        """测试会话配置"""
        from scrapers.base import ConfigDrivenScraper
        
        config = {
            "headers": {"Custom-Header": "test-value"}
        }
        scraper = ConfigDrivenScraper("test_scraper", config)
        
        self.assertIn("User-Agent", scraper.session.headers)

    @patch('scrapers.base.requests.Session.get')
    def test_fetch_success(self, mock_get):
        """测试成功请求"""
        from scrapers.base import ConfigDrivenScraper
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        scraper = ConfigDrivenScraper("test", {"max_retries": 1})
        result = scraper.fetch("http://test.com")
        
        self.assertIsNotNone(result)

    @patch('scrapers.base.requests.Session.get')
    def test_fetch_failure_retry(self, mock_get):
        """测试请求失败重试"""
        from scrapers.base import ConfigDrivenScraper
        
        mock_get.side_effect = Exception("Network error")
        
        scraper = ConfigDrivenScraper("test", {"max_retries": 2, "timeout": 1})
        result = scraper.fetch("http://test.com")
        
        self.assertIsNone(result)
        self.assertEqual(mock_get.call_count, 2)

    def test_parse_json(self):
        """测试 JSON 解析"""
        from scrapers.base import ConfigDrivenScraper
        
        scraper = ConfigDrivenScraper("test", {})
        
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": "test"}
        
        result = scraper.parse_json(mock_response)
        self.assertEqual(result, {"data": "test"})

    def test_parse_json_failure(self):
        """测试 JSON 解析失败"""
        from scrapers.base import ConfigDrivenScraper
        
        scraper = ConfigDrivenScraper("test", {})
        
        mock_response = MagicMock()
        mock_response.json.side_effect = Exception("Invalid JSON")
        
        result = scraper.parse_json(mock_response)
        self.assertIsNone(result)

    def test_standardize_item(self):
        """测试数据项标准化"""
        from scrapers.base import ConfigDrivenScraper
        
        config = {
            "display_name": "测试平台",
            "category": "finance"
        }
        scraper = ConfigDrivenScraper("test_scraper", config)
        
        item = {
            "title": "测试标题",
            "url": "http://test.com/news/1",
            "rank": 5
        }
        
        result = scraper.standardize_item(item)
        
        self.assertEqual(result["title"], "测试标题")
        self.assertEqual(result["url"], "http://test.com/news/1")
        self.assertEqual(result["platform"], "test_scraper")
        self.assertEqual(result["platform_name"], "测试平台")
        self.assertEqual(result["category"], "finance")
        self.assertEqual(result["rank"], 5)
        self.assertIn("timestamp", result)

    @patch('scrapers.base.ConfigDrivenScraper.fetch')
    def test_scrape_json(self, mock_fetch):
        """测试 JSON 爬取"""
        from scrapers.base import ConfigDrivenScraper
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {"title": "新闻1", "link": "http://news1.com"},
                {"title": "新闻2", "link": "http://news2.com"}
            ]
        }
        mock_fetch.return_value = mock_response
        
        config = {
            "urls": ["http://test.com/api"],
            "parser": "json",
            "json_path": "items",
            "field_mapping": {
                "url": "link"
            }
        }
        scraper = ConfigDrivenScraper("test", config)
        result = scraper.scrape()
        
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["title"], "新闻1")

    @patch('scrapers.base.ConfigDrivenScraper.fetch')
    def test_scrape_empty_response(self, mock_fetch):
        """测试空响应"""
        from scrapers.base import ConfigDrivenScraper
        
        mock_fetch.return_value = None
        
        config = {"urls": ["http://test.com/api"]}
        scraper = ConfigDrivenScraper("test", config)
        result = scraper.scrape()
        
        self.assertEqual(result, [])

    @patch('scrapers.base.ConfigDrivenScraper.fetch')
    def test_scrape_html(self, mock_fetch):
        """测试 HTML 爬取"""
        from scrapers.base import ConfigDrivenScraper
        
        mock_response = MagicMock()
        mock_response.text = """
        <html>
            <div class="news-item">
                <h2 class="title">新闻标题</h2>
            </div>
        </html>
        """
        mock_fetch.return_value = mock_response
        
        config = {
            "urls": ["http://test.com"],
            "parser": "html",
            "extraction": {
                "container": ".news-item",
                "fields": {
                    "title": {"selector": ".title"}
                }
            }
        }
        scraper = ConfigDrivenScraper("test", config)
        result = scraper.scrape()
        
        self.assertIsInstance(result, list)


class TestUnifiedDataSource(unittest.TestCase):
    """测试统一数据源"""

    @patch('scrapers.unified.yaml.safe_load')
    @patch('builtins.open')
    def test_init(self, mock_open, mock_yaml):
        """测试初始化"""
        mock_yaml.return_value = {
            "platforms": [],
            "categories": {}
        }
        
        from scrapers.unified import UnifiedDataSource
        
        source = UnifiedDataSource()
        self.assertIsNotNone(source.config)

    @patch('scrapers.unified.yaml.safe_load')
    @patch('builtins.open')
    def test_get_categories(self, mock_open, mock_yaml):
        """测试获取分类"""
        mock_yaml.return_value = {
            "platforms": [],
            "categories": {
                "finance": {"name": "财经"},
                "tech": {"name": "科技"}
            }
        }
        
        from scrapers.unified import UnifiedDataSource
        
        source = UnifiedDataSource()
        categories = source.get_categories()
        
        self.assertIn("finance", categories)
        self.assertIn("tech", categories)

    @patch('scrapers.unified.yaml.safe_load')
    @patch('builtins.open')
    def test_get_platforms_by_category(self, mock_open, mock_yaml):
        """测试按分类获取平台"""
        mock_yaml.return_value = {
            "platforms": [
                {"id": "p1", "name": "平台1", "category": "finance"},
                {"id": "p2", "name": "平台2", "category": "tech"},
                {"id": "p3", "name": "平台3", "category": "finance"}
            ],
            "categories": {}
        }
        
        from scrapers.unified import UnifiedDataSource
        
        source = UnifiedDataSource()
        
        finance_platforms = source.get_platforms_by_category("finance")
        self.assertEqual(len(finance_platforms), 2)
        
        all_platforms = source.get_platforms_by_category("all")
        self.assertEqual(len(all_platforms), 3)

    @patch('scrapers.unified.requests.get')
    @patch('scrapers.unified.yaml.safe_load')
    @patch('builtins.open')
    def test_crawl_newsnow_success(self, mock_open, mock_yaml, mock_get):
        """测试 newsnow 爬取成功"""
        mock_yaml.return_value = {"platforms": [], "categories": {}}
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "success",
            "items": [
                {"title": "新闻1", "url": "http://news1.com"}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        from scrapers.unified import UnifiedDataSource
        
        source = UnifiedDataSource()
        result = source.crawl_newsnow("test_platform")
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "新闻1")

    @patch('scrapers.unified.requests.get')
    @patch('scrapers.unified.yaml.safe_load')
    @patch('builtins.open')
    def test_crawl_newsnow_failure(self, mock_open, mock_yaml, mock_get):
        """测试 newsnow 爬取失败"""
        mock_yaml.return_value = {"platforms": [], "categories": {}}
        mock_get.side_effect = Exception("Network error")
        
        from scrapers.unified import UnifiedDataSource
        
        source = UnifiedDataSource()
        result = source.crawl_newsnow("test_platform")
        
        self.assertEqual(result, [])

    @patch('scrapers.unified.requests.post')
    @patch('scrapers.unified.yaml.safe_load')
    @patch('builtins.open')
    def test_push_to_wework_no_webhook(self, mock_open, mock_yaml, mock_post):
        """测试无 webhook 推送"""
        mock_yaml.return_value = {"platforms": [], "categories": {}}
        
        from scrapers.unified import UnifiedDataSource
        
        source = UnifiedDataSource()
        # 应该不会抛出异常
        source.push_to_wework([{"title": "test"}], "finance", None)
        
        mock_post.assert_not_called()

    @patch('scrapers.unified.requests.post')
    @patch('scrapers.unified.yaml.safe_load')
    @patch('builtins.open')
    def test_push_to_wework_empty_data(self, mock_open, mock_yaml, mock_post):
        """测试空数据推送"""
        mock_yaml.return_value = {"platforms": [], "categories": {}}
        
        from scrapers.unified import UnifiedDataSource
        
        source = UnifiedDataSource()
        source.push_to_wework([], "finance", "http://webhook.com")
        
        mock_post.assert_not_called()


class TestScraperFactory(unittest.TestCase):
    """测试爬虫工厂"""

    def test_create_registered_scraper(self):
        """测试创建已注册的爬虫"""
        from scrapers.factory import ScraperFactory
        
        # 注册一个测试爬虫
        class TestScraper:
            def __init__(self, name, config):
                self.name = name
                self.config = config
            
            def scrape(self):
                return []
        
        ScraperFactory.register("test_custom_scraper", TestScraper)
        scraper = ScraperFactory.create("test_custom_scraper", {})
        
        self.assertIsNotNone(scraper)
        self.assertIsInstance(scraper, TestScraper)

    def test_create_fallback_scraper(self):
        """测试创建回退爬虫"""
        from scrapers.factory import ScraperFactory
        from scrapers.base import ConfigDrivenScraper
        
        # 未注册的爬虫会返回 ConfigDrivenScraper
        scraper = ScraperFactory.create("unknown_scraper", {})
        self.assertIsInstance(scraper, ConfigDrivenScraper)


class TestFinanceScrapers(unittest.TestCase):
    """测试财经爬虫"""

    @patch('scrapers.finance.requests.get')
    def test_sina_forex_scraper(self, mock_get):
        """测试新浪外汇爬虫"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "data": {
                    "usdcny": "7.25",
                    "eurcny": "7.90"
                }
            }
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        from scrapers.finance import SinaForexScraper
        
        scraper = SinaForexScraper({})
        result = scraper.scrape()
        
        self.assertIsInstance(result, list)

    @patch('scrapers.finance.requests.get')
    def test_coingecko_scraper(self, mock_get):
        """测试 CoinGecko 爬虫"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "bitcoin",
                "symbol": "btc",
                "name": "Bitcoin",
                "current_price": 100000,
                "price_change_percentage_24h": 2.5
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        from scrapers.finance import CoinGeckoScraper
        
        scraper = CoinGeckoScraper({})
        result = scraper.scrape()
        
        self.assertIsInstance(result, list)


class TestCommodityScraper(unittest.TestCase):
    """测试大宗商品爬虫"""

    @patch('scrapers.commodity.requests.get')
    def test_commodity_scraper_init(self, mock_get):
        """测试大宗商品爬虫初始化"""
        from scrapers.commodity import CommodityScraper
        
        scraper = CommodityScraper()
        self.assertIsNotNone(scraper)

    @patch('scrapers.commodity.requests.get')
    def test_commodity_scrape(self, mock_get):
        """测试大宗商品爬取"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": []
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        from scrapers.commodity import CommodityScraper
        
        scraper = CommodityScraper()
        result = scraper.scrape()
        
        self.assertIsInstance(result, list)


class TestSMMScraper(unittest.TestCase):
    """测试上海有色网爬虫"""

    def test_smm_scraper_init(self):
        """测试 SMM 爬虫初始化"""
        from scrapers.smm import SMMScraper
        
        scraper = SMMScraper()
        self.assertIsNotNone(scraper)
        self.assertEqual(scraper.name, "smm_news")

    @patch('scrapers.smm.requests.get')
    def test_smm_scrape(self, mock_get):
        """测试 SMM 爬取"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><div class='news'></div></body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        from scrapers.smm import SMMScraper
        
        scraper = SMMScraper()
        result = scraper.scrape()
        
        self.assertIsInstance(result, list)


if __name__ == '__main__':
    unittest.main()
