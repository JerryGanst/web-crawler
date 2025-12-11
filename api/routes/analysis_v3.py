"""
模块化分析 API V3 - 分而治之

调用流程：
1. 第一轮：并行调用 4 个模块（客户/友商/原材料/政策）
2. 第二轮：整合总结

优势：
- 每个 prompt 更短更专注
- AI 注意力集中，输出质量高
- 可并行调用，速度快
"""
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict
from pathlib import Path
from fastapi import APIRouter, HTTPException
import yaml
import os

from ..cache import cache
from ..models import AnalysisRequest

# 导入模块化 prompts
from prompts.analysis_prompts_v3 import (
    get_all_module_prompts,
    get_summary_prompt,
    precheck_news_quality
)

router = APIRouter()

BASE_DIR = Path(__file__).parent.parent.parent


def get_ai_config():
    """获取 AI 配置"""
    config_path = BASE_DIR / "config" / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    
    ai_config = config.get("ai", {})
    external = ai_config.get("external", {})
    
    return {
        "api_key": external.get("api_key", "") or os.environ.get("AI_API_KEY", ""),
        "api_base": external.get("api_base", "https://api.siliconflow.cn/v1"),
        "model": external.get("model", "Pro/google/gemini-2.0-flash-001")
    }


async def call_ai_async(
    session: aiohttp.ClientSession,
    api_base: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 1500,
    timeout: int = 60
) -> str:
    """异步调用 AI API"""
    is_google_api = "generativelanguage.googleapis.com" in api_base
    
    # Google 官方 generateContent 接口
    if is_google_api:
        headers = {"Content-Type": "application/json"}
        if api_key:
            # Google API 支持 query param，也接受 header
            headers["x-goog-api-key"] = api_key
        
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generation_config": {
                "temperature": 0.7,
                "max_output_tokens": max_tokens
            }
        }
        url = f"{api_base.rstrip('/')}/models/{model}:generateContent"
        if api_key and "key=" not in url:
            url = f"{url}?key={api_key}"
    else:
        # OpenAI/SiliconFlow 兼容的 chat/completions
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens
        }
        url = f"{api_base.rstrip('/')}/chat/completions"
    
    try:
        async with session.post(
            url,
            headers=headers,
            json=payload,
            timeout=aiohttp.ClientTimeout(total=timeout)
        ) as response:
            if response.status != 200:
                text = await response.text()
                raise Exception(f"API 返回 {response.status}: {text[:200]}")
            
            result = await response.json()
            if is_google_api:
                # Google generateContent 响应
                candidates = result.get("candidates", [])
                for cand in candidates:
                    parts = cand.get("content", {}).get("parts", [])
                    texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
                    merged = "".join(texts).strip()
                    if merged:
                        return merged
                raise Exception("无法解析 AI 响应 (google)")
            else:
                # OpenAI 兼容响应
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
                else:
                    raise Exception("无法解析 AI 响应")
                
    except asyncio.TimeoutError:
        raise Exception("API 调用超时")


async def run_first_round(
    news_summary: str,
    commodity_summary: str,
    today: str,
    ai_config: dict
) -> Dict[str, str]:
    """
    第一轮：并行调用 4 个分析模块
    """
    prompts = get_all_module_prompts(news_summary, commodity_summary, today)
    
    results = {}
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        module_names = []
        
        for name, prompt_data in prompts.items():
            module_names.append(name)
            task = call_ai_async(
                session=session,
                api_base=ai_config["api_base"],
                api_key=ai_config["api_key"],
                model=ai_config["model"],
                system_prompt=prompt_data["system"],
                user_prompt=prompt_data["user"],
                max_tokens=prompt_data["max_tokens"],
                timeout=60
            )
            tasks.append(task)
        
        # 并行执行
        print(f"🚀 [V3] 并行调用 {len(tasks)} 个模块...")
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for name, response in zip(module_names, responses):
            if isinstance(response, Exception):
                print(f"⚠️ 模块 {name} 失败: {response}")
                results[name] = f"*{name} 模块分析失败: {str(response)[:100]}*"
            else:
                print(f"✅ 模块 {name} 完成")
                results[name] = response
    
    return results


async def run_second_round(
    today: str,
    first_round_results: Dict[str, str],
    ai_config: dict
) -> str:
    """
    第二轮：整合总结
    """
    prompt_data = get_summary_prompt(
        today=today,
        customer_analysis=first_round_results.get("customer", "无数据"),
        competitor_analysis=first_round_results.get("competitor", "无数据"),
        material_analysis=first_round_results.get("material", "无数据"),
        tariff_analysis=first_round_results.get("tariff", "无数据")
    )
    
    async with aiohttp.ClientSession() as session:
        print(f"🔄 [V3] 第二轮：整合总结...")
        result = await call_ai_async(
            session=session,
            api_base=ai_config["api_base"],
            api_key=ai_config["api_key"],
            model=ai_config["model"],
            system_prompt=prompt_data["system"],
            user_prompt=prompt_data["user"],
            max_tokens=prompt_data["max_tokens"],
            timeout=90
        )
        print(f"✅ 整合完成")
        return result


def assemble_final_report(
    first_round: Dict[str, str],
    second_round: str,
    today: str
) -> str:
    """
    组装最终报告
    """
    report = f"""# 立讯技术产业链分析报告
**分析日期**：{today}

---

{second_round}

---

# 详细分析

{first_round.get("customer", "")}

---

{first_round.get("competitor", "")}

---

{first_round.get("material", "")}

---

{first_round.get("tariff", "")}

---

*报告由 TrendRadar V3 模块化分析系统生成*
"""
    return report


