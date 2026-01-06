# V4 深度优化版（推荐用于 /api/generate-analysis-v4）
# 特点：关税按国家/地区独立分析模块
# ============================================================
from .analysis_prompts_v4 import (
    # 基础接口
    get_all_module_prompts as get_all_module_prompts_v4,
    get_summary_prompt as get_summary_prompt_v4,
    get_module_prompt as get_module_prompt_v4,
    # 原材料模块
    build_material_section,
    # 新闻处理
    fetch_news_full_content,
    filter_tariff_news,
    filter_news_by_region,
    format_news_for_analysis,
    # 关税模块（独立）
    TARIFF_REGIONS,
    TARIFF_CLASSIFIER_MODULE as TARIFF_CLASSIFIER_MODULE_V4,
    TARIFF_SUMMARY_MODULE,
    TARIFF_MODULES,
    get_region_tariff_prompt,
    get_tariff_summary_prompt,
    get_all_region_prompts,
    build_tariff_report_section,
    # 报告组装
    assemble_final_report_v4,
    # 模块列表
    FIRST_ROUND_MODULES as FIRST_ROUND_MODULES_V4,
    SECOND_ROUND_TARIFF_MODULES,
    THIRD_ROUND_MODULES,
    # 其他
    precheck_news_quality as precheck_news_quality_v4
)

# 市场分析 prompts（独立）
from .market_prompts import get_market_analysis_prompt, MARKET_SYSTEM_PROMPT

# ============================================================
# V3 模块化版本（推荐用于 /api/generate-analysis-v3）
# ============================================================
from .analysis_prompts_v3 import (
    # 模块化接口
    get_all_module_prompts,
    get_summary_prompt,
    get_module_prompt,
    FIRST_ROUND_MODULES,
    CUSTOMER_MODULE,
    COMPETITOR_MODULE,
    MATERIAL_MODULE,
    TARIFF_MODULE,
    SUMMARY_MODULE,
    # 兼容接口
    get_supply_chain_analysis_prompt,
    get_supplier_analysis_prompt,
    ANALYSIS_SYSTEM_PROMPT,
    MATERIAL_CATEGORIES,
    precheck_news_quality,
    COMPETITORS  # 完整友商列表
)

__all__ = [
    # V3 模块化接口
    'get_all_module_prompts',
    'get_summary_prompt',
    'get_module_prompt',
    'FIRST_ROUND_MODULES',
    'CUSTOMER_MODULE',
    'COMPETITOR_MODULE',
    'MATERIAL_MODULE',
    'TARIFF_MODULE',
    'SUMMARY_MODULE',
    'COMPETITORS',
    # 兼容接口
    'get_supply_chain_analysis_prompt',
    'get_supplier_analysis_prompt',
    'ANALYSIS_SYSTEM_PROMPT',
    'MATERIAL_CATEGORIES',
    'precheck_news_quality',
    # 市场分析
    'get_market_analysis_prompt', 
    'MARKET_SYSTEM_PROMPT',
    # V4 深度优化接口（基础）
    'get_all_module_prompts_v4',
    'get_summary_prompt_v4',
    'get_module_prompt_v4',
    'build_material_section',
    'fetch_news_full_content',
    'filter_tariff_news',
    'assemble_final_report_v4',
    'precheck_news_quality_v4',
    # V4 关税独立模块
    'TARIFF_REGIONS',
    'TARIFF_CLASSIFIER_MODULE_V4',
    'TARIFF_SUMMARY_MODULE',
    'TARIFF_MODULES',
    'get_region_tariff_prompt',
    'get_tariff_summary_prompt',
    'get_all_region_prompts',
    'build_tariff_report_section',
    'filter_news_by_region',
    'format_news_for_analysis',
    'FIRST_ROUND_MODULES_V4',
    'SECOND_ROUND_TARIFF_MODULES',
    'THIRD_ROUND_MODULES',
]