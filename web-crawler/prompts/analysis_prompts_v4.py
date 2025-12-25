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

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import re


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
# 关税政策分析模块（独立模块）
# ============================================================

# 预定义的国家/地区关税分析分类
TARIFF_REGIONS = {
    "china_us": {
        "name": "中美关税政策",
        "display_name": "🇨🇳🇺🇸 中美关税政策",
        "keywords": ["中美", "美中", "美国", "华盛顿", "白宫", "USTR", "拜登", "特朗普", 
                    "芯片禁令", "实体清单", "半导体制裁", "技术封锁", "出口管制"],
        "focus_areas": ["芯片/半导体禁令", "实体清单变化", "关税税率调整", "技术出口管制"]
    },
    "china_eu": {
        "name": "中欧关税政策",
        "display_name": "🇨🇳🇪🇺 中欧关税政策",
        "keywords": ["中欧", "欧盟", "欧洲", "布鲁塞尔", "德国", "法国", 
                    "反补贴", "电动车关税", "光伏双反", "碳边境税"],
        "focus_areas": ["电动车反补贴调查", "光伏/风电双反", "碳边境调节机制(CBAM)", "电池法规"]
    },
    "southeast_asia": {
        "name": "东南亚产能转移",
        "display_name": "🌏 东南亚产能转移",
        "keywords": ["越南", "印度", "马来西亚", "印尼", "泰国", "菲律宾", "东南亚",
                    "产能转移", "建厂", "工厂迁移", "投资建设"],
        "focus_areas": ["产能转移动态", "当地关税优惠政策", "供应链本地化要求", "劳动力成本"]
    },
    "mexico_nearshoring": {
        "name": "墨西哥近岸外包",
        "display_name": "🇲🇽 墨西哥近岸外包",
        "keywords": ["墨西哥", "中墨", "美墨", "北美", "USMCA", "近岸外包", "Nearshoring"],
        "focus_areas": ["USMCA原产地规则", "近岸外包趋势", "对华产品转口限制", "北美供应链重构"]
    },
    "other_regions": {
        "name": "其他地区政策",
        "display_name": "🌐 其他地区政策",
        "keywords": ["日本", "韩国", "中东", "拉美", "非洲", "英国", "加拿大", "澳大利亚"],
        "focus_areas": ["日韩贸易政策", "中东市场机会", "拉美关税变化", "其他区域动态"]
    }
}


# 第一轮：关税新闻分类器
TARIFF_CLASSIFIER_MODULE = AnalysisModule(
    name="tariff_classifier",
    system_prompt="""你是国际贸易政策分析专家。
你的任务是阅读新闻，将其分类到预定义的国家/地区类别中。

**预定义分类**：
1. china_us - 中美关税政策（芯片禁令、实体清单、关税）
2. china_eu - 中欧关税政策（反补贴、电动车关税、碳边境税）
3. southeast_asia - 东南亚产能转移（越南、印度、马来西亚等）
4. mexico_nearshoring - 墨西哥近岸外包（USMCA、北美供应链）
5. other_regions - 其他地区政策（日韩、中东、拉美等）

**输出要求**：
- 只输出匹配的分类ID列表
- 用 JSON 数组格式输出
- 如果没有关税相关新闻，输出空数组 []""",
    
    user_prompt="""# 任务
阅读以下新闻，识别涉及哪些**国家/地区的贸易政策**，并分类。

# 分类规则
| 分类ID | 名称 | 关键词 |
|--------|------|--------|
| china_us | 中美关税政策 | 中美、芯片禁令、实体清单、USTR、技术封锁 |
| china_eu | 中欧关税政策 | 欧盟、反补贴、电动车关税、碳边境税 |
| southeast_asia | 东南亚产能转移 | 越南、印度、马来西亚、印尼、产能转移 |
| mexico_nearshoring | 墨西哥近岸外包 | 墨西哥、USMCA、北美供应链、近岸外包 |
| other_regions | 其他地区政策 | 日本、韩国、中东、拉美 |

# 新闻列表（含全文）
{news_with_content}

# 输出格式
只输出 JSON 数组，不要有其他文字：
["分类ID1", "分类ID2", ...]

示例输出：
["china_us", "china_eu", "southeast_asia"]

如果没有关税相关内容：
[]
""",
    max_tokens=200,
    requires_full_content=True
)


