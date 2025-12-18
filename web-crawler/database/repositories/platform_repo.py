# coding=utf-8
"""
平台配置仓库
提供平台配置的 CRUD 操作
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

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


def _platform_from_mongo_doc(doc: Dict[str, Any]) -> Platform:
    return Platform(
        id=str(doc.get("_id")),
        name=doc.get("name") or "",
        category=doc.get("category") or "",
        enabled=bool(doc.get("enabled", True)),
        api_type=doc.get("api_type") or "newsnow",
        crawl_interval_ms=int(doc.get("crawl_interval_ms") or 1000),
        max_retries=int(doc.get("max_retries") or 3),
        last_crawled_at=doc.get("last_crawled_at"),
        total_crawled=int(doc.get("total_crawled") or 0),
        success_rate=float(doc.get("success_rate") or 1.0),
        created_at=doc.get("created_at"),
        updated_at=doc.get("updated_at"),
    )


class MongoPlatformRepository:
    def __init__(self, mongo_db: Any):
        if mongo_db is None:
            raise ValueError("mongo_db 不能为空")
        self._db = mongo_db

    @property
    def _col(self):
        return self._db["platforms"]

    def insert(self, platform: Platform) -> str:
        now = datetime.now()
        created_at = platform.created_at or now
        updated_at = platform.updated_at or now
        update = {
            "$set": {
                "name": platform.name,
                "category": platform.category,
                "enabled": bool(platform.enabled),
                "api_type": platform.api_type,
                "crawl_interval_ms": int(platform.crawl_interval_ms),
                "max_retries": int(platform.max_retries),
                "last_crawled_at": platform.last_crawled_at,
                "total_crawled": int(platform.total_crawled),
                "success_rate": float(platform.success_rate),
                "updated_at": updated_at,
            },
            "$setOnInsert": {"created_at": created_at},
        }
        self._col.update_one({"_id": platform.id}, update, upsert=True)
        return platform.id

    def insert_batch(self, platforms: List[Platform]) -> int:
        if not platforms:
            return 0
        from pymongo import UpdateOne

        now = datetime.now()
        ops = []
        for p in platforms:
            created_at = p.created_at or now
            updated_at = p.updated_at or now
            ops.append(
                UpdateOne(
                    {"_id": p.id},
                    {
                        "$set": {
                            "name": p.name,
                            "category": p.category,
                            "enabled": bool(p.enabled),
                            "api_type": p.api_type,
                            "crawl_interval_ms": int(p.crawl_interval_ms),
                            "max_retries": int(p.max_retries),
                            "last_crawled_at": p.last_crawled_at,
                            "total_crawled": int(p.total_crawled),
                            "success_rate": float(p.success_rate),
                            "updated_at": updated_at,
                        },
                        "$setOnInsert": {"created_at": created_at},
                    },
                    upsert=True,
                )
            )
        self._col.bulk_write(ops, ordered=False)
        return len(platforms)

    def find_by_id(self, platform_id: str) -> Optional[Platform]:
        doc = self._col.find_one({"_id": platform_id})
        return _platform_from_mongo_doc(doc) if doc else None

    def find_all(self, enabled_only: bool = False) -> List[Platform]:
        query: Dict[str, Any] = {}
        if enabled_only:
            query["enabled"] = True
        cursor = self._col.find(query).sort([("category", 1), ("name", 1)])
        return [_platform_from_mongo_doc(d) for d in cursor]

    def find_by_category(self, category: str) -> List[Platform]:
        cursor = self._col.find({"category": category}).sort("name", 1)
        return [_platform_from_mongo_doc(d) for d in cursor]

    def update_crawl_stats(self, platform_id: str, news_count: int, success: bool = True) -> None:
        doc = self._col.find_one({"_id": platform_id}, {"total_crawled": 1, "success_rate": 1})
        if not doc:
            return

        total_crawled = int(doc.get("total_crawled") or 0)
        success_rate = float(doc.get("success_rate") or 1.0)

        if total_crawled < 0:
            total_crawled = 0

        if total_crawled == 0:
            new_success_rate = 1.0 if success else 0.0
        else:
            if success:
                new_success_rate = (success_rate * total_crawled + 1) / (total_crawled + 1)
            else:
                new_success_rate = (success_rate * total_crawled) / (total_crawled + 1)

        self._col.update_one(
            {"_id": platform_id},
            {
                "$set": {
                    "last_crawled_at": datetime.now(),
                    "success_rate": float(new_success_rate),
                    "updated_at": datetime.now(),
                },
                "$inc": {"total_crawled": int(news_count)},
            },
        )

    def set_enabled(self, platform_id: str, enabled: bool) -> None:
        self._col.update_one(
            {"_id": platform_id},
            {"$set": {"enabled": bool(enabled), "updated_at": datetime.now()}},
        )

    def get_stats(self) -> Dict:
        pipeline = [
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": 1},
                    "enabled_count": {"$sum": {"$cond": ["$enabled", 1, 0]}},
                    "total_crawled": {"$sum": "$total_crawled"},
                    "avg_success_rate": {"$avg": "$success_rate"},
                }
            }
        ]
        rows = list(self._col.aggregate(pipeline))
        if not rows:
            return {}
        row = rows[0]
        return {
            "total": int(row.get("total") or 0),
            "enabled_count": int(row.get("enabled_count") or 0),
            "total_crawled": int(row.get("total_crawled") or 0),
            "avg_success_rate": float(row.get("avg_success_rate") or 0.0),
        }

    def sync_from_config(self, platforms_config: List[Dict]) -> int:
        platforms = []
        for config in platforms_config:
            platform = Platform(
                id=config.get("id"),
                name=config.get("name", config.get("id")),
                category=config.get("category", ""),
                enabled=True,
            )
            platforms.append(platform)
        return self.insert_batch(platforms)
