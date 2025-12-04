"""
TrendRadar Web API 服务
提供新闻数据、爬虫配置和触发爬取的 REST API
"""
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import yaml
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import time
import threading

# ==================== 简单缓存 ====================
class SimpleCache:
    """简单的内存缓存，带过期时间"""
    def __init__(self, ttl_seconds: int = 300):  # 默认5分钟
        self.cache = {}
        self.ttl = ttl_seconds
        self.lock = threading.Lock()
    
    def get(self, key: str):
        with self.lock:
            if key in self.cache:
                data, expire_time = self.cache[key]
                if time.time() < expire_time:
                    return data
                del self.cache[key]
        return None
    
    def set(self, key: str, value):
        with self.lock:
            self.cache[key] = (value, time.time() + self.ttl)
    
    def clear(self):
        with self.lock:
            self.cache.clear()

# 全局缓存实例
news_cache = SimpleCache(ttl_seconds=180)  # 新闻缓存3分钟
data_cache = SimpleCache(ttl_seconds=120)  # 数据缓存2分钟

# 初始化 FastAPI
app = FastAPI(
    title="TrendRadar API",
    description="热点新闻聚合与推送服务",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路径配置
BASE_DIR = Path(__file__).parent
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"
SCRAPERS_CONFIG_PATH = BASE_DIR / "config" / "scrapers.yaml"
OUTPUT_DIR = BASE_DIR / "output"


def load_config() -> Dict:
    """加载配置"""
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# ==================== 数据模型 ====================

class CrawlRequest(BaseModel):
    category: str
    include_custom: bool = True

class PushRequest(BaseModel):
    category: str
    data: List[Dict]

class ReportPushRequest(BaseModel):
    title: str
    content: str

class AnalysisRequest(BaseModel):
    company_name: str = "立讯精密"
    competitors: List[str] = []
    upstream: List[str] = []
    downstream: List[str] = []
    news: List[Dict] = []


# ==================== API 路由 ====================

@app.get("/")
async def root():
    """API 根路径"""
    return {
        "name": "TrendRadar API",
        "version": "1.0.0",
        "endpoints": {
            "/api/categories": "获取所有分类",
            "/api/platforms": "获取所有平台",
            "/api/news/{category}": "获取指定分类的新闻",
            "/api/crawl": "触发爬取",
            "/api/config": "获取/更新配置",
        }
    }


@app.get("/api/categories")
async def get_categories():
    """获取所有分类"""
    config = load_config()
    categories = config.get("categories", {})
    
    result = []
    for key, value in categories.items():
        result.append({
            "id": key,
            "name": value.get("name", key),
            "keywords": value.get("keywords", [])
        })
    
    return {"categories": result}


@app.get("/api/platforms")
async def get_platforms():
    """获取所有平台"""
    config = load_config()
    platforms = config.get("platforms", [])
    
    # 按分类分组
    by_category = {}
    for p in platforms:
        cat = p.get("category", "other")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(p)
    
    return {
        "platforms": platforms,
        "by_category": by_category,
        "total": len(platforms)
    }


@app.get("/api/data")
async def get_data():
    """
    获取大宗商品市场数据（数据看板专用）
    返回贵金属、能源、工业金属、农产品等大宗商品数据
    """
    # 检查缓存
    cached = data_cache.get("commodity_data")
    if cached:
        cached["cached"] = True
        return cached
    
    try:
        from scrapers.commodity import CommodityScraper
        
        scraper = CommodityScraper()
        data = scraper.scrape()
        
        # 按分类排序：贵金属 > 能源 > 工业金属 > 农产品
        category_order = {'贵金属': 0, '能源': 1, '工业金属': 2, '农产品': 3, '其他': 4}
        data.sort(key=lambda x: category_order.get(x.get('category', '其他'), 4))
        
        result = {
            "data": data,
            "source": "TrendRadar Commodity",
            "cached": False,
            "categories": list(set(item.get('category', '其他') for item in data))
        }
        data_cache.set("commodity_data", result)
        return result
    except Exception as e:
        print(f"获取大宗商品数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/commodity-news")
async def get_commodity_news():
    """
    获取大宗商品相关新闻（市场快讯专用）
    筛选财经新闻中与大宗商品相关的内容
    """
    # 检查缓存
    cached = news_cache.get("commodity_news")
    if cached:
        cached["cached"] = True
        return cached
    
    try:
        from scrapers.unified import UnifiedDataSource
        ds = UnifiedDataSource()
        
        # 获取财经新闻
        data = ds.crawl_category("finance", include_custom=False)
        
        # 大宗商品关键词
        commodity_keywords = [
            '黄金', '白银', '原油', '石油', '天然气', '铜', '铝', '锌',
            '玉米', '小麦', '大豆', '期货', '大宗商品', '贵金属', '有色金属',
            'gold', 'silver', 'oil', 'copper', 'commodit', 'futures',
            '布伦特', 'WTI', 'COMEX', 'LME', '纽约', '伦敦金属'
        ]
        
        # 筛选相关新闻
        commodity_news = []
        for item in data:
            title = (item.get('title', '') or '').lower()
            if any(kw.lower() in title for kw in commodity_keywords):
                commodity_news.append(item)
        
        # 如果筛选结果太少，返回前10条财经新闻作为补充
        if len(commodity_news) < 5:
            commodity_news = data[:10]
        
        result = {
            "data": commodity_news[:15],
            "total": len(commodity_news),
            "cached": False,
            "timestamp": datetime.now().isoformat()
        }
        news_cache.set("commodity_news", result)
        return result
    except Exception as e:
        print(f"获取大宗商品新闻失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 供应链新闻缓存（需要放在通配符路由之前）
_supply_chain_news_cache = {
    "data": [],
    "timestamp": None
}

@app.get("/api/news/supply-chain")
async def get_supply_chain_news():
    """获取供应链相关新闻（带缓存，5分钟刷新一次）"""
    from datetime import datetime, timedelta
    
    # 检查缓存是否有效（5分钟内）
    if _supply_chain_news_cache["timestamp"]:
        cache_age = datetime.now() - _supply_chain_news_cache["timestamp"]
        if cache_age < timedelta(minutes=5) and _supply_chain_news_cache["data"]:
            return {
                "status": "cache",
                "data": _supply_chain_news_cache["data"],
                "count": len(_supply_chain_news_cache["data"]),
                "cached_at": _supply_chain_news_cache["timestamp"].isoformat()
            }
    
    # 抓取新闻
    keywords = [
        # 核心公司
        "立讯", "歌尔", "蓝思", "富联", "富士康", "京东方", "BOE",
        "欣旺达", "德赛", "舜宇", "鹏鼎", "东山精密", "领益", "瑞声",
        # 客户
        "苹果", "Apple", "iPhone", "AirPods", "Vision Pro", "iPad", "Mac",
        "华为", "Huawei", "鸿蒙", "Mate", "荣耀",
        "小米", "OPPO", "vivo", "三星", "Samsung",
        # 行业关键词
        "消费电子", "果链", "代工", "供应链", "芯片", "半导体",
        "智能手机", "穿戴", "耳机", "VR", "AR", "XR",
        "新能源汽车", "电动汽车", "动力电池", "锂电",
        "AI", "人工智能", "算力", "GPU", "英伟达"
    ]
    
    news = fetch_realtime_news(keywords)
    
    # 更新缓存
    _supply_chain_news_cache["data"] = news
    _supply_chain_news_cache["timestamp"] = datetime.now()
    
    return {
        "status": "success",
        "data": news,
        "count": len(news),
        "fetched_at": datetime.now().isoformat()
    }


@app.get("/api/news/{category}")
async def get_news(category: str, include_custom: bool = True, refresh: bool = False):
    """
    获取指定分类的新闻（带缓存）
    
    Args:
        category: 分类名称 (finance, news, social, tech, all)
        include_custom: 是否包含自定义爬虫数据
        refresh: 是否强制刷新缓存
    """
    cache_key = f"news_{category}_{include_custom}"
    
    # 检查缓存
    if not refresh:
        cached = news_cache.get(cache_key)
        if cached:
            cached["cached"] = True
            return cached
    
    try:
        from scrapers.unified import UnifiedDataSource
        ds = UnifiedDataSource()
        
        data = ds.crawl_category(category, include_custom=include_custom)
        
        # 统计
        sources = {}
        for item in data:
            src = item.get("platform_name", item.get("platform", "unknown"))
            sources[src] = sources.get(src, 0) + 1
        
        result = {
            "category": category,
            "total": len(data),
            "sources": sources,
            "data": data,
            "timestamp": datetime.now().isoformat(),
            "cached": False
        }
        news_cache.set(cache_key, result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/crawl")
async def trigger_crawl(request: CrawlRequest, background_tasks: BackgroundTasks):
    """
    触发爬取任务
    
    Args:
        category: 要爬取的分类
        include_custom: 是否包含自定义爬虫
    """
    try:
        # 供应链分类特殊处理（同时支持 supply-chain 和 supply_chain）
        if request.category in ["supply-chain", "supply_chain"]:
            keywords = [
                "立讯", "歌尔", "蓝思", "富联", "富士康", "京东方", "BOE",
                "欣旺达", "德赛", "舜宇", "鹏鼎", "东山精密", "领益", "瑞声",
                "苹果", "Apple", "iPhone", "AirPods", "Vision Pro", "iPad", "Mac",
                "华为", "Huawei", "鸿蒙", "Mate", "荣耀",
                "小米", "OPPO", "vivo", "三星", "Samsung",
                "消费电子", "果链", "代工", "供应链", "芯片", "半导体",
                "AI", "人工智能", "算力", "GPU", "英伟达"
            ]
            data = fetch_realtime_news(keywords)
            
            # 更新缓存
            _supply_chain_news_cache["data"] = data
            _supply_chain_news_cache["timestamp"] = datetime.now()
            
            return {
                "status": "success",
                "category": request.category,
                "total": len(data),
                "message": f"已爬取 {len(data)} 条供应链相关新闻"
            }
        
        from scrapers.unified import UnifiedDataSource
        ds = UnifiedDataSource()
        
        # 爬取数据
        data = ds.crawl_category(request.category, include_custom=request.include_custom)
        
        # 获取 webhook URL
        config = load_config()
        webhook_url = config.get("notification", {}).get("webhooks", {}).get("wework_url", "")
        
        # 异步推送
        if webhook_url and data:
            background_tasks.add_task(ds.push_to_wework, data, request.category, webhook_url)
        
        return {
            "status": "success",
            "category": request.category,
            "total": len(data),
            "message": f"已爬取 {len(data)} 条数据" + ("，正在推送..." if webhook_url else "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
async def get_config():
    """获取配置"""
    config = load_config()
    
    # 隐藏敏感信息
    if "notification" in config and "webhooks" in config["notification"]:
        webhooks = config["notification"]["webhooks"]
        for key in webhooks:
            if webhooks[key] and len(str(webhooks[key])) > 10:
                webhooks[key] = webhooks[key][:10] + "***"
    
    return config


# 报告存储目录
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

@app.post("/api/push-report")
async def push_report(request: ReportPushRequest):
    """推送分析报告到企业微信（渲染为图片直接发送）"""
    import requests
    import urllib3
    import hashlib
    import base64
    import markdown
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    config = load_config()
    webhook_urls = config.get("notification", {}).get("webhooks", {}).get("wework_url", "")
    
    # 支持单个URL或URL列表
    if isinstance(webhook_urls, str):
        webhook_urls = [webhook_urls] if webhook_urls else []
    elif not webhook_urls:
        webhook_urls = []
    
    if not webhook_urls:
        return {"status": "error", "message": "未配置企业微信 Webhook，请在 config/config.yaml 中设置 wework_url"}
    
    try:
        # 生成报告文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_id = hashlib.md5(f"{request.title}{timestamp}".encode()).hexdigest()[:8]
        filename = f"report_{timestamp}_{report_id}.md"
        filepath = REPORTS_DIR / filename
        
        # 写入 Markdown 文件
        full_report = f"""# {request.title}

> 📅 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
> 🤖 来源：立讯技术产业链分析助手

---

{request.content}

---
*本报告由 AI 自动生成，仅供参考，不构成投资建议。*
"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(full_report)
        
        print(f"📄 报告已保存: {filepath}")
        
        # 渲染报告为图片
        image_data = await render_report_to_image(request.title, request.content, timestamp)
        
        if image_data:
            # 计算图片MD5
            image_md5 = hashlib.md5(image_data).hexdigest()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # 发送图片到企业微信
            payload = {
                "msgtype": "image",
                "image": {
                    "base64": image_base64,
                    "md5": image_md5
                }
            }
            
            success_count = 0
            errors = []
            for webhook_url in webhook_urls:
                try:
                    resp = requests.post(webhook_url, json=payload, timeout=60, verify=False)
                    if resp.status_code == 200 and resp.json().get("errcode") == 0:
                        success_count += 1
                        print(f"✅ 图片推送成功: {webhook_url[:50]}...")
                    else:
                        errors.append(f"{webhook_url[:30]}: {resp.json().get('errmsg', 'HTTP ' + str(resp.status_code))}")
                except Exception as e:
                    errors.append(f"{webhook_url[:30]}: {str(e)[:50]}")
            
            if success_count > 0:
                print(f"✅ 推送完成: {success_count}/{len(webhook_urls)} 个群成功")
                return {
                    "status": "success",
                    "message": f"报告图片已推送到 {success_count}/{len(webhook_urls)} 个群",
                    "filename": filename,
                    "errors": errors if errors else None
                }
            else:
                return {"status": "error", "message": f"所有推送均失败: {'; '.join(errors)}"}
        else:
            # 图片渲染失败，降级为Markdown摘要
            print("⚠️ 图片渲染失败，降级为Markdown摘要发送")
            summary = request.content[:3500]
            if len(request.content) > 3500:
                last_newline = summary.rfind('\n')
                if last_newline > 2000:
                    summary = summary[:last_newline]
                summary += "\n\n... *(报告较长，已截断)*"
            
            message = f"""📊 **{request.title}**
━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━━━━━

{summary}"""
            
            payload = {"msgtype": "markdown", "markdown": {"content": message}}
            
            success_count = 0
            errors = []
            for webhook_url in webhook_urls:
                try:
                    resp = requests.post(webhook_url, json=payload, timeout=30, verify=False)
                    if resp.status_code == 200 and resp.json().get("errcode") == 0:
                        success_count += 1
                except Exception as e:
                    errors.append(str(e)[:50])
            
            return {
                "status": "partial",
                "message": f"图片渲染失败，已发送文字摘要到 {success_count}/{len(webhook_urls)} 个群",
                "errors": errors if errors else None
            }
        
    except Exception as e:
        error_msg = str(e)
        if "SSL" in error_msg or "ssl" in error_msg:
            return {"status": "error", "message": "SSL连接失败，可能是代理/VPN导致。请尝试关闭代理后重试。"}
        return {"status": "error", "message": error_msg}


async def render_report_to_image(title: str, content: str, timestamp: str) -> bytes:
    """使用 Playwright 将报告渲染为图片（压缩至2MB以内）"""
    import markdown
    from io import BytesIO
    
    try:
        from playwright.async_api import async_playwright
        from PIL import Image
        
        # 如果内容太长，截断（避免图片过大）
        max_content_length = 8000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n\n... *(报告较长，已截断显示)*"
        
        # 转换 Markdown 为 HTML
        html_content = markdown.markdown(
            content,
            extensions=['tables', 'fenced_code', 'nl2br']
        )
        
        # 生成完整的 HTML 页面
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            padding: 40px;
            min-width: 800px;
            max-width: 1000px;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 30px;
            border-radius: 16px;
            margin-bottom: 30px;
            box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
        }}
        .header h1 {{
            font-size: 28px;
            margin-bottom: 10px;
            color: white;
        }}
        .header .meta {{
            font-size: 14px;
            opacity: 0.9;
            color: rgba(255,255,255,0.9);
        }}
        .content {{
            background: rgba(255,255,255,0.05);
            padding: 30px;
            border-radius: 16px;
            line-height: 1.8;
        }}
        h1, h2, h3, h4 {{
            color: #a5b4fc;
            margin: 20px 0 15px 0;
        }}
        h2 {{ font-size: 22px; border-bottom: 2px solid #4f46e5; padding-bottom: 10px; }}
        h3 {{ font-size: 18px; }}
        p {{ margin: 12px 0; }}
        ul, ol {{ margin: 12px 0; padding-left: 24px; }}
        li {{ margin: 6px 0; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            background: rgba(0,0,0,0.2);
            border-radius: 8px;
            overflow: hidden;
        }}
        th {{
            background: rgba(79, 70, 229, 0.3);
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        tr:last-child td {{ border-bottom: none; }}
        code {{
            background: rgba(0,0,0,0.3);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Fira Code', monospace;
        }}
        pre {{
            background: rgba(0,0,0,0.3);
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
        }}
        blockquote {{
            border-left: 4px solid #4f46e5;
            padding-left: 16px;
            margin: 16px 0;
            color: #a0a0b0;
        }}
        .footer {{
            margin-top: 30px;
            text-align: center;
            font-size: 12px;
            color: #6b7280;
        }}
        strong {{ color: #fbbf24; }}
        em {{ color: #a5b4fc; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 {title}</h1>
        <div class="meta">📅 生成时间：{timestamp} | 🤖 立讯技术产业链分析助手</div>
    </div>
    <div class="content">
        {html_content}
    </div>
    <div class="footer">
        本报告由 AI 自动生成，仅供参考，不构成投资建议。
    </div>
</body>
</html>"""
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={'width': 800, 'height': 600})
            await page.set_content(full_html, wait_until='networkidle')
            
            # 获取内容高度并截图（限制最大高度）
            height = await page.evaluate('document.body.scrollHeight')
            max_height = 4000  # 限制最大高度
            await page.set_viewport_size({'width': 800, 'height': min(height + 50, max_height)})
            
            screenshot = await page.screenshot(full_page=True, type='jpeg', quality=85)
            await browser.close()
            
            # 如果图片仍然太大（>1.8MB），进一步压缩
            if len(screenshot) > 1800000:
                img = Image.open(BytesIO(screenshot))
                # 缩小尺寸
                new_width = int(img.width * 0.7)
                new_height = int(img.height * 0.7)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                output = BytesIO()
                img.save(output, format='JPEG', quality=75, optimize=True)
                screenshot = output.getvalue()
            
            print(f"📸 报告图片生成成功: {len(screenshot) / 1024:.1f} KB")
            return screenshot
            
    except Exception as e:
        print(f"❌ 图片渲染失败: {e}")
        return None


@app.get("/api/reports/{filename}")
async def download_report(filename: str, format: str = "html"):
    """
    下载报告文件
    
    Args:
        filename: 报告文件名
        format: 输出格式 - html(默认，浏览器渲染) 或 md(原始Markdown下载)
    """
    from fastapi.responses import FileResponse, HTMLResponse
    
    # 安全检查：防止路径遍历
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    
    filepath = REPORTS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="报告不存在")
    
    # 读取 Markdown 内容
    with open(filepath, 'r', encoding='utf-8') as f:
        md_content = f.read()
    
    # 如果请求原始 Markdown 下载
    if format == "md":
        return FileResponse(
            path=str(filepath),
            filename=filename,
            media_type="text/markdown"
        )
    
    # 默认返回 HTML 渲染版本
    import markdown
    import re
    
    # 预处理 Markdown：修复常见格式问题
    def preprocess_markdown(text):
        lines = text.split('\n')
        result = []
        in_table = False
        table_has_separator = False
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 检测表格行（以 | 开头和结尾）
            is_table_row = stripped.startswith('|') and stripped.endswith('|')
            is_separator = bool(re.match(r'^\|[\s\-:|]+\|$', stripped))
            
            if is_table_row:
                if not in_table:
                    in_table = True
                    table_has_separator = False
                
                # 如果是分隔符行，确保格式正确
                if is_separator:
                    parts = stripped.split('|')
                    normalized = '|' + '|'.join([' --- ' if p.strip().replace('-', '').replace(':', '') == '' else p for p in parts[1:-1]]) + '|'
                    result.append(normalized)
                    table_has_separator = True
                else:
                    if in_table and not table_has_separator and len(result) > 0:
                        prev_line = result[-1].strip()
                        if prev_line.startswith('|') and prev_line.endswith('|'):
                            cols = prev_line.count('|') - 1
                            separator = '|' + ' --- |' * cols
                            result.append(separator)
                            table_has_separator = True
                    result.append(line)
            else:
                if in_table and stripped == '':
                    in_table = False
                    table_has_separator = False
                result.append(line)
        
        return '\n'.join(result)
    
    # 预处理
    processed_content = preprocess_markdown(md_content)
    
    # 转换 Markdown 为 HTML
    html_content = markdown.markdown(
        processed_content,
        extensions=['tables', 'fenced_code', 'codehilite', 'toc', 'nl2br']
    )
    
    # 后处理：为表格添加容器以支持横向滚动
    html_content = re.sub(
        r'<table>',
        '<div class="table-wrapper"><table>',
        html_content
    )
    html_content = re.sub(
        r'</table>',
        '</table></div>',
        html_content
    )
    
    # 后处理：检测并转换JSON雷达图为真实图表
    import json
    radar_charts = []
    chart_id = 0
    
    def replace_radar_chart(match):
        nonlocal chart_id
        json_str = match.group(1)
        try:
            data = json.loads(json_str)
            if data.get('type') == 'radar' or 'dimensions' in data:
                chart_id += 1
                radar_charts.append({'id': f'radar-chart-{chart_id}', 'data': data})
                title = data.get('title', '竞争力对比雷达图')
                return f'<div class="chart-container"><h4 class="chart-title">{title}</h4><canvas id="radar-chart-{chart_id}"></canvas></div>'
        except:
            pass
        return match.group(0)
    
    # 匹配 JSON 代码块（包括 json:radar-chart 和普通 json）
    html_content = re.sub(
        r'<code class="[^"]*">(\{[\s\S]*?"dimensions"[\s\S]*?\})</code>',
        replace_radar_chart,
        html_content
    )
    # 也匹配 pre > code 结构
    html_content = re.sub(
        r'<pre><code[^>]*>(\{[\s\S]*?"dimensions"[\s\S]*?\})</code></pre>',
        replace_radar_chart,
        html_content
    )
    
    # 生成雷达图初始化JS代码
    radar_init_js = ""
    colors = [
        ('rgba(99, 102, 241, 0.8)', 'rgba(99, 102, 241, 0.2)'),   # 紫色
        ('rgba(34, 197, 94, 0.8)', 'rgba(34, 197, 94, 0.2)'),     # 绿色
        ('rgba(245, 158, 11, 0.8)', 'rgba(245, 158, 11, 0.2)'),   # 橙色
        ('rgba(239, 68, 68, 0.8)', 'rgba(239, 68, 68, 0.2)'),     # 红色
        ('rgba(59, 130, 246, 0.8)', 'rgba(59, 130, 246, 0.2)'),   # 蓝色
        ('rgba(168, 85, 247, 0.8)', 'rgba(168, 85, 247, 0.2)'),   # 紫红
    ]
    
    for chart in radar_charts:
        chart_data = chart['data']
        dimensions = chart_data.get('dimensions', [])
        companies = chart_data.get('companies', {})
        
        datasets_js = []
        for i, (company, scores) in enumerate(companies.items()):
            color_border, color_bg = colors[i % len(colors)]
            datasets_js.append(f'''{{
                label: '{company}',
                data: {scores},
                borderColor: '{color_border}',
                backgroundColor: '{color_bg}',
                borderWidth: 2,
                pointBackgroundColor: '{color_border}',
                pointRadius: 4
            }}''')
        
        radar_init_js += f'''
        new Chart(document.getElementById('{chart['id']}'), {{
            type: 'radar',
            data: {{
                labels: {json.dumps(dimensions, ensure_ascii=False)},
                datasets: [{','.join(datasets_js)}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: true,
                scales: {{
                    r: {{
                        min: 0,
                        max: 10,
                        ticks: {{ stepSize: 2, color: '#6b6b7a', backdropColor: 'transparent' }},
                        grid: {{ color: 'rgba(255,255,255,0.1)' }},
                        angleLines: {{ color: 'rgba(255,255,255,0.1)' }},
                        pointLabels: {{ color: '#a0a0b0', font: {{ size: 12 }} }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{ color: '#a0a0b0', padding: 20, font: {{ size: 12 }} }}
                    }}
                }}
            }}
        }});
        '''
    
    # 生成完整 HTML 页面（优化版）
    html_page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>立讯技术新闻专业分析助手</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-card: #1a1a24;
            --bg-hover: #22222e;
            --text-primary: #f0f0f5;
            --text-secondary: #a0a0b0;
            --text-muted: #6b6b7a;
            --accent: #6366f1;
            --accent-light: #818cf8;
            --accent-dim: rgba(99, 102, 241, 0.15);
            --success: #22c55e;
            --success-dim: rgba(34, 197, 94, 0.15);
            --warning: #f59e0b;
            --warning-dim: rgba(245, 158, 11, 0.15);
            --danger: #ef4444;
            --danger-dim: rgba(239, 68, 68, 0.15);
            --border: #2a2a3a;
            --border-light: #3a3a4a;
            --gradient-1: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            --gradient-2: linear-gradient(135deg, #0a0a0f 0%, #1a1a24 100%);
            --shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        html {{ scroll-behavior: smooth; }}
        
        body {{
            font-family: 'Inter', 'Noto Sans SC', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.75;
            font-size: 15px;
            min-height: 100vh;
        }}
        
        /* 顶部导航栏 */
        .navbar {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            height: 60px;
            background: rgba(10, 10, 15, 0.85);
            backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border);
            z-index: 1000;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 2rem;
        }}
        
        .navbar-brand {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
            font-weight: 700;
            font-size: 1.25rem;
            color: var(--text-primary);
        }}
        
        .navbar-brand svg {{
            width: 28px;
            height: 28px;
        }}
        
        .navbar-actions {{
            display: flex;
            gap: 0.75rem;
        }}
        
        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            border-radius: 8px;
            font-size: 0.875rem;
            font-weight: 500;
            text-decoration: none;
            transition: all 0.2s ease;
            cursor: pointer;
            border: none;
        }}
        
        .btn-primary {{
            background: var(--gradient-1);
            color: white;
        }}
        
        .btn-primary:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 20px rgba(99, 102, 241, 0.4);
        }}
        
        .btn-ghost {{
            background: transparent;
            color: var(--text-secondary);
            border: 1px solid var(--border);
        }}
        
        .btn-ghost:hover {{
            background: var(--bg-hover);
            color: var(--text-primary);
            border-color: var(--border-light);
        }}
        
        /* 主内容区 */
        .main {{
            max-width: 900px;
            margin: 0 auto;
            padding: 100px 2rem 4rem;
        }}
        
        /* 报告头部 */
        .report-header {{
            margin-bottom: 3rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid var(--border);
        }}
        
        .report-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 1rem;
            margin-bottom: 1.5rem;
        }}
        
        .meta-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.375rem 0.875rem;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 20px;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}
        
        /* 文章内容 */
        article {{
            color: var(--text-secondary);
        }}
        
        article h1 {{
            font-size: 2.25rem;
            font-weight: 700;
            color: var(--text-primary);
            margin: 2.5rem 0 1.5rem;
            letter-spacing: -0.02em;
            line-height: 1.3;
        }}
        
        article h1:first-child {{
            margin-top: 0;
        }}
        
        article h2 {{
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
            margin: 3rem 0 1.25rem;
            padding-bottom: 0.75rem;
            border-bottom: 2px solid var(--accent);
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        
        article h2::before {{
            content: '';
            width: 4px;
            height: 24px;
            background: var(--gradient-1);
            border-radius: 2px;
        }}
        
        article h3 {{
            font-size: 1.2rem;
            font-weight: 600;
            color: var(--text-primary);
            margin: 2rem 0 1rem;
        }}
        
        article h4 {{
            font-size: 1.05rem;
            font-weight: 600;
            color: var(--text-primary);
            margin: 1.5rem 0 0.75rem;
        }}
        
        article p {{
            margin-bottom: 1.25rem;
            color: var(--text-secondary);
        }}
        
        article strong {{
            color: var(--text-primary);
            font-weight: 600;
        }}
        
        /* 引用块 */
        article blockquote {{
            background: var(--accent-dim);
            border-left: 4px solid var(--accent);
            border-radius: 0 12px 12px 0;
            padding: 1.25rem 1.5rem;
            margin: 1.5rem 0;
        }}
        
        article blockquote p {{
            margin: 0;
            color: var(--text-primary);
        }}
        
        article blockquote strong {{
            color: var(--accent-light);
        }}
        
        /* 表格 */
        .table-wrapper {{
            overflow-x: auto;
            margin: 1.5rem 0;
            border-radius: 12px;
            border: 1px solid var(--border);
            background: var(--bg-card);
        }}
        
        article table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.875rem;
        }}
        
        article th {{
            background: var(--bg-secondary);
            color: var(--accent-light);
            font-weight: 600;
            text-align: left;
            padding: 1rem;
            white-space: nowrap;
            border-bottom: 1px solid var(--border);
        }}
        
        article td {{
            padding: 0.875rem 1rem;
            border-bottom: 1px solid var(--border);
            color: var(--text-secondary);
            vertical-align: top;
        }}
        
        article tr:last-child td {{
            border-bottom: none;
        }}
        
        article tr:hover td {{
            background: var(--bg-hover);
        }}
        
        article td strong {{
            color: var(--text-primary);
        }}
        
        /* 表格内的标记 */
        article td:first-child {{
            font-weight: 500;
        }}
        
        /* 列表 */
        article ul, article ol {{
            margin: 1rem 0 1.5rem;
            padding-left: 1.75rem;
        }}
        
        article li {{
            margin-bottom: 0.625rem;
            color: var(--text-secondary);
        }}
        
        article li::marker {{
            color: var(--accent);
        }}
        
        article li strong {{
            color: var(--text-primary);
        }}
        
        /* 代码 */
        article code {{
            background: var(--bg-secondary);
            padding: 0.2rem 0.5rem;
            border-radius: 6px;
            font-family: 'SF Mono', 'Fira Code', Consolas, monospace;
            font-size: 0.85em;
            color: var(--success);
            border: 1px solid var(--border);
        }}
        
        article pre {{
            background: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.25rem;
            overflow-x: auto;
            margin: 1.5rem 0;
        }}
        
        article pre code {{
            background: none;
            padding: 0;
            border: none;
            color: var(--text-secondary);
            font-size: 0.875rem;
        }}
        
        /* 分隔线 */
        article hr {{
            border: none;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--border-light), transparent);
            margin: 3rem 0;
        }}
        
        /* 雷达图容器 */
        .chart-container {{
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            margin: 2rem 0;
            max-width: 600px;
        }}
        
        .chart-title {{
            color: var(--accent-light);
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 1rem;
            text-align: center;
        }}
        
        .chart-container canvas {{
            max-height: 400px;
        }}
        
        /* 特殊标记样式 */
        article em {{
            color: var(--text-muted);
            font-style: italic;
        }}
        
        /* 页脚 */
        .footer {{
            margin-top: 4rem;
            padding: 2rem 0;
            border-top: 1px solid var(--border);
            text-align: center;
            color: var(--text-muted);
            font-size: 0.875rem;
        }}
        
        .footer-logo {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            margin-bottom: 0.5rem;
            color: var(--text-secondary);
            font-weight: 500;
        }}
        
        /* 返回顶部按钮 */
        .back-to-top {{
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            width: 44px;
            height: 44px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.2s;
            opacity: 0;
            visibility: hidden;
        }}
        
        .back-to-top.visible {{
            opacity: 1;
            visibility: visible;
        }}
        
        .back-to-top:hover {{
            background: var(--accent);
            border-color: var(--accent);
            color: white;
            transform: translateY(-2px);
        }}
        
        /* 响应式 */
        @media (max-width: 768px) {{
            .navbar {{
                padding: 0 1rem;
            }}
            .main {{
                padding: 80px 1rem 2rem;
            }}
            article h1 {{
                font-size: 1.75rem;
            }}
            article h2 {{
                font-size: 1.25rem;
            }}
            .table-wrapper {{
                margin-left: -1rem;
                margin-right: -1rem;
                border-radius: 0;
                border-left: none;
                border-right: none;
            }}
            article th, article td {{
                padding: 0.625rem 0.75rem;
                font-size: 0.8rem;
            }}
        }}
        
        /* 打印样式 */
        @media print {{
            .navbar, .back-to-top, .navbar-actions {{
                display: none !important;
            }}
            body {{
                background: white;
                color: #1a1a1a;
            }}
            .main {{
                padding-top: 0;
                max-width: 100%;
            }}
            article h1, article h2, article h3, article strong {{
                color: #1a1a1a;
            }}
            article p, article li, article td {{
                color: #333;
            }}
            .table-wrapper {{
                border-color: #ddd;
            }}
        }}
    </style>
