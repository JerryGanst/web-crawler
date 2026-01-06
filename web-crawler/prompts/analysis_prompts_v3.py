"""
供应链分析报告 - 模块化 Prompt V3.0

核心思路：分而治之
- 第一轮：4个模块并行分析（客户/友商/原材料/政策）
- 第二轮：整合总结（执行摘要/SWOT/建议）

优势：
- 每个 prompt 更短更专注
- AI 注意力集中，输出质量高
- 可并行调用，速度快
- 某模块失败不影响其他
"""

from typing import Dict, List, Optional
from dataclasses import dataclass

# ============================================================
# 模块定义
# ============================================================

@dataclass
class AnalysisModule:
    """分析模块"""
    name: str           # 模块名
    system_prompt: str  # System Prompt
    user_prompt: str    # User Prompt 模板
    max_tokens: int     # 最大输出 tokens


# ============================================================
# 第一轮：并行分析模块
# ============================================================

# 模块1：客户动态分析
CUSTOMER_MODULE = AnalysisModule(
    name="customer",
    system_prompt="""你是立讯技术的客户关系分析师。
只分析客户相关的新闻，不要扯其他内容。
风格：简洁、有洞见、引用来源。""",
    
    user_prompt="""# 任务
分析以下新闻中与**客户**相关的内容。

# 立讯技术主要客户
苹果、华为、Meta、小米、OPPO、vivo、汽车客户

# 新闻列表
{news_summary}

# 输出格式

## 客户动态分析

### 关键发现
用2-3个要点总结最重要的客户动态，格式：
- ✅/⚠️/🔴 **[客户名]**：一句话结论 — [来源](链接)

### 详细分析
| 客户 | 事件 | 对立讯影响 | 来源 |
|------|------|------------|------|
（只填有新闻的客户）

### 小结
一句话总结客户面的整体情况。

---
*如果没有客户相关新闻，直接写"本周客户面暂无重大动态"即可。*
""",
    max_tokens=1000
)


# 模块2：友商竞争分析
COMPETITOR_MODULE = AnalysisModule(
    name="competitor",
    system_prompt="""你是立讯技术的竞争情报分析师。
按三大业务领域（光电模块/连接器/电源）分析友商动态。
风格：简洁、有洞见、引用来源。""",
    
    user_prompt="""# 任务
分析以下新闻中与**友商**相关的内容。

# 立讯技术三大业务领域及友商

### 💡 光电模块
Credo、旭创科技（中际旭创）、新易盛、天孚通信、光迅科技、Finisar

### 🔌 连接器
安费诺、莫仕(Molex)、TE、中航光电、得意精密、意华股份、金信诺、华丰科技

### ⚡ 电源
奥海科技、航嘉、赛尔康、台达电子

# 新闻列表
{news_summary}

# 输出格式

## 友商竞争分析

### 💡 光电模块
（分析这个领域友商的动态，没新闻就写"暂无重大动态"）

### 🔌 连接器
（分析这个领域友商的动态）

### ⚡ 电源
（分析这个领域友商的动态）

### 竞争格局小结
一句话总结本周友商面的整体情况。

---
*只分析有新闻的友商，不要把没新闻的硬塞进去。*
""",
    max_tokens=1500
)


# 模块3：原材料行情分析
MATERIAL_MODULE = AnalysisModule(
    name="material",
    system_prompt="""你是立讯技术的采购成本分析师。
分析原材料价格变化对成本的影响。
覆盖金属（铜镍锡锌铝）和塑料（ABS/PP/PA66等）。""",
    
    user_prompt="""# 任务
分析原材料价格对立讯技术成本的影响。

# 大宗商品价格数据
{commodity_summary}

# 立讯技术原材料需求
- **金属**：铜（连接器端子）、镍、锡（焊接）、锌、铝
- **塑料**：ABS（外壳）、PP、PA66（线材护套）、PVC、PBT、PC

# 输出格式

## 原材料行情分析

### 金属类
| 原材料 | 价格 | 周涨跌 | 对立讯成本影响 |
|--------|------|--------|----------------|
（填入有数据的金属）

### 塑料类
| 原材料 | 价格 | 周涨跌 | 对立讯成本影响 |
|--------|------|--------|----------------|
（填入有数据的塑料）

### 成本影响小结
总结本周原材料对立讯成本的综合影响。

---
*没有价格数据的原材料跳过，不要编造。*
""",
    max_tokens=800
)


