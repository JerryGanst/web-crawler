# coding=utf-8
"""
平台配置仓库
提供平台配置的 CRUD 操作
"""

from datetime import datetime
from typing import List, Optional, Dict

from ..connection import DatabaseManager, get_db
from ..models import Platform


class PlatformRepository:
    """平台配置仓库"""
    
    def __init__(self, db: DatabaseManager = None):
        self.db = db or get_db()
    
    def insert(self, platform: Platform) -> str:
        """插入或替换平台配置"""
        sql = """
            INSERT OR REPLACE INTO platforms (
                id, name, category, enabled, api_type,
                crawl_interval_ms, max_retries, last_crawled_at,
                total_crawled, success_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.db.get_connection() as conn:
            conn.execute(sql, platform.to_db_tuple())
            return platform.id
    
    def insert_batch(self, platforms: List[Platform]) -> int:
        """批量插入平台配置"""
        sql = """
            INSERT OR REPLACE INTO platforms (
                id, name, category, enabled, api_type,
                crawl_interval_ms, max_retries, last_crawled_at,
                total_crawled, success_rate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.db.get_connection() as conn:
            conn.executemany(sql, [p.to_db_tuple() for p in platforms])
            return len(platforms)
    
    def find_by_id(self, platform_id: str) -> Optional[Platform]:
        """根据 ID 查找平台"""
        sql = "SELECT * FROM platforms WHERE id = ?"
        row = self.db.fetch_one(sql, (platform_id,))
        return Platform.from_db_row(row) if row else None
    
    def find_all(self, enabled_only: bool = False) -> List[Platform]:
        """查找所有平台"""
        if enabled_only:
            sql = "SELECT * FROM platforms WHERE enabled = 1 ORDER BY category, name"
        else:
            sql = "SELECT * FROM platforms ORDER BY category, name"
        
        rows = self.db.fetch_all(sql)
        return [Platform.from_db_row(row) for row in rows]
    
    def find_by_category(self, category: str) -> List[Platform]:
        """按分类查找平台"""
        sql = "SELECT * FROM platforms WHERE category = ? ORDER BY name"
        rows = self.db.fetch_all(sql, (category,))
        return [Platform.from_db_row(row) for row in rows]
    
    def update_crawl_stats(
        self,
        platform_id: str,
        news_count: int,
        success: bool = True
    ) -> None:
        """更新爬取统计"""
        sql = """
            UPDATE platforms SET
                last_crawled_at = ?,
                total_crawled = total_crawled + ?,
                success_rate = CASE
                    WHEN ? = 1 THEN (success_rate * total_crawled + 1) / (total_crawled + 1)
                    ELSE (success_rate * total_crawled) / (total_crawled + 1)
                END
            WHERE id = ?
        """
        with self.db.get_connection() as conn:
            conn.execute(sql, (
                datetime.now().isoformat(),
                news_count,
                1 if success else 0,
                platform_id
            ))
    
    def set_enabled(self, platform_id: str, enabled: bool) -> None:
        """设置平台启用状态"""
        sql = "UPDATE platforms SET enabled = ? WHERE id = ?"
        with self.db.get_connection() as conn:
            conn.execute(sql, (1 if enabled else 0, platform_id))
    
    def get_stats(self) -> Dict:
        """获取平台统计概览"""
        sql = """
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN enabled = 1 THEN 1 ELSE 0 END) as enabled_count,
                SUM(total_crawled) as total_crawled,
                AVG(success_rate) as avg_success_rate
            FROM platforms
        """
        row = self.db.fetch_one(sql)
        return dict(row) if row else {}
    
    def sync_from_config(self, platforms_config: List[Dict]) -> int:
        """从配置文件同步平台"""
        platforms = []
        for config in platforms_config:
            platform = Platform(
                id=config.get('id'),
                name=config.get('name', config.get('id')),
                category=config.get('category', ''),
                enabled=True,
            )
            platforms.append(platform)
        
        return self.insert_batch(platforms)
