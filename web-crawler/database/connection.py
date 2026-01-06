# coding=utf-8
"""
数据库连接管理模块
支持 SQLite 持久化和可选的 Redis 缓存
"""

import os
import sqlite3
import hashlib
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Generator
from urllib.parse import quote_plus

# 可选的异步支持
try:
    import aiosqlite
    HAS_AIOSQLITE = True
except ImportError:
    HAS_AIOSQLITE = False

try:
    from pymongo import MongoClient
    HAS_PYMONGO = True
except ImportError:
    MongoClient = None
    HAS_PYMONGO = False


class DatabaseManager:
    """数据库管理器"""
    
    # 默认配置
    DEFAULT_DB_PATH = "data/trendradar.db"
    DEFAULT_BUSY_TIMEOUT = 5000  # 毫秒
    
    _instance: Optional['DatabaseManager'] = None
    
    def __new__(cls, db_path: str = None):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: str = None):
        if self._initialized:
            return
            
        self.db_path = db_path or os.environ.get("DB_PATH", self.DEFAULT_DB_PATH)
        self._initialized = True
        
    def _ensure_db_directory(self) -> None:
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """获取数据库连接（上下文管理器）"""
        self._ensure_db_directory()
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.DEFAULT_BUSY_TIMEOUT / 1000,  # 转换为秒
            isolation_level=None  # 自动提交模式
        )
        conn.row_factory = sqlite3.Row  # 返回字典式结果
        conn.execute("PRAGMA foreign_keys = ON")
        
        try:
            yield conn
        finally:
            conn.close()
    
    def execute(self, sql: str, params: tuple = None) -> sqlite3.Cursor:
        """执行 SQL 语句"""
        with self.get_connection() as conn:
            if params:
                return conn.execute(sql, params)
            return conn.execute(sql)
    
    def execute_many(self, sql: str, params_list: list) -> None:
        """批量执行 SQL 语句"""
        with self.get_connection() as conn:
            conn.executemany(sql, params_list)
    
    def fetch_one(self, sql: str, params: tuple = None) -> Optional[sqlite3.Row]:
        """查询单条记录"""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params or ())
            return cursor.fetchone()
    
    def fetch_all(self, sql: str, params: tuple = None) -> list:
        """查询所有记录"""
        with self.get_connection() as conn:
            cursor = conn.execute(sql, params or ())
            return cursor.fetchall()
    
    def health_check(self) -> dict:
        """健康检查"""
        try:
            with self.get_connection() as conn:
                # 检查数据库是否可访问
                cursor = conn.execute("SELECT sqlite_version()")
                version = cursor.fetchone()[0]
                
                # 获取表统计
                cursor = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """)
                tables = [row[0] for row in cursor.fetchall()]
                
                # 获取数据库大小
                db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
                
                return {
                    "status": "healthy",
                    "sqlite_version": version,
                    "db_path": self.db_path,
                    "db_size_bytes": db_size,
                    "db_size_mb": round(db_size / 1024 / 1024, 2),
                    "tables": tables,
                    "table_count": len(tables)
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    def vacuum(self) -> None:
        """压缩数据库"""
        with self.get_connection() as conn:
            conn.execute("VACUUM")
            print("数据库压缩完成")
    
    def analyze(self) -> None:
        """分析并优化索引"""
        with self.get_connection() as conn:
            conn.execute("ANALYZE")
            print("索引分析完成")
    
    def backup(self, backup_path: str = None) -> str:
        """备份数据库"""
        if backup_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = Path(self.db_path).parent / "backups"
            backup_dir.mkdir(exist_ok=True)
            backup_path = str(backup_dir / f"trendradar_{timestamp}.db")
        
        with self.get_connection() as conn:
            backup_conn = sqlite3.connect(backup_path)
            conn.backup(backup_conn)
            backup_conn.close()
        
        print(f"数据库备份完成: {backup_path}")
        return backup_path
    
    def cleanup_old_data(self, retention_days: int = 30) -> int:
        """清理过期数据"""
        cutoff_date = (datetime.now() - timedelta(days=retention_days)).strftime("%Y-%m-%d")
        
        with self.get_connection() as conn:
            # 删除旧新闻
            cursor = conn.execute(
                "DELETE FROM news WHERE crawl_date < ?",
                (cutoff_date,)
            )
            deleted_news = cursor.rowcount
            
            # 删除旧爬取日志
            conn.execute(
                "DELETE FROM crawl_logs WHERE DATE(started_at) < ?",
                (cutoff_date,)
            )
            
            # 删除过期缓存
            conn.execute(
                "DELETE FROM analytics_cache WHERE expires_at < CURRENT_TIMESTAMP"
            )
            
            print(f"清理完成: 删除 {deleted_news} 条过期新闻")
            return deleted_news
def get_db(db_path: str = None) -> DatabaseManager:
    """获取数据库管理器实例"""
    return DatabaseManager(db_path)


_mongo_clients: dict[str, "MongoClient"] = {}


def _get_mongo_cfg_from_yaml() -> dict:
    config_path = Path(__file__).resolve().parent.parent / "config" / "database.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    mongo_cfg = data.get("mongodb", {}) or {}
    return dict(mongo_cfg)


def build_mongo_uri(mongo_cfg: dict) -> str:
    host = mongo_cfg.get("host")
    port = mongo_cfg.get("port")
    username = mongo_cfg.get("username")
    password = mongo_cfg.get("password")
    database = mongo_cfg.get("database")
    auth_source = mongo_cfg.get("authentication_source")

    if not host or not port:
        raise ValueError("MongoDB host/port 缺失")

    database = database or "trendradar"
    auth_source = auth_source or "admin"

    if (username and not password) or (password and not username):
        raise ValueError("MongoDB 用户名/密码配置不完整")

    if username and password:
        return (
            f"mongodb://{quote_plus(str(username))}:{quote_plus(str(password))}"
            f"@{host}:{int(port)}/{database}?authSource={auth_source}"
        )

    return f"mongodb://{host}:{int(port)}/{database}"


def get_mongo_database(mongo_cfg: Optional[dict] = None):
    if not HAS_PYMONGO:
        raise ImportError("未安装 pymongo")

    cfg = dict(mongo_cfg or _get_mongo_cfg_from_yaml() or {})

    # 环境变量代码移除，严格遵循 yaml 配置
    # env_overrides = { ... }
    # cfg.update(env_overrides)

    if isinstance(cfg.get("port"), str):
        cfg["port"] = int(cfg["port"])

    uri = build_mongo_uri(cfg)

    global _mongo_clients
    client = _mongo_clients.get(uri)
    if client is None:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        _mongo_clients[uri] = client

    database = cfg.get("database") or "trendradar"
    if database == "admin":
        trend_db = client["trendradar"]
        try:
            trend_db.command("ping")
            return trend_db
        except Exception:
            return client["admin"]

    return client[database]


def generate_title_hash(title: str) -> str:
    """生成标题哈希"""
    return hashlib.md5(title.encode('utf-8')).hexdigest()
