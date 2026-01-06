"""
模块化分析 API V4 - 动态关税分类 + 原材料分离分析

核心改进（基于领导反馈）：
1. 关税政策：AI 先分类，然后逐一单独分析
2. 原材料：数据直接嵌入 + 成本分析单独走大模型
3. 模块完全独立，最后拼装整合

流程：
    第一轮（并行）：客户分析、友商分析、关税分类
    第二轮（并行）：关税各分类单独分析、原材料成本分析
    第三轮：执行摘要整合
    最终：拼装报告
"""
import asyncio
import aiohttp
import json
import re
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
import yaml
import os

from ..cache import cache
from ..models import AnalysisRequest

from prompts.analysis_prompts_v4 import (
    CUSTOMER_MODULE,
    COMPETITOR_MODULE,
    TARIFF_CLASSIFIER_MODULE,
    MATERIAL_ANALYSIS_MODULE,
    SUMMARY_MODULE,
    get_module_prompt,
    get_tariff_analysis_prompt,
    build_material_section,
    fetch_news_full_content,
    filter_tariff_news,
    filter_news_by_category,
    precheck_news_quality,
    assemble_final_report_v4
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
        "api_base": external.get("api_base", "https://generativelanguage.googleapis.com/v1beta"),
        "model": external.get("model", "gemini-3-pro-preview"),
    }


async def call_ai_async(
    session: aiohttp.ClientSession,
    api_base: str, api_key: str, model: str,
    system_prompt: str, user_prompt: str,
    max_tokens: int = 1500, timeout: int = 90
) -> str:
    """异步调用 AI API"""
    is_google_api = "generativelanguage.googleapis.com" in api_base
    
    if is_google_api:
        headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generation_config": {"temperature": 1.0, "max_output_tokens": max_tokens}
        }
        url = f"{api_base.rstrip('/')}/models/{model}:generateContent?key={api_key}"
    else:
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
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
    
    async with session.post(url, headers=headers, json=payload, 
                           timeout=aiohttp.ClientTimeout(total=timeout)) as response:
        if response.status != 200:
            text = await response.text()
            raise Exception(f"API error {response.status}: {text[:200]}")
        
        result = await response.json()
        
        if is_google_api:
            candidates = result.get("candidates", [])
            for c in candidates:
                parts = c.get("content", {}).get("parts", [])
                texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
                if texts:
                    return "".join(texts).strip()
            raise Exception("No response from Gemini")
        else:
            if "choices" in result and result["choices"]:
                return result["choices"][0]["message"]["content"]
            raise Exception("No response")


def parse_tariff_categories(response: str) -> List[str]:
    """
    解析关税分类结果
    
    Args:
        response: AI 返回的 JSON 数组字符串
    
    Returns:
        分类列表
    """
    # 尝试直接解析 JSON
    try:
        # 清理可能的 markdown 代码块
        cleaned = response.strip()
        if cleaned.startswith("```"):
            # 去掉代码块标记
            cleaned = re.sub(r'^```json?\s*', '', cleaned)
            cleaned = re.sub(r'\s*```$', '', cleaned)
        
        categories = json.loads(cleaned)
        if isinstance(categories, list):
            return [str(c) for c in categories if c]
        return []
    except json.JSONDecodeError:
        pass
    
    # 尝试用正则提取
    try:
        # 找到类似 ["xxx", "yyy"] 的模式
        match = re.search(r'\[([^\]]*)\]', response)
        if match:
            content = match.group(1)
            # 提取引号内的内容
            items = re.findall(r'"([^"]+)"', content)
            if items:
                return items
    except Exception:
        pass
    
    # 最后尝试按行分割
    lines = response.strip().split('\n')
    categories = []
    for line in lines:
        line = line.strip().strip('-').strip('•').strip()
        if line and not line.startswith('[') and not line.startswith('{'):
            categories.append(line)
    
    return categories[:10]  # 最多返回10个分类