def fetch_realtime_news(keywords: list, max_news: int = 30) -> list:
    """获取实时新闻（复用现有逻辑）"""
    import requests as req
    
    all_news = []
    
    # 同花顺快讯
    try:
        url = "https://news.10jqka.com.cn/tapp/news/push/stock/?page=1&tag=&track=website&pagesize=50"
        resp = req.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if resp.status_code == 200:
            data = resp.json()
            if data.get("data", {}).get("list"):
                for item in data["data"]["list"][:30]:
                    title = item.get("title", "")
                    if any(kw in title for kw in keywords):
                        all_news.append({
                            "title": title,
                            "url": item.get("url", ""),
                            "source": "同花顺",
                            "time": item.get("ctime", "")
                        })
    except Exception as e:
        print(f"⚠️ 同花顺获取失败: {e}")
    
    # 东方财富快讯
    try:
        url = "https://np-listapi.eastmoney.com/comm/wap/getListInfo?cb=callback&client=wap&type=0&mession=&page=1&pagesize=50"
        resp = req.get(url, timeout=10)
        if resp.status_code == 200:
            text = resp.text
            if text.startswith("callback("):
                text = text[9:-1]
            import json
            data = json.loads(text)
            if data.get("data", {}).get("list"):
                for item in data["data"]["list"][:30]:
                    title = item.get("title", "")
                    if any(kw in title for kw in keywords):
                        all_news.append({
                            "title": title,
                            "url": item.get("url", ""),
                            "source": "东方财富",
                            "time": item.get("showtime", "")
                        })
    except Exception as e:
        print(f"⚠️ 东方财富获取失败: {e}")
    
    return all_news[:max_news]


@router.post("/api/generate-analysis-v3")
async def generate_analysis_modular(request: AnalysisRequest):
    """
    模块化分析报告生成（V3）
    
    优势：
    - 第一轮 4 个模块并行调用，速度快
    - 每个模块 prompt 更短更专注，质量高
    - 第二轮整合，有全局视角
    """
    ai_config = get_ai_config()
    if request.model:
        ai_config["model"] = request.model.strip()
    
    if not ai_config["api_key"]:
        raise HTTPException(status_code=400, detail="未配置 AI API Key")
    
    # ==================== 获取数据 ====================
    print(f"📡 [V3] 开始模块化分析...")
    
    # 获取新闻
    supply_chain_keywords = [
        "立讯", "歌尔", "蓝思", "富联", "旭创", "新易盛", "光迅", "天孚",
        "苹果", "Apple", "iPhone", "华为", "Meta", "小米",
        "连接器", "电源", "充电器", "光模块", "线材",
        "安费诺", "莫仕", "TE", "中航光电", "奥海", "航嘉", "台达",
        "关税", "贸易", "制裁",
        "铜", "镍", "塑料", "ABS", "PA66"
    ]
    
    realtime_news = fetch_realtime_news(supply_chain_keywords)
    print(f"📰 实时新闻: {len(realtime_news)} 条")
    
    # 合并请求中的新闻
    all_news = list(request.news) if request.news else []
    all_news.extend(realtime_news)
    
    # 合并缓存新闻
    cached_supply = cache.get("news:supply-chain")
    if cached_supply:
        all_news.extend(cached_supply.get("data", []))
    
    # 去重
    seen = set()
    unique_news = []
    for n in all_news:
        title = n.get("title", "")
        if title and title not in seen:
            seen.add(title)
            unique_news.append(n)
    
    print(f"✅ 去重后新闻: {len(unique_news)} 条")
    
    # 新闻质量预检
    news_quality = precheck_news_quality(unique_news)
    print(f"📊 新闻质量: {news_quality['quality_score']}/100")
    if news_quality['suggestions']:
        for s in news_quality['suggestions']:
            print(f"   💡 {s}")
    
    # 构建新闻摘要
    news_summary = "\n".join([
        f"- [{n.get('title', '')}]({n.get('url', '')}) 【{n.get('source', '')}】"
        for n in unique_news[:50]
    ])
    
    # 获取大宗商品数据
    commodity_summary = ""
    try:
        from scrapers.commodity import CommodityScraper
        scraper = CommodityScraper()
        commodity_data = scraper.scrape()
        
        if commodity_data:
            lines = []
            for c in commodity_data[:30]:
                name = c.get('chinese_name') or c.get('name', '')
                price = c.get('price', 0)
                change = c.get('change_percent', 0)
                unit = c.get('unit', '')
                lines.append(f"- {name}: {price} {unit} ({'+' if change >= 0 else ''}{change}%)")
            commodity_summary = "\n".join(lines)
            print(f"📈 大宗商品: {len(commodity_data)} 条")
    except Exception as e:
        print(f"⚠️ 大宗商品数据获取失败: {e}")
        commodity_summary = "大宗商品数据暂未获取"
    
    today = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    
    # ==================== 模块化调用 ====================
    try:
        # 第一轮：并行分析
        first_round = await run_first_round(
            news_summary=news_summary,
            commodity_summary=commodity_summary,
            today=today,
            ai_config=ai_config
        )
        
        # 第二轮：整合总结
        second_round = await run_second_round(
            today=today,
            first_round_results=first_round,
            ai_config=ai_config
        )
        
        # 组装最终报告
        final_report = assemble_final_report(first_round, second_round, today)
        
        return {
            "status": "success",
            "content": final_report,
            "model": ai_config["model"],
            "api_source": "外网",
            "news_count": len(unique_news),
            "news_quality": {
                "score": news_quality["quality_score"],
                "suggestions": news_quality.get("suggestions", [])
            },
            "modules_completed": list(first_round.keys()),
            "version": "V3-modular",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")