# 模块4：关税政策分析
TARIFF_MODULE = AnalysisModule(
    name="tariff",
    system_prompt="""你是立讯技术的政策风险分析师。
只分析关税、贸易政策、出口管制等相关新闻。""",
    
    user_prompt="""# 任务
分析与关税/贸易政策相关的新闻。

# 关注点
- 中美关税变化
- 出口管制/实体清单
- 产业政策变化
- 对消费电子供应链的影响

# 新闻列表
{news_summary}

# 输出格式

## 关税政策分析

### 政策动态
（如有相关新闻，分析其对立讯的影响）

### 风险评估
（评估当前政策风险等级）

---
*如果没有相关新闻，直接写"本周暂无重大政策变化"即可，不要硬凑。*
""",
    max_tokens=600
)


# ============================================================
# 第二轮：整合总结模块
# ============================================================

SUMMARY_MODULE = AnalysisModule(
    name="summary",
    system_prompt="""你是立讯技术的首席战略分析师。
根据各模块的分析结果，生成执行摘要、SWOT分析和行动建议。
风格：高度概括、有洞见、可执行。
禁止套话：不要写"加强研发"、"密切关注"等空话。""",
    
    user_prompt="""# 任务
根据以下各模块的分析结果，生成最终报告。

# 日期
{today}

# 客户动态分析
{customer_analysis}

# 友商竞争分析
{competitor_analysis}

# 原材料行情分析
{material_analysis}

# 关税政策分析
{tariff_analysis}

# 输出格式

## 一、执行摘要

用3-5个要点概括本周最重要的发现：
- ✅/⚠️/🔴 **[结论]**：说明
（从上面各模块中提炼最关键的信息）

**对立讯技术的整体影响**：一句话定性判断

---

## 二、SWOT分析

基于本周信息，列出关键点（每条必须有具体依据）：

| 维度 | 要点 | 依据 |
|------|------|------|
| S优势 | | |
| W劣势 | | |
| O机会 | | |
| T威胁 | | |

---

## 三、本周行动建议

给出**具体可执行**的建议：

| 优先级 | 针对问题 | 建议动作 | 预期效果 |
|--------|----------|----------|----------|
| P0 | | | |
| P1 | | | |

**禁止**：写"加强管理"、"持续优化"、"密切关注"等套话

---

## 四、下周关注

列出2-3个下周需要重点跟踪的事项。
""",
    max_tokens=1500
)


# ============================================================
# 模块化调用接口
# ============================================================

# 所有第一轮模块
FIRST_ROUND_MODULES = [
    CUSTOMER_MODULE,
    COMPETITOR_MODULE,
    MATERIAL_MODULE,
    TARIFF_MODULE
]


def get_module_prompt(module: AnalysisModule, **kwargs) -> dict:
    """
    获取模块的 prompt
    
    Returns:
        {
            "system": system_prompt,
            "user": formatted_user_prompt,
            "max_tokens": max_tokens
        }
    """
    return {
        "system": module.system_prompt,
        "user": module.user_prompt.format(**kwargs),
        "max_tokens": module.max_tokens
    }


def get_all_module_prompts(
    news_summary: str,
    commodity_summary: str,
    today: str
) -> Dict[str, dict]:
    """
    获取所有第一轮模块的 prompts
    
    Returns:
        {
            "customer": {"system": ..., "user": ..., "max_tokens": ...},
            "competitor": {...},
            "material": {...},
            "tariff": {...}
        }
    """
    return {
        "customer": get_module_prompt(
            CUSTOMER_MODULE, 
            news_summary=news_summary
        ),
        "competitor": get_module_prompt(
            COMPETITOR_MODULE, 
            news_summary=news_summary
        ),
        "material": get_module_prompt(
            MATERIAL_MODULE, 
            commodity_summary=commodity_summary
        ),
        "tariff": get_module_prompt(
            TARIFF_MODULE, 
            news_summary=news_summary
        )
    }


def get_summary_prompt(
    today: str,
    customer_analysis: str,
    competitor_analysis: str,
    material_analysis: str,
    tariff_analysis: str
) -> dict:
    """
    获取第二轮整合模块的 prompt
    """
    return get_module_prompt(
        SUMMARY_MODULE,
        today=today,
        customer_analysis=customer_analysis,
        competitor_analysis=competitor_analysis,
        material_analysis=material_analysis,
        tariff_analysis=tariff_analysis
    )


