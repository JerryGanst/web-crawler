"""
TrendRadar Web API 服务 (重构版)
提供新闻数据、爬虫配置和触发爬取的 REST API
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

# 导入 API 模块
from api.cache import cache, CACHE_TTL, REDIS_HOST, REDIS_PORT
from api.routes import data, news, reports, analysis
from api.routes import cache as cache_routes
from api.scheduler import scheduler

# ==================== 应用配置 ====================

BASE_DIR = Path(__file__).parent

app = FastAPI(
    title="TrendRadar API",
    description="大宗商品市场监控与供应链分析平台",
    version="2.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== 注册路由 ====================

# 根路由
@app.get("/")
async def root():
    """API 根路由"""
    return {
        "name": "TrendRadar API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "data": "/api/data",
            "news": "/api/news/{category}",
            "reports": "/api/reports",
            "analysis": "/api/generate-analysis",
            "market_analysis": "/api/market-analysis",
            "cache": "/api/cache/status"
        }
    }

# 注册数据路由
app.include_router(data.router, tags=["数据"])

# 注册新闻路由
app.include_router(news.router, tags=["新闻"])

# 注册报告路由
app.include_router(reports.router, tags=["报告"])

# 注册分析路由
app.include_router(analysis.router, tags=["分析"])

# 注册缓存管理路由
app.include_router(cache_routes.router, tags=["缓存"])


# ==================== 启动事件 ====================

@app.on_event("startup")
async def startup():
    """应用启动事件"""
    print("🚀 TrendRadar API 启动中...")
    print(f"📦 Redis: {REDIS_HOST}:{REDIS_PORT}")
    print(f"⏰ 缓存 TTL: {CACHE_TTL}秒 ({CACHE_TTL // 60}分钟)")
    
    # 启动后台调度器：预热缓存 + 定时刷新
    print("🔥 启动缓存预热和定时任务...")
    scheduler.warmup_cache()
    scheduler.start_scheduled_tasks()
    
    print("✅ 服务就绪！")


@app.on_event("shutdown")
async def shutdown():
    """应用关闭事件"""
    print("🛑 TrendRadar API 关闭中...")
    scheduler.stop()
    print("✅ 服务已关闭")


# ==================== 启动服务 ====================

if __name__ == "__main__":
    uvicorn.run(
        "server_new:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