# ============================================================
# 第二轮模块：各地区关税政策深度分析（独立模块）
# ============================================================

def get_region_tariff_prompt(region_id: str, news_content: str) -> dict:
    """
    为特定地区生成关税政策分析 prompt
    
    Args:
        region_id: 地区ID，如 "china_us", "china_eu"
        news_content: 该地区相关的新闻全文
    
    Returns:
        {"system": ..., "user": ..., "max_tokens": ...}
    """
    region_info = TARIFF_REGIONS.get(region_id, {
        "name": region_id,
        "display_name": region_id,
        "focus_areas": []
    })
    
    region_name = region_info["name"]
    display_name = region_info["display_name"]
    focus_areas = region_info.get("focus_areas", [])
    focus_areas_str = "\n".join([f"- {area}" for area in focus_areas]) if focus_areas else "- 一般贸易政策变化"
    
    # 针对不同地区的定制化分析要点
    region_specific_guidance = {
        "china_us": """**分析重点**：
- 芯片/半导体出口管制的具体产品范围
- 实体清单增减变化及影响企业
- 关税税率调整的具体品类
- 对立讯客户（苹果等）的影响传导""",
        "china_eu": """**分析重点**：
- 电动车反补贴调查进展及税率
- 碳边境调节机制(CBAM)实施时间表
- 对光伏、风电、电池产品的影响
- 欧洲本地化生产要求""",
        "southeast_asia": """**分析重点**：
- 各国产能转移的优惠政策比较
- 当地供应链配套成熟度
- 中国企业在当地的投资动态
- 对立讯产能布局的建议""",
        "mexico_nearshoring": """**分析重点**：
- USMCA原产地规则变化
- 对中国产品转口的限制政策
- 北美供应链重构的机会与挑战
- 墨西哥本地化生产的成本分析""",
        "other_regions": """**分析重点**：
- 各地区的关税政策变化
- 新兴市场的进入机会
- 区域贸易协定的影响"""
    }
    
    specific_guidance = region_specific_guidance.get(region_id, region_specific_guidance["other_regions"])
    
    system_prompt = f"""你是立讯技术的国际贸易政策分析师，专注【{region_name}】领域。

{specific_guidance}

要求：
1. 引用新闻原文作为依据
2. 评估对立讯技术各业务线的具体影响
3. 给出量化的风险等级和可执行的应对建议
4. 禁止套话，要有具体数据和事实支撑"""

    user_prompt = f"""# 任务
深度分析【{region_name}】相关的贸易政策动态。

# 重点关注领域
{focus_areas_str}

# 相关新闻（含全文）
{news_content}

# 输出格式

### {display_name}

#### 📋 政策变化
| 政策/事件 | 具体内容 | 生效时间 | 来源 |
|-----------|----------|----------|------|
| | | | |

#### 📊 对立讯业务影响

| 业务线 | 影响程度 | 具体影响 |
|--------|----------|----------|
| 连接器 | 🔴/🟡/🟢 | |
| 光模块 | 🔴/🟡/🟢 | |
| 电源 | 🔴/🟡/🟢 | |

**整体风险评估**：🔴高风险 / 🟡中等风险 / 🟢低风险

#### 🎯 应对建议

| 优先级 | 建议措施 | 预期效果 | 时间窗口 |
|--------|----------|----------|----------|
| P0 | | | |
| P1 | | | |

#### 📰 信息来源
- [新闻标题1](链接)
- [新闻标题2](链接)

---
*如果新闻内容不足以做深度分析，简要概括即可，不要编造信息。*
"""
    
    return {
        "system": system_prompt,
        "user": user_prompt,
        "max_tokens": 1000,
        "region_id": region_id,
        "region_name": region_name
    }


