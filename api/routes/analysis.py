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
    MARKET_SYSTEM_PROMPT
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
            "model": external_model
        }
    }


def call_ai_api(api_base: str, api_key: str, model: str, 
                system_prompt: str, user_prompt: str, 
                timeout: int = 180, max_tokens: int = 8000):
    """调用 AI API"""
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
    
    # 去重
    seen = set()
    unique_news = []
    for n in all_news:
        title = n["title"]
        if title not in seen and len(title) > 5:
            seen.add(title)
            unique_news.append(n)
    
    return unique_news[:50]


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
    
    # 构建商品数据摘要
    commodity_summary = []
    for item in commodity_data[:20]:
        name = item.get('chinese_name') or item.get('name', '')
        price = item.get('price', 0)
        change = item.get('change_percent', 0)
        unit = item.get('unit', '')
        commodity_summary.append(f"- {name}: ${price} ({'+' if change >= 0 else ''}{change}%) {unit}")
    
    today = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    prompt = get_market_analysis_prompt(commodity_summary, today)
    
    used_model = ""
    used_api = ""
    
    try:
        print(f"🔄 市场分析: 尝试内网 API...")
        response = call_ai_api(
            internal["api_base"], internal["api_key"], internal["model"],
            MARKET_SYSTEM_PROMPT, prompt, timeout=30, max_tokens=1000
        )
        
        if response.status_code == 200:
            used_model = internal["model"]
            used_api = "内网"
            print(f"✅ 内网 API 调用成功")
        else:
            raise Exception(f"内网 API 返回 {response.status_code}")
            
    except Exception as e:
        print(f"⚠️ 内网 API 不可用: {e}")
        print(f"🔄 切换到外网 API...")
        
        if not external["api_key"]:
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
            response = call_ai_api(
                external["api_base"], external["api_key"], external["model"],
                MARKET_SYSTEM_PROMPT, prompt, timeout=60, max_tokens=1000
            )
            used_model = external["model"]
            used_api = "外网"
            print(f"✅ 外网 API 调用成功")
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"AI API 不可用: {e2}")
    
    try:
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=f"AI API调用失败")
        
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
    
    # 关键词
    keywords = [
        "立讯", "歌尔", "蓝思", "富联", "富士康", "京东方", "BOE",
        "欣旺达", "德赛", "舜宇", "鹏鼎", "东山精密", "领益", "瑞声",
        "苹果", "Apple", "iPhone", "AirPods", "Vision Pro",
        "华为", "Huawei", "小米", "OPPO", "vivo", "三星",
        "消费电子", "果链", "代工", "供应链", "芯片", "半导体",
        "AI", "人工智能", "算力", "GPU", "英伟达"
    ]
    
    print(f"📡 正在实时抓取供应链相关新闻...")
    realtime_news = fetch_realtime_news(keywords)
    print(f"✅ 抓取到 {len(realtime_news)} 条相关新闻")
    
    # 合并新闻
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
    
    # 构建新闻摘要
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
    
    competitors = request.competitors or ['歌尔股份', '蓝思科技', '工业富联', '鹏鼎控股', '东山精密', '领益智造', '瑞声科技']
    upstream = request.upstream or ['京东方A', '舜宇光学', '欣旺达', '德赛电池', '信维通信', '长盈精密']
    downstream = request.downstream or ['苹果', '华为', 'Meta', '奇瑞汽车', '小米', 'OPPO/vivo']
    
    prompt = get_supply_chain_analysis_prompt(
        company_name=request.company_name,
        today=today,
        competitors=competitors,
        upstream=upstream,
        downstream=downstream,
        news_summary=news_summary,
        news_count=len(unique_news)
    )
    
    used_model = ""
    used_api = ""
    
    try:
        print(f"🔄 尝试内网 API: {internal['api_base']}")
        response = call_ai_api(
            internal["api_base"], internal["api_key"], internal["model"],
            ANALYSIS_SYSTEM_PROMPT, prompt, timeout=60, max_tokens=8000
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
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成分析失败: {str(e)}")