</head>
<body>
    <!-- 顶部导航 -->
    <nav class="navbar">
        <div class="navbar-brand">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 6v6l4 2"/>
            </svg>
            立讯技术
        </div>
        <div class="navbar-actions">
            <a href="/api/reports/{filename}?format=md" download="{filename}" class="btn btn-ghost">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7,10 12,15 17,10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                下载 MD
            </a>
            <button onclick="window.print()" class="btn btn-primary">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M6 9V2h12v7"/>
                    <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/>
                    <rect x="6" y="14" width="12" height="8"/>
                </svg>
                打印
            </button>
        </div>
    </nav>
    
    <!-- 主内容 -->
    <main class="main">
        <article>
            {html_content}
        </article>
        
        <footer class="footer">
            <div class="footer-logo">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <path d="M12 6v6l4 2"/>
                </svg>
                立讯技术产业链分析助手
            </div>
            <p>Powered by AI · 仅供参考，不构成投资建议</p>
        </footer>
    </main>
    
    <!-- 返回顶部 -->
    <button class="back-to-top" onclick="window.scrollTo({{top:0,behavior:'smooth'}})">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="18,15 12,9 6,15"/>
        </svg>
    </button>
    
    <script>
        // 返回顶部按钮显示逻辑
        const backToTop = document.querySelector('.back-to-top');
        window.addEventListener('scroll', () => {{
            if (window.scrollY > 300) {{
                backToTop.classList.add('visible');
            }} else {{
                backToTop.classList.remove('visible');
            }}
        }});
        
        // 初始化雷达图
        document.addEventListener('DOMContentLoaded', function() {{
            {radar_init_js}
        }});
    </script>
