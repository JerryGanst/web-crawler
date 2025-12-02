# coding=utf-8
"""
数据库连接管理模块
支持 SQLite 持久化和可选的 Redis 缓存
"""

import os
import sqlite3
import hashlib
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional, Generator

# 可选的异步支持
try:
    import aiosqlite
    HAS_AIOSQLITE = True
except ImportError:
    HAS_AIOSQLITE = False


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
        self._ensure_db_directory()
        self._init_database()
        self._initialized = True
        
    def _ensure_db_directory(self) -> None:
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        
    def _init_database(self) -> None:
        """初始化数据库（执行迁移脚本）"""
        migrations_path = Path(__file__).parent / "migrations" / "init_schema.sql"
        
        if not migrations_path.exists():
            print(f"警告: 迁移脚本不存在: {migrations_path}")
            return
            
        with self.get_connection() as conn:
            # 启用 WAL 模式和外键约束
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(f"PRAGMA busy_timeout = {self.DEFAULT_BUSY_TIMEOUT}")
            
            # 执行初始化脚本
            with open(migrations_path, "r", encoding="utf-8") as f:
                sql_script = f.read()
            
            # 分割并执行每条语句
            statements = self._split_sql_statements(sql_script)
            for statement in statements:
                if statement.strip():
                    try:
                        conn.execute(statement)
                    except sqlite3.Error as e:
                        # 忽略已存在的对象错误
                        if "already exists" not in str(e).lower():
                            print(f"SQL 执行警告: {e}")
            
            conn.commit()
            print(f"数据库初始化完成: {self.db_path}")
    
    def _split_sql_statements(self, sql_script: str) -> list:
        """分割 SQL 脚本为独立语句"""
        statements = []
        current = []
        in_trigger = False
        
        for line in sql_script.split('\n'):
            stripped = line.strip()
            
            # 跳过注释和空行
            if stripped.startswith('--') or not stripped:
                continue
            
            # 检测 TRIGGER 开始
            if 'CREATE TRIGGER' in stripped.upper():
                in_trigger = True
            
            current.append(line)
            
            # 在 TRIGGER 中，遇到 END; 才结束
            if in_trigger:
                if stripped.upper() == 'END;':
                    statements.append('\n'.join(current))
                    current = []
                    in_trigger = False
            elif stripped.endswith(';'):
                statements.append('\n'.join(current))
                current = []
        
        if current:
            statements.append('\n'.join(current))
        
        return statements
    
    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """获取数据库连接（上下文管理器）"""
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


# 添加缺失的导入
from datetime import timedelta


def get_db(db_path: str = None) -> DatabaseManager:
    """获取数据库管理器实例"""
    return DatabaseManager(db_path)


def generate_title_hash(title: str) -> str:
    """生成标题哈希"""
    return hashlib.md5(title.encode('utf-8')).hexdigest()
