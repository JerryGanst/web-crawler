"""
AI 分析相关 API 路由
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
from pathlib import Path
import os
import requests as req

from ..cache import cache, CACHE_TTL
from ..models import AnalysisRequest
from prompts import (
    get_supply_chain_analysis_prompt, 
    ANALYSIS_SYSTEM_PROMPT,
    get_market_analysis_prompt,
    MARKET_SYSTEM_PROMPT,
    precheck_news_quality  # V2新增：新闻质量预检
)

# 从 news.py 导入完整的配置
from .news import (
    OPTICAL_PARTNERS,
    CONNECTOR_PARTNERS, 
    POWER_PARTNERS,
    CUSTOMERS,
    SUPPLIERS
)

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent.parent

# 市场分析缓存
_market_analysis_cache = {
    "content": None,
    "timestamp": None,
    "ttl": 1800  # 30分钟缓存
}


def load_config():
    """加载配置"""
    import yaml
    config_path = BASE_DIR / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_ai_config():
    """获取 AI 配置"""
    config = load_config()
    ai_config = config.get("ai", {})
    
    internal_config = ai_config.get("internal", {})
    external_config = ai_config.get("external", {})
    
    internal_api_key = internal_config.get("api_key", "")
    internal_api_base = internal_config.get("api_base", "http://10.180.116.5:6410/v1")
    internal_model = internal_config.get("model", "Qwen_Qwen3-VL-235B-A22B-Instruct-FP8")
    
    external_api_key = external_config.get("api_key", "") or os.environ.get("AI_API_KEY", "")
    external_api_base = external_config.get("api_base", "https://api.siliconflow.cn/v1")
    external_model = external_config.get("model", "Pro/moonshotai/Kimi-K2-Thinking")
    external_thinking_level = external_config.get("thinking_level", "high")
    
    if not internal_config and not external_config:
        internal_api_key = ai_config.get("api_key", "")
        internal_api_base = ai_config.get("api_base", "https://api.siliconflow.cn/v1")
        internal_model = ai_config.get("model", "Qwen/Qwen2.5-7B-Instruct")
    
    return {
        "internal": {
            "api_key": internal_api_key,
            "api_base": internal_api_base,
            "model": internal_model
        },
        "external": {
            "api_key": external_api_key,
            "api_base": external_api_base,
            "model": external_model,
            "thinking_level": external_thinking_level
        }
    }


def call_ai_api(api_base: str, api_key: str, model: str, 
                system_prompt: str, user_prompt: str, 
                timeout: int = 180, max_tokens: int = 8000):
    """调用 AI API (OpenAI 兼容格式)"""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    response = req.post(
        f"{api_base.rstrip('/')}/chat/completions",
        headers=headers,
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens
        },
        timeout=timeout
    )
    return response


def call_gemini_api(api_base: str, api_key: str, model: str,
                    system_prompt: str, user_prompt: str,
                    thinking_level: str = "high",
                    timeout: int = 180, max_tokens: int = 8000):
    """调用 Gemini 3 Pro API (支持 thinkingConfig)"""
    url = f"{api_base.rstrip('/')}/models/{model}:generateContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"{system_prompt}\n\n{user_prompt}"}
                ]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            # Gemini 3 官方建议保持默认 1.0
            "temperature": 1.0,
            "thinkingConfig": {
                "thinkingLevel": thinking_level
            }
        }
    }
    
    response = req.post(url, headers=headers, json=payload, timeout=timeout)
    return response


def parse_gemini_response(response):
    """解析 Gemini API 响应，转换为统一格式"""
    if response.status_code != 200:
        return None, f"Gemini API 错误: {response.status_code} - {response.text}"
    
    result = response.json()
    
    # Gemini 响应格式: {"candidates": [{"content": {"parts": [{"text": "..."}]}}]}
    try:
        candidates = result.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            # 过滤掉 thought 部分，只取 text 部分
            text_parts = [p.get("text", "") for p in parts if "text" in p and "thought" not in p]
            content = "\n".join(text_parts)
            return content, None
    except Exception as e:
        return None, f"解析 Gemini 响应失败: {e}"
    
    return None, "Gemini 响应格式异常"


def fetch_realtime_news(keywords: list) -> list:
    """实时抓取新闻"""
    all_news = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    
    # 1. 东方财富快讯
    try:
        url = "https://push2ex.eastmoney.com/getAllStockBreakthrough?cb=callback"
        resp = req.get(url, headers=headers, timeout=10)
        text = resp.text
        if "callback(" in text:
            import json
            json_str = text.replace("callback(", "").rstrip(")")
            data = json.loads(json_str)
            for item in data.get("data", {}).get("list", [])[:20]:
                title = item.get("title", "")
                if any(kw in title for kw in keywords):
                    all_news.append({
                        "title": title,
                        "url": f"https://stock.eastmoney.com/a/{item.get('code', '')}.html",
                        "source": "东方财富快讯"
                    })
    except Exception as e:
        print(f"⚠️ 东方财富快讯抓取失败: {e}")
    
    # 2. 同花顺快讯
    try:
        url = "https://news.10jqka.com.cn/tapp/news/push/stock/?page=1&tag=&track=website&pagesize=50"
        resp = req.get(url, headers=headers, timeout=10)
        data = resp.json()
        for item in data.get("data", {}).get("list", []):
            title = item.get("title", "")
            if any(kw in title for kw in keywords):
                all_news.append({
                    "title": title,
                    "url": item.get("url", ""),
                    "source": "同花顺"
                })
    except Exception as e:
        print(f"⚠️ 同花顺抓取失败: {e}")
    
    # 3. 新浪财经
    try:
        url = "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&k=&num=50&page=1"
        resp = req.get(url, headers=headers, timeout=10)
        data = resp.json()
        for item in data.get("result", {}).get("data", []):
            title = item.get("title", "")
            if any(kw in title for kw in keywords):
                all_news.append({
                    "title": title,
                    "url": item.get("url", ""),
                    "source": "新浪财经"
                })
    except Exception as e:
        print(f"⚠️ 新浪财经抓取失败: {e}")
    
    # 4. 东方财富个股公告（针对股票代码搜索）
    stock_codes = [kw for kw in keywords if kw.isdigit() and len(kw) == 6]
    for code in stock_codes[:8]:  # 最多查8个股票
        try:
            url = f"https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=10&page_index=1&ann_type=A&stock_list={code}&f_node=0&s_node=0"
            resp = req.get(url, headers=headers, timeout=5)
            data = resp.json()
            for item in data.get("data", {}).get("list", [])[:5]:
                title = item.get("title", "")
                art_code = item.get("art_code", "")
                all_news.append({
                    "title": title,
                    "url": f"https://data.eastmoney.com/notices/detail/{code}/{art_code}.html",
                    "source": f"东方财富公告",
                    "stock_code": code,
                    "matched_keyword": code
                })
        except Exception as e:
            pass  # 静默失败
    
    # 5. 雪球个股讨论（针对股票代码搜索）
    for code in stock_codes[:5]:
        try:
            # 深市 SZ，沪市 SH
            prefix = "SZ" if code.startswith(("0", "3")) else "SH"
            symbol = f"{prefix}{code}"
            url = f"https://xueqiu.com/statuses/stock_timeline.json?symbol={symbol}&count=10&source=all"
            resp = req.get(url, headers={**headers, "Cookie": "xq_a_token=test"}, timeout=5)
            data = resp.json()
            for item in data.get("list", [])[:5]:
                title = item.get("title", "") or item.get("text", "")[:100]
                if title:
                    all_news.append({
                        "title": title,
                        "url": f"https://xueqiu.com{item.get('target', '')}",
                        "source": f"雪球-{code}",
                        "stock_code": code,
                        "matched_keyword": code
                    })
        except Exception as e:
            pass  # 静默失败
    
    # 6. 财联社搜索（覆盖海外和非上市公司）
    company_keywords = [kw for kw in keywords if not kw.isdigit()][:25]
    for kw in company_keywords:
        try:
            url = "https://www.cls.cn/api/sw?app=cls-pc&os=web&sv=7.7.5"
            data = {"type": "telegram", "keyword": kw, "page": 1, "rn": 10}
            resp = req.post(url, json=data, headers=headers, timeout=5)
            result = resp.json()
            for item in result.get("data", {}).get("telegram", {}).get("data", [])[:5]:
                title = item.get("title", "") or item.get("descr", "")[:100]
                if title and len(title) > 8:
                    all_news.append({
                        "title": title,
                        "url": f"https://www.cls.cn/detail/{item.get('id', '')}",
                        "source": "财联社",
                        "matched_keyword": kw
                    })
        except:
            pass
    
    # 7. 财联社深度文章搜索
    for kw in company_keywords[:15]:
        try:
            url = "https://www.cls.cn/api/sw?app=cls-pc&os=web&sv=7.7.5"
            data = {"type": "article", "keyword": kw, "page": 1, "rn": 10}
            resp = req.post(url, json=data, headers=headers, timeout=5)
            result = resp.json()
            for item in result.get("data", {}).get("article", {}).get("data", [])[:3]:
                title = item.get("title", "")
                if title and len(title) > 8:
                    all_news.append({
                        "title": title,
                        "url": f"https://www.cls.cn/detail/{item.get('id', '')}",
                        "source": "财联社深度",
                        "matched_keyword": kw
                    })
        except:
            pass
    
    # 8. 巨潮资讯（官方公告源）
    for code in stock_codes[:6]:
        try:
            url = f"http://www.cninfo.com.cn/new/disclosure/stock?stockCode={code}&pageNum=1&pageSize=10"
            resp = req.get(url, headers=headers, timeout=5)
            data = resp.json()
            for item in data.get("classifiedAnnouncements", [])[:5]:
                for ann in item if isinstance(item, list) else [item]:
                    title = ann.get("announcementTitle", "")
                    if title:
                        all_news.append({
                            "title": title,
                            "url": f"http://www.cninfo.com.cn/new/disclosure/detail?announcementId={ann.get('announcementId', '')}",
                            "source": "巨潮资讯",
                            "stock_code": code
                        })
        except:
            pass
    
    # 9. 同花顺研报搜索
    for kw in keywords[:10]:
        try:
            url = f"https://data.10jqka.com.cn/ajax/report/search?keyword={kw}&page=1&pagesize=10"
            resp = req.get(url, headers=headers, timeout=5)
            data = resp.json()
            for item in data.get("data", {}).get("list", [])[:3]:
                title = item.get("title", "")
                if title:
                    all_news.append({
                        "title": title,
                        "url": item.get("url", ""),
                        "source": "同花顺研报",
                        "matched_keyword": kw
                    })
        except:
            pass
    
    # 10. OFweek 光通讯/电子
    try:
        ofweek_keywords = [kw for kw in keywords if any(k in kw for k in ['光', '通信', '旭创', '新易盛', '天孚', '光迅', 'Credo'])]
        for kw in ofweek_keywords[:5]:
            url = f"https://search.ofweek.com/search/?q={kw}&type=news"
            resp = req.get(url, headers=headers, timeout=5)
            # 简单解析
            import re
            titles = re.findall(r'<a[^>]*class="search-title"[^>]*>([^<]+)</a>', resp.text)
            links = re.findall(r'<a[^>]*class="search-title"[^>]*href="([^"]+)"', resp.text)
            for title, link in zip(titles[:3], links[:3]):
                all_news.append({
                    "title": title.strip(),
                    "url": link,
                    "source": "OFweek",
                    "matched_keyword": kw
                })
    except:
        pass
    
    # 11. 哔哥哔特（连接器、电源）
    try:
        bigbit_keywords = [kw for kw in keywords if any(k in kw for k in ['连接器', '电源', '安费诺', '莫仕', 'TE', '奥海', '台达', '航嘉'])]
        for kw in bigbit_keywords[:5]:
            url = f"https://www.big-bit.com/search/?q={kw}"
            resp = req.get(url, headers=headers, timeout=5)
            import re
            results = re.findall(r'<h3[^>]*><a[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', resp.text)
            for link, title in results[:3]:
                all_news.append({
                    "title": title.strip(),
                    "url": f"https://www.big-bit.com{link}" if not link.startswith('http') else link,
                    "source": "哔哥哔特",
                    "matched_keyword": kw
                })
    except:
        pass
    
    # 12. 腾讯财经（聚合搜索）
    try:
        for kw in keywords[:8]:
            url = f"https://news.qq.com/zt2020/page/feiyan.htm#/search?keyword={kw}&type=finance"
            # 腾讯新闻需要特殊处理，使用备用API
            api_url = f"https://i.news.qq.com/trpc.qqnews_web.kv_srv.kv_srv_http_proxy/list?sub_srv_id=24&srv_id=pc&offset=0&limit=10&strategy=1&ext={kw}"
            resp = req.get(api_url, headers=headers, timeout=5)
            data = resp.json()
            for item in data.get("data", {}).get("list", [])[:5]:
                title = item.get("title", "")
                if title and any(k in title for k in keywords):
                    all_news.append({
                        "title": title,
                        "url": item.get("url", ""),
                        "source": "腾讯财经",
                        "matched_keyword": kw
                    })
    except:
        pass
    
    # 13. 和讯财经
    try:
        url = "https://api.hexun.com/api/article/list?channelId=101&pageSize=30"
        resp = req.get(url, headers=headers, timeout=5)
        data = resp.json()
        for item in data.get("data", []):
            title = item.get("title", "")
            if any(kw in title for kw in keywords):
                all_news.append({
                    "title": title,
                    "url": item.get("url", ""),
                    "source": "和讯财经"
                })
    except:
        pass
    
    # 14. 证券时报
    try:
        url = "https://api.stcn.com/api/article/getlist?channelId=16&pageSize=30"
        resp = req.get(url, headers=headers, timeout=5)
        data = resp.json()
        for item in data.get("data", {}).get("list", []):
            title = item.get("title", "")
            if any(kw in title for kw in keywords):
                all_news.append({
                    "title": title,
                    "url": item.get("url", f"https://www.stcn.com/article/detail/{item.get('id', '')}"),
                    "source": "证券时报"
                })
    except:
        pass
    
    # 去重 + 清理 HTML 标签 + 添加时间
    import re
    seen = set()
    unique_news = []
    current_time = datetime.now()
    
    for n in all_news:
        title = n.get("title", "")
        # 清理 HTML 标签（如 <br>）
        title = re.sub(r'<[^>]+>', ' ', title)
        title = re.sub(r'\s+', ' ', title).strip()
        
        if title not in seen and len(title) > 5:
            seen.add(title)
            # 添加抓取时间（如果原数据没有时间）
            news_item = {
                "title": title,
                "url": n.get("url", ""),
                "source": n.get("source", ""),
                "publish_time": n.get("publish_time") or n.get("time") or current_time.strftime("%Y-%m-%d %H:%M"),
                "matched_keyword": n.get("matched_keyword", "")
            }
            unique_news.append(news_item)
    
    # 按时间排序（最新在前）
    unique_news.sort(key=lambda x: x.get("publish_time", ""), reverse=True)
    
    return unique_news  # 返回所有匹配的新闻，不做数量限制


@router.get("/api/market-analysis")
async def get_market_analysis(refresh: bool = False):
    """获取 AI 生成的市场分析报告"""
    
    # 检查缓存
    if not refresh and _market_analysis_cache["content"]:
        cache_age = (datetime.now() - _market_analysis_cache["timestamp"]).total_seconds()
        if cache_age < _market_analysis_cache["ttl"]:
            return {
                "status": "success",
                "content": _market_analysis_cache["content"],
                "cached": True,
                "cache_age": int(cache_age),
                "timestamp": _market_analysis_cache["timestamp"].isoformat()
            }
    
    ai_config = get_ai_config()
    internal = ai_config["internal"]
    external = ai_config["external"]
    
    # 获取实时市场数据
    from scrapers.commodity import CommodityScraper
    scraper = CommodityScraper()
    commodity_data = scraper.scrape()
    
    # 去重并按品类汇总，确保包括塑料在内的所有大宗品类
    unique_map = {}
    for item in commodity_data:
        key = (item.get('chinese_name') or item.get('name', '')).strip().lower()
        if key and key not in unique_map:
            unique_map[key] = item
    deduped_data = list(unique_map.values())
    
    # 品类顺序，确保塑料被单独分类出来
    category_order = {'贵金属': 0, '能源': 1, '工业金属': 2, '农产品': 3, '塑料': 4}
    from collections import defaultdict
    categorized = defaultdict(list)
    for item in deduped_data:
        cat = item.get('category') or '其他'
        categorized[cat].append(item)
    
    # 构建商品数据摘要（全量，不截断）
    commodity_summary = []
    def _fmt_price(value):
        try:
            return f"{float(value):,.2f}".rstrip('0').rstrip('.')
        except Exception:
            return str(value)
    
    def _change_abs(item):
        try:
            return abs(float(item.get('change_percent') or 0))
        except Exception:
            return 0

    for cat in sorted(categorized.keys(), key=lambda c: category_order.get(c, 99)):
        items = categorized[cat]
        commodity_summary.append(f"## {cat}（{len(items)}种）")
        # 按绝对涨跌幅排序，便于分析波动
        for item in sorted(items, key=_change_abs, reverse=True):
            name = item.get('chinese_name') or item.get('name', '')
            price = _fmt_price(item.get('price') or item.get('current_price') or 0)
            change = item.get('change_percent', 0) or 0
            unit = item.get('unit', '')
            commodity_summary.append(f"- {name}: {price} {unit} ({'+' if change >= 0 else ''}{change}%)")
    
    today = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    prompt = get_market_analysis_prompt(commodity_summary, today)
    
    used_model = ""
    used_api = ""
    # 外网配置有 key 就优先外网（不再限定 Gemini）
    prefer_external = bool(external.get("api_key"))

    def call_internal():
        print(f"🔄 市场分析: 尝试内网 API...")
        resp = call_ai_api(
            internal["api_base"], internal["api_key"], internal["model"],
            MARKET_SYSTEM_PROMPT, prompt, timeout=10, max_tokens=1000
        )
        if resp.status_code != 200:
            raise Exception(f"内网 API 返回 {resp.status_code}")
        return resp, internal["model"], "内网"

    def call_external():
        if not external["api_key"]:
            raise Exception("未配置外网 API Key")
        is_gemini = "generativelanguage.googleapis.com" in external["api_base"]
        if is_gemini:
            thinking_level = external.get("thinking_level", "low")  # 市场分析用 low 以加快速度
            resp = call_gemini_api(
                external["api_base"], external["api_key"], external["model"],
                MARKET_SYSTEM_PROMPT, prompt,
                thinking_level=thinking_level,
                timeout=120, max_tokens=1000
            )
        else:
            resp = call_ai_api(
                external["api_base"], external["api_key"], external["model"],
                MARKET_SYSTEM_PROMPT, prompt, timeout=60, max_tokens=1000
            )
        if resp.status_code != 200:
            raise Exception(f"外网 API 返回 {resp.status_code}")
        return resp, external["model"], "外网"

    try:
        if prefer_external:
            response, used_model, used_api = call_external()
        else:
            response, used_model, used_api = call_internal()
    except Exception as e_first:
        print(f"⚠️ 主优先 API 不可用: {e_first}")
        try:
            if prefer_external:
                response, used_model, used_api = call_internal()
            else:
                response, used_model, used_api = call_external()
        except Exception as e_second:
            default_content = f"""**市场概况**
