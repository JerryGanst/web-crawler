"""
Redis 缓存管理
"""
import os
import json
import redis
from typing import Any, Optional
from datetime import datetime


# Redis 配置（支持环境变量覆盖）
REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "49907"))
REDIS_DB = int(os.environ.get("REDIS_DB", "0"))
REDIS_PREFIX = "trendradar:"

# 缓存 TTL 配置（秒）
CACHE_TTL = 3600  # 1小时


class RedisCache:
    """Redis 缓存管理器"""
    
    def __init__(self):
        self.client = None
        self._fallback_cache = {}
        self._connect()
    
    def _connect(self):
        """连接 Redis"""
        try:
            self.client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=5
            )
            self.client.ping()
            print(f"✅ Redis 连接成功: {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            print(f"⚠️ Redis 连接失败: {e}，将使用内存缓存作为备用")
            self.client = None
    
    def _key(self, key: str) -> str:
        """添加前缀"""
        return f"{REDIS_PREFIX}{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        try:
            if self.client:
                data = self.client.get(self._key(key))
                if data:
                    return json.loads(data)
            else:
                # 使用内存缓存
                cached = self._fallback_cache.get(key)
                if cached and cached.get("expires_at", 0) > datetime.now().timestamp():
                    return cached.get("data")
        except Exception as e:
            print(f"⚠️ 缓存读取失败: {e}")
        return None
    
    def set(self, key: str, value: Any, ttl: int = CACHE_TTL) -> bool:
        """设置缓存"""
        try:
            if self.client:
                self.client.setex(self._key(key), ttl, json.dumps(value, ensure_ascii=False, default=str))
                return True
            else:
                # 使用内存缓存
                self._fallback_cache[key] = {
                    "data": value,
                    "expires_at": datetime.now().timestamp() + ttl
                }
                return True
        except Exception as e:
            print(f"⚠️ 缓存写入失败: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            if self.client:
                self.client.delete(self._key(key))
            else:
                self._fallback_cache.pop(key, None)
            return True
        except Exception as e:
            print(f"⚠️ 缓存删除失败: {e}")
            return False
    
    def clear_all(self) -> int:
        """清除所有缓存"""
        try:
            if self.client:
                keys = self.client.keys(f"{REDIS_PREFIX}*")
                if keys:
                    return self.client.delete(*keys)
            else:
                count = len(self._fallback_cache)
                self._fallback_cache.clear()
                return count
        except Exception as e:
            print(f"⚠️ 缓存清除失败: {e}")
        return 0
    
    def get_ttl(self, key: str) -> int:
        """获取剩余 TTL"""
        try:
            if self.client:
                return self.client.ttl(self._key(key))
            else:
                cached = self._fallback_cache.get(key)
                if cached:
                    return int(cached.get("expires_at", 0) - datetime.now().timestamp())
        except Exception:
            pass
        return -1
    
    def get_all_keys(self) -> list:
        """获取所有缓存键"""
        try:
            if self.client:
                keys = self.client.keys(f"{REDIS_PREFIX}*")
                return [k.replace(REDIS_PREFIX, "") for k in keys]
            else:
                return list(self._fallback_cache.keys())
        except Exception:
            return []
    
    def get_status(self) -> dict:
        """获取缓存状态"""
        try:
            if self.client:
                info = self.client.info("memory")
                keys = self.client.keys(f"{REDIS_PREFIX}*")
                return {
                    "backend": "redis",
                    "connected": True,
                    "host": f"{REDIS_HOST}:{REDIS_PORT}",
                    "keys_count": len(keys),
                    "memory_used": info.get("used_memory_human", "unknown")
                }
            else:
                return {
                    "backend": "memory",
                    "connected": False,
                    "keys_count": len(self._fallback_cache)
                }
        except Exception as e:
            return {
                "backend": "unknown",
                "connected": False,
                "error": str(e)
            }


# 全局缓存实例
cache = RedisCache()
