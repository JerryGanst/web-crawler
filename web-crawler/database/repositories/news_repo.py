# coding=utf-8
"""
新闻数据仓库
提供新闻数据的 CRUD 操作
"""

import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple, Any

from ..connection import DatabaseManager, get_db
from ..models import News, KeywordMatch


class NewsRepository:
    """新闻数据仓库"""
    
    def __init__(self, db: DatabaseManager = None):
        self.db = db or get_db()
    
    def insert(self, news: News) -> int:
        """插入单条新闻"""
        sql = """
            INSERT INTO news (
                platform_id, title, title_hash, url, mobile_url,
                current_rank, ranks_history, hot_value,
                first_seen_at, last_seen_at, crawled_at, crawl_date,
                published_at, appearance_count, weight_score, category, extra_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, news.to_db_tuple())
            return cursor.lastrowid
    
    def insert_or_update(self, news: News) -> Tuple[int, bool]:
        """
        插入或更新新闻
        
        Returns:
            (news_id, is_new): 新闻ID和是否为新增
        """
        # 检查是否已存在
        existing = self.find_by_title_hash(
            news.platform_id, 
            news.title_hash, 
            news.crawl_date
        )
        
        if existing:
            # 更新现有记录
            self.update_appearance(
                existing.id,
                news.current_rank,
                news.last_seen_at
            )
            return existing.id, False
        else:
            # 插入新记录
            news_id = self.insert(news)
            return news_id, True
    
    def insert_batch(self, news_list: List[News]) -> Tuple[int, int]:
        """
        批量插入新闻（使用 INSERT OR IGNORE）
        
        Returns:
            (inserted_count, updated_count)
        """
        inserted = 0
        updated = 0
        
        for news in news_list:
            try:
                news_id, is_new = self.insert_or_update(news)
                if is_new:
                    inserted += 1
                else:
                    updated += 1
            except Exception as e:
                print(f"插入新闻失败: {news.title[:30]}... - {e}")
        
        return inserted, updated
    
    def update_appearance(
        self, 
        news_id: int, 
        new_rank: int = None,
        last_seen_at: datetime = None
    ) -> None:
        """更新新闻出现记录"""
        sql = """
            UPDATE news SET
                appearance_count = appearance_count + 1,
                last_seen_at = ?,
                current_rank = COALESCE(?, current_rank),
                ranks_history = (
                    CASE 
                        WHEN ranks_history IS NULL THEN json_array(?)
                        ELSE json_insert(ranks_history, '$[#]', ?)
                    END
                )
            WHERE id = ?
        """
        last_seen = last_seen_at or datetime.now()
        with self.db.get_connection() as conn:
            conn.execute(sql, (
                last_seen.isoformat(),
                new_rank,
                new_rank,
                new_rank,
                news_id
            ))
    
    def find_by_id(self, news_id: int) -> Optional[News]:
        """根据 ID 查找新闻"""
        sql = "SELECT * FROM news WHERE id = ?"
        row = self.db.fetch_one(sql, (news_id,))
        return News.from_db_row(row) if row else None
    
    def find_by_title_hash(
        self, 
        platform_id: str, 
        title_hash: str,
        crawl_date: str
    ) -> Optional[News]:
        """根据平台、标题哈希和日期查找新闻"""
        sql = """
            SELECT * FROM news 
            WHERE platform_id = ? AND title_hash = ? AND crawl_date = ?
        """
        row = self.db.fetch_one(sql, (platform_id, title_hash, crawl_date))
        return News.from_db_row(row) if row else None
    
    def find_by_date(
        self, 
        crawl_date: str = None,
        platform_id: str = None,
        category: str = None,
        limit: int = 100
    ) -> List[News]:
        """按日期查询新闻"""
        if crawl_date is None:
            crawl_date = datetime.now().strftime("%Y-%m-%d")
        
        conditions = ["crawl_date = ?"]
        params = [crawl_date]
        
        if platform_id:
            conditions.append("platform_id = ?")
            params.append(platform_id)
        
        if category:
            conditions.append("category = ?")
            params.append(category)
        
        sql = f"""
            SELECT * FROM news 
            WHERE {' AND '.join(conditions)}
            ORDER BY weight_score DESC, current_rank ASC
            LIMIT ?
        """
        params.append(limit)
        
        rows = self.db.fetch_all(sql, tuple(params))
        return [News.from_db_row(row) for row in rows]
    
    def find_new_since(
        self,
        since_time: datetime,
        platform_ids: List[str] = None
    ) -> List[News]:
        """查找指定时间之后的新增新闻"""
        conditions = ["first_seen_at > ?"]
        params = [since_time.isoformat()]
        
        if platform_ids:
            placeholders = ','.join(['?' for _ in platform_ids])
            conditions.append(f"platform_id IN ({placeholders})")
            params.extend(platform_ids)
        
        sql = f"""
            SELECT * FROM news 
            WHERE {' AND '.join(conditions)}
            ORDER BY first_seen_at DESC
        """
        rows = self.db.fetch_all(sql, tuple(params))
        return [News.from_db_row(row) for row in rows]
    
    def search_by_keyword(
        self, 
        keyword: str,
        crawl_date: str = None,
        limit: int = 50
    ) -> List[News]:
        """按关键词搜索新闻"""
        conditions = ["title LIKE ?"]
        params = [f"%{keyword}%"]
        
        if crawl_date:
            conditions.append("crawl_date = ?")
            params.append(crawl_date)
        
        sql = f"""
            SELECT * FROM news 
            WHERE {' AND '.join(conditions)}
            ORDER BY weight_score DESC
            LIMIT ?
        """
        params.append(limit)
        
        rows = self.db.fetch_all(sql, tuple(params))
        return [News.from_db_row(row) for row in rows]
    
    def get_platform_stats(self, crawl_date: str = None) -> List[Dict]:
        """获取各平台新闻统计"""
        if crawl_date is None:
            crawl_date = datetime.now().strftime("%Y-%m-%d")
        
        sql = """
            SELECT 
                platform_id,
                COUNT(*) as total_news,
                AVG(current_rank) as avg_rank,
                SUM(appearance_count) as total_appearances
            FROM news
            WHERE crawl_date = ?
            GROUP BY platform_id
            ORDER BY total_news DESC
        """
        rows = self.db.fetch_all(sql, (crawl_date,))
        return [dict(row) for row in rows]
    
    def get_trending_keywords(
        self, 
        crawl_date: str = None, 
        top_n: int = 20
    ) -> List[Dict]:
        """获取热门关键词（简单分词）"""
        if crawl_date is None:
            crawl_date = datetime.now().strftime("%Y-%m-%d")
        
        # 这里使用关键词匹配表的统计
        sql = """
            SELECT 
                keyword_group,
                COUNT(*) as match_count
            FROM keyword_matches
            WHERE crawl_date = ?
            GROUP BY keyword_group
            ORDER BY match_count DESC
            LIMIT ?
        """
        rows = self.db.fetch_all(sql, (crawl_date, top_n))
        return [dict(row) for row in rows]
    
    def delete_old_news(self, before_date: str) -> int:
        """删除指定日期之前的新闻"""
        sql = "DELETE FROM news WHERE crawl_date < ?"
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, (before_date,))
            return cursor.rowcount


class KeywordMatchRepository:
    """关键词匹配仓库"""
    
    def __init__(self, db: DatabaseManager = None):
        self.db = db or get_db()
    
    def insert(self, match: KeywordMatch) -> int:
        """插入匹配记录"""
        sql = """
            INSERT INTO keyword_matches (
                news_id, keyword_group, keywords_matched, matched_at,
                title, platform_id, crawl_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, match.to_db_tuple())
            return cursor.lastrowid
    
    def insert_batch(self, matches: List[KeywordMatch]) -> int:
        """批量插入匹配记录"""
        sql = """
            INSERT INTO keyword_matches (
                news_id, keyword_group, keywords_matched, matched_at,
                title, platform_id, crawl_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self.db.get_connection() as conn:
            conn.executemany(sql, [m.to_db_tuple() for m in matches])
            return len(matches)
    
    def find_by_keyword_group(
        self, 
        keyword_group: str,
        crawl_date: str = None,
        limit: int = 50
    ) -> List[KeywordMatch]:
        """按关键词组查找匹配"""
        conditions = ["keyword_group = ?"]
        params = [keyword_group]
        
        if crawl_date:
            conditions.append("crawl_date = ?")
            params.append(crawl_date)
        
        sql = f"""
            SELECT * FROM keyword_matches 
            WHERE {' AND '.join(conditions)}
            ORDER BY matched_at DESC
            LIMIT ?
        """
        params.append(limit)
        
        rows = self.db.fetch_all(sql, tuple(params))
        return [KeywordMatch.from_db_row(row) for row in rows]
    
    def get_keyword_stats(self, crawl_date: str = None) -> List[Dict]:
        """获取关键词统计"""
        if crawl_date is None:
            crawl_date = datetime.now().strftime("%Y-%m-%d")
        
        sql = """
            SELECT 
                keyword_group,
                COUNT(*) as match_count,
                COUNT(DISTINCT platform_id) as platform_count
            FROM keyword_matches
            WHERE crawl_date = ?
            GROUP BY keyword_group
            ORDER BY match_count DESC
        """
        rows = self.db.fetch_all(sql, (crawl_date,))
        return [dict(row) for row in rows]


def _maybe_object_id(value: Any) -> Any:
    if value is None:
        return None
    try:
        from bson import ObjectId
    except Exception:
        return value
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str):
        try:
            return ObjectId(value)
        except Exception:
            return value
    return value


def _news_from_mongo_doc(doc: Dict[str, Any]) -> News:
    crawled_at = doc.get("crawled_at")
    first_seen_at = doc.get("first_seen_at")
    last_seen_at = doc.get("last_seen_at")
    published_at = doc.get("published_at")
    return News(
        id=str(doc.get("_id")),
        platform_id=doc.get("platform_id") or "",
        title=doc.get("title") or "",
        url=doc.get("url") or "",
        mobile_url=doc.get("mobile_url") or "",
        current_rank=int(doc.get("current_rank") or 0),
        ranks_history=list(doc.get("ranks_history") or []),
        hot_value=int(doc.get("hot_value") or 0),
        first_seen_at=first_seen_at,
        last_seen_at=last_seen_at,
        crawled_at=crawled_at,
        crawl_date=doc.get("crawl_date") or "",
        published_at=published_at,
        appearance_count=int(doc.get("appearance_count") or 1),
        weight_score=float(doc.get("weight_score") or 0.0),
        category=doc.get("category") or "",
        extra_data=dict(doc.get("extra_data") or {}),
    )


def _keyword_match_from_mongo_doc(doc: Dict[str, Any]) -> KeywordMatch:
    return KeywordMatch(
        id=str(doc.get("_id")),
        news_id=str(doc.get("news_id")) if doc.get("news_id") is not None else "",
        keyword_group=doc.get("keyword_group") or "",
        keywords_matched=list(doc.get("keywords_matched") or []),
        matched_at=doc.get("matched_at"),
        title=doc.get("title") or "",
        platform_id=doc.get("platform_id") or "",
        crawl_date=doc.get("crawl_date") or "",
    )


class MongoNewsRepository:
    def __init__(self, mongo_db: Any):
        if mongo_db is None:
            raise ValueError("mongo_db 不能为空")
        self._db = mongo_db

    @property
    def _col(self):
        return self._db["news"]

    @property
    def _keyword_col(self):
        return self._db["keyword_matches"]

    def insert(self, news: News) -> str:
        doc: Dict[str, Any] = {
            "platform_id": news.platform_id,
            "title": news.title,
            "title_hash": news.title_hash,
            "url": news.url,
            "mobile_url": news.mobile_url,
            "current_rank": int(news.current_rank),
            "ranks_history": list(news.ranks_history or []),
            "hot_value": int(news.hot_value),
            "first_seen_at": news.first_seen_at,
            "last_seen_at": news.last_seen_at,
            "crawled_at": news.crawled_at,
            "crawl_date": news.crawl_date,
            "published_at": news.published_at,
            "appearance_count": int(news.appearance_count),
            "weight_score": float(news.weight_score),
            "category": news.category,
            "extra_data": dict(news.extra_data or {}),
        }
        result = self._col.insert_one(doc)
        return str(result.inserted_id)

    def insert_or_update(self, news: News) -> Tuple[str, bool]:
        existing = self._col.find_one(
            {
                "platform_id": news.platform_id,
                "title_hash": news.title_hash,
                "crawl_date": news.crawl_date,
            },
            {"_id": 1},
        )
        if existing:
            self.update_appearance(
                str(existing.get("_id")),
                new_rank=news.current_rank,
                last_seen_at=news.last_seen_at,
            )
            return str(existing.get("_id")), False

        news_id = self.insert(news)
        return news_id, True

    def insert_batch(self, news_list: List[News]) -> Tuple[int, int]:
        inserted = 0
        updated = 0
        for news in news_list:
            try:
                _, is_new = self.insert_or_update(news)
                if is_new:
                    inserted += 1
                else:
                    updated += 1
            except Exception as e:
                print(f"插入新闻失败: {news.title[:30]}... - {e}")
        return inserted, updated

    def upsert_exact_batch(self, news_list: List[News]) -> Tuple[int, int]:
        if not news_list:
            return 0, 0

        from pymongo import UpdateOne

        now = datetime.now()
        ops = []
        for news in news_list:
            set_doc: Dict[str, Any] = {
                "platform_id": news.platform_id,
                "title": news.title,
                "title_hash": news.title_hash,
                "url": news.url,
                "mobile_url": news.mobile_url,
                "current_rank": int(news.current_rank),
                "ranks_history": list(news.ranks_history or []),
                "hot_value": int(news.hot_value),
                "first_seen_at": news.first_seen_at,
                "last_seen_at": news.last_seen_at,
                "crawled_at": news.crawled_at,
                "crawl_date": news.crawl_date,
                "published_at": news.published_at,
                "appearance_count": int(news.appearance_count),
                "weight_score": float(news.weight_score),
                "category": news.category,
                "extra_data": dict(news.extra_data or {}),
            }
            if news.id is not None:
                try:
                    set_doc["sqlite_id"] = int(news.id)
                except Exception:
                    set_doc["sqlite_id"] = news.id

            created_at = news.crawled_at or now
            ops.append(
                UpdateOne(
                    {
                        "platform_id": news.platform_id,
                        "title_hash": news.title_hash,
                        "crawl_date": news.crawl_date,
                    },
                    {"$set": set_doc, "$setOnInsert": {"created_at": created_at}},
                    upsert=True,
                )
            )

        result = self._col.bulk_write(ops, ordered=False)
        inserted = int(result.upserted_count or 0)
        updated = int(result.matched_count or 0)
        return inserted, updated

    def update_appearance(
        self,
        news_id: str,
        new_rank: int = None,
        last_seen_at: datetime = None,
    ) -> None:
        _id = _maybe_object_id(news_id)
        last_seen = last_seen_at or datetime.now()
        update: Dict[str, Any] = {
            "$inc": {"appearance_count": 1},
            "$set": {"last_seen_at": last_seen},
        }
        if new_rank is not None:
            update["$set"]["current_rank"] = int(new_rank)
            update["$push"] = {"ranks_history": int(new_rank)}
        self._col.update_one({"_id": _id}, update)

    def find_by_id(self, news_id: str) -> Optional[News]:
        _id = _maybe_object_id(news_id)
        doc = self._col.find_one({"_id": _id})
        return _news_from_mongo_doc(doc) if doc else None

    def find_by_title_hash(
        self,
        platform_id: str,
        title_hash: str,
        crawl_date: str,
    ) -> Optional[News]:
        doc = self._col.find_one(
            {
                "platform_id": platform_id,
                "title_hash": title_hash,
                "crawl_date": crawl_date,
            }
        )
        return _news_from_mongo_doc(doc) if doc else None

    def find_by_date(
        self,
        crawl_date: str = None,
        platform_id: str = None,
        category: str = None,
        limit: int = 100,
    ) -> List[News]:
        if crawl_date is None:
            crawl_date = datetime.now().strftime("%Y-%m-%d")

        query: Dict[str, Any] = {"crawl_date": crawl_date}
        if platform_id:
            query["platform_id"] = platform_id
        if category:
            query["category"] = category

        cursor = (
            self._col.find(query)
            .sort([("weight_score", -1), ("current_rank", 1)])
            .limit(int(limit))
        )
        return [_news_from_mongo_doc(d) for d in cursor]

    def find_new_since(
        self,
        since_time: datetime,
        platform_ids: List[str] = None,
    ) -> List[News]:
        query: Dict[str, Any] = {"first_seen_at": {"$gt": since_time}}
        if platform_ids:
            query["platform_id"] = {"$in": list(platform_ids)}
        cursor = self._col.find(query).sort("first_seen_at", -1)
        return [_news_from_mongo_doc(d) for d in cursor]

    def search_by_keyword(
        self,
        keyword: str,
        crawl_date: str = None,
        limit: int = 50,
    ) -> List[News]:
        query: Dict[str, Any] = {"title": {"$regex": keyword, "$options": "i"}}
        if crawl_date:
            query["crawl_date"] = crawl_date
        cursor = self._col.find(query).sort("weight_score", -1).limit(int(limit))
        return [_news_from_mongo_doc(d) for d in cursor]

    def get_platform_stats(self, crawl_date: str = None) -> List[Dict]:
        if crawl_date is None:
            crawl_date = datetime.now().strftime("%Y-%m-%d")

        pipeline = [
            {"$match": {"crawl_date": crawl_date}},
            {
                "$group": {
                    "_id": "$platform_id",
                    "total_news": {"$sum": 1},
                    "avg_rank": {"$avg": "$current_rank"},
                    "total_appearances": {"$sum": "$appearance_count"},
                }
            },
            {"$sort": {"total_news": -1}},
        ]
        rows = list(self._col.aggregate(pipeline))
        return [
            {
                "platform_id": r.get("_id"),
                "total_news": int(r.get("total_news") or 0),
                "avg_rank": r.get("avg_rank"),
                "total_appearances": int(r.get("total_appearances") or 0),
            }
            for r in rows
        ]

    def get_trending_keywords(self, crawl_date: str = None, top_n: int = 20) -> List[Dict]:
        if crawl_date is None:
            crawl_date = datetime.now().strftime("%Y-%m-%d")

        pipeline = [
            {"$match": {"crawl_date": crawl_date}},
            {
                "$group": {
                    "_id": "$keyword_group",
                    "match_count": {"$sum": 1},
                }
            },
            {"$sort": {"match_count": -1}},
            {"$limit": int(top_n)},
        ]
        rows = list(self._keyword_col.aggregate(pipeline))
        return [
            {"keyword_group": r.get("_id"), "match_count": int(r.get("match_count") or 0)}
            for r in rows
        ]

    def delete_old_news(self, before_date: str) -> int:
        result = self._col.delete_many({"crawl_date": {"$lt": before_date}})
        return int(result.deleted_count or 0)


class MongoKeywordMatchRepository:
    def __init__(self, mongo_db: Any):
        if mongo_db is None:
            raise ValueError("mongo_db 不能为空")
        self._db = mongo_db

    @property
    def _col(self):
        return self._db["keyword_matches"]

    def insert(self, match: KeywordMatch) -> str:
        doc: Dict[str, Any] = {
            "news_id": _maybe_object_id(match.news_id),
            "keyword_group": match.keyword_group,
            "keywords_matched": list(match.keywords_matched or []),
            "matched_at": match.matched_at,
            "title": match.title,
            "platform_id": match.platform_id,
            "crawl_date": match.crawl_date,
        }
        result = self._col.insert_one(doc)
        return str(result.inserted_id)

    def insert_batch(self, matches: List[KeywordMatch]) -> int:
        if not matches:
            return 0
        docs = []
        for m in matches:
            docs.append(
                {
                    "news_id": _maybe_object_id(m.news_id),
                    "keyword_group": m.keyword_group,
                    "keywords_matched": list(m.keywords_matched or []),
                    "matched_at": m.matched_at,
                    "title": m.title,
                    "platform_id": m.platform_id,
                    "crawl_date": m.crawl_date,
                }
            )
        self._col.insert_many(docs, ordered=False)
        return len(docs)

    def find_by_keyword_group(
        self,
        keyword_group: str,
        crawl_date: str = None,
        limit: int = 50,
    ) -> List[KeywordMatch]:
        query: Dict[str, Any] = {"keyword_group": keyword_group}
        if crawl_date:
            query["crawl_date"] = crawl_date
        cursor = self._col.find(query).sort("matched_at", -1).limit(int(limit))
        return [_keyword_match_from_mongo_doc(d) for d in cursor]

    def get_keyword_stats(self, crawl_date: str = None) -> List[Dict]:
        if crawl_date is None:
            crawl_date = datetime.now().strftime("%Y-%m-%d")

        pipeline = [
            {"$match": {"crawl_date": crawl_date}},
            {
                "$group": {
                    "_id": "$keyword_group",
                    "match_count": {"$sum": 1},
                    "platforms": {"$addToSet": "$platform_id"},
                }
            },
            {
                "$project": {
                    "keyword_group": "$_id",
                    "match_count": 1,
                    "platform_count": {"$size": "$platforms"},
                }
            },
            {"$sort": {"match_count": -1}},
        ]
        rows = list(self._col.aggregate(pipeline))
        return [
            {
                "keyword_group": r.get("keyword_group"),
                "match_count": int(r.get("match_count") or 0),
                "platform_count": int(r.get("platform_count") or 0),
            }
            for r in rows
        ]
