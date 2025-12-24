"""
AI 提示词模块

版本说明：
- V1: 原版（表格多，易空洞）
- V2: 优化版（减少表格，先观点后数据）
- V3: 模块化版（分而治之，并行调用）★ 推荐
"""
# ============================================================
# V4 模块化版本
# ============================================================
from .analysis_prompts_v4 import (
    # 模块化接口
    get_all_module_prompts,
    get_summary_prompt,
    get_module_prompt,
    FIRST_ROUND_MODULES,
    CUSTOMER_MODULE,
    COMPETITOR_MODULE,
    TARIFF_CLASSIFIER_MODULE,
    MATERIAL_ANALYSIS_MODULE,
    SUMMARY_MODULE
)




# ============================================================
# V3 模块化版本（推荐用于 /api/generate-analysis-v3）
# ============================================================
# from .analysis_prompts_v3 import (
#     # 模块化接口
#     get_all_module_prompts,
#     get_summary_prompt,
#     get_module_prompt,
#     FIRST_ROUND_MODULES,
#     CUSTOMER_MODULE,
#     COMPETITOR_MODULE,
#     MATERIAL_MODULE,
#     TARIFF_MODULE,
#     SUMMARY_MODULE,
#     # 兼容接口
#     get_supply_chain_analysis_prompt,
#     get_supplier_analysis_prompt,
#     ANALYSIS_SYSTEM_PROMPT,
#     MATERIAL_CATEGORIES,
#     precheck_news_quality,
#     COMPETITORS  # 完整友商列表
# )

# ============================================================
# V2 优化版（用于 /api/generate-analysis，向后兼容）
# ============================================================
# from .analysis_prompts_v2 import (
#     get_supply_chain_analysis_prompt,
#     get_supplier_analysis_prompt,
#     ANALYSIS_SYSTEM_PROMPT,
#     MATERIAL_CATEGORIES,
#     precheck_news_quality
# )

# ============================================================
# V1 原版（如需回退）
# ============================================================
# from .analysis_prompts import (
#     get_supply_chain_analysis_prompt,
#     get_supplier_analysis_prompt,
#     ANALYSIS_SYSTEM_PROMPT,
#     MATERIAL_CATEGORIES
# )
# def precheck_news_quality(news_list): return {"quality_score": 100}

# 市场分析 prompts（独立）
from .market_prompts import get_market_analysis_prompt, MARKET_SYSTEM_PROMPT

__all__ = [
    # V4 模块化接口
    'get_all_module_prompts',
    'get_summary_prompt',
    'get_module_prompt',
    'FIRST_ROUND_MODULES',
    'CUSTOMER_MODULE',
    'COMPETITOR_MODULE',
    'TARIFF_CLASSIFIER_MODULE',
    'MATERIAL_ANALYSIS_MODULE',
    'SUMMARY_MODULE',
    ''
    # 市场分析
    'get_market_analysis_prompt', 
    'MARKET_SYSTEM_PROMPT',
]