</body>
</html>"""
    
    return HTMLResponse(content=html_page)


@app.get("/api/reports")
async def list_reports():
    """列出所有报告"""
    reports = []
    for f in sorted(REPORTS_DIR.glob("*.md"), reverse=True):
        stat = f.stat()
        reports.append({
            "filename": f.name,
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "download_url": f"http://localhost:8000/api/reports/{f.name}"
        })
    return {"reports": reports[:20]}  # 最近20份


@app.get("/api/custom-scrapers")
async def get_custom_scrapers():
    """获取自定义爬虫配置"""
    try:
        if SCRAPERS_CONFIG_PATH.exists():
            with open(SCRAPERS_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config.get("custom_scrapers", {})
        return {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/status")
async def get_status():
    """获取服务状态"""
    config = load_config()
    
    # 检查 webhook 配置
    webhooks = config.get("notification", {}).get("webhooks", {})
    wework_configured = bool(webhooks.get("wework_url"))
    
    return {
        "status": "running",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "config": {
            "platforms_count": len(config.get("platforms", [])),
            "categories_count": len(config.get("categories", {})),
            "wework_configured": wework_configured,
        }
    }


def fetch_realtime_news(keywords: list) -> list:
    """
    实时抓取供应链相关新闻
    数据源：东方财富、同花顺、新浪财经等证券网站
    """
    import requests as req
    from urllib.parse import quote
    
    all_news = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.eastmoney.com/"
    }
    
    # 上市公司股票代码映射（用于精准抓取个股新闻）
    stock_codes = {
        "立讯精密": "002475",
        "歌尔股份": "002241",
        "蓝思科技": "300433",
        "工业富联": "601138",
        "京东方A": "000725",
        "京东方": "000725",
        "舜宇光学": "02382",
        "欣旺达": "300207",
        "德赛电池": "000049",
        "鹏鼎控股": "002938",
        "东山精密": "002384",
        "领益智造": "002600",
        "瑞声科技": "02018",
        "信维通信": "300136",
        "长盈精密": "300115",
        "比亚迪": "002594",
        "宁德时代": "300750",
    }
    
    # ==================== 1. 东方财富个股新闻 ====================
    for company, code in stock_codes.items():
        if not any(kw in company for kw in keywords):
            continue
        try:
            # 东方财富个股新闻API
            url = f"https://search-api-web.eastmoney.com/search/jsonp?cb=jQuery&param=%7B%22uid%22%3A%22%22%2C%22keyword%22%3A%22{code}%22%2C%22type%22%3A%5B%22cmsArticleWebOld%22%5D%2C%22client%22%3A%22web%22%2C%22clientType%22%3A%22web%22%2C%22clientVersion%22%3A%22curr%22%2C%22param%22%3A%7B%22cmsArticleWebOld%22%3A%7B%22searchScope%22%3A%22default%22%2C%22sort%22%3A%22default%22%2C%22pageIndex%22%3A1%2C%22pageSize%22%3A10%2C%22preTag%22%3A%22%22%2C%22postTag%22%3A%22%22%7D%7D%7D"
            resp = req.get(url, headers=headers, timeout=8)
            text = resp.text
            # 解析JSONP
            if "jQuery" in text:
                import json
                json_str = text[text.index("(")+1:text.rindex(")")]
                data = json.loads(json_str)
                articles = data.get("result", {}).get("cmsArticleWebOld", [])
                for item in articles:
                    title = item.get("title", "").replace("<em>", "").replace("</em>", "")
                    if title:
                        all_news.append({
                            "title": f"[{company}] {title}",
                            "url": item.get("url", ""),
                            "source": "东方财富",
                            "stock_code": code
                        })
        except Exception as e:
            print(f"⚠️ 东方财富个股({company})抓取失败: {e}")
    
    # ==================== 2. 东方财富快讯 ====================
    try:
        url = "https://np-listapi.eastmoney.com/comm/web/getNewsByKeyword?keyword=&fields=title,url&pageSize=50&pageNo=1&type=0"
        resp = req.get(url, headers=headers, timeout=10)
        data = resp.json()
        if data.get("success") and data.get("data"):
            for item in data["data"].get("list", []):
                title = item.get("title", "")
                if any(kw in title for kw in keywords):
                    all_news.append({
                        "title": title,
                        "url": item.get("url", f"https://finance.eastmoney.com/a/{item.get('code', '')}.html"),
                        "source": "东方财富快讯"
                    })
    except Exception as e:
        print(f"⚠️ 东方财富快讯抓取失败: {e}")
    
    # ==================== 3. 东方财富7x24快讯 ====================
    try:
        url = "https://np-listapi.eastmoney.com/comm/web/getLivingList?pageSize=50&pageNo=1&type=0"
        resp = req.get(url, headers=headers, timeout=10)
        data = resp.json()
        if data.get("success") and data.get("data"):
            for item in data["data"].get("list", []):
                title = item.get("title", "") or item.get("digest", "")
                if title and any(kw in title for kw in keywords):
                    all_news.append({
                        "title": title,
                        "url": f"https://kuaixun.eastmoney.com/",
                        "source": "东方财富7x24"
                    })
    except Exception as e:
        print(f"⚠️ 东方财富7x24抓取失败: {e}")
    
    # ==================== 4. 同花顺个股新闻 ====================
    for company, code in stock_codes.items():
        if not any(kw in company for kw in keywords):
            continue
        try:
            # 同花顺个股新闻
            url = f"https://stockpage.10jqka.com.cn/ajax/code/{code}/type/news/"
            ths_headers = {**headers, "Referer": "https://stockpage.10jqka.com.cn/"}
            resp = req.get(url, headers=ths_headers, timeout=8)
            data = resp.json()
            if data.get("data"):
                for item in data["data"][:5]:
                    title = item.get("title", "")
                    if title:
                        all_news.append({
                            "title": f"[{company}] {title}",
                            "url": item.get("url", ""),
                            "source": "同花顺",
                            "stock_code": code
                        })
        except Exception as e:
            pass  # 同花顺反爬严格，静默失败
    
    # ==================== 5. 新浪财经滚动新闻 ====================
    try:
        resp = req.get(
            "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&k=&num=50",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        data = resp.json()
        if "result" in data and "data" in data["result"]:
            for item in data["result"]["data"]:
                title = item.get("title", "")
                if any(kw in title for kw in keywords):
                    all_news.append({
                        "title": title,
                        "url": item.get("url", ""),
                        "source": "新浪财经"
                    })
    except Exception as e:
        print(f"⚠️ 新浪财经抓取失败: {e}")
    
    # ==================== 6. 新浪股票新闻 ====================
    try:
        resp = req.get(
            "https://feed.mix.sina.com.cn/api/roll/get?pageid=155&lid=2520&k=&num=50",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10
        )
        data = resp.json()
        if "result" in data and "data" in data["result"]:
            for item in data["result"]["data"]:
                title = item.get("title", "")
                if any(kw in title for kw in keywords):
                    all_news.append({
                        "title": title,
                        "url": item.get("url", ""),
                        "source": "新浪股票"
                    })
    except Exception as e:
        print(f"⚠️ 新浪股票抓取失败: {e}")
    
    # ==================== 7. 雪球热帖 ====================
    try:
        url = "https://xueqiu.com/statuses/hot/listV2.json?since_id=-1&max_id=-1&size=30"
        xq_headers = {**headers, "Referer": "https://xueqiu.com/", "Cookie": "xq_a_token=test"}
        resp = req.get(url, headers=xq_headers, timeout=10)
        data = resp.json()
        if data.get("data"):
            for item in data["data"].get("items", []):
                title = item.get("original_status", {}).get("title", "") or item.get("original_status", {}).get("text", "")[:80]
                if title and any(kw in title for kw in keywords):
                    all_news.append({
                        "title": title,
                        "url": f"https://xueqiu.com{item.get('target', '')}",
                        "source": "雪球"
                    })
    except Exception as e:
        print(f"⚠️ 雪球抓取失败: {e}")
    
    # 去重
    seen = set()
    unique_news = []
    for n in all_news:
        title = n["title"]
        if title not in seen and len(title) > 5:
            seen.add(title)
            unique_news.append(n)
    
    # 按来源优先级排序（证券网站优先）
    source_priority = {"东方财富": 0, "同花顺": 1, "东方财富快讯": 2, "东方财富7x24": 3, "雪球": 4, "新浪股票": 5, "新浪财经": 6}
    unique_news.sort(key=lambda x: source_priority.get(x["source"], 10))
    
    return unique_news[:50]


@app.post("/api/generate-analysis")
async def generate_analysis(request: AnalysisRequest):
    """
    使用 AI 生成供应链分析报告 (OpenAI 兼容格式)
    
    Args:
        company_name: 主体公司名称
        competitors: 竞争对手列表
        upstream: 上游供应商列表
        downstream: 下游客户列表
        news: 相关新闻列表
    """
    import os
    import requests as req
    from datetime import datetime
    
    config = load_config()
    ai_config = config.get("ai", {})
    
    # 支持内外网双 API 配置
    internal_config = ai_config.get("internal", {})
    external_config = ai_config.get("external", {})
    
    # 内网配置
    internal_api_key = internal_config.get("api_key", "")
    internal_api_base = internal_config.get("api_base", "http://10.180.116.5:6410/v1")
    internal_model = internal_config.get("model", "Qwen_Qwen3-VL-235B-A22B-Instruct-FP8")
    
    # 外网配置
    external_api_key = external_config.get("api_key", "") or os.environ.get("AI_API_KEY", "")
    external_api_base = external_config.get("api_base", "https://api.siliconflow.cn/v1")
    external_model = external_config.get("model", "Pro/moonshotai/Kimi-K2-Thinking")
    
    # 兼容旧配置格式
    if not internal_config and not external_config:
        internal_api_key = ai_config.get("api_key", "")
        internal_api_base = ai_config.get("api_base", "https://api.siliconflow.cn/v1")
        internal_model = ai_config.get("model", "Qwen/Qwen2.5-7B-Instruct")
    
    # 实时抓取供应链相关新闻 - 扩大关键词范围
    keywords = [
        # 核心公司
        "立讯", "歌尔", "蓝思", "富联", "富士康", "京东方", "BOE",
        "欣旺达", "德赛", "舜宇", "鹏鼎", "东山精密", "领益", "瑞声",
        # 客户
        "苹果", "Apple", "iPhone", "AirPods", "Vision Pro", "iPad", "Mac",
        "华为", "Huawei", "鸿蒙", "Mate", "荣耀",
        "小米", "OPPO", "vivo", "三星", "Samsung",
        # 行业关键词
        "消费电子", "果链", "代工", "供应链", "芯片", "半导体",
        "智能手机", "穿戴", "耳机", "VR", "AR", "XR",
        "新能源汽车", "电动汽车", "动力电池", "锂电",
        "AI", "人工智能", "算力", "GPU", "英伟达"
    ]
    
    print(f"📡 正在实时抓取供应链相关新闻...")
    realtime_news = fetch_realtime_news(keywords)
    print(f"✅ 抓取到 {len(realtime_news)} 条相关新闻")
    
    # 合并传入的新闻和实时抓取的新闻
    all_news = list(request.news) if request.news else []
    all_news.extend(realtime_news)
    
    # 去重
    seen_titles = set()
    unique_news = []
    for n in all_news:
        title = n.get("title", "")
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_news.append(n)
    
    # 构建新闻摘要（包含链接）
    news_summary = ""
    if unique_news:
        news_items = []
        for n in unique_news[:30]:
            title = n.get('title', '')
            url = n.get('url', '')
            source = n.get('source', '')
            if url:
                news_items.append(f"- [{title}]({url}) 【{source}】")
            else:
                news_items.append(f"- {title} 【{source}】")
        news_summary = "\n".join(news_items)
    
    today = datetime.now().strftime("%Y年%m月%d日")
    
    # 竞争对手列表
    competitors = request.competitors if request.competitors else ['歌尔股份', '蓝思科技', '工业富联', '鹏鼎控股', '东山精密', '领益智造', '瑞声科技']
    upstream = request.upstream if request.upstream else ['京东方A', '舜宇光学', '欣旺达', '德赛电池', '信维通信', '长盈精密']
    downstream = request.downstream if request.downstream else ['苹果', '华为', 'Meta', '奇瑞汽车', '小米', 'OPPO/vivo']
    
    prompt = f"""# 角色定义
