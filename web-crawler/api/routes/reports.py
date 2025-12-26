"""
报告相关 API 路由
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from datetime import datetime
from pathlib import Path
import hashlib
import markdown
import re

from ..models import ReportPushRequest

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent.parent
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def load_config():
    """加载配置"""
    import yaml
    config_path = BASE_DIR / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@router.post("/api/push-report")
async def push_report(request: ReportPushRequest):
    """推送分析报告到企业微信"""
    import requests
    import urllib3
    import base64
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    config = load_config()
    webhook_urls = config.get("notification", {}).get("webhooks", {}).get("wework_url", "")
    
    print(f"📤 推送报告: {request.title[:30]}...")
    print(f"🔗 Webhook配置: {type(webhook_urls)} = {webhook_urls[:50] if isinstance(webhook_urls, str) else webhook_urls}")
    
    if isinstance(webhook_urls, str):
        webhook_urls = [webhook_urls] if webhook_urls else []
    elif not webhook_urls:
        webhook_urls = []
    
    # 过滤掉空字符串
    webhook_urls = [url for url in webhook_urls if url and url.strip()]
    
    if not webhook_urls:
        print("❌ 未配置有效的企业微信 Webhook")
        return {"status": "error", "message": "未配置企业微信 Webhook，请在 config/config.yaml 中配置 notification.webhooks.wework_url"}
    
    try:
        # 生成报告文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_id = hashlib.md5(f"{request.title}{timestamp}".encode()).hexdigest()[:8]
        filename = f"report_{timestamp}_{report_id}.md"
        filepath = REPORTS_DIR / filename
        
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
            image_md5 = hashlib.md5(image_data).hexdigest()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
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
                        print(f"✅ 图片推送成功")
                except Exception as e:
                    errors.append(str(e)[:50])
            
            if success_count > 0:
                return {
                    "status": "success",
                    "message": f"报告图片已推送到 {success_count}/{len(webhook_urls)} 个群",
                    "filename": filename,
                    "errors": errors if errors else None
                }
            else:
                return {"status": "error", "message": f"推送失败: {'; '.join(errors)}"}
        else:
            # 降级为文字
            summary = request.content[:3500]
            message = f"""📊 **{request.title}**
━━━━━━━━━━━━━━━━━━━━━━━━━━
📅 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}
━━━━━━━━━━━━━━━━━━━━━━━━━━

{summary}"""
            
            payload = {"msgtype": "markdown", "markdown": {"content": message}}
            
            success_count = 0
            for webhook_url in webhook_urls:
                try:
                    resp = requests.post(webhook_url, json=payload, timeout=30, verify=False)
                    if resp.status_code == 200 and resp.json().get("errcode") == 0:
                        success_count += 1
                except:
                    pass
            
            return {
                "status": "partial",
                "message": f"图片渲染失败，已发送文字摘要到 {success_count} 个群"
            }
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def render_report_to_image(title: str, content: str, timestamp: str) -> bytes:
    """使用 Playwright 将报告渲染为图片"""
    try:
        from playwright.async_api import async_playwright
        print(f"🎨 开始渲染报告图片...")
    except ImportError as e:
        print(f"⚠️ Playwright 未安装: {e}")
        print("💡 请运行: pip install playwright && playwright install chromium")
        return None
    
    try:
        # 提高允许的报告内容长度，避免被过早截断
        max_content_length = 20000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "\n\n... *(报告内容较长，已截断)*"
        
        html_content = markdown.markdown(content, extensions=['tables', 'fenced_code'])
        
        full_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif,"Noto Sans SC", "WenQuanYi Micro Hei", "Microsoft YaHei"; 
               padding: 30px; background: #f8f9fa; color: #333; }}
        h1, h2, h3 {{ color: #1a1a1a; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 10px; text-align: left; }}
        th {{ background: #f0f0f0; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 4px; }}
        .header {{ background: linear-gradient(135deg, #667eea, #764ba2); 
                  color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <p>📅 {datetime.now().strftime('%Y-%m-%d %H:%M')} | 🤖 立讯技术产业链分析助手</p>
    </div>
    {html_content}
</body>
</html>"""
        
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page(viewport={'width': 800, 'height': 600})
            await page.set_content(full_html, wait_until='networkidle')
            
            height = await page.evaluate('document.body.scrollHeight')
            # 提高截图最大高度以支持更长的报告（注意：过大高度可能导致浏览器资源占用增加）
            max_height = 8000
            await page.set_viewport_size({'width': 800, 'height': min(height + 50, max_height)})
            
            screenshot = await page.screenshot(full_page=True, type='jpeg', quality=85)
            await browser.close()
            
            print(f"✅ 图片渲染成功: {len(screenshot)} bytes")
            return screenshot
    except Exception as e:
        import traceback
        print(f"⚠️ 图片渲染失败: {e}")
        print(f"📋 详细错误: {traceback.format_exc()}")
        return None


@router.get("/api/reports/{filename}")
async def download_report(filename: str, format: str = "html"):
    """下载报告"""
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    
    filepath = REPORTS_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="报告不存在")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if format == "html":
        html_content = markdown.markdown(content, extensions=['tables', 'fenced_code'])
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{filename}</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; max-width: 900px; 
               margin: 0 auto; padding: 40px 20px; background: #f8fafc; }}
        h1, h2 {{ color: #1e40af; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #e5e7eb; padding: 12px; text-align: left; }}
        th {{ background: #f3f4f6; }}
    </style>
</head>
<body>{html_content}</body>
</html>"""
        return HTMLResponse(content=html)
    else:
        return {"content": content, "filename": filename}


@router.get("/api/reports")
async def list_reports():
    """获取报告列表"""
    reports = []
    for f in sorted(REPORTS_DIR.glob("*.md"), reverse=True)[:50]:
        stat = f.stat()
        reports.append({
            "filename": f.name,
            "size": stat.st_size,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
    
    return {"reports": reports, "total": len(reports)}


@router.get("/api/custom-scrapers")
async def get_custom_scrapers():
    """获取自定义爬虫列表"""
    from scrapers.factory import ScraperFactory
    
    scrapers = ScraperFactory.list_scrapers()
    return {
        "scrapers": scrapers,
        "total": len(scrapers)
    }
