# coding=utf-8
"""
日志记录仓库
提供爬取日志和推送记录的 CRUD 操作
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from ..connection import DatabaseManager, get_db
from ..models import CrawlLog, PushRecord


class CrawlLogRepository:
    """爬取日志仓库"""
    
    def __init__(self, db: DatabaseManager = None):
        self.db = db or get_db()
    
    def create_task(self) -> CrawlLog:
        """创建新的爬取任务"""
        log = CrawlLog(
            task_id=str(uuid.uuid4()),
            status="pending",
            started_at=datetime.now()
        )
        return log
    
    def insert(self, log: CrawlLog) -> int:
        """插入爬取日志"""
        sql = """
            INSERT INTO crawl_logs (
                task_id, started_at, finished_at, duration_ms,
                platforms_crawled, total_news, new_news, failed_platforms,
                status, error_message, platform_results
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, log.to_db_tuple())
            return cursor.lastrowid
    
    def update_status(
        self,
        task_id: str,
        status: str,
        total_news: int = 0,
        new_news: int = 0,
        error_message: str = None
    ) -> None:
        """更新任务状态"""
        finished_at = datetime.now()
        
        # 获取开始时间计算时长
        existing = self.find_by_task_id(task_id)
        duration_ms = 0
        if existing and existing.started_at:
            delta = finished_at - existing.started_at
            duration_ms = int(delta.total_seconds() * 1000)
        
        sql = """
            UPDATE crawl_logs SET
                status = ?,
                finished_at = ?,
                duration_ms = ?,
                total_news = ?,
                new_news = ?,
                error_message = ?
            WHERE task_id = ?
        """
        with self.db.get_connection() as conn:
            conn.execute(sql, (
                status,
                finished_at.isoformat(),
                duration_ms,
                total_news,
                new_news,
                error_message,
                task_id
            ))
    
    def find_by_task_id(self, task_id: str) -> Optional[CrawlLog]:
        """根据任务 ID 查找日志"""
        sql = "SELECT * FROM crawl_logs WHERE task_id = ?"
        row = self.db.fetch_one(sql, (task_id,))
        return CrawlLog.from_db_row(row) if row else None
    
    def find_recent(self, limit: int = 20) -> List[CrawlLog]:
        """查找最近的爬取日志"""
        sql = """
            SELECT * FROM crawl_logs 
            ORDER BY started_at DESC 
            LIMIT ?
        """
        rows = self.db.fetch_all(sql, (limit,))
        return [CrawlLog.from_db_row(row) for row in rows]
    
    def find_by_status(self, status: str, limit: int = 20) -> List[CrawlLog]:
        """按状态查找日志"""
        sql = """
            SELECT * FROM crawl_logs 
            WHERE status = ?
            ORDER BY started_at DESC 
            LIMIT ?
        """
        rows = self.db.fetch_all(sql, (status, limit))
        return [CrawlLog.from_db_row(row) for row in rows]
    
    def get_daily_stats(self, date: str = None) -> Dict:
        """获取每日统计"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        sql = """
            SELECT 
                COUNT(*) as task_count,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                SUM(total_news) as total_news,
                SUM(new_news) as new_news,
                AVG(duration_ms) as avg_duration_ms
            FROM crawl_logs
            WHERE DATE(started_at) = ?
        """
        row = self.db.fetch_one(sql, (date,))
        return dict(row) if row else {}
    
    def cleanup_old_logs(self, retention_days: int = 30) -> int:
        """清理旧日志"""
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
        sql = "DELETE FROM crawl_logs WHERE DATE(started_at) < ?"
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, (cutoff_date,))
            return cursor.rowcount


class PushRecordRepository:
    """推送记录仓库"""
    
    def __init__(self, db: DatabaseManager = None):
        self.db = db or get_db()
    
    def insert(self, record: PushRecord) -> int:
        """插入推送记录"""
        sql = """
            INSERT INTO push_records (
                channel, report_type, status, error_message,
                news_count, keyword_groups, message_batches, message_hash,
                pushed_at, push_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, record.to_db_tuple())
            return cursor.lastrowid
    
    def find_by_channel_date(
        self, 
        channel: str, 
        push_date: str = None
    ) -> List[PushRecord]:
        """按渠道和日期查找推送记录"""
        if push_date is None:
            push_date = datetime.now().strftime("%Y-%m-%d")
        
        sql = """
            SELECT * FROM push_records 
            WHERE channel = ? AND push_date = ?
            ORDER BY pushed_at DESC
        """
        rows = self.db.fetch_all(sql, (channel, push_date))
        return [PushRecord.from_db_row(row) for row in rows]
    
    def has_pushed_today(self, channel: str = None) -> bool:
        """检查今天是否已推送"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if channel:
            sql = """
                SELECT COUNT(*) FROM push_records 
                WHERE push_date = ? AND channel = ? AND status = 'success'
            """
            row = self.db.fetch_one(sql, (today, channel))
        else:
            sql = """
                SELECT COUNT(*) FROM push_records 
                WHERE push_date = ? AND status = 'success'
            """
            row = self.db.fetch_one(sql, (today,))
        
        return row[0] > 0 if row else False
    
    def find_recent(self, limit: int = 20) -> List[PushRecord]:
        """查找最近的推送记录"""
        sql = """
            SELECT * FROM push_records 
            ORDER BY pushed_at DESC 
            LIMIT ?
        """
        rows = self.db.fetch_all(sql, (limit,))
        return [PushRecord.from_db_row(row) for row in rows]
    
    def get_channel_stats(self, days: int = 7) -> Dict:
        """获取各渠道推送统计"""
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        sql = """
            SELECT 
                channel,
                COUNT(*) as total_pushes,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success_count,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_count,
                SUM(news_count) as total_news
            FROM push_records
            WHERE push_date >= ?
            GROUP BY channel
        """
        rows = self.db.fetch_all(sql, (cutoff_date,))
        return {row['channel']: dict(row) for row in rows}
    
    def cleanup_old_records(self, retention_days: int = 30) -> int:
        """清理旧推送记录"""
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
        sql = "DELETE FROM push_records WHERE push_date < ?"
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, (cutoff_date,))
            return cursor.rowcount


def _crawl_log_from_mongo_doc(doc: Dict[str, Any]) -> CrawlLog:
    return CrawlLog(
        id=str(doc.get("_id")),
        task_id=doc.get("task_id") or "",
        status=doc.get("status") or "pending",
        started_at=doc.get("started_at"),
        finished_at=doc.get("finished_at"),
        duration_ms=int(doc.get("duration_ms") or 0),
        platforms_crawled=list(doc.get("platforms_crawled") or []),
        total_news=int(doc.get("total_news") or 0),
        new_news=int(doc.get("new_news") or 0),
        failed_platforms=list(doc.get("failed_platforms") or []),
        error_message=doc.get("error_message") or "",
        platform_results=list(doc.get("platform_results") or []),
    )


def _push_record_from_mongo_doc(doc: Dict[str, Any]) -> PushRecord:
    return PushRecord(
        id=str(doc.get("_id")),
        channel=doc.get("channel") or "",
        report_type=doc.get("report_type") or "",
        status=doc.get("status") or "pending",
        error_message=doc.get("error_message") or "",
        news_count=int(doc.get("news_count") or 0),
        keyword_groups=list(doc.get("keyword_groups") or []),
        message_batches=int(doc.get("message_batches") or 1),
        message_hash=doc.get("message_hash") or "",
        pushed_at=doc.get("pushed_at"),
        push_date=doc.get("push_date") or "",
    )


class MongoCrawlLogRepository:
    def __init__(self, mongo_db: Any):
        if mongo_db is None:
            raise ValueError("mongo_db 不能为空")
        self._db = mongo_db

    @property
    def _col(self):
        return self._db["crawl_logs"]

    def create_task(self) -> CrawlLog:
        log = CrawlLog(task_id=str(uuid.uuid4()), status="pending", started_at=datetime.now())
        return log

    def insert(self, log: CrawlLog) -> str:
        doc: Dict[str, Any] = {
            "task_id": log.task_id,
            "started_at": log.started_at,
            "finished_at": log.finished_at,
            "duration_ms": int(log.duration_ms),
            "platforms_crawled": list(log.platforms_crawled or []),
            "total_news": int(log.total_news),
            "new_news": int(log.new_news),
            "failed_platforms": list(log.failed_platforms or []),
            "status": log.status,
            "error_message": log.error_message,
            "platform_results": list(log.platform_results or []),
        }
        result = self._col.insert_one(doc)
        return str(result.inserted_id)

    def update_status(
        self,
        task_id: str,
        status: str,
        total_news: int = 0,
        new_news: int = 0,
        error_message: str = None,
    ) -> None:
        finished_at = datetime.now()
        existing = self._col.find_one({"task_id": task_id}, {"started_at": 1})
        duration_ms = 0
        started_at = existing.get("started_at") if existing else None
        if started_at:
            delta = finished_at - started_at
            duration_ms = int(delta.total_seconds() * 1000)

        update = {
            "$set": {
                "status": status,
                "finished_at": finished_at,
                "duration_ms": int(duration_ms),
                "total_news": int(total_news),
                "new_news": int(new_news),
                "error_message": error_message,
            }
        }
        self._col.update_one({"task_id": task_id}, update)

    def find_by_task_id(self, task_id: str) -> Optional[CrawlLog]:
        doc = self._col.find_one({"task_id": task_id})
        return _crawl_log_from_mongo_doc(doc) if doc else None

    def find_recent(self, limit: int = 20) -> List[CrawlLog]:
        cursor = self._col.find({}).sort("started_at", -1).limit(int(limit))
        return [_crawl_log_from_mongo_doc(d) for d in cursor]

    def find_by_status(self, status: str, limit: int = 20) -> List[CrawlLog]:
        cursor = (
            self._col.find({"status": status})
            .sort("started_at", -1)
            .limit(int(limit))
        )
        return [_crawl_log_from_mongo_doc(d) for d in cursor]

    def get_daily_stats(self, date: str = None) -> Dict:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        start = datetime.strptime(date, "%Y-%m-%d")
        end = start + timedelta(days=1)

        pipeline = [
            {"$match": {"started_at": {"$gte": start, "$lt": end}}},
            {
                "$group": {
                    "_id": None,
                    "task_count": {"$sum": 1},
                    "success_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}
                    },
                    "failed_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}
                    },
                    "total_news": {"$sum": "$total_news"},
                    "new_news": {"$sum": "$new_news"},
                    "avg_duration_ms": {"$avg": "$duration_ms"},
                }
            },
        ]
        rows = list(self._col.aggregate(pipeline))
        if not rows:
            return {}
        row = rows[0]
        return {
            "task_count": int(row.get("task_count") or 0),
            "success_count": int(row.get("success_count") or 0),
            "failed_count": int(row.get("failed_count") or 0),
            "total_news": int(row.get("total_news") or 0),
            "new_news": int(row.get("new_news") or 0),
            "avg_duration_ms": row.get("avg_duration_ms"),
        }

    def cleanup_old_logs(self, retention_days: int = 30) -> int:
        cutoff = datetime.now() - timedelta(days=retention_days)
        result = self._col.delete_many({"started_at": {"$lt": cutoff}})
        return int(result.deleted_count or 0)


class MongoPushRecordRepository:
    def __init__(self, mongo_db: Any):
        if mongo_db is None:
            raise ValueError("mongo_db 不能为空")
        self._db = mongo_db

    @property
    def _col(self):
        return self._db["push_records"]

    def insert(self, record: PushRecord) -> str:
        doc: Dict[str, Any] = {
            "channel": record.channel,
            "report_type": record.report_type,
            "status": record.status,
            "error_message": record.error_message,
            "news_count": int(record.news_count),
            "keyword_groups": list(record.keyword_groups or []),
            "message_batches": int(record.message_batches),
            "message_hash": record.message_hash,
            "pushed_at": record.pushed_at,
            "push_date": record.push_date,
        }
        result = self._col.insert_one(doc)
        return str(result.inserted_id)

    def find_by_channel_date(self, channel: str, push_date: str = None) -> List[PushRecord]:
        if push_date is None:
            push_date = datetime.now().strftime("%Y-%m-%d")
        cursor = (
            self._col.find({"channel": channel, "push_date": push_date})
            .sort("pushed_at", -1)
        )
        return [_push_record_from_mongo_doc(d) for d in cursor]

    def has_pushed_today(self, channel: str = None) -> bool:
        today = datetime.now().strftime("%Y-%m-%d")
        query: Dict[str, Any] = {"push_date": today, "status": "success"}
        if channel:
            query["channel"] = channel
        doc = self._col.find_one(query, {"_id": 1})
        return doc is not None

    def find_recent(self, limit: int = 20) -> List[PushRecord]:
        cursor = self._col.find({}).sort("pushed_at", -1).limit(int(limit))
        return [_push_record_from_mongo_doc(d) for d in cursor]

    def get_channel_stats(self, days: int = 7) -> Dict:
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        pipeline = [
            {"$match": {"push_date": {"$gte": cutoff_date}}},
            {
                "$group": {
                    "_id": "$channel",
                    "total_pushes": {"$sum": 1},
                    "success_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "success"]}, 1, 0]}
                    },
                    "failed_count": {
                        "$sum": {"$cond": [{"$eq": ["$status", "failed"]}, 1, 0]}
                    },
                    "total_news": {"$sum": "$news_count"},
                }
            },
        ]
        rows = list(self._col.aggregate(pipeline))
        result: Dict[str, Any] = {}
        for row in rows:
            channel = row.get("_id")
            result[channel] = {
                "channel": channel,
                "total_pushes": int(row.get("total_pushes") or 0),
                "success_count": int(row.get("success_count") or 0),
                "failed_count": int(row.get("failed_count") or 0),
                "total_news": int(row.get("total_news") or 0),
            }
        return result

    def cleanup_old_records(self, retention_days: int = 30) -> int:
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
        result = self._col.delete_many({"push_date": {"$lt": cutoff_date}})
        return int(result.deleted_count or 0)