你是一位顶级投行的TMT行业首席分析师，拥有15年消费电子产业链研究经验，曾任职于高盛、摩根士丹利。你的分析以数据驱动、逻辑严谨、结论明确著称。

# 任务目标
为 **{request.company_name}**（002475.SZ）生成一份机构级别的**竞争格局与供应链深度分析报告**。

# 分析日期
{today}

# 公司画像
| 维度 | 信息 |
|------|------|
| 公司名称 | {request.company_name} |
| 股票代码 | 002475.SZ |
| 所属行业 | 消费电子精密制造 |
| 核心业务 | iPhone/AirPods/Apple Watch/Vision Pro代工、汽车电子、通信连接器 |
| 第一大客户 | 苹果（营收占比约70-75%） |
| 市值规模 | 约2000亿人民币（A股消费电子龙头） |
| 核心竞争力 | 垂直整合能力、精密制造工艺、客户粘性 |

# 竞争对手矩阵
{chr(10).join([f'- **{c}**' for c in competitors])}

# 供应链图谱
**上游供应商**: {', '.join(upstream)}
**下游客户**: {', '.join(downstream)}

# 实时新闻情报（共{len(unique_news)}条，抓取时间：{today}）
{news_summary if news_summary else '⚠️ 当前时段未抓取到直接相关新闻'}

