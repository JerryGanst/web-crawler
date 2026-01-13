# coding=utf-8
"""
数据洞察工具集

将 MCP 工具封装为 LangChain Tools，供 LangGraph Agent 调用。
"""

import json
import sys
import os
from typing import Optional, List, Dict, Any
from datetime import datetime

from langchain_core.tools import tool

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp_server.tools.data_query import DataQueryTools
from mcp_server.tools.analytics import AnalyticsTools
from mcp_server.tools.search_tools import SearchTools
from mcp_server.tools.date_tools import DateTools

# 大宗商品数据库查询 - 延迟导入避免启动时连接失败
def _get_commodity_functions():
    """延迟导入商品查询函数，避免启动时 MySQL 连接失败"""
    try:
        from database.mysql.pipeline import get_latest_prices, get_price_history, get_commodities_by_date
        return get_latest_prices, get_price_history, get_commodities_by_date
    except Exception as e:
        print(f"⚠️ 商品数据库模块加载失败: {e}")
        return None, None, None


class DataInsightTools:
    """数据洞察工具管理器"""

    def __init__(self, project_root: str = None):
        """初始化工具实例"""
        self.data_tools = DataQueryTools(project_root)
        self.analytics_tools = AnalyticsTools(project_root)
        self.search_tools = SearchTools(project_root)
        self.date_tools = DateTools()

    def get_langchain_tools(self) -> List:
        """获取所有 LangChain 工具"""
        return [
            # 新闻热搜工具
            self._create_get_latest_news(),
            self._create_search_news(),
            self._create_get_trending_topics(),
            self._create_analyze_topic_trend(),
            self._create_compare_periods(),
            self._create_get_news_by_date(),
            self._create_resolve_date_range(),
            self._create_trigger_crawl(),
            # 大宗商品工具
            self._create_get_commodity_prices(),
            self._create_get_commodity_history(),
            self._create_search_commodity(),
        ]

    def _create_get_latest_news(self):
        """创建获取最新新闻工具"""
        data_tools = self.data_tools

        @tool
        def get_latest_news(
            platforms: Optional[str] = None,
            limit: int = 20
        ) -> str:
            """
            获取最新一批爬取的热搜新闻数据。

            Args:
                platforms: 平台ID列表，用逗号分隔，如 'zhihu,weibo,baidu'。
                          可选平台: zhihu(知乎), weibo(微博), baidu(百度),
                          douyin(抖音), bilibili(B站), toutiao(头条)
                          不传则获取所有平台
                limit: 返回条数，默认20条

            Returns:
                JSON格式的新闻列表，包含标题、平台、热度等信息

            使用场景：
            - "最新有什么热搜？"
            - "知乎上有什么热门话题？"
            - "给我看看今天的新闻"
            """
            platform_list = platforms.split(',') if platforms else None
            result = data_tools.get_latest_news(
                platforms=platform_list,
                limit=limit,
                include_url=False
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        return get_latest_news

    def _create_search_news(self):
        """创建新闻搜索工具"""
        search_tools = self.search_tools

        @tool
        def search_news(
            keyword: str,
            days: int = 7,
            platforms: Optional[str] = None,
            limit: int = 30
        ) -> str:
            """
            按关键词搜索历史新闻数据。

            Args:
                keyword: 搜索关键词，如 "人工智能"、"特朗普"、"房价"
                days: 搜索最近多少天的数据，默认7天
                platforms: 平台ID列表，用逗号分隔，不传则搜索所有平台
                limit: 返回条数，默认30条

            Returns:
                JSON格式的搜索结果，按相关度排序

            使用场景：
            - "最近一周有关AI的新闻"
            - "搜索关于特斯拉的热搜"
            - "找找关于房价的讨论"
            """
            from datetime import datetime, timedelta

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            platform_list = platforms.split(',') if platforms else None

            result = search_tools.search_news_unified(
                query=keyword,
                search_mode="keyword",
                date_range={
                    "start": start_date.strftime("%Y-%m-%d"),
                    "end": end_date.strftime("%Y-%m-%d")
                },
                platforms=platform_list,
                limit=limit
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        return search_news

    def _create_get_trending_topics(self):
        """创建热门话题工具"""
        data_tools = self.data_tools

        @tool
        def get_trending_topics(
            top_n: int = 10,
            mode: str = "current"
        ) -> str:
            """
            获取当前热门关注词的出现频率统计。

            Args:
                top_n: 返回TOP N个话题，默认10个
                mode: 统计模式
                    - "current": 最新一批数据
                    - "daily": 当日累计
                    - "incremental": 增量变化

            Returns:
                JSON格式的热门话题列表，包含关键词和出现次数

            使用场景：
            - "现在最热门的话题是什么？"
            - "今天讨论最多的是什么？"
            - "有什么热点趋势？"
            """
            result = data_tools.get_trending_topics(top_n=top_n, mode=mode)
            return json.dumps(result, ensure_ascii=False, indent=2)

        return get_trending_topics

    def _create_analyze_topic_trend(self):
        """创建话题趋势分析工具"""
        analytics_tools = self.analytics_tools

        @tool
        def analyze_topic_trend(
            keyword: str,
            days: int = 7,
            analysis_type: str = "热度趋势"
        ) -> str:
            """
            分析某个话题/关键词的趋势变化。

            Args:
                keyword: 要分析的关键词，如 "ChatGPT"、"房价"
                days: 分析最近多少天，默认7天
                analysis_type: 分析类型
                    - "热度趋势": 话题热度随时间的变化
                    - "生命周期": 话题从出现到消退的完整周期
                    - "爆火检测": 检测是否有突然爆发的迹象

            Returns:
                JSON格式的趋势分析结果

            使用场景：
            - "分析AI话题最近的热度变化"
            - "这个话题是不是要火了？"
            - "特斯拉最近的讨论趋势怎么样？"
            """
            result = analytics_tools.analyze_topic_trend_unified(
                topic=keyword,
                analysis_type=analysis_type
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        return analyze_topic_trend

    def _create_compare_periods(self):
        """创建时期对比工具"""
        analytics_tools = self.analytics_tools
        date_tools = self.date_tools

        @tool
        def compare_periods(
            period1_expr: str,
            period2_expr: str
        ) -> str:
            """
            对比两个时间段的热点话题差异。

            Args:
                period1_expr: 第一个时间段的自然语言表达，如 "上周"、"最近3天"
                period2_expr: 第二个时间段的自然语言表达，如 "本周"、"昨天"

            Returns:
                JSON格式的对比结果，包含：
                - 新增话题（period2有但period1没有）
                - 消失话题（period1有但period2没有）
                - 热度变化

            使用场景：
            - "对比上周和本周的热点变化"
            - "这周比上周多了什么新话题？"
            - "最近3天和之前3天有什么不同？"
            """
            # 解析自然语言日期
            p1 = date_tools.resolve_date_range(period1_expr)
            p2 = date_tools.resolve_date_range(period2_expr)

            if not p1.get("success") or not p2.get("success"):
                return json.dumps({
                    "success": False,
                    "error": f"日期解析失败: {period1_expr} 或 {period2_expr}"
                }, ensure_ascii=False)

            result = analytics_tools.compare_periods(
                period1={"start": p1["start"], "end": p1["end"]},
                period2={"start": p2["start"], "end": p2["end"]}
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        return compare_periods

    def _create_get_news_by_date(self):
        """创建按日期查询新闻工具"""
        data_tools = self.data_tools

        @tool
        def get_news_by_date(
            date_query: str = "今天",
            platforms: Optional[str] = None,
            limit: int = 30
        ) -> str:
            """
            按日期查询新闻，支持自然语言日期表达。

            Args:
                date_query: 日期表达式，支持：
                    - 相对日期：今天、昨天、前天、3天前
                    - 星期：上周一、本周三
                    - 绝对日期：2025-01-15、1月15日
                platforms: 平台ID列表，用逗号分隔
                limit: 返回条数，默认30条

            Returns:
                JSON格式的新闻列表

            使用场景：
            - "昨天有什么新闻？"
            - "上周一的热搜是什么？"
            - "1月5号发生了什么？"
            """
            platform_list = platforms.split(',') if platforms else None
            result = data_tools.get_news_by_date(
                date_query=date_query,
                platforms=platform_list,
                limit=limit,
                include_url=False
            )
            return json.dumps(result, ensure_ascii=False, indent=2)

        return get_news_by_date

    def _create_resolve_date_range(self):
        """创建日期解析工具"""
        date_tools = self.date_tools

        @tool
        def resolve_date_range(expression: str) -> str:
            """
            将自然语言日期表达式转换为标准日期范围。

            Args:
                expression: 自然语言日期表达式，如：
                    - "今天"、"昨天"、"前天"
                    - "本周"、"上周"、"这周"
                    - "本月"、"上个月"
                    - "最近7天"、"过去3天"
                    - "2025年1月"、"一月份"

            Returns:
                JSON格式的日期范围，包含 start 和 end 字段

            使用场景：
            - 用于理解用户说的时间范围
            - 在进行日期相关查询前先解析日期
            """
            result = date_tools.resolve_date_range(expression)
            return json.dumps(result, ensure_ascii=False, indent=2)

        return resolve_date_range

    def _create_trigger_crawl(self):
        """创建触发爬虫工具"""

        @tool
        def trigger_crawl() -> str:
            """
            立即启动爬虫获取最新热搜数据。

            当用户查询数据但发现数据为空或过期时，调用此工具启动爬虫。
            爬虫会在后台运行，获取知乎、微博、百度、抖音等平台的最新热搜。

            Returns:
                启动状态信息

            使用场景：
            - 当 get_latest_news 返回空数据时
            - 用户说"没有数据"、"获取最新的"
            - 用户主动要求刷新或爬取数据
            """
            import subprocess
            import os
            import threading

            try:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

                def run_crawler():
                    try:
                        subprocess.run(
                            ["python3", "-m", "scrapers.hotlist_scraper"],
                            cwd=project_root,
                            timeout=120,
                            capture_output=True
                        )
                    except Exception as e:
                        pass

                # 后台启动爬虫
                thread = threading.Thread(target=run_crawler, daemon=True)
                thread.start()

                return json.dumps({
                    "success": True,
                    "message": "🚀 爬虫已启动！正在获取知乎、微博、百度、抖音等平台的最新热搜，请等待 30-60 秒后再次提问。"
                }, ensure_ascii=False)

            except Exception as e:
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, ensure_ascii=False)

        return trigger_crawl

    def _create_get_commodity_prices(self):
        """创建获取大宗商品价格工具"""

        @tool
        def get_commodity_prices(category: Optional[str] = None) -> str:
            """
            获取最新的大宗商品价格数据。

            Args:
                category: 商品分类，可选值:
                    - "贵金属": 黄金、白银、铂金、钯金
                    - "能源": 原油(WTI/Brent)、天然气、汽油
                    - "工业金属": 铜、铝、锌、镍、铅、锡
                    - "农产品": 玉米、小麦、大豆、棉花、糖、咖啡等
                    - 不传则获取所有分类

            Returns:
                JSON格式的商品价格列表，包含价格、涨跌幅、单位等信息

            使用场景：
            - "黄金现在多少钱？"
            - "原油价格是多少？"
            - "查看贵金属价格"
            - "大宗商品行情怎么样？"
            """
            try:
                get_latest_prices, _, _ = _get_commodity_functions()
                if get_latest_prices is None:
                    return json.dumps({
                        "success": False,
                        "error": "商品数据库连接失败"
                    }, ensure_ascii=False)

                results = get_latest_prices(category)
                if not results:
                    return json.dumps({
                        "success": False,
                        "message": "暂无商品数据",
                        "data": []
                    }, ensure_ascii=False)

                # 格式化输出
                formatted = []
                for r in results:
                    formatted.append({
                        "id": r.get("id"),
                        "name": r.get("name"),
                        "chinese_name": r.get("chinese_name"),
                        "category": r.get("category"),
                        "price": float(r.get("price", 0)),
                        "price_unit": r.get("price_unit", "USD"),
                        "weight_unit": r.get("weight_unit", ""),
                        "change_percent": float(r.get("change_percent") or 0),
                        "high_price": float(r.get("high_price") or 0) if r.get("high_price") else None,
                        "low_price": float(r.get("low_price") or 0) if r.get("low_price") else None,
                        "update_time": str(r.get("as_of_ts", ""))
                    })

                return json.dumps({
                    "success": True,
                    "count": len(formatted),
                    "data": formatted
                }, ensure_ascii=False, indent=2)

            except Exception as e:
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, ensure_ascii=False)

        return get_commodity_prices

    def _create_get_commodity_history(self):
        """创建获取商品历史价格工具"""

        @tool
        def get_commodity_history(
            commodity_name: str,
            days: int = 7
        ) -> str:
            """
            获取某个大宗商品的历史价格走势。

            Args:
                commodity_name: 商品名称，支持中英文，如:
                    - "黄金" 或 "gold"
                    - "原油" 或 "oil_wti" / "oil_brent"
                    - "铜" 或 "copper"
                    - "白银" 或 "silver"
                days: 查询最近多少天，默认7天

            Returns:
                JSON格式的历史价格数据

            使用场景：
            - "黄金最近一周走势怎么样？"
            - "原油这个月的价格变化"
            - "铜价历史数据"
            """
            from datetime import datetime, timedelta

            # 商品名称映射
            name_map = {
                "黄金": "gold", "金": "gold", "金价": "gold",
                "白银": "silver", "银": "silver",
                "铂金": "platinum", "钯金": "palladium",
                "原油": "oil_wti", "WTI原油": "oil_wti", "布伦特原油": "oil_brent",
                "天然气": "natural_gas", "汽油": "gasoline",
                "铜": "copper", "铝": "aluminum", "锌": "zinc",
                "镍": "nickel", "铅": "lead", "锡": "tin",
                "玉米": "corn", "小麦": "wheat", "大豆": "soybeans",
                "棉花": "cotton", "糖": "sugar", "咖啡": "coffee",
            }

            # 转换名称
            commodity_id = name_map.get(commodity_name, commodity_name.lower().replace(" ", "_"))

            try:
                _, get_price_history, _ = _get_commodity_functions()
                if get_price_history is None:
                    return json.dumps({
                        "success": False,
                        "error": "商品数据库连接失败"
                    }, ensure_ascii=False)

                end_time = datetime.now()
                start_time = end_time - timedelta(days=days)

                results = get_price_history(commodity_id, start_time, end_time)

                if not results:
                    return json.dumps({
                        "success": False,
                        "message": f"未找到 {commodity_name} 的历史数据",
                        "data": []
                    }, ensure_ascii=False)

                # 格式化输出
                formatted = []
                for r in results:
                    formatted.append({
                        "date": str(r.get("record_date", "")),
                        "price": float(r.get("price", 0)),
                        "change_percent": float(r.get("change_percent") or 0),
                        "high_price": float(r.get("high_price") or 0) if r.get("high_price") else None,
                        "low_price": float(r.get("low_price") or 0) if r.get("low_price") else None,
                    })

                return json.dumps({
                    "success": True,
                    "commodity": commodity_name,
                    "days": days,
                    "count": len(formatted),
                    "data": formatted
                }, ensure_ascii=False, indent=2)

            except Exception as e:
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, ensure_ascii=False)

        return get_commodity_history

    def _create_search_commodity(self):
        """创建搜索商品工具"""

        @tool
        def search_commodity(keyword: str) -> str:
            """
            按关键词搜索大宗商品。

            Args:
                keyword: 搜索关键词，如 "金"、"油"、"金属"

            Returns:
                JSON格式的匹配商品列表

            使用场景：
            - "有哪些贵金属？"
            - "搜索和油相关的商品"
            - "查找金属类商品"
            """
            try:
                get_latest_prices, _, _ = _get_commodity_functions()
                if get_latest_prices is None:
                    return json.dumps({
                        "success": False,
                        "error": "商品数据库连接失败"
                    }, ensure_ascii=False)

                # 获取所有商品
                all_commodities = get_latest_prices(None)

                if not all_commodities:
                    return json.dumps({
                        "success": False,
                        "message": "暂无商品数据",
                        "data": []
                    }, ensure_ascii=False)

                # 关键词搜索
                matched = []
                keyword_lower = keyword.lower()
                for r in all_commodities:
                    name = (r.get("name") or "").lower()
                    chinese_name = r.get("chinese_name") or ""
                    category = r.get("category") or ""

                    if (keyword_lower in name or
                        keyword in chinese_name or
                        keyword in category):
                        matched.append({
                            "id": r.get("id"),
                            "name": r.get("name"),
                            "chinese_name": r.get("chinese_name"),
                            "category": r.get("category"),
                            "price": float(r.get("price", 0)),
                            "price_unit": r.get("price_unit", "USD"),
                            "change_percent": float(r.get("change_percent") or 0),
                        })

                return json.dumps({
                    "success": True,
                    "keyword": keyword,
                    "count": len(matched),
                    "data": matched
                }, ensure_ascii=False, indent=2)

            except Exception as e:
                return json.dumps({
                    "success": False,
                    "error": str(e)
                }, ensure_ascii=False)

        return search_commodity


# 全局工具实例
_tools_instance = None

def get_tools_instance(project_root: str = None) -> DataInsightTools:
    """获取工具单例"""
    global _tools_instance
    if _tools_instance is None:
        _tools_instance = DataInsightTools(project_root)
    return _tools_instance
