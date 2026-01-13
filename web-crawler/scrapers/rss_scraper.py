# coding=utf-8
"""
RSS 爬虫模块

基于 feedparser 实现 RSS 订阅源抓取。
"""

import logging
import time
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml

try:
    import feedparser
except ImportError:
    feedparser = None

from database.models import RSSItem, RSSFeed

logger = logging.getLogger(__name__)


class RSSFetcher:
    """RSS 抓取器"""

    def __init__(self, config_path: Optional[str] = None, config: Optional[Dict] = None):
        """
        初始化 RSS 抓取器

        Args:
            config_path: RSS 配置文件路径
            config: 直接传入的配置字典（优先级高于 config_path）
        """
        if feedparser is None:
            raise ImportError(
                "feedparser 库未安装，请运行: pip install feedparser"
            )

        if config:
            self.config = config.get('rss', config)
        elif config_path:
            self.config = self._load_config(config_path)
        else:
            # 默认配置路径
            default_path = Path(__file__).parent.parent / "config" / "rss.yaml"
            self.config = self._load_config(str(default_path))

        self.feeds = self._load_feeds()
        self.request_interval = self.config.get('request_interval', 2)
        self.request_timeout = self.config.get('request_timeout', 30)
        self.max_retries = self.config.get('max_retries', 3)
        self.user_agent = self.config.get(
            'user_agent',
            "Mozilla/5.0 (compatible; TrendRadar/4.0; RSS Reader)"
        )
        self.default_max_items = self.config.get('default_max_items', 20)
        self.article_max_age_hours = self.config.get('article_max_age_hours', 72)

    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config.get('rss', {})
        except FileNotFoundError:
            logger.warning(f"RSS 配置文件不存在: {config_path}")
            return {'enabled': False, 'feeds': []}
        except yaml.YAMLError as e:
            logger.error(f"RSS 配置文件解析错误: {e}")
            return {'enabled': False, 'feeds': []}

    def _load_feeds(self) -> List[RSSFeed]:
        """加载 RSS 源列表"""
        feeds = []
        for feed_config in self.config.get('feeds', []):
            if feed_config.get('enabled', True) and feed_config.get('url'):
                feeds.append(RSSFeed.from_config(feed_config))
        return feeds

    def is_enabled(self) -> bool:
        """检查 RSS 功能是否启用"""
        return self.config.get('enabled', False)

    def fetch_feed(self, feed: RSSFeed) -> List[RSSItem]:
        """
        抓取单个 RSS 源

        Args:
            feed: RSS 源配置

        Returns:
            RSS 文章列表
        """
        items = []

        for attempt in range(self.max_retries):
            try:
                logger.info(f"抓取 RSS 源: {feed.name} ({feed.url})")

                # 设置 User-Agent
                feedparser.USER_AGENT = self.user_agent

                # 解析 RSS
                parsed = feedparser.parse(
                    feed.url,
                    agent=self.user_agent
                )

                # 检查解析状态
                if parsed.bozo and not parsed.entries:
                    logger.warning(
                        f"RSS 解析警告 ({feed.name}): {parsed.bozo_exception}"
                    )
                    if attempt < self.max_retries - 1:
                        time.sleep(self.request_interval)
                        continue
                    return []

                # 限制条目数量
                max_items = feed.max_items or self.default_max_items
                entries = parsed.entries[:max_items]

                # 转换为 RSSItem
                for entry in entries:
                    item = self._parse_entry(entry, feed)
                    if item:
                        items.append(item)

                logger.info(f"RSS 源 {feed.name} 抓取完成: {len(items)} 条")
                break

            except Exception as e:
                logger.error(f"抓取 RSS 源 {feed.name} 失败 (尝试 {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.request_interval)

        return items

    def _parse_entry(self, entry: Dict, feed: RSSFeed) -> Optional[RSSItem]:
        """
        解析 RSS 条目

        Args:
            entry: feedparser 条目
            feed: RSS 源配置

        Returns:
            RSSItem 或 None
        """
        try:
            # 获取标题
            title = entry.get('title', '').strip()
            if not title:
                return None

            # 获取链接
            url = entry.get('link', '') or entry.get('id', '')

            # 获取摘要（限制长度）
            summary = ''
            if entry.get('summary'):
                summary = entry.get('summary', '')[:500]
            elif entry.get('description'):
                summary = entry.get('description', '')[:500]

            # 获取作者
            author = entry.get('author', '') or entry.get('creator', '')

            # 获取发布时间
            published_at = self._parse_date(entry)

            # 检查文章是否过期
            if published_at and self.article_max_age_hours > 0:
                age_hours = (datetime.now() - published_at).total_seconds() / 3600
                if age_hours > self.article_max_age_hours:
                    return None

            # 获取标签
            tags = []
            if entry.get('tags'):
                tags = [tag.get('term', '') for tag in entry.get('tags', [])]

            return RSSItem(
                feed_id=feed.id,
                feed_name=feed.name,
                title=title,
                url=url,
                summary=summary,
                author=author,
                published_at=published_at,
                crawled_at=datetime.now(),
                crawl_date=datetime.now().strftime("%Y-%m-%d"),
                category=feed.category,
                tags=tags,
            )

        except Exception as e:
            logger.warning(f"解析 RSS 条目失败: {e}")
            return None

    def _parse_date(self, entry: Dict) -> Optional[datetime]:
        """
        解析发布日期

        Args:
            entry: feedparser 条目

        Returns:
            datetime 或 None
        """
        # 尝试多个日期字段
        date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']

        for field in date_fields:
            if entry.get(field):
                try:
                    time_tuple = entry.get(field)
                    return datetime(*time_tuple[:6])
                except:
                    pass

        # 尝试解析字符串日期
        date_str_fields = ['published', 'updated', 'created']
        for field in date_str_fields:
            if entry.get(field):
                try:
                    return parsedate_to_datetime(entry.get(field))
                except:
                    pass

        return None

    def fetch_all(self) -> Dict[str, Any]:
        """
        抓取所有启用的 RSS 源

        Returns:
            抓取结果字典 {
                "items": [...],
                "total": N,
                "success_feeds": [...],
                "failed_feeds": [...]
            }
        """
        if not self.is_enabled():
            logger.info("RSS 功能未启用")
            return {
                "items": [],
                "total": 0,
                "success_feeds": [],
                "failed_feeds": [],
                "enabled": False
            }

        all_items = []
        success_feeds = []
        failed_feeds = []

        for feed in self.feeds:
            try:
                items = self.fetch_feed(feed)

                if items:
                    all_items.extend(items)
                    success_feeds.append({
                        "id": feed.id,
                        "name": feed.name,
                        "count": len(items)
                    })
                else:
                    failed_feeds.append({
                        "id": feed.id,
                        "name": feed.name,
                        "error": "无法获取内容"
                    })

                # 请求间隔
                time.sleep(self.request_interval)

            except Exception as e:
                logger.error(f"抓取 RSS 源 {feed.name} 异常: {e}")
                failed_feeds.append({
                    "id": feed.id,
                    "name": feed.name,
                    "error": str(e)
                })

        logger.info(
            f"RSS 抓取完成: 成功 {len(success_feeds)} 个源, "
            f"失败 {len(failed_feeds)} 个源, 共 {len(all_items)} 条文章"
        )

        return {
            "items": all_items,
            "total": len(all_items),
            "success_feeds": success_feeds,
            "failed_feeds": failed_feeds,
            "enabled": True
        }

    def get_feed_info(self) -> List[Dict[str, Any]]:
        """
        获取所有配置的 RSS 源信息

        Returns:
            RSS 源信息列表
        """
        return [
            {
                "id": feed.id,
                "name": feed.name,
                "url": feed.url,
                "category": feed.category,
                "enabled": feed.enabled,
                "max_items": feed.max_items
            }
            for feed in self.feeds
        ]