async def run_first_round(
    news_summary: str,
    news_with_content: str,
    ai_config: dict
) -> Dict[str, any]:
    """
    第一轮：并行运行客户、友商、关税分类模块
    
    Returns:
        {
            "customer": "客户分析结果",
            "competitor": "友商分析结果", 
            "tariff_categories": ["中美", "中欧", ...]
        }
    """
    results = {}
    
    async with aiohttp.ClientSession() as session:
        # 准备任务
        tasks = []
        task_names = []
        
        # 客户模块
        customer_prompt = get_module_prompt(CUSTOMER_MODULE, news_summary=news_summary)
        tasks.append(call_ai_async(
            session, ai_config["api_base"], ai_config["api_key"], ai_config["model"],
            customer_prompt["system"], customer_prompt["user"], customer_prompt["max_tokens"]
        ))
        task_names.append("customer")
        
        # 友商模块
        competitor_prompt = get_module_prompt(COMPETITOR_MODULE, news_summary=news_summary)
        tasks.append(call_ai_async(
            session, ai_config["api_base"], ai_config["api_key"], ai_config["model"],
            competitor_prompt["system"], competitor_prompt["user"], competitor_prompt["max_tokens"]
        ))
        task_names.append("competitor")
        
        # 关税分类模块
        classifier_prompt = get_module_prompt(TARIFF_CLASSIFIER_MODULE, news_with_content=news_with_content)
        tasks.append(call_ai_async(
            session, ai_config["api_base"], ai_config["api_key"], ai_config["model"],
            classifier_prompt["system"], classifier_prompt["user"], classifier_prompt["max_tokens"]
        ))
        task_names.append("tariff_classifier")
        
        print(f"🚀 [V4] 第一轮：并行调用 {len(tasks)} 个模块...")
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for name, resp in zip(task_names, responses):
            if isinstance(resp, Exception):
                print(f"⚠️ 模块 {name} 失败: {resp}")
                if name == "tariff_classifier":
                    results["tariff_categories"] = []
                else:
                    results[name] = f"*{name} 模块分析失败*"
            else:
                print(f"✅ 模块 {name} 完成")
                if name == "tariff_classifier":
                    categories = parse_tariff_categories(resp)
                    results["tariff_categories"] = categories
                    print(f"   📂 识别到 {len(categories)} 个关税分类: {categories}")
                else:
                    results[name] = resp
    
    return results


async def run_second_round(
    tariff_categories: List[str],
    tariff_news: List[Dict],
    material_data_section: str,
    ai_config: dict
) -> Dict[str, any]:
    """
    第二轮：并行运行各关税分类分析 + 原材料成本分析
    
    Returns:
        {
            "tariff_sections": {"中美": "分析内容", "中欧": "分析内容"},
            "material_analysis": "成本分析内容"
        }
    """
    results = {
        "tariff_sections": {},
        "material_analysis": ""
    }
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        task_info = []  # (type, name)
        
        # 为每个关税分类创建分析任务
        for category in tariff_categories:
            # 筛选该分类相关的新闻
            category_news = filter_news_by_category(tariff_news, category)
            
            if not category_news:
                print(f"   ⏭️ 分类 [{category}] 无相关新闻，跳过")
                continue
            
            # 构建新闻内容
            news_content = "\n\n".join([
                f"### {n.get('title', '')}\n**来源**: {n.get('source', '')} | [链接]({n.get('url', '')})\n**内容**: {n.get('content', '无全文')[:800]}"
                for n in category_news[:5]
            ])
            
            prompt = get_tariff_analysis_prompt(category, news_content)
            tasks.append(call_ai_async(
                session, ai_config["api_base"], ai_config["api_key"], ai_config["model"],
                prompt["system"], prompt["user"], prompt["max_tokens"]
            ))
            task_info.append(("tariff", category))
        
        # 原材料成本分析任务
        material_prompt = get_module_prompt(MATERIAL_ANALYSIS_MODULE, material_data=material_data_section)
        tasks.append(call_ai_async(
            session, ai_config["api_base"], ai_config["api_key"], ai_config["model"],
            material_prompt["system"], material_prompt["user"], material_prompt["max_tokens"]
        ))
        task_info.append(("material", "analysis"))
        
        if tasks:
            print(f"🚀 [V4] 第二轮：并行调用 {len(tasks)} 个模块（{len(tariff_categories)} 个关税分类 + 1 个原材料分析）...")
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            for (task_type, name), resp in zip(task_info, responses):
                if isinstance(resp, Exception):
                    print(f"⚠️ {task_type}/{name} 失败: {resp}")
                    if task_type == "tariff":
                        results["tariff_sections"][name] = f"*{name} 分析失败*"
                    else:
                        results["material_analysis"] = "*原材料成本分析失败*"
                else:
                    print(f"✅ {task_type}/{name} 完成")
                    if task_type == "tariff":
                        results["tariff_sections"][name] = resp
                    else:
                        results["material_analysis"] = resp
    
    return results