---

# 输出要求

请严格按照以下结构输出报告，**必须包含表格和数据对比**：

## 一、执行摘要（Executive Summary）
用3-5个要点概括核心发现，每个要点用 ✅ ⚠️ 🔴 标注利好/中性/利空。

## 二、新闻事件深度解读
针对上述每条重要新闻，请用表格展示（**必须保留新闻原文链接**）：

| 新闻标题 | 来源 | 事件概述 | 影响路径 | 影响程度 | 时间维度 |
|----------|------|----------|----------|----------|----------|
| [新闻标题](原文链接) | 来源网站 | 一句话总结 | 如何传导到{request.company_name} | 高/中/低 + 正面/负面 | 短期/中期/长期 |

如果新闻较少，请分析近期行业趋势对公司的潜在影响。

## 三、竞争格局分析

### 3.1 市场份额对比表
请用Markdown表格展示（注意：{request.company_name}是我们的主体公司，应显示"综合竞争力"，其他竞争对手显示"威胁等级"）：

| 公司 | 主营产品 | 苹果业务占比 | 核心优势 | 核心劣势 | 综合竞争力/威胁等级 |
|------|----------|--------------|----------|----------|----------------------|
| **{request.company_name}** | ... | ... | ... | ... | ⭐⭐⭐⭐⭐ (综合竞争力) |
| 歌尔股份 | ... | ... | ... | ... | ⭐⭐⭐ (威胁等级) |
| ... | ... | ... | ... | ... | ... |

