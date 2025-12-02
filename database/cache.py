# coding=utf-8
"""
缓存模块
提供可选的 Redis 缓存支持和 SQLite 备用缓存
"""

import json
import hashlib
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Optional

# 可选的 Redis 支持
try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    redis = None

from .connection import get_db


class CacheInterface(ABC):
    """缓存接口"""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        pass
    
    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        pass
    
    @abstractmethod
    def delete(self, key: str) -> bool:
        pass
    
    @abstractmethod
    def exists(self, key: str) -> bool:
        pass
    
    @abstractmethod
    def clear_expired(self) -> int:
        pass


class SQLiteCache(CacheInterface):
    """SQLite 备用缓存（使用 analytics_cache 表）"""
    
    def __init__(self, db=None):
        self.db = db or get_db()
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        sql = """
            SELECT result FROM analytics_cache 
            WHERE cache_key = ? AND expires_at > CURRENT_TIMESTAMP
        """
        row = self.db.fetch_one(sql, (key,))
        if row:
            try:
                return json.loads(row['result'])
            except json.JSONDecodeError:
                return row['result']
        return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """设置缓存"""
        expires_at = (datetime.now() + timedelta(seconds=ttl_seconds)).isoformat()
        result_json = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        
        sql = """
            INSERT OR REPLACE INTO analytics_cache (cache_key, cache_type, result, expires_at)
            VALUES (?, ?, ?, ?)
        """
        cache_type = key.split('_')[0] if '_' in key else 'general'
        
        try:
            with self.db.get_connection() as conn:
                conn.execute(sql, (key, cache_type, result_json, expires_at))
            return True
        except Exception as e:
            print(f"缓存设置失败: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        sql = "DELETE FROM analytics_cache WHERE cache_key = ?"
        try:
            with self.db.get_connection() as conn:
                conn.execute(sql, (key,))
            return True
        except Exception:
            return False
    
    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        sql = """
            SELECT 1 FROM analytics_cache 
            WHERE cache_key = ? AND expires_at > CURRENT_TIMESTAMP
        """
        row = self.db.fetch_one(sql, (key,))
        return row is not None
    
    def clear_expired(self) -> int:
        """清理过期缓存"""
        sql = "DELETE FROM analytics_cache WHERE expires_at < CURRENT_TIMESTAMP"
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql)
            return cursor.rowcount


class RedisCache(CacheInterface):
    """Redis 缓存实现"""
    
    def __init__(
        self,
        host: str = 'localhost',
        port: int = 6379,
        db: int = 0,
        password: str = None,
        prefix: str = 'trendradar:'
    ):
        if not HAS_REDIS:
            raise ImportError("Redis 未安装，请运行: pip install redis")
        
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=True
        )
        self.prefix = prefix
    
    def _prefixed_key(self, key: str) -> str:
        return f"{self.prefix}{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        value = self.client.get(self._prefixed_key(key))
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return None
    
    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """设置缓存"""
        value_json = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
        return self.client.setex(
            self._prefixed_key(key),
            ttl_seconds,
            value_json
        )
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        return self.client.delete(self._prefixed_key(key)) > 0
    
    def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        return self.client.exists(self._prefixed_key(key)) > 0
    
    def clear_expired(self) -> int:
        """Redis 自动处理过期，这里返回 0"""
        return 0
    
    def ping(self) -> bool:
        """测试连接"""
        try:
            return self.client.ping()
        except Exception:
            return False


class CacheManager:
    """缓存管理器（自动选择缓存后端）"""
    
    def __init__(
        self,
        use_redis: bool = False,
        redis_config: dict = None,
        fallback_to_sqlite: bool = True
    ):
        self.cache: CacheInterface = None
        
        if use_redis and HAS_REDIS:
            try:
                config = redis_config or {}
                self.cache = RedisCache(**config)
                if self.cache.ping():
                    print("使用 Redis 缓存")
                else:
                    raise ConnectionError("Redis 连接失败")
            except Exception as e:
                print(f"Redis 初始化失败: {e}")
                if fallback_to_sqlite:
                    print("回退到 SQLite 缓存")
                    self.cache = SQLiteCache()
        else:
            self.cache = SQLiteCache()
            print("使用 SQLite 缓存")
    
    def get(self, key: str) -> Optional[Any]:
        return self.cache.get(key)
    
    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        return self.cache.set(key, value, ttl_seconds)
    
    def delete(self, key: str) -> bool:
        return self.cache.delete(key)
    
    def exists(self, key: str) -> bool:
        return self.cache.exists(key)
    
    def clear_expired(self) -> int:
        return self.cache.clear_expired()
    
    @staticmethod
    def generate_key(*args) -> str:
        """生成缓存键"""
        key_str = '_'.join(str(arg) for arg in args)
        return hashlib.md5(key_str.encode()).hexdigest()


# 全局缓存实例
_cache_manager: Optional[CacheManager] = None


def get_cache(use_redis: bool = False, redis_config: dict = None) -> CacheManager:
    """获取缓存管理器单例"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager(use_redis=use_redis, redis_config=redis_config)
    return _cache_manager