async def run_third_round(
    today: str,
    customer_analysis: str,
    competitor_analysis: str,
    tariff_sections: Dict[str, str],
    material_analysis: str,
    ai_config: dict
) -> str:
    """
    第三轮：生成执行摘要
    """
    # 汇总关税分析
    tariff_summary = ""
    if tariff_sections:
        for category, analysis in tariff_sections.items():
            tariff_summary += f"### {category}\n{analysis}\n\n"
    else:
        tariff_summary = "本周暂无重大关税政策变化。"
    
    summary_prompt = get_module_prompt(
        SUMMARY_MODULE,
        today=today,
        customer_analysis=customer_analysis,
        competitor_analysis=competitor_analysis,
        tariff_analysis=tariff_summary,
        material_analysis=material_analysis
    )
    
    async with aiohttp.ClientSession() as session:
        print("🔄 [V4] 第三轮：生成执行摘要...")
        result = await call_ai_async(
            session, ai_config["api_base"], ai_config["api_key"], ai_config["model"],
            summary_prompt["system"], summary_prompt["user"], summary_prompt["max_tokens"], 120
        )
        print("✅ 执行摘要完成")
        return result


def fetch_realtime_news(keywords: list, max_news: int = 30) -> list:
    """获取实时新闻"""
    import requests as req
    all_news = []
    
    # 同花顺
    try:
        url = "https://news.10jqka.com.cn/tapp/news/push/stock/?page=1&tag=&track=website&pagesize=50"
        resp = req.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("data", {}).get("list", [])[:30]:
                title = item.get("title", "")
                if any(kw in title for kw in keywords):
                    all_news.append({
                        "title": title,
                        "url": item.get("url", ""),
                        "source": "同花顺"
                    })
    except Exception as e:
        print(f"⚠️ 同花顺失败: {e}")
    
    return all_news[:max_news]




def get_price_history() -> Dict[str, List[Dict]]:
    """获取价格历史数据"""
    try:
        from core.price_history import price_history
        return price_history.get_all_commodities_history(days=395)
    except Exception as e:
        print(f"⚠️ 获取价格历史失败: {e}")
        return {}


def get_today_key() -> str:
    """获取当天的日期键（格式：YYYYMMDD）"""
    return datetime.now().strftime("%Y%m%d")


def get_cache_keys(date_key: str) -> Dict[str, str]:
    """
    获取缓存键
    
    Args:
        date_key: 日期键（YYYYMMDD格式）
    
    Returns:
        包含状态键和数据键的字典
    """
    return {
        "status": f"analysis-v4-status-{date_key}",
        "data": f"analysis-v4-{date_key}"
    }


def check_analysis_status(date_key: str) -> Dict[str, any]:
    """
    检查分析状态
    
    Args:
        date_key: 日期键（YYYYMMDD格式）
    
    Returns:
        {
            "status": "none|pending|completed",
            "data": None 或完整的分析报告数据
        }
    """
    keys = get_cache_keys(date_key)
    
    # 检查状态缓存
    status_cache = cache.get(keys["status"])
    
    if not status_cache:
        # 状态缓存不存在，检查数据缓存是否存在
        data_cache = cache.get(keys["data"])
        if data_cache:
            return {"status": "completed", "data": data_cache}
        return {"status": "none", "data": None}
    
    # 状态缓存存在
    current_status = status_cache.get("status", "none")
    
    if current_status == "completed":
        # 尝试获取数据缓存
        data_cache = cache.get(keys["data"])
        if data_cache:
            return {"status": "completed", "data": data_cache}
        else:
            # 数据缓存已过期，重置状态
            return {"status": "none", "data": None}
    
    return {"status": current_status, "data": None}


