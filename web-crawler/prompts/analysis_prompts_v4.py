"""
供应链分析报告 - 模块化 Prompt V4.0 (升级版)

核心改进（基于领导反馈）：
1. 关税政策：AI自动分类国家/地区组合，然后逐一单独分析
2. 原材料：数据直接嵌入（不走大模型），趋势分析单独走大模型
3. 模块完全独立，最后拼装整合
4. 新闻全文下载支持深度分析

架构：
    第一轮（并行）：客户分析、友商分析、关税分类、原材料数据生成
    第二轮（串行/并行）：关税各分类单独分析、原材料成本影响分析
    第三轮：执行摘要整合
    最终：拼装报告
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import matplotlib.pyplot as plt



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
    requires_full_content: bool = False  # 是否需要新闻全文


# ============================================================
# 第一轮模块：客户动态分析
# ============================================================

CUSTOMER_MODULE = AnalysisModule(
    name="customer",
    system_prompt="""你是立讯技术的客户关系分析师。
只分析客户相关的新闻，不要扯其他内容。
风格：简洁、有洞见、引用来源。""",
    
    user_prompt="""# 任务
分析以下新闻中与**客户**相关的内容。

# 立讯技术主要客户
苹果、华为、Meta、小米、OPPO、vivo、汽车客户（特斯拉、比亚迪、蔚来等）

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


# ============================================================
# 第一轮模块：友商竞争分析
# ============================================================