# 兼容旧版接口
def get_tariff_analysis_prompt(category: str, news_content: str) -> dict:
    """
    兼容旧版：为单一关税分类生成分析 prompt
    自动匹配到新的地区分类
    """
    # 尝试匹配到预定义分类
    category_mapping = {
        "中美": "china_us",
        "芯片禁令": "china_us",
        "实体清单": "china_us",
        "中欧": "china_eu",
        "电动车关税": "china_eu",
        "反补贴": "china_eu",
        "东南亚": "southeast_asia",
        "越南": "southeast_asia",
        "印度": "southeast_asia",
        "产能转移": "southeast_asia",
        "墨西哥": "mexico_nearshoring",
        "中墨": "mexico_nearshoring",
        "北美": "mexico_nearshoring"
    }
    
    matched_region = None
    for keyword, region_id in category_mapping.items():
        if keyword in category:
            matched_region = region_id
            break
    
    if matched_region:
        return get_region_tariff_prompt(matched_region, news_content)
    else:
        # 未匹配到，使用通用模板
        return get_region_tariff_prompt("other_regions", news_content)


def filter_news_by_region(news_list: List[Dict], region_id: str) -> List[Dict]:
    """
    根据地区ID筛选相关新闻
    
    Args:
        news_list: 新闻列表
        region_id: 地区ID，如 "china_us"
    
    Returns:
        相关的新闻列表
    """
    region_info = TARIFF_REGIONS.get(region_id)
    if not region_info:
        return []
    
    keywords = region_info.get("keywords", [])
    
    filtered = []
    for news in news_list:
        text = news.get('title', '') + news.get('content', '')[:500]
        if any(kw in text for kw in keywords):
            filtered.append(news)
    
    return filtered


# ============================================================
# 关税政策汇总模块（第三轮）
# ============================================================

TARIFF_SUMMARY_MODULE = AnalysisModule(
    name="tariff_summary",
    system_prompt="""你是立讯技术的国际贸易政策首席分析师。
根据各地区的关税政策分析结果，生成整体评估和战略建议。
要求：
1. 综合评估全球贸易环境对立讯的影响
2. 给出优先级排序的战略建议
3. 禁止套话，要有具体可执行的行动""",
    
    user_prompt="""# 任务
根据以下各地区的关税政策分析结果，生成整体评估。

# 各地区分析结果
{region_analyses}

# 输出格式

## 🌐 关税政策整体评估

### 本周关键发现
用 2-3 个要点概括最重要的政策变化：
- ✅/⚠️/🔴 **[地区]**：一句话结论

### 各地区风险概览
| 地区 | 风险等级 | 主要关注点 | 紧迫程度 |
|------|----------|------------|----------|
| | 🔴/🟡/🟢 | | 高/中/低 |

### 战略建议（按优先级排序）
| 优先级 | 建议措施 | 针对地区 | 预期效果 |
|--------|----------|----------|----------|
| P0 | | | |
| P1 | | | |
| P2 | | | |

---
*如果没有关税政策相关新闻，直接写"本周关税政策面暂无重大变化"即可。*
""",
    max_tokens=800
)