def set_analysis_status(date_key: str, status: str, data: Optional[Dict] = None) -> bool:
    """
    设置分析状态
    
    Args:
        date_key: 日期键（YYYYMMDD格式）
        status: 状态（pending|completed）
        data: 分析报告数据（当状态为completed时必须提供）
    
    Returns:
        是否设置成功
    """
    keys = get_cache_keys(date_key)
    
    # 设置状态缓存（10分钟）
    status_data = {
        "status": status,
        "started_at": datetime.now().isoformat()
    }
    cache.set(keys["status"], status_data, ttl=600)  # 10分钟
    
    # 如果状态为completed，保存数据缓存（36小时）
    if status == "completed" and data:
        cache.set(keys["data"], data, ttl=129600)  # 36小时
        return True
    
    return True


def try_acquire_lock(date_key: str) -> bool:
    """
    尝试获取分布式锁（使用Redis SETNX）
    
    Args:
        date_key: 日期键
    
    Returns:
        是否成功获取锁
    """
    keys = get_cache_keys(date_key)
    status_cache = cache.get(keys["status"])
    
    # 如果状态缓存不存在，尝试设置为pending
    if not status_cache:
        return set_analysis_status(date_key, "pending")
    
    # 状态缓存已存在，无法获取锁
    return False




@router.post("/api/generate-analysis-v4")
async def generate_analysis_v4(request: AnalysisRequest):
    """
    V4 模块化分析 API（升级版）
    
    流程：
    1. 数据准备（新闻、原材料）
    2. 第一轮：客户、友商、关税分类（并行）
    3. 第二轮：关税各分类分析、原材料成本分析（并行）
    4. 第三轮：执行摘要整合
    5. 拼装最终报告
    
    缓存机制：
    - 状态缓存：10分钟（防止重复请求）
    - 数据缓存：36小时（提升响应速度）
    """
    # ========== 缓存检查 ==========
    date_key = get_today_key()
    cache_status = check_analysis_status(date_key)
    
    print(f"🔍 [缓存检查] 日期: {date_key}, 状态: {cache_status['status']}, 强制刷新: {request.force_refresh}")
    
    # 强制刷新：跳过缓存，直接生成新数据
    if request.force_refresh:
        print(f"🔄 [强制刷新] 跳过缓存检查，生成最新数据")
        # 清除旧的状态缓存，避免锁冲突
        cache.delete(f"analysis-v4-status-{date_key}")
    else:
        # 如果状态为 pending，返回提示
        if cache_status["status"] == "pending":
            return {
                "status": "pending",
                "message": "分析报告正在生成中，请稍后再试（约需3-5分钟）",
                "date": date_key,
                "timestamp": datetime.now().isoformat()
            }
        
        # 如果状态为 completed 且有缓存数据，直接返回
        if cache_status["status"] == "completed" and cache_status["data"]:
            print(f"✅ [缓存命中] 直接返回缓存数据")
            cached_data = cache_status["data"]
            cached_data["from_cache"] = True
            cached_data["cache_date"] = date_key
            return cached_data
    
    # ========== 获取分布式锁 ==========
    if not try_acquire_lock(date_key):
        # 锁获取失败，说明有其他请求正在处理
        return {
            "status": "pending",
            "message": "分析报告正在生成中，请稍后再试",
            "date": date_key,
            "timestamp": datetime.now().isoformat()
        }
    
    print(f"🔒 [已获取锁] 开始生成分析报告")
    
    # ========== AI 配置验证 ==========
    ai_config = get_ai_config()
    if request.model:
        ai_config["model"] = request.model.strip()
    if not ai_config["api_key"]:
        # 释放锁（删除状态缓存）
        cache.delete(f"analysis-v4-status-{date_key}")
        raise HTTPException(status_code=400, detail="未配置 AI API Key")
    
    print("=" * 60)
    print("📡 [V4] 开始模块化分析（动态关税分类 + 原材料分离分析）")
    print("=" * 60)
    
    # ========== 数据准备 ==========
    print("\n📦 [数据准备]")
    
    # 获取新闻
    keywords = ["立讯", "苹果", "华为", "关税", "贸易", "中美", "中欧", "越南", "印度", "铜", "塑料", "ABS"]
    # 异步执行同步的爬虫函数
    realtime_news = await run_in_threadpool(fetch_realtime_news, keywords)
    all_news = list(request.news) if request.news else []
    all_news.extend(realtime_news)
    
    # 从缓存获取
    cached = cache.get("news:supply-chain")
    if cached:
        all_news.extend(cached.get("data", []))
    
    # 去重
    seen = set()
    unique_news = [n for n in all_news if n.get("title") and n.get("title") not in seen and not seen.add(n.get("title"))]
    print(f"   📰 新闻总数: {len(unique_news)} 条")
    
    # 新闻质量预检
    quality = await run_in_threadpool(precheck_news_quality, unique_news)
    print(f"   📊 新闻质量: {quality['quality_score']}/100")
    if quality['suggestions']:
        print(f"   💡 建议: {', '.join(quality['suggestions'])}")
    
    # 筛选关税新闻并获取全文
    tariff_news = await run_in_threadpool(filter_tariff_news, unique_news)
    print(f"   🌐 关税相关: {len(tariff_news)} 条")
    
    if tariff_news:
        print("   📄 获取新闻全文...")
        tariff_news = await run_in_threadpool(fetch_news_full_content, tariff_news, max_items=20)
        content_count = len([n for n in tariff_news if n.get('content')])
        print(f"   ✅ 成功获取 {content_count} 条全文")
    
    # 获取原材料数据（从 MySQL 读取标准化数据）
    commodity_data = []
    try:
        from scrapers.commodity import CommodityScraper
        from database.manager import db_manager
        
        # 1. 爬取最新数据并入库
        scraper = CommodityScraper()
        raw_data = await run_in_threadpool(scraper.scrape)
        print(f"   📈 原材料爬取: {len(raw_data)} 条")
        
        # 2. 写入 MySQL（去重和标准化）
        try:
            stats_by_source = {}
            sources = set(item.get("source", "unknown") for item in raw_data)
            for src in sources:
                src_records = [item for item in raw_data if item.get("source", "unknown") == src]
                if not src_records:
                    continue
                db_stats = db_manager.write_commodity(src_records, source=src)
                if db_stats:
                    stats_by_source[src] = db_stats
            if stats_by_source:
                print(f"   ✅ MySQL 入库: {stats_by_source}")
        except Exception as e:
            print(f"   ⚠️ MySQL 入库失败: {e}")
        
        # 3. 从 MySQL 读取标准化数据（以 MySQL 为准）
        try:
            commodity_data = db_manager.get_commodity_latest()
            if not commodity_data:
                print("   ⚠️ MySQL commodity_latest 为空，使用原始数据")
                commodity_data = raw_data
            else:
                print(f"   ✅ 从 MySQL 读取: {len(commodity_data)} 条标准化数据")
                # 字段映射：MySQL → API 格式
                for item in commodity_data:
                    # 1. 合并 unit
                    price_unit = item.get('price_unit', '')
                    weight_unit = item.get('weight_unit', '')
                    if price_unit and weight_unit:
                        item['unit'] = f"{price_unit}/{weight_unit}"
                    else:
                        item['unit'] = price_unit or weight_unit or 'USD'
                    
                    # 2. current_price
                    if 'price' in item and 'current_price' not in item:
                        item['current_price'] = item['price']
                    
                    # 3. url
                    if 'url' not in item or not item['url']:
                        item['url'] = item.get('source_url', '')
                    
                    # 4. cleanup
                    for k in ['id', 'price_unit', 'weight_unit', 'version_ts', 'source_url']:
                        item.pop(k, None)
        except Exception as e:
            print(f"   ⚠️ 从 MySQL 读取失败: {e}，使用原始数据")
            commodity_data = raw_data
    except Exception as e:
        print(f"   ⚠️ 原材料获取失败: {e}")
    
    # 获取价格历史
    price_history_data = await run_in_threadpool(get_price_history)
    print(f"   📜 历史数据: {len(price_history_data)} 个品种")
    
    # 构建新闻摘要
    news_summary = "\n".join([
        f"- [{n.get('title', '')}]({n.get('url', '')}) 【{n.get('source', '')}】"
        for n in unique_news[:50]
    ])
    
    # 构建关税新闻全文
    news_with_content = "\n\n".join([
        f"### {n.get('title', '')}\n**来源**: {n.get('source', '')} | [链接]({n.get('url', '')})\n**内容**: {n.get('content', '无全文')[:800]}"
        for n in tariff_news[:15]
    ]) if tariff_news else "暂无关税相关新闻"
    
    # 构建原材料数据部分（不走大模型）
    material_data_section = await run_in_threadpool(build_material_section, commodity_data, price_history_data)
    
    today = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    
    try:
        # ========== 第一轮 ==========
        print("\n🔄 [第一轮] 客户、友商、关税分类")
        first_round = await run_first_round(news_summary, news_with_content, ai_config)
        
        tariff_categories = first_round.get("tariff_categories", [])
        
        # ========== 第二轮 ==========
        print(f"\n🔄 [第二轮] 关税分类分析({len(tariff_categories)}个) + 原材料成本分析")
        second_round = await run_second_round(
            tariff_categories,
            tariff_news,
            material_data_section,
            ai_config
        )
        
        # ========== 第三轮 ==========
        print("\n🔄 [第三轮] 执行摘要整合")
        summary = await run_third_round(
            today,
            first_round.get("customer", ""),
            first_round.get("competitor", ""),
            second_round.get("tariff_sections", {}),
            second_round.get("material_analysis", ""),
            ai_config
        )
        
        # ========== 拼装报告 ==========
        print("\n📝 [拼装] 生成最终报告")
        final_report = assemble_final_report_v4(
            summary,
            first_round.get("customer", ""),
            first_round.get("competitor", ""),
            material_data_section,
            second_round.get("material_analysis", ""),
            second_round.get("tariff_sections", {}),
            today
        )
        
        print("\n" + "=" * 60)
        print("✅ [V4] 分析完成!")
        print("=" * 60)
        
        # ========== 构建返回数据 ==========
        result_data = {
            "status": "success",
            "content": final_report,
            "model": ai_config["model"],
            "version": "V4-modular-upgraded",
            "stats": {
                "news_count": len(unique_news),
                "tariff_news_count": len(tariff_news),
                "tariff_categories": tariff_categories,
                "commodity_count": len(commodity_data),
                "news_quality_score": quality["quality_score"]
            },
            "modules_completed": {
                "first_round": ["customer", "competitor", "tariff_classifier"],
                "second_round": list(second_round.get("tariff_sections", {}).keys()) + ["material_analysis"],
                "third_round": ["summary"]
            },
            "timestamp": datetime.now().isoformat(),
            "from_cache": False,
            "cache_date": date_key
        }
        
        # ========== 保存到缓存 ==========
        print(f"💾 [保存缓存] 日期: {date_key}")
        set_analysis_status(date_key, "completed", result_data)
        
        return result_data
        
    except Exception as e:
        # ========== 异常处理：清除状态锁 ==========
        print(f"❌ [异常] 清除状态锁: {date_key}")
        cache.delete(f"analysis-v4-status-{date_key}")
        
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