COMPETITOR_MODULE = AnalysisModule(
    name="competitor",
    system_prompt="""你是立讯技术的竞争情报分析师。
按三大业务领域（光电模块/连接器/电源）分析友商动态。
风格：简洁、有洞见、引用来源。""",
    
    user_prompt="""# 任务
分析以下新闻中与**友商**相关的内容。

# 立讯技术三大业务领域及友商

### 💡 光电模块
Credo、旭创科技（中际旭创）、新易盛、天孚通信、光迅科技、Finisar、Coherent、Lumentum

### 🔌 连接器
安费诺、莫仕(Molex)、TE、中航光电、得意精密、意华股份、金信诺、华丰科技、JAE

### ⚡ 电源
奥海科技、航嘉、赛尔康、台达电子、Delta、Flex

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


# ============================================================
# 第一轮模块：关税新闻分类器（核心改进）
# ============================================================

TARIFF_CLASSIFIER_MODULE = AnalysisModule(
    name="tariff_classifier",
    system_prompt="""你是国际贸易政策分析专家。
你的任务是阅读新闻，识别其中涉及的国家/地区贸易关系。

**输出要求**：
- 只输出涉及的国家/地区组合列表
- 每个组合用简短标签表示，如"中美"、"中欧-电动车"、"东南亚-产能转移"
- 用 JSON 数组格式输出
- 如果没有关税相关新闻，输出空数组 []""",
    
    user_prompt="""# 任务
阅读以下新闻全文，识别涉及哪些**国家/地区之间的贸易关系**。

# 关注的贸易关系类型
- 中美关系：关税、实体清单、芯片禁令、技术封锁
- 中欧关系：反补贴调查、电动车关税、光伏双反
- 东南亚：越南/印度/马来西亚/印尼的产能转移、关税优惠
- 中墨/美墨：墨西哥产能转移、北美供应链重构
- 其他：日韩、中东、拉美等

# 新闻列表（含全文）
{news_with_content}

# 输出格式
只输出 JSON 数组，不要有其他文字：
["分类1", "分类2", ...]

示例输出：
["中美-芯片禁令", "中欧-电动车关税", "东南亚-产能转移"]

如果没有关税相关内容：
[]
""",
    max_tokens=300,
    requires_full_content=True
)


# ============================================================
# 第二轮模块：单一关税分类的深度分析（动态生成）
# ============================================================

def get_tariff_analysis_prompt(category: str, news_content: str) -> dict:
    """
    为单一关税分类生成分析 prompt
    
    Args:
        category: 分类名称，如 "中美-芯片禁令"
        news_content: 该分类相关的新闻全文
    
    Returns:
        {"system": ..., "user": ..., "max_tokens": ...}
    """
    system_prompt = f"""你是立讯技术的国际贸易政策分析师。
专注分析【{category}】相关的贸易政策变化。
要求：
1. 引用新闻原文作为依据
2. 评估对立讯技术的具体影响
3. 给出风险等级和应对建议"""

    user_prompt = f"""# 任务
深度分析【{category}】相关的贸易政策动态。

# 相关新闻（含全文）
{news_content}

# 输出格式

### {category}

**政策变化**：
- 具体描述1（引用新闻原文）
- 具体描述2

**对立讯影响**：
- 影响程度：🔴高风险 / 🟡中等 / 🟢低风险
- 具体影响：（描述对哪些业务有什么影响）

**建议应对**：
- 具体可执行的建议1
- 具体可执行的建议2

**来源**：
- [新闻标题1](链接)
- [新闻标题2](链接)

---
*如果新闻内容不足以做深度分析，简要概括即可。*
"""
    
    return {
        "system": system_prompt,
        "user": user_prompt,
        "max_tokens": 800
    }


# ============================================================
# 原材料数据生成（不走大模型）- 增强版
# ============================================================

def build_material_section(
    commodity_data: List[Dict[str, Any]],
    price_history: Dict[str, List[Dict]] = None
) -> str:
    """
    构建原材料行情数据部分（直接生成，不走大模型）
    
    增加周涨跌、月涨跌趋势
    
    Args:
        commodity_data: 当前商品价格数据
        price_history: 历史价格数据 {商品名: [{date, price, change_percent}]}
    
    Returns:
        Markdown 格式的原材料数据表格
    """
    if not commodity_data:
        return """## 原材料行情数据

> ⚠️ 暂无原材料价格数据

---
"""
    
    # 计算历史变化
    def calc_period_change(name: str, days: int) -> Optional[float]:
        """计算指定天数的价格变化百分比"""
        if not price_history or name not in price_history:
            return None
        
        history = price_history.get(name, [])
        if len(history) < 2:
            return None
        
        # 找到最新价格和N天前的价格
        sorted_history = sorted(history, key=lambda x: x.get("date", ""), reverse=True)
        latest = sorted_history[0]
        
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        older = None
        for record in sorted_history:
            if record.get("date", "") <= cutoff_date:
                older = record
                break
        
        if not older or not older.get("price") or not latest.get("price"):
            return None
        
        old_price = float(older["price"])
        new_price = float(latest["price"])
        
        if old_price == 0:
            return None
        
        return ((new_price - old_price) / old_price) * 100
    
    # 输出指定N天历史价格列表
    def output_prices_list(name:str,days:int) -> Optional[List[float]]:
        prices = []
        if not price_history or name not in price_history:
            return None
        
        history = price_history.get(name, [])
        if len(history) < 2:
            return None
        
        sorted_history = sorted(history, key=lambda x: x.get("date", ""), reverse=True)
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        index = None
        for record in sorted_history:
            #找到后返回索引
            if record.get("date", "") <= cutoff_date:
                index = sorted_history.index(record)
                break
        if not index:
            return None
        for current_stock in sorted_history[:index]:
            prices.append(current_stock.get('price',0))
        return prices
    #绘制价格走势图
    def plot_price_trend_from_prices(name:str,days:int,*,
                                     title:str="价格趋势",
                                     xlabel:str="日期",
                                     ylabel:str = "价格",
                                     save_path:Optional[str]=None)-> Optional[str]:
        title = name+title
        prices = output_prices_list(name,days)
        if not prices:
            raise ValueError('Prices is empty')
        x= list(range(len(prices)))
        plt.figure()
        plt.plot(x,prices,marker='o')
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.tight_layout()
        plt.savefig(save_path,dpi=150)
        plt.close()
        if save_path:
            return save_path
        else:
            return "暂无图表"
        

    # 分类材料
    metals = []
    plastics = []
    energy = []
    
    metal_keywords = ['铜', '镍', '锡', '锌', '铝', '铅', '金', '银', '钯', '铂', 'COMEX', 'LME', '有色']
    plastic_keywords = ['ABS', 'PP', 'PE', 'PVC', 'PA', 'PBT', 'PC', 'GPPS', 'HIPS', '塑料', '树脂', 'PA66', 'PA6']
    energy_keywords = ['原油', 'WTI', 'Brent', '布伦特', '天然气', '煤炭', '汽油', '柴油']
    
    for item in commodity_data:
        name = item.get('chinese_name') or item.get('name', '')
        category = item.get('category', '')
        
        if category == '塑料' or any(kw in name.upper() for kw in plastic_keywords):
            plastics.append(item)
        elif any(kw in name for kw in energy_keywords):
            energy.append(item)
        elif any(kw in name for kw in metal_keywords):
            metals.append(item)
        else:
            # 默认归入金属类
            metals.append(item)
    
    # 构建报告
    lines = ["## 原材料行情数据\n"]
    lines.append(f"> 📊 数据更新时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("> 💡 本部分数据为实时采集，未经大模型处理\n")
    
    def format_change(value: Optional[float]) -> str:
        """格式化涨跌幅"""
        if value is None:
            return "N/A"
        if value > 0:
            return f"+{value:.2f}%"
        return f"{value:.2f}%"
    
    def get_trend_icon(day_change: float, week_change: Optional[float]) -> str:
        """获取趋势图标"""
        if week_change is not None:
            ref = week_change
        else:
            ref = day_change
        
        if ref > 2:
            return "📈🔥"  # 强势上涨
        elif ref > 0.5:
            return "📈"    # 上涨
        elif ref < -2:
            return "📉⚠️"  # 强势下跌
        elif ref < -0.5:
            return "📉"    # 下跌
        else:
            return "➡️"    # 横盘
    days = 7 #默认七天的趋势图
    # 金属类
    if metals:
        lines.append("### 🔩 金属类\n")
        lines.append("| 原材料 | 当前价格 | 日涨跌 | 周涨跌 | 月涨跌 | 趋势 |")
        lines.append("|--------|----------|--------|--------|--------|------|")
        
        for m in sorted(metals, key=lambda x: abs(x.get('change_percent', 0)), reverse=True):
            name = m.get('chinese_name') or m.get('name', '')
            price = m.get('price', 0)
            unit = m.get('unit', '')
            day_change = m.get('change_percent', 0) or 0
            
            week_change = calc_period_change(name, 7)
            month_change = calc_period_change(name, 30)
            
            trend = get_trend_icon(day_change, week_change)

            
            
            lines.append(f"| {name} | {price} {unit} | {format_change(day_change)} | {format_change(week_change)} | {format_change(month_change)} | {trend} |")
            
        lines.append("")
        for n in sorted(metals, key=lambda x: abs(x.get('change_percent', 0)), reverse=True):
            name = m.get('chinese_name') or m.get('name', '')
            chart_path = name+'.png'
            lines.append(f'![]({plot_price_trend_from_prices(name,days,save_path=chart_path)})')
        lines.append("")

    
    # 塑料类
    if plastics:
        lines.append("### 🧪 塑料/化工类\n")
        lines.append("| 原材料 | 当前价格 | 日涨跌 | 周涨跌 | 月涨跌 | 趋势 |")
        lines.append("|--------|----------|--------|--------|--------|------|")
        
        for p in sorted(plastics, key=lambda x: abs(x.get('change_percent', 0)), reverse=True):
            name = p.get('chinese_name') or p.get('name', '')
            price = p.get('price', 0)
            unit = p.get('unit', '')
            day_change = p.get('change_percent', 0) or 0
            
            week_change = calc_period_change(name, 7)
            month_change = calc_period_change(name, 30)
            
            trend = get_trend_icon(day_change, week_change)
            
            
            lines.append(f"| {name} | {price} {unit} | {format_change(day_change)} | {format_change(week_change)} | {format_change(month_change)} | {trend} |")
        lines.append("")
        for n in sorted(metals, key=lambda x: abs(x.get('change_percent', 0)), reverse=True):
            name = m.get('chinese_name') or m.get('name', '')
            chart_path = name+'.png'
            lines.append(f'![]({plot_price_trend_from_prices(name,days,save_path=chart_path)})')
        lines.append("")

    # 能源类
    if energy:
        lines.append("### ⛽ 能源类\n")
        lines.append("| 品种 | 当前价格 | 日涨跌 | 周涨跌 | 月涨跌 | 趋势 |")
        lines.append("|------|----------|--------|--------|--------|------|")
        
        for e in sorted(energy, key=lambda x: abs(x.get('change_percent', 0)), reverse=True):
            name = e.get('chinese_name') or e.get('name', '')
            price = e.get('price', 0)
            unit = e.get('unit', '')
            day_change = e.get('change_percent', 0) or 0
            
            week_change = calc_period_change(name, 7)
            month_change = calc_period_change(name, 30)
            
            trend = get_trend_icon(day_change, week_change)
            
            
            lines.append(f"| {name} | {price} {unit} | {format_change(day_change)} | {format_change(week_change)} | {format_change(month_change)} | {trend} |")
            
        lines.append("")
        for n in sorted(metals, key=lambda x: abs(x.get('change_percent', 0)), reverse=True):
            name = m.get('chinese_name') or m.get('name', '')
            chart_path = name+'.png'
            lines.append(f'![]({plot_price_trend_from_prices(name,days,save_path=chart_path)})')
        lines.append("")

    # 数据统计摘要（纯数据，不做解读）
    lines.append("### 📊 数据统计\n")
    
    all_materials = metals + plastics + energy
    if all_materials:
        # 找涨跌幅最大的
        valid_materials = [m for m in all_materials if m.get('change_percent') is not None]
        if valid_materials:
            max_up = max(valid_materials, key=lambda x: x.get('change_percent', 0))
            max_down = min(valid_materials, key=lambda x: x.get('change_percent', 0))
            
            if max_up.get('change_percent', 0) > 0:
                lines.append(f"- **今日涨幅最大**：{max_up.get('chinese_name') or max_up.get('name')} (+{max_up.get('change_percent', 0):.2f}%)")
            if max_down.get('change_percent', 0) < 0:
                lines.append(f"- **今日跌幅最大**：{max_down.get('chinese_name') or max_down.get('name')} ({max_down.get('change_percent', 0):.2f}%)")
        
        # 计算各类平均
        metal_changes = [m.get('change_percent', 0) for m in metals if m.get('change_percent') is not None]
        plastic_changes = [p.get('change_percent', 0) for p in plastics if p.get('change_percent') is not None]
        
        if metal_changes:
            avg_metal = sum(metal_changes) / len(metal_changes)
            lines.append(f"- **金属类平均日涨跌**：{avg_metal:+.2f}%")
        
        if plastic_changes:
            avg_plastic = sum(plastic_changes) / len(plastic_changes)
            lines.append(f"- **塑料类平均日涨跌**：{avg_plastic:+.2f}%")
    
    lines.append("")
    lines.append("---\n")
    
    return "\n".join(lines)


# ============================================================
# 第二轮模块：原材料成本影响分析（走大模型）
# ============================================================

MATERIAL_ANALYSIS_MODULE = AnalysisModule(
    name="material_analysis",
    system_prompt="""你是立讯技术的成本分析师。
根据原材料价格数据，分析对公司各业务线的成本影响。

要求：
1. 结合立讯的业务特点分析
2. 给出具体的成本影响判断
3. 提出可执行的采购建议
4. 禁止套话，要有具体数据支撑""",
    
    user_prompt="""# 任务
根据以下原材料价格数据，分析对立讯技术的成本影响。

# 立讯技术业务与原材料关系
- **连接器**：主要用铜（端子、导体）、工程塑料（外壳）
- **光模块**：主要用铜（PCB、散热）、塑料（外壳）、特种金属
- **电源**：主要用铜（变压器、线缆）、铝（散热片）

# 原材料数据
{material_data}

# 输出格式

## 原材料成本影响分析

### 对各业务线的影响

| 业务线 | 关键原材料 | 价格趋势 | 成本影响 | 影响程度 |
|--------|------------|----------|----------|----------|
| 连接器 | 铜、塑料 | | | 🔴/🟡/🟢 |
| 光模块 | | | | |
| 电源 | | | | |

### 成本压力评估
- **短期（1个月）**：
- **中期（1季度）**：

### 采购策略建议
给出2-3条**具体可执行**的建议：
1. 
2. 
3. 

**禁止**：写"密切关注"、"加强管理"等套话

---
""",
    max_tokens=1000
)


# ============================================================
# 第三轮模块：执行摘要整合
# ============================================================

SUMMARY_MODULE = AnalysisModule(
    name="summary",
    system_prompt="""你是立讯技术的首席战略分析师。
根据各模块的分析结果，生成执行摘要、SWOT分析和行动建议。
风格：高度概括、有洞见、可执行。
禁止套话：不要写"加强研发"、"密切关注"等空话。""",
    
    user_prompt="""# 任务
根据以下各模块的分析结果，生成最终报告的执行摘要部分。

# 日期
{today}

# 客户动态分析
{customer_analysis}

# 友商竞争分析
{competitor_analysis}

# 关税政策分析（各分类汇总）
{tariff_analysis}

# 原材料成本分析
{material_analysis}

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
# 工具函数
# ============================================================

def fetch_news_full_content(news_list: List[Dict], max_items: int = 20) -> List[Dict]:
    """
    获取新闻全文内容
    """
    import requests
    from bs4 import BeautifulSoup
    
    results = []
    
    for news in news_list[:max_items]:
        url = news.get('url', '')
        if not url:
            results.append(news)
            continue
        
        try:
            resp = requests.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                content = ""
                for selector in ['article', '.article-content', '.content', '.post-content', 
                                '#content', '.news-content', '.article-body']:
                    elem = soup.select_one(selector)
                    if elem:
                        content = elem.get_text(strip=True, separator='\n')[:2000]
                        break
                
                if not content:
                    body = soup.find('body')
                    if body:
                        content = body.get_text(strip=True, separator='\n')[:1500]
                
                news['content'] = content
            else:
                news['content'] = ""
        except Exception:
            news['content'] = ""
        
        results.append(news)
    
    return results


def filter_tariff_news(news_list: List[Dict]) -> List[Dict]:
    """筛选关税/贸易政策相关新闻"""
    tariff_keywords = [
        '关税', '贸易战', '贸易摩擦', '贸易壁垒', '反倾销', '反补贴',
        '制裁', '实体清单', '出口管制', '技术封锁', '芯片禁令', '半导体禁令',
        '中美', '中欧', '越南', '印度', '马来西亚', '墨西哥', '印尼',
        'USTR', '商务部', '海关', '进出口', '供应链安全', '脱钩',
        '产能转移', '工厂迁移', '东南亚建厂', '墨西哥建厂', '印度建厂'
    ]
    
    filtered = []
    for news in news_list:
        title = news.get('title', '')
        content = news.get('content', '')[:500]
        text = title + content
        
        if any(kw in text for kw in tariff_keywords):
            filtered.append(news)
    
    return filtered


def filter_news_by_category(news_list: List[Dict], category: str) -> List[Dict]:
    """
    根据分类筛选相关新闻
    
    Args:
        news_list: 新闻列表
        category: 分类名称，如 "中美-芯片禁令"
    
    Returns:
        相关的新闻列表
    """
    # 分类关键词映射
    category_keywords = {
        "中美": ["中美", "美中", "美国", "华盛顿", "白宫", "USTR", "拜登", "特朗普"],
        "中欧": ["中欧", "欧盟", "欧洲", "布鲁塞尔", "德国", "法国"],
        "东南亚": ["越南", "印度", "马来西亚", "印尼", "泰国", "菲律宾", "东南亚"],
        "中墨": ["墨西哥", "中墨", "北美"],
        "芯片": ["芯片", "半导体", "晶圆", "光刻", "EDA", "GPU"],
        "电动车": ["电动车", "新能源车", "电池", "锂电"],
        "产能转移": ["产能转移", "建厂", "工厂", "迁移", "投资建设"],
        "关税": ["关税", "贸易战", "反倾销", "反补贴"],
        "制裁": ["制裁", "实体清单", "出口管制", "封锁"]
    }
    
    # 解析分类名称中的关键词
    keywords = []
    for key, kws in category_keywords.items():
        if key in category:
            keywords.extend(kws)
    
    if not keywords:
        # 直接用分类名作为关键词
        keywords = [category]
    
    filtered = []
    for news in news_list:
        text = news.get('title', '') + news.get('content', '')[:500]
        if any(kw in text for kw in keywords):
            filtered.append(news)
    
    return filtered


def precheck_news_quality(news_list: list) -> dict:
    """预检新闻质量"""
    customer_keywords = ["苹果", "Apple", "华为", "Huawei", "Meta", "iPhone", "小米", "特斯拉", "Tesla"]
    competitor_keywords = [
        "Credo", "旭创", "新易盛", "天孚", "光迅", "Finisar", "Coherent",
        "安费诺", "莫仕", "TE", "中航光电", "得意精密", "意华", "金信诺", "华丰",
        "奥海", "航嘉", "赛尔康", "台达",
        "工业富联", "富士康", "比亚迪电子", "歌尔", "蓝思"
    ]
    tariff_keywords = ["关税", "贸易战", "出口管制", "制裁", "中美", "中欧", "越南", "印度"]
    material_keywords = ["铜", "镍", "锡", "铝", "塑料", "ABS", "PP", "PA66", "PVC"]
    
    result = {
        "total_count": len(news_list),
        "has_customer_news": False,
        "has_competitor_news": False,
        "has_tariff_news": False,
        "has_material_news": False,
        "tariff_news_count": 0,
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
            result["tariff_news_count"] += 1
        if any(kw in text for kw in material_keywords):
            result["has_material_news"] = True
    
    score = min(len(news_list) * 3, 30)
    if result["has_customer_news"]: score += 25
    if result["has_competitor_news"]: score += 25
    if result["has_material_news"]: score += 15
    if result["has_tariff_news"]: score += 5
    result["quality_score"] = min(score, 100)
    
    if not result["has_customer_news"]:
        result["suggestions"].append("缺少客户相关新闻")
    if not result["has_competitor_news"]:
        result["suggestions"].append("缺少友商相关新闻")
    if not result["has_tariff_news"]:
        result["suggestions"].append("缺少关税政策新闻")
    
    return result


# ============================================================
# 报告组装
# ============================================================

def assemble_final_report_v4(
    summary_analysis: str,
    customer_analysis: str,
    competitor_analysis: str,
    material_data_section: str,  # 原材料数据（不走大模型）
    material_analysis: str,      # 原材料成本分析（走大模型）
    tariff_sections: Dict[str, str],  # {分类: 分析内容}
    today: str
) -> str:
    """
    组装最终报告
    
    特点：
    - 原材料数据和分析分离
    - 关税按实际分类动态生成
    """
    # 组装关税部分
    tariff_content = ""
    if tariff_sections:
        tariff_content = "## 关税政策分析\n\n"
        tariff_content += "> 💡 以下分析按 AI 自动识别的国家/地区分类展开\n\n"
        for category, analysis in tariff_sections.items():
            tariff_content += f"{analysis}\n\n"
    else:
        tariff_content = "## 关税政策分析\n\n本周暂无重大关税政策变化。\n\n"
    
    report = f"""# 立讯技术产业链分析报告

**分析日期**：{today}
**版本**：V4.0（模块化 + 动态关税分类 + 原材料分离分析）

---

{summary_analysis}

---

# 详细分析

{customer_analysis}

---

{competitor_analysis}

---

{material_data_section}

{material_analysis}

---

{tariff_content}

---

*报告由 TrendRadar 模块化分析系统生成*
*原材料数据为实时采集，关税分类由 AI 动态识别*
"""
    return report


# ============================================================
# Prompt 获取接口（兼容旧版）
# ============================================================

def get_module_prompt(module: AnalysisModule, **kwargs) -> dict:
    """获取模块的 prompt"""
    return {
        "system": module.system_prompt,
        "user": module.user_prompt.format(**kwargs),
        "max_tokens": module.max_tokens,
        "requires_full_content": module.requires_full_content
    }


# 兼容旧版接口
def get_all_module_prompts(news_summary: str, news_with_content: str, today: str) -> Dict[str, dict]:
    """兼容旧版：获取所有第一轮模块的 prompts"""
    return {
        "customer": get_module_prompt(CUSTOMER_MODULE, news_summary=news_summary),
        "competitor": get_module_prompt(COMPETITOR_MODULE, news_summary=news_summary),
        "tariff_classifier": get_module_prompt(TARIFF_CLASSIFIER_MODULE, news_with_content=news_with_content)
    }


def get_summary_prompt(today: str, customer_analysis: str, competitor_analysis: str, 
                       tariff_analysis: str, material_analysis: str = "") -> dict:
    """兼容旧版：获取整合模块的 prompt"""
    return get_module_prompt(
        SUMMARY_MODULE,
        today=today,
        customer_analysis=customer_analysis,
        competitor_analysis=competitor_analysis,
        tariff_analysis=tariff_analysis,
        material_analysis=material_analysis
    )


# 第一轮模块列表
FIRST_ROUND_MODULES = {
    "customer": CUSTOMER_MODULE,
    "competitor": COMPETITOR_MODULE,
    "tariff_classifier": TARIFF_CLASSIFIER_MODULE
}