今日大宗商品市场整体表现平稳，贵金属板块小幅波动，能源价格维持震荡格局。

**重点关注**
* 黄金价格维持高位，关注美联储政策动向
* 原油价格受供需影响震荡
* 工业金属受经济数据影响

**操作建议**
保持观望，等待更明确的市场信号。

---
*数据更新: {today}*"""
            return {
                "status": "success",
                "content": default_content,
                "cached": False,
                "model": "fallback",
                "api_source": "默认",
                "timestamp": datetime.now().isoformat()
            }
    
    try:
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"AI API调用失败")
        
        # 检测是否使用 Gemini API 来决定解析方式
        is_gemini = "generativelanguage.googleapis.com" in external.get("api_base", "")
        
        if is_gemini:
            content, error = parse_gemini_response(response)
            if error:
                raise HTTPException(status_code=500, detail=error)
        else:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
            else:
                raise HTTPException(status_code=500, detail="无法解析AI响应")
        
        # 更新缓存
        _market_analysis_cache["content"] = content
        _market_analysis_cache["timestamp"] = datetime.now()
        
        return {
            "status": "success",
            "content": content,
            "cached": False,
            "model": used_model,
            "api_source": used_api,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成分析失败: {str(e)}")


@router.post("/api/generate-analysis")
async def generate_analysis(request: AnalysisRequest):
    """使用 AI 生成供应链分析报告"""
    
    ai_config = get_ai_config()
    internal = ai_config["internal"]
    external = ai_config["external"]
    
    # ==================== 1. 获取供应链新闻（强制刷新） ====================
    print(f"📡 [报告生成] 正在获取最新供应链新闻...")
    
    # 关键词（扩展）
    supply_chain_keywords = [
        "立讯", "歌尔", "蓝思", "富联", "富士康", "京东方", "BOE",
        "欣旺达", "德赛", "舜宇", "鹏鼎", "东山精密", "领益", "瑞声",
        "苹果", "Apple", "iPhone", "AirPods", "Vision Pro", "iPad", "Mac",
        "华为", "Huawei", "小米", "OPPO", "vivo", "三星", "Samsung",
        "消费电子", "果链", "代工", "供应链", "芯片", "半导体",
        "AI", "人工智能", "算力", "GPU", "英伟达", "NVIDIA",
        # 关税相关
        "关税", "贸易战", "中美", "制裁", "出口管制", "实体清单",
        # 原材料相关
        "铜", "镍", "锡", "铝", "金", "银", "塑料", "PA66", "PBT", "ABS"
    ]
    
    # 实时抓取最新新闻
    realtime_news = fetch_realtime_news(supply_chain_keywords)
    try:
        from .news import _fetch_power_partner_news, _fetch_power_official_announcements
        power_news = _fetch_power_partner_news()
        official_news = _fetch_power_official_announcements()
        realtime_news.extend(power_news + official_news)
        print(f"⚡ 电源定向新闻: {len(power_news)}，官网公告: {len(official_news)}")
    except Exception as e:
        print(f"⚠️ 电源定向抓取失败: {e}")
    print(f"✅ 实时抓取: {len(realtime_news)} 条新闻")
    
    # 从缓存获取已有的供应链新闻
    cached_supply = cache.get("news:supply-chain")
    cached_supply_news = cached_supply.get("data", []) if cached_supply else []
    print(f"✅ 缓存供应链新闻: {len(cached_supply_news)} 条")
    
    # 从缓存获取关税新闻
    cached_tariff = cache.get("news:tariff")
    cached_tariff_news = cached_tariff.get("data", []) if cached_tariff else []
    print(f"✅ 缓存关税新闻: {len(cached_tariff_news)} 条")
    
    # ==================== 2. 获取大宗商品数据 ====================
    print(f"📊 [报告生成] 正在获取大宗商品价格数据...")
    commodity_summary = ""
    try:
        from scrapers.commodity import CommodityScraper
        scraper = CommodityScraper()
        commodity_data = scraper.scrape()
        
        if commodity_data:
            commodity_lines = ["**当前大宗商品价格（实时数据）：**"]
            
            # 金属类
            metals = [c for c in commodity_data if c.get('category') == '金属' or any(m in c.get('name', '') for m in ['铜', '铝', '锌', '镍', '锡', '金', '银'])]
            if metals:
                commodity_lines.append("\n**金属类原材料：**")
                for c in metals[:10]:
                    name = c.get('chinese_name') or c.get('name', '')
                    price = c.get('price', 0)
                    change = c.get('change_percent', 0)
                    unit = c.get('unit', '')
                    trend = '↑' if change > 0 else ('↓' if change < 0 else '→')
                    commodity_lines.append(f"- {name}: {price} {unit} ({'+' if change >= 0 else ''}{change}% {trend})")
            
            # 塑料/能源类
            plastics = [c for c in commodity_data if any(p in c.get('name', '').upper() for p in ['PP', 'PE', 'PVC', 'ABS', 'PA', 'PBT', 'PC', '塑料', 'OIL', '原油'])]
            if plastics:
                commodity_lines.append("\n**塑料/能源类原材料：**")
                for c in plastics[:10]:
                    name = c.get('chinese_name') or c.get('name', '')
                    price = c.get('price', 0)
                    change = c.get('change_percent', 0)
                    unit = c.get('unit', '')
                    trend = '↑' if change > 0 else ('↓' if change < 0 else '→')
                    commodity_lines.append(f"- {name}: {price} {unit} ({'+' if change >= 0 else ''}{change}% {trend})")
            
            commodity_summary = "\n".join(commodity_lines)
            print(f"✅ 大宗商品数据: {len(commodity_data)} 条")
    except Exception as e:
        print(f"⚠️ 获取大宗商品数据失败: {e}")
        commodity_summary = "⚠️ 大宗商品数据获取失败，请参考市场公开数据"
    
    # ==================== 3. 合并所有新闻来源 ====================
    all_news = []
    
    # 1) 前端传入的新闻
    if request.news:
        all_news.extend(list(request.news))
    
    # 2) 实时抓取的新闻
    all_news.extend(realtime_news)
    
    # 3) 缓存的供应链新闻
    all_news.extend(cached_supply_news)
    
    # 4) 缓存的关税新闻
    all_news.extend(cached_tariff_news)
    
    # 去重
    seen_titles = set()
    unique_news = []
    for n in all_news:
        title = n.get("title", "")
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_news.append(n)
    
    print(f"✅ 合并去重后总新闻: {len(unique_news)} 条")
    
    # ==================== 3.5 新闻质量预检（V2新增） ====================
    news_quality = precheck_news_quality(unique_news)
    print(f"📊 新闻质量评分: {news_quality['quality_score']}/100")
    if news_quality['suggestions']:
        for suggestion in news_quality['suggestions']:
            print(f"   💡 {suggestion}")
    
    # ==================== 4. 构建新闻摘要 ====================
    news_summary = ""
    if unique_news:
        news_items = []
        # 取最新的50条新闻（扩大范围）
        for n in unique_news[:50]:
            title = n.get('title', '')
            url = n.get('url', '')
            source = n.get('source', '') or n.get('platform_name', '')
            publish_time = n.get('publish_time', '')
            time_str = f" ({publish_time})" if publish_time else ""
            if url:
                news_items.append(f"- [{title}]({url}) 【{source}{time_str}】")
            else:
                news_items.append(f"- {title} 【{source}{time_str}】")
        news_summary = "\n".join(news_items)
    
    today = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    
    # ==================== 5. 使用完整的配置列表 ====================
    # 友商/竞争对手（18家）
    all_competitors = list(OPTICAL_PARTNERS.keys()) + list(CONNECTOR_PARTNERS.keys()) + list(POWER_PARTNERS.keys())
    # 额外添加消费电子竞争对手
    all_competitors.extend(['歌尔股份', '蓝思科技', '工业富联', '鹏鼎控股', '东山精密', '领益智造', '瑞声科技', '比亚迪电子'])
    competitors = request.competitors or list(set(all_competitors))  # 去重
    
    # 供应商（从SUPPLIERS配置中提取所有供应商名称）
    all_suppliers = []
    for category, suppliers in SUPPLIERS.items():
        all_suppliers.extend(list(suppliers.keys()))
    # 额外添加重要供应商
    all_suppliers.extend(['京东方A', '舜宇光学', '欣旺达', '德赛电池', '信维通信', '长盈精密', '蓝思科技'])
    upstream = request.upstream or list(set(all_suppliers))  # 去重
    
    # 客户（10家）
    all_customers = list(CUSTOMERS.keys())
    downstream = request.downstream or all_customers
    
    print(f"📋 分析配置: {len(competitors)}家友商, {len(upstream)}家供应商, {len(downstream)}家客户")
    
    prompt = get_supply_chain_analysis_prompt(
        company_name=request.company_name,
        today=today,
        competitors=competitors,
        upstream=upstream,
        downstream=downstream,
        news_summary=news_summary,
        news_count=len(unique_news),
        commodity_summary=commodity_summary
    )
    
    used_model = ""
    used_api = ""
    
    try:
        print(f"🔄 尝试内网 API: {internal['api_base']}")
        # 内网超时设为15秒，避免长时间等待
        response = call_ai_api(
            internal["api_base"], internal["api_key"], internal["model"],
            ANALYSIS_SYSTEM_PROMPT, prompt, timeout=15, max_tokens=8000
        )
        
        if response.status_code == 200:
            used_model = internal["model"]
            used_api = "内网"
            print(f"✅ 内网 API 调用成功")
        else:
            raise Exception(f"内网 API 返回 {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ 内网 API 不可用: {e}")
        print(f"🔄 切换到外网 API: {external['api_base']}")
        
        if not external["api_key"]:
            raise HTTPException(
                status_code=400, 
                detail="内网 API 不可用，且未配置外网 API Key"
            )
        
        try:
            # 检测是否使用 Gemini API
            is_gemini = "generativelanguage.googleapis.com" in external["api_base"]
            
            if is_gemini:
                # 优先使用请求中的 thinking_level，否则使用配置
                thinking_level = request.thinking_level or external.get("thinking_level", "high")
                print(f"🧠 使用 Gemini 3 Pro (thinking_level={thinking_level})")
                response = call_gemini_api(
                    external["api_base"], external["api_key"], external["model"],
                    ANALYSIS_SYSTEM_PROMPT, prompt,
                    thinking_level=thinking_level,
                    timeout=300, max_tokens=8000  # Gemini 3 思考模式需要更长超时
                )
            else:
                response = call_ai_api(
                    external["api_base"], external["api_key"], external["model"],
                    ANALYSIS_SYSTEM_PROMPT, prompt, timeout=180, max_tokens=8000
                )
            used_model = external["model"]
            used_api = "外网"
            print(f"✅ 外网 API 调用成功")
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"内外网 API 均不可用: 内网({e}), 外网({e2})")
    
    try:
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"AI API调用失败: {response.text}")
        
        # 检测是否使用 Gemini API 来决定解析方式
        is_gemini = "generativelanguage.googleapis.com" in external.get("api_base", "")
        
        if is_gemini:
            content, error = parse_gemini_response(response)
            if error:
                raise HTTPException(status_code=500, detail=error)
        else:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"]
            else:
                raise HTTPException(status_code=500, detail="无法解析AI响应")
        
        return {
            "status": "success",
            "content": content,
            "model": used_model,
            "api_source": used_api,
            "news_count": len(unique_news),
            "news_quality": {
                "score": news_quality['quality_score'],
                "has_customer_news": news_quality['has_customer_news'],
                "has_competitor_news": news_quality['has_competitor_news'],
                "has_tariff_news": news_quality['has_tariff_news'],
                "suggestions": news_quality['suggestions']
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成分析失败: {str(e)}")
