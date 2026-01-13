# coding=utf-8
"""
RSS 数据仓库 - MongoDB 实现

提供 RSS 文章数据的 CRUD 操作，基于 MongoDB 存储。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from pymongo import UpdateOne, DESCENDING
from pymongo.database import Database
from pymongo.errors import PyMongoError

from ..models import RSSItem, RSSFeed

logger = logging.getLogger(__name__)


class MongoRSSRepository:
    """MongoDB RSS 数据仓库"""

    # Collection 名称
    ITEMS_COLLECTION = "rss_items"
    FEEDS_COLLECTION = "rss_feeds"

    def __init__(self, mongo_db: Database):
        """
        初始化 RSS 仓库

        Args:
            mongo_db: MongoDB 数据库实例
        """
        self._db = mongo_db
        self._ensure_indexes()

    @property
    def _items_col(self):
        """RSS 文章 Collection"""
        return self._db[self.ITEMS_COLLECTION]

    @property
    def _feeds_col(self):
        """RSS 源 Collection"""
        return self._db[self.FEEDS_COLLECTION]

    def _ensure_indexes(self):
        """确保索引存在"""
        try:
            # RSS 文章索引
            self._items_col.create_index("feed_id")
            self._items_col.create_index("crawl_date")
            self._items_col.create_index("published_at")
            self._items_col.create_index([("feed_id", 1), ("title", 1)], unique=True)
            self._items_col.create_index(
                [("title", "text"), ("summary", "text")],
                default_language="none"  # 支持中文
            )

            # RSS 源索引
            self._feeds_col.create_index("id", unique=True)
            self._feeds_col.create_index("enabled")

            logger.debug("RSS 索引创建成功")
        except PyMongoError as e:
            logger.warning(f"创建 RSS 索引时出错: {e}")

    # ==================== RSS 文章操作 ====================

    def save_rss_batch(self, items: List[RSSItem]) -> Tuple[int, int]:
        """
        批量保存 RSS 文章（upsert 模式）

        Args:
            items: RSS 文章列表

        Returns:
            (新增数量, 更新数量)
        """
        if not items:
            return (0, 0)

        operations = []
        for item in items:
            doc = item.to_dict()
            # 移除 None 的 id 字段
            if 'id' in doc and doc['id'] is None:
                del doc['id']

            operations.append(
                UpdateOne(
                    {"feed_id": item.feed_id, "title": item.title},
                    {"$set": doc, "$setOnInsert": {"created_at": datetime.now()}},
                    upsert=True
                )
            )

        try:
            result = self._items_col.bulk_write(operations, ordered=False)
            inserted = result.upserted_count
            updated = result.modified_count
            logger.info(f"RSS 批量保存: 新增 {inserted}, 更新 {updated}")
            return (inserted, updated)
        except PyMongoError as e:
            logger.error(f"RSS 批量保存失败: {e}")
            return (0, 0)

    def get_latest_rss(
        self,
        feed_ids: Optional[List[str]] = None,
        limit: int = 50,
        include_summary: bool = True
    ) -> List[RSSItem]:
        """
        获取最新 RSS 文章

        Args:
            feed_ids: RSS 源 ID 列表，None 表示所有源
            limit: 返回条数限制
            include_summary: 是否包含摘要

        Returns:
            RSS 文章列表
        """
        query = {}
        if feed_ids:
            query["feed_id"] = {"$in": feed_ids}

        projection = None
        if not include_summary:
            projection = {"summary": 0}

        try:
            cursor = self._items_col.find(
                query, projection
            ).sort("crawled_at", DESCENDING).limit(limit)

            return [RSSItem.from_mongo_doc(doc) for doc in cursor]
        except PyMongoError as e:
            logger.error(f"获取最新 RSS 失败: {e}")
            return []

    def search_rss(
        self,
        keyword: str,
        days: int = 7,
        feed_ids: Optional[List[str]] = None,
        limit: int = 50
    ) -> List[RSSItem]:
        """
        按关键词搜索 RSS 文章

        Args:
            keyword: 搜索关键词
            days: 搜索最近 N 天
            feed_ids: RSS 源 ID 列表
            limit: 返回条数限制

        Returns:
            匹配的 RSS 文章列表
        """
        # 计算日期范围
        start_date = datetime.now() - timedelta(days=days)

        query = {
            "crawled_at": {"$gte": start_date},
            "$or": [
                {"title": {"$regex": keyword, "$options": "i"}},
                {"summary": {"$regex": keyword, "$options": "i"}}
            ]
        }

        if feed_ids:
            query["feed_id"] = {"$in": feed_ids}

        try:
            cursor = self._items_col.find(query).sort(
                "crawled_at", DESCENDING
            ).limit(limit)

            return [RSSItem.from_mongo_doc(doc) for doc in cursor]
        except PyMongoError as e:
            logger.error(f"搜索 RSS 失败: {e}")
            return []

    def get_rss_by_date(
        self,
        date: datetime,
        feed_ids: Optional[List[str]] = None,
        limit: int = 100
    ) -> List[RSSItem]:
        """
        获取指定日期的 RSS 文章

        Args:
            date: 目标日期
            feed_ids: RSS 源 ID 列表
            limit: 返回条数限制

        Returns:
            RSS 文章列表
        """
        crawl_date = date.strftime("%Y-%m-%d")
        query = {"crawl_date": crawl_date}

        if feed_ids:
            query["feed_id"] = {"$in": feed_ids}

        try:
            cursor = self._items_col.find(query).sort(
                "published_at", DESCENDING
            ).limit(limit)

            return [RSSItem.from_mongo_doc(doc) for doc in cursor]
        except PyMongoError as e:
            logger.error(f"获取指定日期 RSS 失败: {e}")
            return []

    def get_rss_count(
        self,
        feed_ids: Optional[List[str]] = None,
        days: int = 7
    ) -> Dict[str, int]:
        """
        获取 RSS 文章统计

        Args:
            feed_ids: RSS 源 ID 列表
            days: 统计最近 N 天

        Returns:
            统计字典 {"total": N, "by_feed": {...}}
        """
        start_date = datetime.now() - timedelta(days=days)

        match_stage = {"crawled_at": {"$gte": start_date}}
        if feed_ids:
            match_stage["feed_id"] = {"$in": feed_ids}

        try:
            # 按源统计
            pipeline = [
                {"$match": match_stage},
                {"$group": {"_id": "$feed_id", "count": {"$sum": 1}}},
            ]

            by_feed = {}
            total = 0
            for doc in self._items_col.aggregate(pipeline):
                by_feed[doc["_id"]] = doc["count"]
                total += doc["count"]

            return {"total": total, "by_feed": by_feed}
        except PyMongoError as e:
            logger.error(f"获取 RSS 统计失败: {e}")
            return {"total": 0, "by_feed": {}}

    def delete_old_rss(self, days: int = 30) -> int:
        """
        删除旧的 RSS 文章

        Args:
            days: 保留最近 N 天的数据

        Returns:
            删除的文章数量
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            result = self._items_col.delete_many(
                {"crawled_at": {"$lt": cutoff_date}}
            )
            deleted = result.deleted_count
            logger.info(f"清理旧 RSS 文章: 删除 {deleted} 条")
            return deleted
        except PyMongoError as e:
            logger.error(f"清理旧 RSS 失败: {e}")
            return 0

    # ==================== RSS 源操作 ====================

    def save_feed(self, feed: RSSFeed) -> bool:
        """
        保存 RSS 源配置

        Args:
            feed: RSS 源对象

        Returns:
            是否成功
        """
        try:
            self._feeds_col.update_one(
                {"id": feed.id},
                {"$set": feed.to_dict()},
                upsert=True
            )
            return True
        except PyMongoError as e:
            logger.error(f"保存 RSS 源失败: {e}")
            return False

    def get_feeds_status(self) -> List[Dict[str, Any]]:
        """
        获取所有 RSS 源状态

        Returns:
            RSS 源状态列表
        """
        try:
            feeds = list(self._feeds_col.find())

            result = []
            for feed in feeds:
                # 获取该源的文章统计
                count = self._items_col.count_documents({"feed_id": feed["id"]})

                # 获取最后抓取时间
                latest = self._items_col.find_one(
                    {"feed_id": feed["id"]},
                    sort=[("crawled_at", DESCENDING)]
                )

                result.append({
                    "id": feed["id"],
                    "name": feed.get("name", ""),
                    "url": feed.get("url", ""),
                    "category": feed.get("category", ""),
                    "enabled": feed.get("enabled", True),
                    "article_count": count,
                    "last_fetch_at": feed.get("last_fetch_at"),
                    "last_article_at": latest.get("crawled_at") if latest else None,
                    "error_count": feed.get("error_count", 0),
                    "last_error": feed.get("last_error", ""),
                })

            return result
        except PyMongoError as e:
            logger.error(f"获取 RSS 源状态失败: {e}")
            return []

    def update_feed_status(
        self,
        feed_id: str,
        success: bool,
        error_msg: str = ""
    ) -> bool:
        """
        更新 RSS 源抓取状态

        Args:
            feed_id: RSS 源 ID
            success: 是否成功
            error_msg: 错误信息

        Returns:
            是否更新成功
        """
        try:
            update = {
                "last_fetch_at": datetime.now(),
                "updated_at": datetime.now()
            }

            if success:
                update["error_count"] = 0
                update["last_error"] = ""
            else:
                update["last_error"] = error_msg
                # 累加错误次数
                self._feeds_col.update_one(
                    {"id": feed_id},
                    {"$inc": {"error_count": 1}, "$set": update}
                )
                return True

            self._feeds_col.update_one(
                {"id": feed_id},
                {"$set": update}
            )
            return True
        except PyMongoError as e:
            logger.error(f"更新 RSS 源状态失败: {e}")
            return False

    def get_enabled_feeds(self) -> List[RSSFeed]:
        """
        获取所有启用的 RSS 源

        Returns:
            启用的 RSS 源列表
        """
        try:
            feeds = self._feeds_col.find({"enabled": True})
            return [RSSFeed.from_config(doc) for doc in feeds]
        except PyMongoError as e:
            logger.error(f"获取启用的 RSS 源失败: {e}")
            return []