# ============================================================
# 兼容旧接口（向后兼容）
# ============================================================

# 保留旧的 System Prompt（用于不支持模块化的场景）
ANALYSIS_SYSTEM_PROMPT = """你是立讯技术的战略分析顾问。
风格：说人话，给干货，有洞见，不套话。
分析主体：立讯技术（非立讯精密集团）
三大业务：光电模块、连接器、电源"""

# 完整的友商列表（三大领域）
COMPETITORS = {
    "光电模块": ["Credo", "旭创科技", "新易盛", "天孚通信", "光迅科技", "Finisar"],
    "连接器": ["安费诺", "莫仕", "TE", "中航光电", "得意精密", "意华股份", "金信诺", "华丰科技"],
    "电源": ["奥海科技", "航嘉", "赛尔康", "台达电子"]
}

MATERIAL_CATEGORIES = {
    "金属类": ["铜", "镍", "锡", "锌", "金", "铝", "银"],
    "塑料类": ["PVC", "PA66", "PBT", "LDPE", "ABS", "PP", "PET", "PC"]
}


def get_supply_chain_analysis_prompt(
    company_name: str,
    today: str,
    competitors: list,
    upstream: list,
    downstream: list,
    news_summary: str,
    news_count: int,
    commodity_summary: str = ""
) -> str:
    """
    兼容旧接口的单一 prompt（建议使用模块化接口替代）
    """
    return f"""# 分析任务
为**立讯技术**生成竞争格局分析报告。
日期：{today}
新闻数量：{news_count}条

# 新闻
{news_summary}

# 大宗商品价格
{commodity_summary}

# 要求
1. 有料就说，没料跳过
2. 引用新闻来源
3. 禁止套话

# 结构
1. 执行摘要（3-5个要点）
2. 客户动态
3. 友商分析（光电模块/连接器/电源三个领域）
4. 原材料行情（金属+塑料）
5. 关税政策
6. SWOT分析
7. 行动建议
"""


def precheck_news_quality(news_list: list) -> dict:
    """预检新闻质量"""
    customer_keywords = ["苹果", "Apple", "华为", "Huawei", "Meta", "iPhone", "小米"]
    competitor_keywords = [
        "Credo", "旭创", "新易盛", "天孚", "光迅", "Finisar",
        "安费诺", "莫仕", "TE", "中航光电", "得意精密", "意华", "金信诺", "华丰",
        "奥海", "航嘉", "赛尔康", "台达",
        "工业富联", "富士康", "比亚迪电子", "歌尔", "蓝思"
    ]
    tariff_keywords = ["关税", "贸易战", "出口管制", "制裁"]
    material_keywords = ["铜", "镍", "锡", "铝", "塑料", "ABS", "PP", "PA66"]
    
    result = {
        "total_count": len(news_list),
        "has_customer_news": False,
        "has_competitor_news": False,
        "has_tariff_news": False,
        "has_material_news": False,
        "quality_score": 0,
        "suggestions": []
    }
    
    for news in news_list:
        text = news.get("title", "") + news.get("content", "")[:200]
        if any(kw in text for kw in customer_keywords):
            result["has_customer_news"] = True
        if any(kw in text for kw in competitor_keywords):
            result["has_competitor_news"] = True
        if any(kw in text for kw in tariff_keywords):
            result["has_tariff_news"] = True
        if any(kw in text for kw in material_keywords):
            result["has_material_news"] = True
    
    score = min(len(news_list) * 3, 30)
    if result["has_customer_news"]: score += 25
    if result["has_competitor_news"]: score += 25
    if result["has_material_news"]: score += 15
    if result["has_tariff_news"]: score += 5
    result["quality_score"] = min(score, 100)
    
    if not result["has_customer_news"]:
        result["suggestions"].append("缺少客户新闻")
    if not result["has_competitor_news"]:
        result["suggestions"].append("缺少友商新闻")
    
    return result


def get_supplier_analysis_prompt(
    supplier_name: str,
    today: str,
    material_categories: list,
    related_companies: list,
    news_summary: str,
    news_count: int
) -> str:
    """供应商分析 prompt"""
    return f"""分析供应商 {supplier_name}，日期 {today}。
相关新闻：{news_summary}
输出：概况、动态、能力评估、风险建议。"""