def build_tariff_report_section(
    region_analyses: Dict[str, str],
    tariff_summary: str = None
) -> str:
    """
    构建关税政策分析报告部分
    
    Args:
        region_analyses: 各地区分析结果 {region_id: analysis_text}
        tariff_summary: 整体汇总分析（可选）
    
    Returns:
        Markdown 格式的关税政策报告部分
    """
    lines = ["## 🌐 关税政策分析\n"]
    lines.append("> 💡 本部分按国家/地区分类分析，由 AI 自动识别和分类\n")
    
    if not region_analyses:
        lines.append("本周关税政策面暂无重大变化。\n")
        return "\n".join(lines)
    
    # 按定义顺序输出各地区分析
    region_order = ["china_us", "china_eu", "southeast_asia", "mexico_nearshoring", "other_regions"]
    
    for region_id in region_order:
        if region_id in region_analyses:
            analysis = region_analyses[region_id]
            lines.append(analysis)
            lines.append("\n")
    
    # 处理未在预定义顺序中的地区
    for region_id, analysis in region_analyses.items():
        if region_id not in region_order:
            lines.append(analysis)
            lines.append("\n")
    
    # 添加汇总分析
    if tariff_summary:
        lines.append("---\n")
        lines.append(tariff_summary)
    
    lines.append("---\n")
    
    return "\n".join(lines)


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
            print('暂无数据')
            return prices
        
        history = price_history.get(name, [])
        if len(history) < 2:
            print('数据过少')
            return prices
        
        sorted_history = sorted(history, key=lambda x: x.get("date", ""), reverse=True)
        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        index = None
        for idx, record in enumerate(sorted_history):  # 用enumerate避免index()重复问题
            record_date = record.get("date", "")
            if record_date <= cutoff_date:
                index = idx
                break
        if index is None:
        # 所有记录都 > 截止日期 → 取全部数据
            print(f'{name}：所有数据都在{days}天内，取全部')
            target_data = sorted_history
        else:
        # 取截止日期之前的所有数据
            target_data = sorted_history[:index]
        for current_stock in target_data:
            price_val = current_stock.get('price', 0.0)
            if isinstance(price_val, (int, float)):  # 确保价格是数字
                prices.append(price_val)
        if not prices:
            print(f'{name}：{days}天内无有效价格数据')
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
            return f"{name}暂无数据"
        x= list(range(len(prices)))
        plt.figure()
        plt.plot(x,prices,marker='o')
        plt.title(title)
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.tight_layout()
        try:
            plt.savefig(save_path,dpi=150)
            print(f"【调试】{name} - 图片保存成功")
        except Exception as e:
            print(f"【调试】{name} - 保存失败：{str(e)}")  # 打印保存异常
        plt.close()
        if save_path:
            return save_path
        else:
            return f"{name}暂无图表"
        
    # 获取日期价格元组
    def get_price_with_dates(name: str, days: int) -> Optional[List[Tuple[str, float]]]:
    # """
    # 获取指定名称资产在最近N天内的价格列表（包含对应日期）
    
    # Args:
    #     name: 资产名称
    #     days: 回溯天数
        
    # Returns:
    #     元组列表，每个元组格式为 (日期字符串, 价格浮点数)，按日期倒序排列；
    #     无数据时返回空列表，异常情况返回None
    # """
    # 初始化返回结果
        price_date_list: List[(str, float)] = []
        
        # 校验核心数据源
        if not price_history or name not in price_history:
            print(f'{name}：暂无数据')
            return price_date_list
        
        # 获取该资产的历史记录
        history = price_history.get(name, [])
        
        # 校验数据量
        if len(history) < 2:
            print(f'{name}：数据过少（仅{len(history)}条记录）')
            return price_date_list
        
        # 按日期倒序排序（最新的在前）
        try:
            sorted_history = sorted(
                history, 
                key=lambda x: x.get("date", ""), 
                reverse=True
            )
        except Exception as e:
            print(f'{name}：数据排序失败 - {str(e)}')
            return None
        
        # 计算截止日期（N天前）
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        except Exception as e:
            print(f'日期计算失败 - {str(e)}')
            return None
        
        # 找到截止日期的分界点
        cutoff_index = None
        for idx, record in enumerate(sorted_history):
            record_date = record.get("date", "")
            if record_date <= cutoff_date:
                cutoff_index = idx
                break
        
        # 筛选目标数据
        if cutoff_index is None:
            print(f'{name}：所有数据都在{days}天内，取全部')
            target_data = sorted_history
        else:
            target_data = sorted_history[:cutoff_index]
        
        # 构建(日期, 价格)元组列表
        for record in target_data:
            record_date = record.get("date", "")
            price_val = record.get("price", 0.0)
            
            # 数据有效性校验
            if not record_date:
                print(f'{name}：发现无日期记录，跳过')
                continue
            
            if not isinstance(price_val, (int, float)):
                print(f'{name}：{record_date}价格非数字({price_val})，跳过')
                continue
            
            price_date_list.append((record_date, float(price_val)))
        
        # 最终数据校验
        if not price_date_list:
            print(f'{name}：{days}天内无有效价格数据')
        
        return price_date_list
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
    print('分类结果：')
    print("金属类：", [m.get('name',''),m.get('chinese_name') for m in metals])
    print("塑料类：", [p.get('name',''),p.get('chinese_name') for p in plastics])
    print("能源类：", [e.get('name',''),e.get('chinese_name') for e in energy])
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

    #折中方案，若图表不生成
    def generate_table_prices(category:List[Dict]):
        lines.append("")
        for n in sorted(category, key=lambda x: abs(x.get('change_percent', 0)), reverse=True):
            lines.append("")
            raw_name = n.get('chinese_name') or n.get('name', '')
            # 去除可能来自上游数据的 Markdown 标题符号（如 '### '）或多余空白
            name = re.sub(r'^\s*#+\s*', '', str(raw_name)).strip()
            prices_s = get_price_with_dates(name, days)
            if not prices_s:
                lines.append(f'### {name}前{days}天内价格\n暂无有效价格数据\n')
                continue
            unit = n.get('unit','')#这里默认所有商品的价格单位一致
            lines.append(f'### {name}前{days}天内价格')
            lines.append('|  日期  |  价格  |')
            lines.append('|------|------|')
            for p in prices_s:
                lines.append(f'| {p[0]} | {p[1]} {unit}|')
            

    #按类型生成所有商品图表
    def generate_chart(category:List[Dict]):
        lines.append("")
        for n in sorted(category, key=lambda x: abs(x.get('change_percent', 0)), reverse=True):
            name = n.get('chinese_name') or n.get('name', '')
            chart_path = name+'.png'
            plot_result = plot_price_trend_from_prices(name, days, save_path=chart_path)
            if plot_result.endswith(".png"):  # 成功保存
                lines.append(f"### {name}\n![]({plot_result})")
            else:  # 失败/无数据
                lines.append(f"### {name}\n{plot_result}")
        lines.append("")

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
        generate_table_prices(metals)
    # 塑料类
    if plastics:
        lines.append("")
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
        generate_table_prices(plastics)
    
    # 能源类
    if energy:
        lines.append("")
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
        generate_table_prices(energy)
    
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
    根据分类筛选相关新闻（兼容旧版，内部调用新的 filter_news_by_region）
    
    Args:
        news_list: 新闻列表
        category: 分类名称，如 "中美-芯片禁令" 或 "china_us"
    
    Returns:
        相关的新闻列表
    """
    # 如果是新版 region_id，直接调用
    if category in TARIFF_REGIONS:
        return filter_news_by_region(news_list, category)
    
    # 尝试匹配到预定义分类
    category_mapping = {
        "中美": "china_us",
        "芯片禁令": "china_us",
        "芯片": "china_us",
        "实体清单": "china_us",
        "制裁": "china_us",
        "中欧": "china_eu",
        "电动车关税": "china_eu",
        "电动车": "china_eu",
        "反补贴": "china_eu",
        "东南亚": "southeast_asia",
        "越南": "southeast_asia",
        "印度": "southeast_asia",
        "马来西亚": "southeast_asia",
        "印尼": "southeast_asia",
        "产能转移": "southeast_asia",
        "墨西哥": "mexico_nearshoring",
        "中墨": "mexico_nearshoring",
        "北美": "mexico_nearshoring",
        "关税": "other_regions"
    }
    
    matched_region = None
    for keyword, region_id in category_mapping.items():
        if keyword in category:
            matched_region = region_id
            break
    
    if matched_region:
        return filter_news_by_region(news_list, matched_region)
    
    # 未匹配到，使用通用关键词搜索
    tariff_keywords = [
        '关税', '贸易战', '贸易摩擦', '贸易壁垒', '反倾销', '反补贴',
        '制裁', '实体清单', '出口管制', '技术封锁'
    ]
    
    filtered = []
    for news in news_list:
        text = news.get('title', '') + news.get('content', '')[:500]
        if any(kw in text for kw in tariff_keywords):
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
    tariff_sections: Dict[str, str],  # {region_id: 分析内容}
    today: str,
    tariff_summary: str = None   # 关税整体汇总（可选）
) -> str:
    """
    组装最终报告
    
    特点：
    - 原材料数据和分析分离
    - 关税按国家/地区独立分析，最后汇总
    """
    # 使用新的关税报告构建函数
    tariff_content = build_tariff_report_section(tariff_sections, tariff_summary)
    
    report = f"""# 立讯技术产业链分析报告

