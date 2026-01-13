"""
TrendRadar MCP Server - FastMCP 2.0 实现

使用 FastMCP 2.0 提供生产级 MCP 工具服务器。
支持 stdio 和 HTTP 两种传输模式。
"""

import json
from typing import List, Optional, Dict

from fastmcp import FastMCP

from .tools.data_query import DataQueryTools
from .tools.analytics import AnalyticsTools
from .tools.search_tools import SearchTools
from .tools.config_mgmt import ConfigManagementTools
from .tools.system import SystemManagementTools
from .tools.date_tools import DateTools


# 创建 FastMCP 2.0 应用
mcp = FastMCP('trendradar-news')

# 全局工具实例（在第一次请求时初始化）
_tools_instances = {}


def _get_tools(project_root: Optional[str] = None):
    """获取或创建工具实例（单例模式）"""
    if not _tools_instances:
        _tools_instances['data'] = DataQueryTools(project_root)
        _tools_instances['analytics'] = AnalyticsTools(project_root)
        _tools_instances['search'] = SearchTools(project_root)
        _tools_instances['config'] = ConfigManagementTools(project_root)
        _tools_instances['system'] = SystemManagementTools(project_root)
        _tools_instances['date'] = DateTools()
    return _tools_instances


# ==================== 数据查询工具 ====================

