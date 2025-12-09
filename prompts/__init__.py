"""
AI 提示词模块
"""
from .analysis_prompts import (
    get_supply_chain_analysis_prompt,
    get_supplier_analysis_prompt,
    ANALYSIS_SYSTEM_PROMPT,
    MATERIAL_CATEGORIES
)
from .market_prompts import get_market_analysis_prompt, MARKET_SYSTEM_PROMPT

__all__ = [
    'get_supply_chain_analysis_prompt',
    'get_supplier_analysis_prompt',
    'ANALYSIS_SYSTEM_PROMPT',
    'MATERIAL_CATEGORIES',
    'get_market_analysis_prompt', 
    'MARKET_SYSTEM_PROMPT'
]
