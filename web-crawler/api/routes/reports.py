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
    
    if isinstance(webhook_urls, str):
        webhook_urls = [webhook_urls] if webhook_urls else []
    elif not webhook_urls:
        webhook_urls = []
    
    webhook_urls = [url for url in webhook_urls if url and url.strip()]
    
    if not webhook_urls:
        print("❌ 未配置有效的企业微信 Webhook")
        return {"status": "error", "message": "未配置企业微信 Webhook"}
    
    try:
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
        
        image_data = await render_report_to_image(request.title, request.content, timestamp)
        
        if image_data:
            # 检查图片大小 (企业微信限制为 2MB)
            MAX_IMAGE_SIZE = 2 * 1024 * 1024 # 2MB
            image_size = len(image_data)
            
            if image_size <= MAX_IMAGE_SIZE:
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
                        resp_json = resp.json()
                        if resp.status_code == 200 and resp_json.get("errcode") == 0:
                            success_count += 1
                            print(f"✅ 图片推送成功")
                        else:
                            error_msg = resp_json.get("errmsg", "未知错误")
                            error_code = resp_json.get("errcode", -1)
                            print(f"❌ 图片推送失败: {error_code} - {error_msg}")
                            # 如果是文件过大错误，且成功数为0，则标记需要切换至文件发送
                            if error_code == 40009:
                                success_count = 0
                                break
                            errors.append(f"{error_code}: {error_msg}")
                    except Exception as e:
                        print(f"❌ 推送异常: {e}")
                        errors.append(str(e)[:50])
                
                if success_count > 0:
                    return {
                        "status": "success",
                        "message": f"报告图片已推送到 {success_count}/{len(webhook_urls)} 个群",
                        "filename": filename
                    }
            else:
                print(f"⚠️ 图片大小 ({image_size/1024:.2f} KB) 超过 2MB 限制，切换为文件推送")
        
        # 降级处理：图片过大、渲染失败或图片发送失败 -> 发送 Markdown 文件
        print(f"💡 正在发送 Markdown 文件报告: {filename}...")
        
        success_count = 0
        for webhook_url in webhook_urls:
            try:
                # 1. 提取 Key
                import re
                key_match = re.search(r'key=([a-z0-9-]+)', webhook_url)
                if not key_match:
                    continue
                key = key_match.group(1)
                
                # 2. 上传素材
                upload_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={key}&type=file"
                with open(filepath, 'rb') as f:
                    files = {'media': (filename, f, 'text/markdown')}
                    up_resp = requests.post(upload_url, files=files, timeout=30, verify=False)
                
                up_data = up_resp.json()
                if up_data.get("errcode") != 0:
                    print(f"❌ 文件上传失败: {up_data}")
                    continue
                
                media_id = up_data.get("media_id")
                
                # 3. 发送文件消息
                file_payload = {
                    "msgtype": "file",
                    "file": {
                        "media_id": media_id
                    }
                }
                send_resp = requests.post(webhook_url, json=file_payload, timeout=30, verify=False)
                if send_resp.status_code == 200 and send_resp.json().get("errcode") == 0:
                    success_count += 1
                    print(f"✅ 文件推送成功")
            except Exception as e:
                print(f"❌ 文件推送异常: {e}")
        
        if success_count > 0:
            return {
                "status": "success",
                "message": f"图片超限，已将完整报告文件推送到 {success_count} 个群",
                "filename": filename
            }
        
        return {"status": "error", "message": "图片展示失败且文件发送也未成功"}
        
    except Exception as e:
        print(f"❌ 推送过程发生异常: {e}")
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
            # 启用 headless 模式并优化性能参数
            browser = await p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox"])
            page = await browser.new_page(viewport={'width': 800, 'height': 800})
            
            # 设置 HTML 内容，带超时控制
            await page.set_content(full_html, wait_until='networkidle', timeout=60000)
            
            # 动态计算高度
            height = await page.evaluate('document.body.scrollHeight')
            # 限制截图最大高度，防止图片过长导致无法推送
            max_height = 8000
            current_height = min(height + 50, max_height)
            await page.set_viewport_size({'width': 800, 'height': current_height})
            
            # 维持高质量渲染为 85
            screenshot = await page.screenshot(full_page=True, type='jpeg', quality=85)
            await browser.close()
            
            size_kb = len(screenshot) / 1024
            print(f"✅ 图片渲染成功: {len(screenshot)} bytes ({size_kb:.2f} KB), 高度: {current_height}px")
            if len(screenshot) > 2 * 1024 * 1024:
                print(f"⚠️ 警告: 图片大小 ({size_kb:.2f} KB) 超过企业微信 2MB 限制！")
            
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