### 3.2 竞争力雷达图数据
请提供以下维度的1-10分评分（**将自动渲染为雷达图**）：

```json:radar-chart
{{
  "type": "radar",
  "title": "竞争力对比雷达图",
  "dimensions": ["技术能力", "成本控制", "客户关系", "产能规模", "垂直整合", "研发投入"],
  "companies": {{
    "{request.company_name}": [9, 8, 10, 9, 9, 8],
    "歌尔股份": [8, 7, 7, 7, 6, 7],
    "工业富联": [8, 9, 8, 10, 7, 7],
    "蓝思科技": [7, 6, 8, 8, 6, 7]
  }}
}}
```

### 3.3 波特五力分析
用表格展示五力评估：

| 竞争力量 | 强度 | 关键因素 | 对{request.company_name}影响 |
|----------|------|----------|------------------------------|
| 现有竞争者 | 高/中/低 | ... | ... |
| 潜在进入者 | ... | ... | ... |
| 替代品威胁 | ... | ... | ... |
| 供应商议价 | ... | ... | ... |
| 客户议价 | ... | ... | ... |

## 四、供应链风险评估

### 4.1 供应链风险矩阵
| 风险类型 | 风险描述 | 发生概率 | 影响程度 | 风险等级 | 缓解措施 |
|----------|----------|----------|----------|----------|----------|
| 客户集中度 | 苹果占比过高 | 高 | 极高 | 🔴 | 拓展汽车电子 |
| ... | ... | ... | ... | ... | ... |

