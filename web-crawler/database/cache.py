# coding=utf-8
"""
缓存模块
提供可选的 Redis 缓存支持，默认使用 MongoDB 持久化缓存
"""

import json
import hashlib
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, Dict

# 可选的 Redis 支持
try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    redis = None

def _load_redis_config_from_yaml() -> dict:
    config_path = Path(__file__).resolve().parent.parent / "config" / "database.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return dict(data.get("redis", {}) or {})
    except Exception:
        return {}


def _load_mongo_config_from_yaml() -> dict:
    config_path = Path(__file__).resolve().parent.parent / "config" / "database.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return dict(data.get("mongodb", {}) or {})
    except Exception:
        return {}


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


class MongoCache(CacheInterface):
    def __init__(self, mongo_db=None, mongo_cfg: Optional[dict] = None):
        if mongo_db is None:
            from .connection import get_mongo_database

            mongo_db = get_mongo_database(mongo_cfg)
        self._db = mongo_db

    @property
    def _col(self):
        return self._db["analytics_cache"]

    def get(self, key: str) -> Optional[Any]:
        now = datetime.now()
        doc = self._col.find_one(
            {"_id": key, "expires_at": {"$gt": now}},
            {"result": 1},
        )
        if not doc:
            return None
        return doc.get("result")

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        now = datetime.now()
        expires_at = now + timedelta(seconds=int(ttl_seconds))
        cache_type = key.split("_")[0] if "_" in key else "general"

        if isinstance(value, str):
            result_value: Any = value
        else:
            result_value = json.loads(json.dumps(value, ensure_ascii=False))

        update: Dict[str, Any] = {
            "$set": {
                "cache_type": cache_type,
                "result": result_value,
                "expires_at": expires_at,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        }
        try:
            self._col.update_one({"_id": key}, update, upsert=True)
            return True
        except Exception as e:
            print(f"缓存设置失败: {e}")
            return False

    def delete(self, key: str) -> bool:
        try:
            return self._col.delete_one({"_id": key}).deleted_count > 0
        except Exception:
            return False

    def exists(self, key: str) -> bool:
        now = datetime.now()
        doc = self._col.find_one(
            {"_id": key, "expires_at": {"$gt": now}},
            {"_id": 1},
        )
        return doc is not None

    def clear_expired(self) -> int:
        now = datetime.now()
        result = self._col.delete_many({"expires_at": {"$lte": now}})
        return int(result.deleted_count)


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
        fallback_to_sqlite: bool = False
    ):
        self.cache: CacheInterface = None

        mongo_cfg = _load_mongo_config_from_yaml()
        mongo_enabled = bool(mongo_cfg.get("enabled"))

        if use_redis and HAS_REDIS:
            try:
                # 1. 加载文件配置
                file_config = _load_redis_config_from_yaml()
                
                # 2. 环境变量覆盖 (保持与其他模块一致)
                env_config = {
                    'host': os.environ.get("REDIS_HOST"),
                    'port': int(os.environ.get("REDIS_PORT")) if os.environ.get("REDIS_PORT") else None,
                    'db': int(os.environ.get("REDIS_DB")) if os.environ.get("REDIS_DB") else None,
                    'password': os.environ.get("REDIS_PASSWORD"),
                }
                # 过滤 None
                env_config = {k: v for k, v in env_config.items() if v is not None}
                
                # 3. 合并配置: 传入参数 > 环境变量 > 文件配置
                final_config = file_config.copy()
                final_config.update(env_config)
                if redis_config:
                    final_config.update(redis_config)
                
                # 4. 提取 RedisCache 需要的参数
                valid_keys = ['host', 'port', 'db', 'password', 'prefix']
                clean_config = {k: v for k, v in final_config.items() if k in valid_keys}
                
                # 如果没有配置，RedisCache 会使用默认值 (localhost:6379)，这是符合预期的
                
                self.cache = RedisCache(**clean_config)
                if self.cache.ping():
                    print(f"使用 Redis 缓存 ({clean_config.get('host', 'localhost')}:{clean_config.get('port', 6379)})")
                else:
                    raise ConnectionError("Redis 连接失败")
            except Exception as e:
                print(f"Redis 初始化失败: {e}")
                if mongo_enabled:
                    try:
                        self.cache = MongoCache(mongo_cfg=mongo_cfg)
                        print("回退到 MongoDB 缓存")
                        return
                    except Exception as mongo_err:
                        print(f"MongoDB 缓存初始化失败: {mongo_err}")
                raise
        else:
            if mongo_enabled:
                try:
                    self.cache = MongoCache(mongo_cfg=mongo_cfg)
                    print("使用 MongoDB 缓存")
                except Exception as e:
                    print(f"MongoDB 缓存初始化失败: {e}")
                    raise
            else:
                raise RuntimeError("MongoDB 未启用，无法初始化缓存")
    
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
