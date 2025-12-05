"""
缓存管理 API 路由
"""
from fastapi import APIRouter
from ..cache import cache

router = APIRouter()


@router.get("/api/cache/status")
async def get_cache_status():
    """获取缓存状态"""
    status = cache.get_status()
    keys = cache.get_all_keys()
    
    # 获取每个键的详细信息
    key_details = []
    for key in keys:
        ttl = cache.get_ttl(key)
        key_details.append({
            "key": key,
            "ttl": ttl,
            "ttl_human": f"{ttl // 60}分{ttl % 60}秒" if ttl > 0 else "已过期"
        })
    
    return {
        **status,
        "keys": key_details
    }


@router.post("/api/cache/clear")
async def clear_cache():
    """清除所有缓存"""
    count = cache.clear_all()
    return {
        "status": "success",
        "message": f"已清除 {count} 个缓存键"
    }


@router.delete("/api/cache/{key}")
async def delete_cache_key(key: str):
    """删除指定缓存键"""
    cache.delete(key)
    return {
        "status": "success",
        "message": f"已删除缓存键: {key}"
    }