### 4.2 关键供应商依赖度
| 供应商 | 供应物料 | 替代难度 | 断供影响 | 备选方案 |
|--------|----------|----------|----------|----------|
| 京东方A | 显示面板 | 中 | 高 | 三星/LG |
| ... | ... | ... | ... | ... |

## 五、财务指标对比（如有公开数据）
| 指标 | {request.company_name} | 歌尔股份 | 工业富联 | 行业均值 |
|------|------------------------|----------|----------|----------|
| 毛利率 | ~18% | ~15% | ~8% | ~12% |
| ROE | ... | ... | ... | ... |
| 营收增速 | ... | ... | ... | ... |

## 六、SWOT分析
用2x2表格展示：

| | 正面 | 负面 |
|---|------|------|
| **内部** | **优势(S)**: 1. xxx 2. xxx | **劣势(W)**: 1. xxx 2. xxx |
| **外部** | **机会(O)**: 1. xxx 2. xxx | **威胁(T)**: 1. xxx 2. xxx |

## 七、投资建议与目标价

### 7.1 投资评级
| 时间维度 | 评级 | 核心逻辑 |
|----------|------|----------|
| 短期(1-3月) | 买入/持有/卖出 | ... |
| 中期(6-12月) | ... | ... |
| 长期(1-3年) | ... | ... |

