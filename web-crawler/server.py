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
from api.routes import analysis_v4  # V4 模块化分析
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

# CORS 配置 - 限定白名单以提升安全性
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",                  # 前端开发服务器
        "http://127.0.0.1:5173",                  # 前端开发服务器（IP访问）
        "http://localhost:8000",                  # 后端本地服务
        "http://127.0.0.1:8000",                  # 后端本地服务（IP访问）
        "https://ai.luxshare-tech.com",           # AI平台正式环境
        "https://ai-test.luxshare-tech.com",      # AI平台测试环境
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 防止被其他网站 iframe 嵌入
@app.middleware("http")
async def add_frame_protection(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
    return response

# 防止被其他网站 iframe 嵌入 + Referrer 检查（严格模式）
@app.middleware("http")
async def add_frame_protection(request, call_next):
    from fastapi.responses import JSONResponse
    from urllib.parse import urlparse

    # 允许的来源域名白名单
    ALLOWED_REFERRERS = [
        "localhost",
        "127.0.0.1",
        "ai.luxshare-tech.com",         # AI平台正式环境
        "ai-test.luxshare-tech.com",    # AI平台测试环境
    ]

    # 允许无需 referrer 检查的路径（API接口等）
    BYPASS_PATHS = [
        "/api/",        # API 接口跳过检查
        "/docs",        # Swagger 文档
        "/openapi.json",
    ]

    request_path = request.url.path

    # API 接口跳过 referrer 检查
    if any(request_path.startswith(path) for path in BYPASS_PATHS):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
        return response

    # 获取 referrer 和当前访问的 host
    referrer = request.headers.get("referer", "")
    current_host = request.headers.get("host", "").split(":")[0]  # 去掉端口号

    # 检查是否允许访问
    is_allowed = False

    if referrer:
        referrer_host = urlparse(referrer).hostname or ""
        # 检查 referrer 是否在白名单
        is_allowed = any(
            referrer_host == allowed or referrer_host.endswith(f".{allowed}")
            for allowed in ALLOWED_REFERRERS
        )
        # 允许同站点内部跳转（TrendRadar 内部页面互跳）
        if referrer_host == current_host:
            is_allowed = True
    else:
        # 没有 referrer，检查是否是允许的 host 直接访问
        is_allowed = any(
            current_host == allowed or current_host.endswith(f".{allowed}")
            for allowed in ALLOWED_REFERRERS
        )

    if not is_allowed:
        return JSONResponse(
            status_code=403,
            content={
                "error": "Access Denied",
                "message": "未授权的访问来源",
                "detail": "请通过授权渠道访问 TrendRadar。"
            }
        )

    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
    return response

# ==================== 注册路由 ====================

# API 状态路由
@app.get("/api/status")
async def api_status():
    """API 状态路由"""
    import time
    return {
        "name": "TrendRadar API",
        "version": "2.0.0",
        "status": "running",
        "timestamp": time.time(),
        "docs": "/docs",
        "endpoints": {
            "data": "/api/data",
            "news": "/api/news/{category}",
            "reports": "/api/reports",
            "analysis": "/api/generate-analysis",
            "analysis_v4": "/api/generate-analysis-v4",  # 模块化版本
            "market_analysis": "/api/market-analysis",
            "cache": "/api/cache/status"
        }
    }

# 根路由 - 返回 API 信息（如果是后端模式）或前端页面
@app.get("/")
async def root():
    # 优先检查是否有构建好的前端
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    
    # 否则返回 API 信息
    return {
        "name": "TrendRadar API",
        "version": "2.0.0",
        "status": "running",
        "message": "Frontend not found, running in API-only mode"
    }

# 注册数据路由
app.include_router(data.router, tags=["数据"])

# 注册新闻路由
app.include_router(news.router, tags=["新闻"])

# 注册报告路由
app.include_router(reports.router, tags=["报告"])

# 注册分析路由
app.include_router(analysis.router, tags=["分析"])

# 注册 V4 模块化分析路由
app.include_router(analysis_v4.router, tags=["分析V4"])

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