async def generate_analysis_task():
    """
    定时任务专用：生成分析报告并缓存
    
    与接口版本的区别：
    - 不需要 Request 参数
    - 使用默认配置
    - 强制刷新缓存（force_refresh=True）
    - 专注于缓存生成，不返回具体数据
    """
    try:
        # 构造默认请求，force_refresh=True 确保总是生成最新数据
        request = AnalysisRequest(news=[], model=None, force_refresh=True)
        
        # 调用生成函数
        result = await generate_analysis_v4(request)
        
        print(f"✅ [定时任务] Analysis V4 报告生成成功")
        return result
    except Exception as e:
        print(f"❌ [定时任务] Analysis V4 报告生成失败: {e}")
        raise


@router.get("/api/analysis-v4/status")
async def get_v4_status():
    """获取 V4 API 状态"""
    ai_config = get_ai_config()
    return {
        "version": "V4-upgraded",
        "features": [
            "动态关税分类（AI自动识别国家/地区组合）",
            "关税分类单独分析（每个分类独立调用）",
            "原材料数据直接嵌入（不走大模型）",
            "原材料成本分析（单独走大模型）",
            "三轮模块化调用架构",
            "定时任务自动缓存（每4小时刷新）"
        ],
        "model": ai_config.get("model", "未配置"),
        "api_configured": bool(ai_config.get("api_key"))
    }
