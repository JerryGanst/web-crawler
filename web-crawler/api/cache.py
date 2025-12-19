"""
Redis 缓存管理
"""
import os
import json
import sys
import redis
from typing import Any, Optional
from datetime import datetime


# 兼容性处理：允许通过 api.cache.redis 路径进行打补丁
# 部分单元测试使用 patch("api.cache.redis.Redis")，需要确保此模块可被导入
sys.modules.setdefault(__name__ + ".redis", redis)

# 加载配置
def _load_redis_config():
    try:
        # 假设当前文件在 api/cache.py，向上两级找到 config/database.yaml
        from pathlib import Path
        import yaml
        config_path = Path(__file__).resolve().parent.parent / "config" / "database.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return data.get("redis", {})
    except Exception as e:
        print(f"⚠️ 加载 Redis 配置失败: {e}")
    return {}

_redis_conf = _load_redis_config()

# Redis 配置（支持环境变量覆盖，优先使用配置文件）
REDIS_HOST = os.environ.get("REDIS_HOST", _redis_conf.get("host", "localhost"))
REDIS_PORT = int(os.environ.get("REDIS_PORT", _redis_conf.get("port", 49907)))
REDIS_DB = int(os.environ.get("REDIS_DB", _redis_conf.get("db", 0)))
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", _redis_conf.get("password", None))
REDIS_PREFIX = "trendradar:"
REDIS_SOCKET_TIMEOUT = float(os.environ.get("REDIS_SOCKET_TIMEOUT", "2"))
REDIS_CONNECT_TIMEOUT = float(os.environ.get("REDIS_CONNECT_TIMEOUT", "2"))

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
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
                socket_timeout=REDIS_SOCKET_TIMEOUT,
                retry_on_timeout=True
            )
            self.client.ping()
            print(f"✅ Redis 连接成功: {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            print(f"⚠️ Redis 连接失败: {e}，将使用内存缓存作为备用")
            self.client = None

    def _disable_redis(self, error: Exception):
        try:
            print(f"⚠️ Redis 操作失败: {error}，切换到内存缓存")
        finally:
            self.client = None
    
    def _key(self, key: str) -> str:
        """添加前缀"""
        # 如果 key 已经包含前缀，则不重复添加
        if key.startswith(REDIS_PREFIX):
            return key
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
            if self.client:
                self._disable_redis(e)
            else:
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
            if self.client:
                self._disable_redis(e)
                return self.set(key, value, ttl=ttl)
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
            if self.client:
                self._disable_redis(e)
                return self.delete(key)
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
            if self.client:
                self._disable_redis(e)
                return self.clear_all()
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
            if self.client:
                self.client = None
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
            if self.client:
                self.client = None
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
            if self.client:
                self._disable_redis(e)
                return self.get_status()
            return {"backend": "unknown", "connected": False, "error": str(e)}


# 全局缓存实例
cache = RedisCache()
