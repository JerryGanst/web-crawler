# coding=utf-8
"""
TrendRadar 核心模块
提供配置管理、数据处理、报告生成和通知推送等功能
"""

from .config import load_config, CONFIG, VERSION, SMTP_CONFIGS
from .utils import (
    get_beijing_time,
    format_date_folder,
    format_time_filename,
    clean_title,
    ensure_directory_exists,
    get_output_path,
    html_escape,
    check_version_update,
    is_first_crawl_today,
)
from .push_record import PushRecordManager
from .data_fetcher import DataFetcher
from .data_processor import (
    save_titles_to_file,
    load_frequency_words,
    parse_file_titles,
    read_all_today_titles,
    process_source_data,
    detect_latest_new_titles,
)
from .statistics import (
    calculate_news_weight,
    matches_word_groups,
    format_time_display,
    format_rank_display,
    count_word_frequency,
)
from .analyzer import NewsAnalyzer

__all__ = [
    # Config
    'load_config', 'CONFIG', 'VERSION', 'SMTP_CONFIGS',
    # Utils
    'get_beijing_time', 'format_date_folder', 'format_time_filename',
    'clean_title', 'ensure_directory_exists', 'get_output_path',
    'html_escape', 'check_version_update', 'is_first_crawl_today',
    # Classes
    'PushRecordManager', 'DataFetcher', 'NewsAnalyzer',
    # Data Processing
    'save_titles_to_file', 'load_frequency_words', 'parse_file_titles',
    'read_all_today_titles', 'process_source_data', 'detect_latest_new_titles',
    # Statistics
    'calculate_news_weight', 'matches_word_groups', 'format_time_display',
    'format_rank_display', 'count_word_frequency',
]
