# coding=utf-8
"""
日志记录仓库
提供爬取日志和推送记录的 CRUD 操作
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict

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
