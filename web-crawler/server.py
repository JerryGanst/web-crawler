"""
TrendRadar Web API 服务 (重构版)
提供新闻数据、爬虫配置和触发爬取的 REST API
"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
from contextlib import asynccontextmanager

# 导入 API 模块
from api.cache import cache, CACHE_TTL, REDIS_HOST, REDIS_PORT
from api.routes import data, news, reports, analysis
from api.routes import analysis_v3  # V3 模块化分析
from api.routes import cache as cache_routes
from api.scheduler import scheduler

# ==================== 应用配置 ====================

BASE_DIR = Path(__file__).parent
FRONTEND_DIR = BASE_DIR / "frontend" / "dist"


# ==================== 生命周期管理 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理 (替代 deprecated on_event)"""
    # 启动
    print("🚀 TrendRadar API 启动中...")
    print(f"📦 Redis: {REDIS_HOST}:{REDIS_PORT}")
    print(f"⏰ 缓存 TTL: {CACHE_TTL}秒 ({CACHE_TTL // 60}分钟)")
    
    # 启动后台调度器：预热缓存 + 定时刷新
    print("🔥 启动缓存预热和定时任务...")
    scheduler.warmup_cache()
    scheduler.start_scheduled_tasks()
    
    print("✅ 服务就绪！")
    
    yield
    
    # 关闭
    print("🛑 TrendRadar API 关闭中...")
    scheduler.stop()
    print("✅ 服务已关闭")


app = FastAPI(
    title="TrendRadar API",
    description="大宗商品市场监控与供应链分析平台",
    version="2.0.0",
    lifespan=lifespan  # 使用新的 lifespan 管理
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 性能监控中间件
@app.middleware("http")
async def add_process_time_header(request, call_next):
    import time
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response

# ==================== 注册路由 ====================

# API 状态路由
@app.get("/api/status")
async def api_status():
    """API 状态路由"""
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
            "analysis_v3": "/api/generate-analysis-v3",  # 模块化版本
            "market_analysis": "/api/market-analysis",
            "cache": "/api/cache/status"
        }
    }

# 根路由 - 返回前端页面
@app.get("/")
async def root():
    """返回前端 SPA 页面"""
    if FRONTEND_DIR.exists():
        return FileResponse(FRONTEND_DIR / "index.html")
    return {"message": "Frontend not built. Run: cd frontend && npm run build"}

# 注册数据路由
app.include_router(data.router, tags=["数据"])

# 注册新闻路由
app.include_router(news.router, tags=["新闻"])

# 注册报告路由
app.include_router(reports.router, tags=["报告"])

# 注册分析路由
app.include_router(analysis.router, tags=["分析"])

# 注册 V3 模块化分析路由
app.include_router(analysis_v3.router, tags=["分析V3"])

# 注册缓存管理路由
app.include_router(cache_routes.router, tags=["缓存"])


# ==================== 静态文件服务 ====================

# 挂载静态资源目录
if FRONTEND_DIR.exists():
    app.mount("/js", StaticFiles(directory=FRONTEND_DIR / "js"), name="js")
    app.mount("/css", StaticFiles(directory=FRONTEND_DIR / "css"), name="css")
    app.mount("/chunks", StaticFiles(directory=FRONTEND_DIR / "chunks"), name="chunks")
    app.mount("/pages", StaticFiles(directory=FRONTEND_DIR / "pages"), name="pages")


# ==================== 启动服务 ====================

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # 避免 watchfiles 监控虚拟环境导致无限重启
        reload_dirs=[str(BASE_DIR)],
        reload_excludes=[
            ".venv/*",
            "*/site-packages/*",
            "*/pip/*",
        ],
    )