@mcp.tool
async def get_latest_news(
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    获取最新一批爬取的新闻数据，快速了解当前热点

    Args:
        platforms: 平台ID列表，如 ['zhihu', 'weibo', 'douyin']
                   - 不指定时：使用 config.yaml 中配置的所有平台
                   - 支持的平台来自 config/config.yaml 的 platforms 配置
                   - 每个平台都有对应的name字段（如"知乎"、"微博"），方便AI识别
        limit: 返回条数限制，默认50，最大1000
               注意：实际返回数量可能少于请求值，取决于当前可用的新闻总数
        include_url: 是否包含URL链接，默认False（节省token）

    Returns:
        JSON格式的新闻列表

    **重要：数据展示建议**
    本工具会返回完整的新闻列表（通常50条）给你。但请注意：
    - **工具返回**：完整的50条数据 ✅
    - **建议展示**：向用户展示全部数据，除非用户明确要求总结
    - **用户期望**：用户可能需要完整数据，请谨慎总结

    **何时可以总结**：
    - 用户明确说"给我总结一下"或"挑重点说"
    - 数据量超过100条时，可先展示部分并询问是否查看全部

    **注意**：如果用户询问"为什么只显示了部分"，说明他们需要完整数据
    """
    tools = _get_tools()
    result = tools['data'].get_latest_news(platforms=platforms, limit=limit, include_url=include_url)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_trending_topics(
    top_n: int = 10,
    mode: str = 'current'
) -> str:
    """
    获取个人关注词的新闻出现频率统计（基于 config/frequency_words.txt）

    注意：本工具不是自动提取新闻热点，而是统计你在 config/frequency_words.txt 中
    设置的个人关注词在新闻中出现的频率。你可以自定义这个关注词列表。

    Args:
        top_n: 返回TOP N关注词，默认10
        mode: 模式选择
            - daily: 当日累计数据统计
            - current: 最新一批数据统计（默认）

    Returns:
        JSON格式的关注词频率统计列表
    """
    tools = _get_tools()
    result = tools['data'].get_trending_topics(top_n=top_n, mode=mode)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_news_by_date(
    date_query: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    获取指定日期的新闻数据，用于历史数据分析和对比

    Args:
        date_query: 日期查询，可选格式:
            - 自然语言: "今天", "昨天", "前天", "3天前"
            - 标准日期: "2024-01-15", "2024/01/15"
            - 默认值: "今天"（节省token）
        platforms: 平台ID列表，如 ['zhihu', 'weibo', 'douyin']
                   - 不指定时：使用 config.yaml 中配置的所有平台
                   - 支持的平台来自 config/config.yaml 的 platforms 配置
                   - 每个平台都有对应的name字段（如"知乎"、"微博"），方便AI识别
        limit: 返回条数限制，默认50，最大1000
               注意：实际返回数量可能少于请求值，取决于指定日期的新闻总数
        include_url: 是否包含URL链接，默认False（节省token）

    Returns:
        JSON格式的新闻列表，包含标题、平台、排名等信息

    **重要：数据展示建议**
    本工具会返回完整的新闻列表（通常50条）给你。但请注意：
    - **工具返回**：完整的50条数据 ✅
    - **建议展示**：向用户展示全部数据，除非用户明确要求总结
    - **用户期望**：用户可能需要完整数据，请谨慎总结

    **何时可以总结**：
    - 用户明确说"给我总结一下"或"挑重点说"
    - 数据量超过100条时，可先展示部分并询问是否查看全部

    **注意**：如果用户询问"为什么只显示了部分"，说明他们需要完整数据
    """
    tools = _get_tools()
    result = tools['data'].get_news_by_date(
        date_query=date_query,
        platforms=platforms,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)



# ==================== 高级数据分析工具 ====================

@mcp.tool
async def analyze_topic_trend(
    topic: str,
    analysis_type: str = "trend",
    date_range: Optional[Dict[str, str]] = None,
    granularity: str = "day",
    threshold: float = 3.0,
    time_window: int = 24,
    lookahead_hours: int = 6,
    confidence_threshold: float = 0.7
) -> str:
    """
    统一话题趋势分析工具 - 整合多种趋势分析模式

    Args:
        topic: 话题关键词（必需）
        analysis_type: 分析类型，可选值：
            - "trend": 热度趋势分析（追踪话题的热度变化）
            - "lifecycle": 生命周期分析（从出现到消失的完整周期）
            - "viral": 异常热度检测（识别突然爆火的话题）
            - "predict": 话题预测（预测未来可能的热点）
        date_range: 日期范围（trend和lifecycle模式），可选
                    - **格式**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}（必须是标准日期格式）
                    - **说明**: AI必须根据当前日期自动计算并填入具体日期，不能使用"今天"等自然语言
                    - **计算示例**:
                      - 用户说"最近7天" → AI计算: {"start": "2025-11-11", "end": "2025-11-17"}（假设今天是11-17）
                      - 用户说"上周" → AI计算: {"start": "2025-11-11", "end": "2025-11-17"}（上周一到上周日）
                      - 用户说"本月" → AI计算: {"start": "2025-11-01", "end": "2025-11-17"}（11月1日到今天）
                    - **默认**: 不指定时默认分析最近7天
        granularity: 时间粒度（trend模式），默认"day"（仅支持 day，因为底层数据按天聚合）
        threshold: 热度突增倍数阈值（viral模式），默认3.0
        time_window: 检测时间窗口小时数（viral模式），默认24
        lookahead_hours: 预测未来小时数（predict模式），默认6
        confidence_threshold: 置信度阈值（predict模式），默认0.7

    Returns:
        JSON格式的趋势分析结果

    **AI使用说明：**
    当用户使用相对时间表达时（如"最近7天"、"过去一周"、"上个月"），
    AI必须根据当前日期（从环境 <env> 获取）计算出具体的 YYYY-MM-DD 格式日期。

    **重要**：date_range 不接受"今天"、"昨天"等自然语言，必须是 YYYY-MM-DD 格式！

    Examples (假设今天是 2025-11-17):
        - 用户："分析AI最近7天的趋势"
          → analyze_topic_trend(topic="人工智能", analysis_type="trend", date_range={"start": "2025-11-11", "end": "2025-11-17"})
        - 用户："看看特斯拉本月的热度"
          → analyze_topic_trend(topic="特斯拉", analysis_type="lifecycle", date_range={"start": "2025-11-01", "end": "2025-11-17"})
        - analyze_topic_trend(topic="比特币", analysis_type="viral", threshold=3.0)
        - analyze_topic_trend(topic="ChatGPT", analysis_type="predict", lookahead_hours=6)
    """
    tools = _get_tools()
    result = tools['analytics'].analyze_topic_trend_unified(
        topic=topic,
        analysis_type=analysis_type,
        date_range=date_range,
        granularity=granularity,
        threshold=threshold,
        time_window=time_window,
        lookahead_hours=lookahead_hours,
        confidence_threshold=confidence_threshold
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def analyze_data_insights(
    insight_type: str = "platform_compare",
    topic: Optional[str] = None,
    date_range: Optional[Dict[str, str]] = None,
    min_frequency: int = 3,
    top_n: int = 20
) -> str:
    """
    统一数据洞察分析工具 - 整合多种数据分析模式

    Args:
        insight_type: 洞察类型，可选值：
            - "platform_compare": 平台对比分析（对比不同平台对话题的关注度）
            - "platform_activity": 平台活跃度统计（统计各平台发布频率和活跃时间）
            - "keyword_cooccur": 关键词共现分析（分析关键词同时出现的模式）
        topic: 话题关键词（可选，platform_compare模式适用）
        date_range: **【对象类型】** 日期范围（可选）
                    - **格式**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **示例**: {"start": "2025-01-01", "end": "2025-01-07"}
                    - **重要**: 必须是对象格式，不能传递整数
        min_frequency: 最小共现频次（keyword_cooccur模式），默认3
        top_n: 返回TOP N结果（keyword_cooccur模式），默认20

    Returns:
        JSON格式的数据洞察分析结果

    Examples:
        - analyze_data_insights(insight_type="platform_compare", topic="人工智能")
        - analyze_data_insights(insight_type="platform_activity", date_range={"start": "2025-01-01", "end": "2025-01-07"})
        - analyze_data_insights(insight_type="keyword_cooccur", min_frequency=5, top_n=15)
    """
    tools = _get_tools()
    result = tools['analytics'].analyze_data_insights_unified(
        insight_type=insight_type,
        topic=topic,
        date_range=date_range,
        min_frequency=min_frequency,
        top_n=top_n
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def analyze_sentiment(
    topic: Optional[str] = None,
    platforms: Optional[List[str]] = None,
    date_range: Optional[Dict[str, str]] = None,
    limit: int = 50,
    sort_by_weight: bool = True,
    include_url: bool = False
) -> str:
    """
    分析新闻的情感倾向和热度趋势

    Args:
        topic: 话题关键词（可选）
        platforms: 平台ID列表，如 ['zhihu', 'weibo', 'douyin']
                   - 不指定时：使用 config.yaml 中配置的所有平台
                   - 支持的平台来自 config/config.yaml 的 platforms 配置
                   - 每个平台都有对应的name字段（如"知乎"、"微博"），方便AI识别
        date_range: **【对象类型】** 日期范围（可选）
                    - **格式**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **示例**: {"start": "2025-01-01", "end": "2025-01-07"}
                    - **重要**: 必须是对象格式，不能传递整数
        limit: 返回新闻数量，默认50，最大100
               注意：本工具会对新闻标题进行去重（同一标题在不同平台只保留一次），
               因此实际返回数量可能少于请求的 limit 值
        sort_by_weight: 是否按热度权重排序，默认True
        include_url: 是否包含URL链接，默认False（节省token）

    Returns:
        JSON格式的分析结果，包含情感分布、热度趋势和相关新闻

    **重要：数据展示策略**
    - 本工具返回完整的分析结果和新闻列表
    - **默认展示方式**：展示完整的分析结果（包括所有新闻）
    - 仅在用户明确要求"总结"或"挑重点"时才进行筛选
    """
    tools = _get_tools()
    result = tools['analytics'].analyze_sentiment(
        topic=topic,
        platforms=platforms,
        date_range=date_range,
        limit=limit,
        sort_by_weight=sort_by_weight,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def find_similar_news(
    reference_title: str,
    threshold: float = 0.6,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    查找与指定新闻标题相似的其他新闻

    Args:
        reference_title: 新闻标题（完整或部分）
        threshold: 相似度阈值，0-1之间，默认0.6
                   注意：阈值越高匹配越严格，返回结果越少
        limit: 返回条数限制，默认50，最大100
               注意：实际返回数量取决于相似度匹配结果，可能少于请求值
        include_url: 是否包含URL链接，默认False（节省token）

    Returns:
        JSON格式的相似新闻列表，包含相似度分数

    **重要：数据展示策略**
    - 本工具返回完整的相似新闻列表
    - **默认展示方式**：展示全部返回的新闻（包括相似度分数）
    - 仅在用户明确要求"总结"或"挑重点"时才进行筛选
    """
    tools = _get_tools()
    result = tools['analytics'].find_similar_news(
        reference_title=reference_title,
        threshold=threshold,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def generate_summary_report(
    report_type: str = "daily",
    date_range: Optional[Dict[str, str]] = None
) -> str:
    """
    每日/每周摘要生成器 - 自动生成热点摘要报告

    Args:
        report_type: 报告类型（daily/weekly）
        date_range: **【对象类型】** 自定义日期范围（可选）
                    - **格式**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **示例**: {"start": "2025-01-01", "end": "2025-01-07"}
                    - **重要**: 必须是对象格式，不能传递整数

    Returns:
        JSON格式的摘要报告，包含Markdown格式内容
    """
    tools = _get_tools()
    result = tools['analytics'].generate_summary_report(
        report_type=report_type,
        date_range=date_range
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== 智能检索工具 ====================

@mcp.tool
async def search_news(
    query: str,
    search_mode: str = "keyword",
    date_range: Optional[Dict[str, str]] = None,
    platforms: Optional[List[str]] = None,
    limit: int = 50,
    sort_by: str = "relevance",
    threshold: float = 0.6,
    include_url: bool = False
) -> str:
    """
    统一搜索接口，支持多种搜索模式

    Args:
        query: 搜索关键词或内容片段
        search_mode: 搜索模式，可选值：
            - "keyword": 精确关键词匹配（默认，适合搜索特定话题）
            - "fuzzy": 模糊内容匹配（适合搜索内容片段，会过滤相似度低于阈值的结果）
            - "entity": 实体名称搜索（适合搜索人物/地点/机构）
        date_range: 日期范围（可选）
                    - **格式**: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
                    - **示例**: {"start": "2025-01-01", "end": "2025-01-07"}
                    - **说明**: AI需要根据用户的自然语言（如"最近7天"）自动计算日期范围
                    - **默认**: 不指定时默认查询今天的新闻
                    - **注意**: start和end可以相同（表示单日查询）
        platforms: 平台ID列表，如 ['zhihu', 'weibo', 'douyin']
                   - 不指定时：使用 config.yaml 中配置的所有平台
                   - 支持的平台来自 config/config.yaml 的 platforms 配置
                   - 每个平台都有对应的name字段（如"知乎"、"微博"），方便AI识别
        limit: 返回条数限制，默认50，最大1000
               注意：实际返回数量取决于搜索匹配结果（特别是 fuzzy 模式下会过滤低相似度结果）
        sort_by: 排序方式，可选值：
            - "relevance": 按相关度排序（默认）
            - "weight": 按新闻权重排序
            - "date": 按日期排序
        threshold: 相似度阈值（仅fuzzy模式有效），0-1之间，默认0.6
                   注意：阈值越高匹配越严格，返回结果越少
        include_url: 是否包含URL链接，默认False（节省token）

    Returns:
        JSON格式的搜索结果，包含标题、平台、排名等信息

    **重要：数据展示策略**
    - 本工具返回完整的搜索结果列表
    - **默认展示方式**：展示全部返回的新闻，无需总结或筛选
    - 仅在用户明确要求"总结"或"挑重点"时才进行筛选

    **AI使用说明：**
    当用户使用相对时间表达时（如"最近7天"、"过去一周"、"最近半个月"），
    AI必须根据当前日期（从环境 <env> 获取）计算出具体的 YYYY-MM-DD 格式日期。

    **重要**：date_range 不接受"今天"、"昨天"等自然语言，必须是 YYYY-MM-DD 格式！

    **计算规则**（假设从 <env> 获取今天是 2025-11-17）：
    - "今天" → 不传 date_range（默认查今天）
    - "最近7天" → {"start": "2025-11-11", "end": "2025-11-17"}
    - "过去一周" → {"start": "2025-11-11", "end": "2025-11-17"}
    - "上周" → 计算上周一到上周日，如 {"start": "2025-11-11", "end": "2025-11-17"}
    - "本月" → {"start": "2025-11-01", "end": "2025-11-17"}
    - "最近30天" → {"start": "2025-10-19", "end": "2025-11-17"}


    Examples (假设今天是 2025-11-17):
        - 用户："今天的AI新闻" → search_news(query="人工智能")
        - 用户："最近7天的AI新闻" → search_news(query="人工智能", date_range={"start": "2025-11-11", "end": "2025-11-17"})
        - 精确日期: search_news(query="人工智能", date_range={"start": "2025-01-01", "end": "2025-01-07"})
        - 模糊搜索: search_news(query="特斯拉降价", search_mode="fuzzy", threshold=0.4)
    """
    tools = _get_tools()
    result = tools['search'].search_news_unified(
        query=query,
        search_mode=search_mode,
        date_range=date_range,
        platforms=platforms,
        limit=limit,
        sort_by=sort_by,
        threshold=threshold,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def search_related_news_history(
    reference_text: str,
    time_preset: str = "yesterday",
    threshold: float = 0.4,
    limit: int = 50,
    include_url: bool = False
) -> str:
    """
    基于种子新闻，在历史数据中搜索相关新闻

    Args:
        reference_text: 参考新闻标题（完整或部分）
        time_preset: 时间范围预设值，可选：
            - "yesterday": 昨天
            - "last_week": 上周 (7天)
            - "last_month": 上个月 (30天)
            - "custom": 自定义日期范围（需要提供 start_date 和 end_date）
        threshold: 相关性阈值，0-1之间，默认0.4
                   注意：综合相似度计算（70%关键词重合 + 30%文本相似度）
                   阈值越高匹配越严格，返回结果越少
        limit: 返回条数限制，默认50，最大100
               注意：实际返回数量取决于相关性匹配结果，可能少于请求值
        include_url: 是否包含URL链接，默认False（节省token）

    Returns:
        JSON格式的相关新闻列表，包含相关性分数和时间分布

    **重要：数据展示策略**
    - 本工具返回完整的相关新闻列表
    - **默认展示方式**：展示全部返回的新闻（包括相关性分数）
    - 仅在用户明确要求"总结"或"挑重点"时才进行筛选
    """
    tools = _get_tools()
    result = tools['search'].search_related_news_history(
        reference_text=reference_text,
        time_preset=time_preset,
        threshold=threshold,
        limit=limit,
        include_url=include_url
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== RSS 查询工具 ====================

@mcp.tool
async def get_latest_rss(
    feed_ids: Optional[List[str]] = None,
    limit: int = 50,
    include_summary: bool = True
) -> str:
    """
    获取最新的 RSS 订阅文章

    Args:
        feed_ids: RSS 源 ID 列表，None 表示所有源
                  - 可用源ID来自 config/rss.yaml 配置
        limit: 返回条数限制，默认50
        include_summary: 是否包含文章摘要，默认True

    Returns:
        JSON格式的 RSS 文章列表
    """
    tools = _get_tools()
    result = tools['data'].get_latest_rss(
        feed_ids=feed_ids,
        limit=limit,
        include_summary=include_summary
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def search_rss(
    keyword: str,
    days: int = 7,
    feed_ids: Optional[List[str]] = None,
    limit: int = 50
) -> str:
    """
    在 RSS 订阅内容中搜索关键词

    Args:
        keyword: 搜索关键词
        days: 搜索最近 N 天，默认7
        feed_ids: RSS 源 ID 列表
        limit: 返回条数限制，默认50

    Returns:
        JSON格式的匹配 RSS 文章列表
    """
    tools = _get_tools()
    result = tools['data'].search_rss(
        keyword=keyword,
        days=days,
        feed_ids=feed_ids,
        limit=limit
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_rss_feeds_status() -> str:
    """
    获取所有 RSS 订阅源的状态

    返回每个 RSS 源的：
    - 名称和 URL
    - 文章数量
    - 最后抓取时间
    - 错误状态（如有）

    Returns:
        JSON格式的 RSS 源状态列表
    """
    tools = _get_tools()
    result = tools['data'].get_rss_feeds_status()
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== 日期解析工具 ====================

@mcp.tool
async def resolve_date_range(expression: str) -> str:
    """
    将自然语言日期表达式转换为标准日期范围

    支持的表达式：
    - 今天、昨天、前天
    - 本周、上周、这周
    - 本月、上个月
    - 最近N天、过去N天、N天前、N天内
    - 2025年1月、一月份、1月
    - YYYY-MM-DD 格式
    - 日期范围：2025-01-01 到 2025-01-07

    Args:
        expression: 自然语言日期表达式

    Returns:
        JSON格式的日期范围，包含 start 和 end 字段（YYYY-MM-DD 格式）

    Example:
        - resolve_date_range("最近7天") → {"start": "2025-01-01", "end": "2025-01-07"}
        - resolve_date_range("本月") → {"start": "2025-01-01", "end": "2025-01-07"}
    """
    tools = _get_tools()
    result = tools['date'].resolve_date_range(expression)
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== 高级分析工具 ====================

@mcp.tool
async def compare_periods(
    period1: Dict[str, str],
    period2: Dict[str, str],
    dimensions: Optional[List[str]] = None
) -> str:
    """
    对比两个时间段的热点差异

    Args:
        period1: 第一个时间段，格式: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
        period2: 第二个时间段，格式: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
        dimensions: 对比维度列表，可选: ["topic", "platform"]

    Returns:
        JSON格式的对比分析结果，包含：
        - 新增话题（period2 有但 period1 没有）
        - 消失话题（period1 有但 period2 没有）
        - 热度变化

    Example:
        compare_periods(
            period1={"start": "2025-01-01", "end": "2025-01-07"},
            period2={"start": "2025-01-08", "end": "2025-01-14"}
        )
    """
    tools = _get_tools()
    result = tools['analytics'].compare_periods(
        period1=period1,
        period2=period2,
        dimensions=dimensions
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def aggregate_news(
    date_range: Optional[Dict[str, str]] = None,
    platforms: Optional[List[str]] = None,
    similarity_threshold: float = 0.7,
    limit: int = 100
) -> str:
    """
    跨平台新闻去重聚合

    将多个平台报道的同一事件合并，识别跨平台热点。

    Args:
        date_range: 日期范围，格式: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
        platforms: 平台过滤列表
        similarity_threshold: 相似度阈值（0-1），默认0.7，越高越严格
        limit: 返回条数限制，默认100

    Returns:
        JSON格式的聚合结果，包含：
        - 聚合后的新闻列表
        - 每条新闻的来源平台列表
        - 去重率统计

    Example:
        aggregate_news(
            date_range={"start": "2025-01-01", "end": "2025-01-07"},
            similarity_threshold=0.7
        )
    """
    tools = _get_tools()
    result = tools['analytics'].aggregate_news(
        date_range=date_range,
        platforms=platforms,
        similarity_threshold=similarity_threshold,
        limit=limit
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def search_all(
    query: str,
    include_hotlist: bool = True,
    include_rss: bool = True,
    date_range: Optional[Dict[str, str]] = None,
    limit: int = 50
) -> str:
    """
    同时搜索热搜和 RSS 订阅内容（联合搜索）

    Args:
        query: 搜索关键词
        include_hotlist: 是否包含热搜数据，默认True
        include_rss: 是否包含RSS数据，默认True
        date_range: 日期范围，格式: {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
        limit: 每种数据源的返回条数限制，默认50

    Returns:
        JSON格式的合并搜索结果，包含：
        - hotlist_results: 热搜匹配结果
        - rss_results: RSS匹配结果
        - total: 总匹配数

    Example:
        search_all(query="人工智能", include_hotlist=True, include_rss=True)
    """
    tools = _get_tools()
    result = tools['search'].search_all(
        query=query,
        include_hotlist=include_hotlist,
        include_rss=include_rss,
        date_range=date_range,
        limit=limit
    )
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== 配置与系统管理工具 ====================

@mcp.tool
async def get_current_config(
    section: str = "all"
) -> str:
    """
    获取当前系统配置

    Args:
        section: 配置节，可选值：
            - "all": 所有配置（默认）
            - "crawler": 爬虫配置
            - "push": 推送配置
            - "keywords": 关键词配置
            - "weights": 权重配置

    Returns:
        JSON格式的配置信息
    """
    tools = _get_tools()
    result = tools['config'].get_current_config(section=section)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def get_system_status() -> str:
    """
    获取系统运行状态和健康检查信息

    返回系统版本、数据统计、缓存状态等信息

    Returns:
        JSON格式的系统状态信息
    """
    tools = _get_tools()
    result = tools['system'].get_system_status()
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool
async def trigger_crawl(
    platforms: Optional[List[str]] = None,
    save_to_local: bool = False,
    include_url: bool = False
) -> str:
    """
    手动触发一次爬取任务（可选持久化）

    Args:
        platforms: 指定平台ID列表，如 ['zhihu', 'weibo', 'douyin']
                   - 不指定时：使用 config.yaml 中配置的所有平台
                   - 支持的平台来自 config/config.yaml 的 platforms 配置
                   - 每个平台都有对应的name字段（如"知乎"、"微博"），方便AI识别
                   - 注意：失败的平台会在返回结果的 failed_platforms 字段中列出
        save_to_local: 是否保存到本地 output 目录，默认 False
        include_url: 是否包含URL链接，默认False（节省token）

    Returns:
        JSON格式的任务状态信息，包含：
        - platforms: 成功爬取的平台列表
        - failed_platforms: 失败的平台列表（如有）
        - total_news: 爬取的新闻总数
        - data: 新闻数据

    Examples:
        - 临时爬取: trigger_crawl(platforms=['zhihu'])
        - 爬取并保存: trigger_crawl(platforms=['weibo'], save_to_local=True)
        - 使用默认平台: trigger_crawl()  # 爬取config.yaml中配置的所有平台
    """
    tools = _get_tools()
    result = tools['system'].trigger_crawl(platforms=platforms, save_to_local=save_to_local, include_url=include_url)
    return json.dumps(result, ensure_ascii=False, indent=2)


# ==================== 启动入口 ====================

def run_server(
    project_root: Optional[str] = None,
    transport: str = 'stdio',
    host: str = '0.0.0.0',
    port: int = 3333
):
    """
    启动 MCP 服务器

    Args:
        project_root: 项目根目录路径
        transport: 传输模式，'stdio' 或 'http'
        host: HTTP模式的监听地址，默认 0.0.0.0
        port: HTTP模式的监听端口，默认 3333
    """
    # 初始化工具实例
    _get_tools(project_root)

    # 打印启动信息
    print()
    print("=" * 60)
    print("  TrendRadar MCP Server - FastMCP 2.0")
    print("=" * 60)
    print(f"  传输模式: {transport.upper()}")

    if transport == 'stdio':
        print("  协议: MCP over stdio (标准输入输出)")
        print("  说明: 通过标准输入输出与 MCP 客户端通信")
    elif transport == 'http':
        print(f"  监听地址: http://{host}:{port}")
        print(f"  HTTP端点: http://{host}:{port}/mcp")
        print("  协议: MCP over HTTP (生产环境)")

    if project_root:
        print(f"  项目目录: {project_root}")
    else:
        print("  项目目录: 当前目录")

    print()
    print("  已注册的工具 (20个):")
    print("    === 基础数据查询（P0核心）===")
    print("    1. get_latest_news        - 获取最新新闻")
    print("    2. get_news_by_date       - 按日期查询新闻（支持自然语言）")
    print("    3. get_trending_topics    - 获取趋势话题")
    print()
    print("    === 智能检索工具 ===")
    print("    4. search_news                  - 统一新闻搜索（关键词/模糊/实体）")
    print("    5. search_related_news_history  - 历史相关新闻检索")
    print("    6. search_all                   - 热搜+RSS联合搜索 [NEW]")
    print()
    print("    === 高级数据分析 ===")
    print("    7. analyze_topic_trend      - 统一话题趋势分析（热度/生命周期/爆火/预测）")
    print("    8. analyze_data_insights    - 统一数据洞察分析（平台对比/活跃度/关键词共现）")
    print("    9. analyze_sentiment        - 情感倾向分析")
    print("    10. find_similar_news       - 相似新闻查找")
    print("    11. generate_summary_report - 每日/每周摘要生成")
    print("    12. compare_periods         - 时期对比分析 [NEW]")
    print("    13. aggregate_news          - 跨平台新闻聚合 [NEW]")
    print()
    print("    === RSS 订阅工具 (v4.0+) ===")
    print("    14. get_latest_rss         - 获取最新RSS文章 [NEW]")
    print("    15. search_rss             - RSS关键词搜索 [NEW]")
    print("    16. get_rss_feeds_status   - RSS源状态查询 [NEW]")
    print()
    print("    === 日期解析工具 ===")
    print("    17. resolve_date_range     - 自然语言日期解析 [NEW]")
    print()
    print("    === 配置与系统管理 ===")
    print("    18. get_current_config     - 获取当前系统配置")
    print("    19. get_system_status      - 获取系统运行状态")
    print("    20. trigger_crawl          - 手动触发爬取任务")
    print("=" * 60)
    print()

    # 根据传输模式运行服务器
    if transport == 'stdio':
        mcp.run(transport='stdio')
    elif transport == 'http':
        # HTTP 模式（生产推荐）
        mcp.run(
            transport='http',
            host=host,
            port=port,
            path='/mcp'  # HTTP 端点路径
        )
    else:
        raise ValueError(f"不支持的传输模式: {transport}")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='TrendRadar MCP Server - 新闻热点聚合 MCP 工具服务器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
详细配置教程请查看: README-Cherry-Studio.md
        """
    )
    parser.add_argument(
        '--transport',
        choices=['stdio', 'http'],
        default='stdio',
        help='传输模式：stdio (默认) 或 http (生产环境)'
    )
    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='HTTP模式的监听地址，默认 0.0.0.0'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=3333,
        help='HTTP模式的监听端口，默认 3333'
    )
    parser.add_argument(
        '--project-root',
        help='项目根目录路径'
    )

    args = parser.parse_args()

    run_server(
        project_root=args.project_root,
        transport=args.transport,
        host=args.host,
        port=args.port
    )