**分析日期**：{today}
**版本**：V4.1（模块化 + 独立关税分析 + 原材料分离分析）

---

{summary_analysis}

---

# 详细分析

{customer_analysis}

---

{competitor_analysis}

---

{tariff_content}

{material_data_section}

{material_analysis}

---

*报告由 TrendRadar 模块化分析系统生成*
*关税政策按国家/地区独立分析，原材料数据为实时采集*
"""
    return report


# 关税模块导出（方便外部调用）
TARIFF_MODULES = {
    "classifier": TARIFF_CLASSIFIER_MODULE,
    "summary": TARIFF_SUMMARY_MODULE,
    "regions": TARIFF_REGIONS
}


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

# 第二轮模块列表（关税各地区分析）
SECOND_ROUND_TARIFF_MODULES = TARIFF_REGIONS

# 第三轮模块列表
THIRD_ROUND_MODULES = {
    "tariff_summary": TARIFF_SUMMARY_MODULE
}


# ============================================================
# 关税分析工作流辅助函数
# ============================================================

def get_tariff_summary_prompt(region_analyses: Dict[str, str]) -> dict:
    """
    获取关税汇总模块的 prompt
    
    Args:
        region_analyses: 各地区分析结果 {region_id: analysis_text}
    
    Returns:
        prompt dict
    """
    # 合并各地区分析结果
    combined = ""
    for region_id, analysis in region_analyses.items():
        region_info = TARIFF_REGIONS.get(region_id, {"display_name": region_id})
        combined += f"\n### {region_info.get('display_name', region_id)}\n"
        combined += analysis
        combined += "\n---\n"
    
    return get_module_prompt(TARIFF_SUMMARY_MODULE, region_analyses=combined)


def get_all_region_prompts(news_list: List[Dict], detected_regions: List[str]) -> Dict[str, dict]:
    """
    为所有检测到的地区生成分析 prompts
    
    Args:
        news_list: 新闻列表（含全文）
        detected_regions: 检测到的地区ID列表，如 ["china_us", "china_eu"]
    
    Returns:
        {region_id: prompt_dict}
    """
    prompts = {}
    
    for region_id in detected_regions:
        # 筛选该地区相关的新闻
        region_news = filter_news_by_region(news_list, region_id)
        
        if not region_news:
            continue
        
        # 格式化新闻内容
        news_content = format_news_for_analysis(region_news)
        
        # 生成 prompt
        prompts[region_id] = get_region_tariff_prompt(region_id, news_content)
    
    return prompts


def format_news_for_analysis(news_list: List[Dict]) -> str:
    """
    格式化新闻列表为分析用的文本
    
    Args:
        news_list: 新闻列表
    
    Returns:
        格式化的文本
    """
    lines = []
    for i, news in enumerate(news_list, 1):
        title = news.get('title', '无标题')
        url = news.get('url', '')
        content = news.get('content', '')[:1500]  # 限制内容长度
        platform = news.get('platform', '')
        
        lines.append(f"### 新闻 {i}: {title}")
        if platform:
            lines.append(f"**来源**: {platform}")
        if url:
            lines.append(f"**链接**: {url}")
        if content:
            lines.append(f"\n{content}\n")
        lines.append("---")
    
    return "\n".join(lines)