### 7.2 关键催化剂与风险点
**上行催化剂** 🚀：
1. ...
2. ...

**下行风险** ⚠️：
1. ...
2. ...

### 7.3 关注时间节点
| 日期 | 事件 | 预期影响 |
|------|------|----------|
| 2025年1月 | 苹果Q1财报 | ... |
| ... | ... | ... |

---

# 格式要求
1. 必须使用Markdown格式，包含表格、列表、加粗、emoji
2. 表格数据要完整，不要用省略号代替实际分析
3. 评分和评级要有明确依据
4. JSON代码块用于前端图表渲染，格式必须正确，会自动转换为雷达图
5. **必须保留所有新闻的原文链接**，使用 [title](url) 格式
6. 报告长度：2000-4000字"""

    # 定义 API 调用函数
    def call_ai_api(api_base, api_key, model, timeout=180):
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        response = req.post(
            f"{api_base.rstrip('/')}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "你是顶级投行TMT行业首席分析师，擅长消费电子产业链竞争格局分析。你的报告必须包含：1)数据表格 2)竞争力评分 3)风险矩阵 4)SWOT分析 5)投资建议。使用专业的Markdown格式，包含表格和结构化数据。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 8000
            },
            timeout=timeout
        )
        return response
    
    used_model = ""
    used_api = ""
    
    try:
        # 优先尝试内网 API
        print(f"🔄 尝试内网 API: {internal_api_base}")
        response = call_ai_api(internal_api_base, internal_api_key, internal_model, timeout=60)
        
        if response.status_code == 200:
            used_model = internal_model
            used_api = "内网"
            print(f"✅ 内网 API 调用成功")
        else:
            raise Exception(f"内网 API 返回 {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ 内网 API 不可用: {e}")
        print(f"🔄 切换到外网 API: {external_api_base}")
        
        if not external_api_key:
            raise HTTPException(
                status_code=400, 
                detail="内网 API 不可用，且未配置外网 API Key"
            )
        
        try:
            response = call_ai_api(external_api_base, external_api_key, external_model, timeout=180)
            used_model = external_model
            used_api = "外网"
            print(f"✅ 外网 API 调用成功")
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"内外网 API 均不可用: 内网({e}), 外网({e2})")
    
    try:
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"AI API调用失败: {response.text}")
        
        result = response.json()
        
        # 提取生成的内容 (OpenAI 格式)
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"]
        else:
            raise HTTPException(status_code=500, detail=f"无法解析AI响应: {result}")
        
        return {
            "status": "success",
            "company": request.company_name,
            "report": content,
            "model": used_model,
            "api_source": used_api,
            "timestamp": datetime.now().isoformat()
        }
        
    except req.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="AI API请求超时，请稍后重试")
    except req.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"网络请求失败: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成报告失败: {str(e)}")


# ==================== 静态文件服务 ====================

# 检查 web 目录是否存在
WEB_DIR = BASE_DIR / "web"
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

@app.get("/ui")
async def serve_ui():
    """返回 Web UI 页面"""
    from fastapi.responses import FileResponse
    ui_path = WEB_DIR / "index.html"
    if ui_path.exists():
        return FileResponse(str(ui_path))
    return {"error": "Web UI not found"}


# ==================== 启动服务 ====================

@app.on_event("startup")
async def startup_preload():
    """服务启动时预加载常用分类数据"""
    import asyncio
    
    async def preload_category(category):
        try:
            from scrapers.unified import UnifiedDataSource
            ds = UnifiedDataSource()
            data = ds.crawl_category(category, include_custom=True)
            
            sources = {}
            for item in data:
                src = item.get("platform_name", item.get("platform", "unknown"))
                sources[src] = sources.get(src, 0) + 1
            
            result = {
                "category": category,
                "total": len(data),
                "sources": sources,
                "data": data,
                "timestamp": datetime.now().isoformat(),
                "cached": False
            }
            news_cache.set(f"news_{category}_True", result)
            print(f"  ✅ {category}: {len(data)} 条")
        except Exception as e:
            print(f"  ❌ {category}: {e}")
    
    print("📦 预加载缓存数据...")
    # 预加载常用分类
    for cat in ["finance", "tech", "news", "social"]:
        await preload_category(cat)
    
    # 预加载供应链新闻
    keywords = [
        "立讯", "歌尔", "蓝思", "富联", "富士康", "京东方",
        "苹果", "Apple", "iPhone", "华为", "小米", "三星",
        "AI", "人工智能", "芯片", "半导体", "消费电子"
    ]
    news = fetch_realtime_news(keywords)
    _supply_chain_news_cache["data"] = news
    _supply_chain_news_cache["timestamp"] = datetime.now()
    print(f"  ✅ supply-chain: {len(news)} 条")
    print("✅ 预加载完成！")


if __name__ == "__main__":
    print("🚀 启动 TrendRadar API 服务...")
    print("📍 API: http://localhost:8000")
    print("🌐 Web UI: http://localhost:8000/ui")
    print("📚 API 文档: http://localhost:8000/docs")
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
