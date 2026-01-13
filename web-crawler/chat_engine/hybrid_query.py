"""
混合查询引擎

架构:
用户问题
    │
    ├─→ [结构化查询] Text-to-SQL → MySQL (商品价格、历史数据)
    │       ↓
    │   直接执行 SQL，快速返回
    │
    └─→ [非结构化查询] RAG/摘要 → MongoDB (新闻、热搜)
            ↓
        语义检索 + LLM 摘要
"""

import os
import json
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml
import google.generativeai as genai

logger = logging.getLogger(__name__)

# ============================================================
# 配置加载
# ============================================================

def _load_config() -> dict:
    """从配置文件加载配置"""
    config_path = Path(__file__).parent.parent / "config" / "database.yaml"
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {}

_CONFIG = _load_config()

# Google AI 配置
_google_config = _CONFIG.get('google_ai', {})
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY") or _google_config.get('api_key', '')
if not GOOGLE_API_KEY:
    logger.warning("GOOGLE_API_KEY 未配置，请设置环境变量或在 config/database.yaml 中配置")
genai.configure(api_key=GOOGLE_API_KEY)

# MongoDB 配置
_mongo_config = _CONFIG.get('mongodb', {})
MONGO_HOST = _mongo_config.get('host', 'localhost')
MONGO_PORT = _mongo_config.get('port', 27017)
MONGO_USERNAME = _mongo_config.get('username', '')
MONGO_PASSWORD = _mongo_config.get('password', '')
MONGO_DATABASE = _mongo_config.get('database', 'trendradar')
MONGO_AUTH_SOURCE = _mongo_config.get('authentication_source', 'admin')


class QueryType(Enum):
    """查询类型"""
    COMMODITY = "commodity"      # 商品查询 → Text-to-SQL
    NEWS = "news"                # 新闻查询 → RAG
    MIXED = "mixed"              # 混合查询
    GENERAL = "general"          # 通用对话


@dataclass
class QueryResult:
    """查询结果"""
    query_type: QueryType
    success: bool
    data: Any
    sql: Optional[str] = None
    error: Optional[str] = None
    execution_time_ms: float = 0


# ============================================================
# MySQL Schema 描述 (供 Text-to-SQL 使用)
# ============================================================

MYSQL_SCHEMA = """
-- 数据库: trendradar (大宗商品数据)

-- 表1: commodity_latest (商品最新快照)
CREATE TABLE commodity_latest (
    id VARCHAR(64) PRIMARY KEY,           -- 商品ID: gold, silver, oil_brent, copper 等
    name VARCHAR(128),                     -- 英文名称
    chinese_name VARCHAR(128),             -- 中文名称: 黄金, 白银, 布伦特原油
    category VARCHAR(64),                  -- 分类: 贵金属, 能源, 工业金属, 农产品
    price DECIMAL(20,6),                   -- 当前价格
    price_unit VARCHAR(32),                -- 货币单位: USD, CNY, USc
    weight_unit VARCHAR(32),               -- 重量单位: 盎司, 吨, 桶
    change_percent DECIMAL(10,4),          -- 涨跌幅(%)
    change_value DECIMAL(20,6),            -- 涨跌值
    high_price DECIMAL(20,6),              -- 当日最高
    low_price DECIMAL(20,6),               -- 当日最低
    as_of_ts DATETIME                      -- 更新时间
);

-- 表2: commodity_history (历史价格)
CREATE TABLE commodity_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    commodity_id VARCHAR(64),              -- 关联 commodity_latest.id
    name VARCHAR(128),
    chinese_name VARCHAR(128),
    category VARCHAR(64),
    price DECIMAL(20,6),
    price_unit VARCHAR(32),
    change_percent DECIMAL(10,4),
    record_date DATE,                      -- 记录日期
    version_ts DATETIME                    -- 数据版本时间
);

-- 表3: change_log (价格变更日志)
CREATE TABLE change_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    commodity_id VARCHAR(64),
    change_type ENUM('INSERT','UPDATE','DELETE'),
    field_name VARCHAR(64),                -- 变更字段: price, change_percent
    old_value TEXT,
    new_value TEXT,
    change_summary VARCHAR(256),           -- 变更描述
    version_ts DATETIME,
    created_at DATETIME
);

-- 常用商品ID映射:
-- 贵金属: gold(黄金), silver(白银), platinum(铂金), palladium(钯金)
-- 能源: oil_brent(布伦特原油), oil_wti(WTI原油), natural_gas(天然气)
-- 工业金属: copper(铜), aluminum(铝), zinc(锌), nickel(镍), lead(铅), tin(锡)
-- 农产品: corn(玉米), wheat(小麦), soybeans(大豆), cotton(棉花), sugar(糖), coffee(咖啡)
"""

# ============================================================
# Text-to-SQL 提示词
# ============================================================

TEXT_TO_SQL_PROMPT = """你是一个 MySQL 查询专家。根据用户问题生成 SQL 查询。

{schema}

规则:
1. 只生成 SELECT 查询，禁止 INSERT/UPDATE/DELETE
2. 使用中文名称搜索时用 chinese_name LIKE '%关键词%'
3. 价格比较用 price 字段
4. 涨跌幅用 change_percent 字段 (正数为涨，负数为跌)
5. 分类查询用 category = '贵金属'/'能源'/'工业金属'/'农产品'/'塑料'
6. 历史数据查询用 commodity_history 表
7. 最新价格用 commodity_latest 表
8. **必须只返回 SQL 语句，不要任何解释或说明**
9. 如果问题不够明确，尽可能生成一个合理的查询

同环比计算规则:
- 月环比: 本月与上月比较，公式 = (本月均价 - 上月均价) / 上月均价 * 100
- 同比: 本月与去年同月比较，公式 = (本月均价 - 去年同月均价) / 去年同月均价 * 100
- 使用 AVG(price) 计算月度均价
- 使用 DATE_FORMAT(record_date, '%Y-%m') 按月分组
- 用 LAG() 窗口函数获取上期数据进行比较

商品名称映射:
- "金"、"金价"、"黄金" -> chinese_name LIKE '%黄金%' OR chinese_name LIKE '%Gold%'
- "银"、"银价"、"白银" -> chinese_name LIKE '%白银%' OR chinese_name LIKE '%Silver%'
- "油"、"油价"、"原油" -> chinese_name LIKE '%原油%' OR chinese_name LIKE '%Oil%'
- "ABS"、"abs" -> chinese_name LIKE '%ABS%'
- "PE"、"PP"、"PS" -> chinese_name LIKE '%PE%' / '%PP%' / '%PS%'
- "华东"、"华南"、"华北" -> chinese_name LIKE '%华东%' / '%华南%' / '%华北%'
- "塑料" -> category = '塑料'

用户问题: {question}

SQL:"""

# ============================================================
# 意图识别提示词
# ============================================================

INTENT_CLASSIFICATION_PROMPT = """判断用户问题的查询类型。

类型:
- commodity: 大宗商品相关 (价格、涨跌、贵金属、能源、原油、黄金、白银等)
- news: 新闻热搜相关 (热搜、新闻、话题、讨论、微博、知乎、百度等)
- mixed: 同时涉及商品和新闻
- general: 通用对话 (问候、闲聊、无关问题)

只返回类型名称，不要解释。

用户问题: {question}

类型:"""

# ============================================================
# 意图识别器
# ============================================================

class IntentClassifier:
    """意图识别器"""

    # 商品关键词
    COMMODITY_KEYWORDS = {
        # 贵金属
        '黄金', '白银', '铂金', '钯金', '金', '银', '铂', '钯',
        '金价', '银价', 'gold', 'silver', 'platinum', 'palladium',
        # 能源
        '原油', 'WTI', '布伦特', '天然气', '油', '油价', 'oil', 'gas',
        # 工业金属
        '铜', '铝', '锌', '镍', '铅', '锡',
        '铜价', '铝价', '锌价', '镍价', 'copper', 'aluminum', 'zinc', 'nickel',
        # 农产品
        '玉米', '小麦', '大豆', '棉花', '糖', '咖啡', '可可', '大米',
        # 塑料类
        'ABS', 'abs', 'PE', 'pe', 'PP', 'pp', 'PS', 'ps',
        'GPPS', 'gpps', 'HIPS', 'hips', '塑料',
        # 区域标识
        '华东', '华南', '华北', '华中', '西南', '西北', '东北',
        # 分类词
        '贵金属', '能源', '工业金属', '农产品', '商品',
        # 价格相关
        '价格', '涨跌', '行情', '期货', '现货', '多少钱', '报价',
        # 分析词
        '走势', '趋势', '分析', '同比', '环比', '月度', '季度', '年度', '对比', '增长'
    }

    # 商品强信号词 - 有这些词时优先识别为 COMMODITY
    COMMODITY_STRONG_SIGNALS = {
        '价格', '多少钱', '行情', '报价', '期货', '现货',
        '黄金', '白银', '原油', '铜', '铝', '锌', '镍',
        '贵金属', '能源', '工业金属', '农产品',
        # 简称和"X价"格式
        '金价', '银价', '油价', '铜价', '铝价', '锌价', '镍价',
        # 塑料类
        'ABS', 'abs', 'PE', 'pe', 'PP', 'pp', '塑料',
        # 区域标识
        '华东', '华南', '华北',
        # 分析词
        '同比', '环比', '增长'
    }

    # 新闻/话题关键词
    NEWS_KEYWORDS = {
        '热搜', '新闻', '话题', '讨论', '微博', '知乎', '百度', '头条',
        '抖音', 'B站', '热点', '热门', '最新', '今天', '昨天', '最近',
        '发生', '事件', '舆情', '舆论', '关注', '动态', '变化', '热度',
        # 科技/AI 话题
        'AI', '人工智能', 'ChatGPT', '大模型', 'GPT', 'OpenAI', 'Claude',
        '科技', '互联网', '数码', '手机', '苹果', '华为', '小米'
    }

    # 纯新闻类关键词 - 只有这些词时才归为 NEWS
    NEWS_ONLY_PATTERNS = {'热搜', '热点', '讨论', '舆情', '热度', '动态', '新闻', '话题'}
    
    def __init__(self, use_llm: bool = False):
        """
        Args:
            use_llm: 是否使用 LLM 进行意图识别 (更准确但更慢)
        """
        self.use_llm = use_llm
        if use_llm:
            self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    def classify(self, question: str) -> QueryType:
        """识别查询意图"""
        if self.use_llm:
            return self._classify_with_llm(question)
        return self._classify_with_rules(question)
    
    def _classify_with_rules(self, question: str) -> QueryType:
        """基于规则的快速分类 - 优化版"""
        question_lower = question.lower()

        # 检查商品强信号词 (有这些词时优先归为 COMMODITY)
        has_commodity_strong = any(
            kw in question for kw in self.COMMODITY_STRONG_SIGNALS
        )

        # 纯话题类关键词 (无商品词时才归为 NEWS)
        has_news_only = any(p in question for p in self.NEWS_ONLY_PATTERNS)

        # 中英文都做大小写无关匹配
        has_commodity = any(
            kw in question or kw.lower() in question_lower
            for kw in self.COMMODITY_KEYWORDS
        )
        has_news = any(
            kw in question or kw.lower() in question_lower
            for kw in self.NEWS_KEYWORDS
        )

        # 检查是否有明确的新闻请求词 (如 "新闻", "热搜", "话题")
        has_explicit_news = any(
            kw in question for kw in {'新闻', '热搜', '话题', '舆情', '动态'}
        )

        # 分类优先级:
        # 1. 同时有商品词和明确新闻词 -> MIXED
        if has_commodity_strong and has_explicit_news:
            logger.debug(f"[IntentClassifier] 同时包含商品和新闻词,归类为 MIXED")
            return QueryType.MIXED

        # 2. 有商品强信号词 -> COMMODITY
        if has_commodity_strong:
            logger.debug(f"[IntentClassifier] 检测到商品强信号词,归类为 COMMODITY")
            return QueryType.COMMODITY

        # 3. 纯话题查询且无商品词 -> NEWS
        if has_news_only and not has_commodity:
            return QueryType.NEWS

        # 4. 有商品词和明确新闻词 -> MIXED
        if has_commodity and has_explicit_news:
            logger.debug(f"[IntentClassifier] 同时包含商品和新闻词,归类为 MIXED")
            return QueryType.MIXED

        # 5. 有商品词 (不管是否有新闻词) -> COMMODITY
        #    因为 "黄金走势分析" 应该是商品查询
        if has_commodity:
            return QueryType.COMMODITY

        # 6. 只有新闻词 -> NEWS
        if has_news:
            return QueryType.NEWS

        # 7. 默认归为 GENERAL
        return QueryType.GENERAL
    
    def _classify_with_llm(self, question: str) -> QueryType:
        """使用 LLM 分类"""
        try:
            prompt = INTENT_CLASSIFICATION_PROMPT.format(question=question)
            response = self.model.generate_content(prompt)
            result = response.text.strip().lower()
            
            if 'commodity' in result:
                return QueryType.COMMODITY
            elif 'news' in result:
                return QueryType.NEWS
            elif 'mixed' in result:
                return QueryType.MIXED
            else:
                return QueryType.GENERAL
        except Exception as e:
            logger.warning(f"LLM 分类失败: {e}")
            return self._classify_with_rules(question)


# ============================================================
# Text-to-SQL 引擎
# ============================================================

class TextToSQLEngine:
    """Text-to-SQL 引擎"""
    
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        self._init_mysql()
    
    def _init_mysql(self):
        """初始化 MySQL 连接"""
        try:
            from database.mysql.connection import get_cursor, test_connection
            self.get_cursor = get_cursor

            # 测试连接是否真正可用
            if test_connection():
                self.available = True
                self.last_error = None
                logger.info("[TextToSQLEngine] MySQL 连接初始化成功")
            else:
                self.available = False
                self.last_error = "MySQL 连接测试失败"
                logger.error("[TextToSQLEngine] MySQL 连接测试失败")
        except Exception as e:
            logger.error(f"[TextToSQLEngine] MySQL 初始化失败: {e}")
            self.available = False
            self.last_error = str(e)
    
    def generate_sql(self, question: str) -> str:
        """生成 SQL 查询"""
        prompt = TEXT_TO_SQL_PROMPT.format(
            schema=MYSQL_SCHEMA,
            question=question
        )

        response = self.model.generate_content(prompt)
        sql = response.text.strip()

        # 清理 SQL (移除 markdown 代码块)
        sql = re.sub(r'^```sql\s*', '', sql)
        sql = re.sub(r'^```\s*', '', sql)
        sql = re.sub(r'\s*```$', '', sql)
        sql = sql.strip()

        # 验证是否为有效 SQL（而非解释性文本）
        sql_upper = sql.upper()
        if not (sql_upper.startswith('SELECT') or sql_upper.startswith('WITH')):
            # LLM 返回了解释性文本而非 SQL，尝试生成一个通用查询
            logger.warning(f"[TextToSQLEngine] LLM 未返回有效 SQL，尝试生成通用查询")
            # 从问题中提取可能的商品关键词
            keywords = []
            for kw in ['ABS', 'PE', 'PP', 'PS', '华东', '华南', '华北', '黄金', '白银', '原油', '铜']:
                if kw.lower() in question.lower():
                    keywords.append(kw)
            if keywords:
                conditions = " OR ".join([f"chinese_name LIKE '%{kw}%'" for kw in keywords])
                sql = f"SELECT * FROM commodity_latest WHERE {conditions}"
            else:
                sql = "SELECT * FROM commodity_latest LIMIT 10"
        
        return sql
    
    def execute_sql(self, sql: str) -> List[Dict]:
        """执行 SQL 查询"""
        if not self.available:
            raise RuntimeError("MySQL 不可用")

        # 安全检查
        sql_upper = sql.upper().strip()
        # 支持 SELECT 和 WITH...SELECT (CTE) 语法
        if not (sql_upper.startswith('SELECT') or sql_upper.startswith('WITH')):
            raise ValueError("只允许 SELECT 查询")

        # 使用词边界检测危险关键词 (避免误拒绝如 'UPDATED_AT' 字段)
        # 注意: 保留 CREATE 检测，但排除 CTE 中的 AS 关键词
        forbidden = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'TRUNCATE', 'ALTER']
        for word in forbidden:
            # 使用正则词边界匹配，确保是独立关键词
            if re.search(rf'\b{word}\b', sql_upper):
                raise ValueError(f"禁止使用 {word} 语句")

        # 额外检查：确保 WITH 语句包含 SELECT
        if sql_upper.startswith('WITH') and 'SELECT' not in sql_upper:
            raise ValueError("WITH 语句必须包含 SELECT")

        try:
            with self.get_cursor() as cursor:
                cursor.execute(sql)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"[TextToSQLEngine] SQL 执行错误: {e}, SQL: {sql}")
            raise
    
    def query(self, question: str) -> QueryResult:
        """执行完整的 Text-to-SQL 查询"""
        import time
        start = time.time()
        
        try:
            # 生成 SQL
            sql = self.generate_sql(question)
            logger.info(f"生成 SQL: {sql}")
            
            # 执行查询
            results = self.execute_sql(sql)
            
            elapsed = (time.time() - start) * 1000
            
            return QueryResult(
                query_type=QueryType.COMMODITY,
                success=True,
                data=results,
                sql=sql,
                execution_time_ms=elapsed
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.error(f"Text-to-SQL 查询失败: {e}")
            return QueryResult(
                query_type=QueryType.COMMODITY,
                success=False,
                data=None,
                error=str(e),
                execution_time_ms=elapsed
            )


# ============================================================
# 新闻 RAG 引擎
# ============================================================

class NewsRAGEngine:
    """新闻 RAG 引擎"""
    
    def __init__(self):
        self.model = genai.GenerativeModel('gemini-2.0-flash')
        self._init_mongodb()
    
    def _init_mongodb(self):
        """初始化 MongoDB 连接"""
        try:
            from pymongo import MongoClient
            # 从配置构建连接 URI
            if MONGO_USERNAME and MONGO_PASSWORD:
                mongo_uri = f"mongodb://{MONGO_USERNAME}:{MONGO_PASSWORD}@{MONGO_HOST}:{MONGO_PORT}/?authSource={MONGO_AUTH_SOURCE}"
            else:
                mongo_uri = f"mongodb://{MONGO_HOST}:{MONGO_PORT}/"
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            self.db = client[MONGO_DATABASE]
            self.news_coll = self.db['news']
            # 测试连接
            self.db.command("ping")
            self.available = True
            logger.info(f"MongoDB 连接成功: {MONGO_HOST}:{MONGO_PORT}/{MONGO_DATABASE}")
        except Exception as e:
            logger.warning(f"MongoDB 连接失败: {e}")
            self.available = False
    
    def search_news(
        self,
        keywords: List[str] = None,
        limit: int = 20,
        days: int = 7
    ) -> List[Dict]:
        """搜索新闻"""
        if not self.available:
            return []
        
        # 构建查询
        query = {}
        
        # 日期过滤 (使用 $in 匹配最近几天的日期字符串)
        date_list = [
            (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(days)
        ]
        query["crawl_date"] = {"$in": date_list}
        
        # 关键词过滤
        if keywords:
            keyword_regex = "|".join(keywords)
            query["title"] = {"$regex": keyword_regex, "$options": "i"}
        
        # 执行查询
        cursor = self.news_coll.find(query).sort("weight_score", -1).limit(limit)
        
        results = []
        for doc in cursor:
            results.append({
                "title": doc.get("title", ""),
                "platform": doc.get("platform_id", "unknown"),
                "rank": doc.get("current_rank", 0),
                "weight": doc.get("weight_score", 0),
                "crawl_date": doc.get("crawl_date", "")
            })
        
        # 如果日期过滤无结果，尝试无日期过滤
        if not results:
            cursor = self.news_coll.find({}).sort("weight_score", -1).limit(limit)
            for doc in cursor:
                results.append({
                    "title": doc.get("title", ""),
                    "platform": doc.get("platform_id", "unknown"),
                    "rank": doc.get("current_rank", 0),
                    "weight": doc.get("weight_score", 0),
                    "crawl_date": doc.get("crawl_date", "")
                })
        
        return results
    
    def extract_keywords(self, question: str) -> List[str]:
        """从问题中提取关键词 (支持中文分词)"""
        stop_words = {
            '的', '是', '有', '什么', '哪些', '最近', '今天', '昨天',
            '吗', '呢', '啊', '了', '在', '和', '与', '一下', '请', '帮',
            '我', '你', '他', '她', '它', '这', '那', '怎么', '如何', '分析'
        }

        # 尝试使用 jieba 分词
        try:
            import jieba
            words = jieba.lcut(question)
        except ImportError:
            # 降级: 使用正则提取中文和英文词
            words = re.findall(r'[\u4e00-\u9fa5]+|[a-zA-Z0-9]+', question)

        # 过滤停用词
        keywords = [w for w in words if w not in stop_words and len(w) >= 2]

        # 保留重要的单字/短词 (如 AI)
        important_short = {'AI', 'GPT'}
        for w in words:
            if w.upper() in important_short and w not in keywords:
                keywords.append(w)

        return list(set(keywords))
    
    def summarize_news(self, news_list: List[Dict], question: str) -> str:
        """生成新闻摘要"""
        if not news_list:
            return "暂无相关新闻数据。"
        
        # 构建上下文
        news_text = "\n".join([
            f"- [{n['platform']}] {n['title']}"
            for n in news_list[:15]
        ])
        
        prompt = f"""根据以下新闻列表回答用户问题。

新闻列表:
{news_text}

用户问题: {question}

要求:
1. 简洁明了，突出关键信息
2. 分类整理相关话题
3. 使用 emoji 增强可读性
4. 如果新闻与问题不相关，如实说明

回答:"""
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"新闻摘要生成失败: {e}")
            return f"找到 {len(news_list)} 条相关新闻，但摘要生成失败。"
    
    def query(self, question: str) -> QueryResult:
        """执行新闻 RAG 查询"""
        import time
        start = time.time()
        
        try:
            # 提取关键词
            keywords = self.extract_keywords(question)
            
            # 搜索新闻
            news_list = self.search_news(keywords=keywords, limit=20, days=7)
            
            # 生成摘要
            summary = self.summarize_news(news_list, question)
            
            elapsed = (time.time() - start) * 1000
            
            return QueryResult(
                query_type=QueryType.NEWS,
                success=True,
                data={
                    "summary": summary,
                    "news_count": len(news_list),
                    "keywords": keywords
                },
                execution_time_ms=elapsed
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            logger.error(f"新闻 RAG 查询失败: {e}")
            return QueryResult(
                query_type=QueryType.NEWS,
                success=False,
                data=None,
                error=str(e),
                execution_time_ms=elapsed
            )


# ============================================================
# 混合查询路由器
# ============================================================

class HybridQueryRouter:
    """混合查询路由器"""
    
    def __init__(self, use_llm_intent: bool = False):
        """
        Args:
            use_llm_intent: 是否使用 LLM 进行意图识别
        """
        self.classifier = IntentClassifier(use_llm=use_llm_intent)
        self.sql_engine = TextToSQLEngine()
        self.rag_engine = NewsRAGEngine()
        self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    def route_and_query(self, question: str) -> Dict:
        """
        路由并执行查询
        
        Returns:
            {
                "query_type": "commodity" | "news" | "mixed" | "general",
                "success": bool,
                "answer": str,
                "data": any,
                "execution_time_ms": float
            }
        """
        import time
        start = time.time()
        
        # 1. 意图识别
        query_type = self.classifier.classify(question)
        logger.info(f"查询类型: {query_type.value}")
        
        # 2. 路由执行
        if query_type == QueryType.COMMODITY:
            result = self._handle_commodity(question)
        elif query_type == QueryType.NEWS:
            result = self._handle_news(question)
        elif query_type == QueryType.MIXED:
            result = self._handle_mixed(question)
        else:
            result = self._handle_general(question)
        
        elapsed = (time.time() - start) * 1000
        result["total_time_ms"] = elapsed
        
        return result
    
    def _handle_commodity(self, question: str) -> Dict:
        """处理商品查询"""
        # 检查 SQL 引擎是否可用，尝试重新初始化
        if not self.sql_engine.available:
            logger.warning("[HybridRouter] SQL 引擎不可用，尝试重新初始化")
            self.sql_engine._init_mysql()
            if not self.sql_engine.available:
                return {
                    "query_type": "commodity",
                    "success": False,
                    "answer": f"数据库连接不可用: {self.sql_engine.last_error or '未知错误'}。请检查 MySQL 服务是否运行。",
                    "data": None,
                    "sql": None,
                    "execution_time_ms": 0
                }

        result = self.sql_engine.query(question)

        if result.success and result.data:
            # 格式化结果
            answer = self._format_commodity_answer(result.data, question)
            return {
                "query_type": "commodity",
                "success": True,
                "answer": answer,
                "data": result.data,
                "sql": result.sql,
                "execution_time_ms": result.execution_time_ms
            }
        elif result.success and not result.data:
            # SQL 执行成功但无数据
            return {
                "query_type": "commodity",
                "success": True,
                "answer": "未找到相关商品数据。请尝试其他商品名称，如：黄金、原油、白银、铜等。",
                "data": [],
                "sql": result.sql,
                "execution_time_ms": result.execution_time_ms
            }
        else:
            # SQL 执行失败
            error_msg = result.error or '查询执行失败'
            return {
                "query_type": "commodity",
                "success": False,
                "answer": f"商品查询失败: {error_msg}",
                "data": None,
                "sql": result.sql,
                "execution_time_ms": result.execution_time_ms
            }
    
    def _handle_news(self, question: str) -> Dict:
        """处理新闻查询"""
        result = self.rag_engine.query(question)
        
        if result.success:
            return {
                "query_type": "news",
                "success": True,
                "answer": result.data["summary"],
                "data": result.data,
                "execution_time_ms": result.execution_time_ms
            }
        else:
            return {
                "query_type": "news",
                "success": False,
                "answer": f"新闻查询失败: {result.error}",
                "data": None,
                "execution_time_ms": result.execution_time_ms
            }
    
    def _handle_mixed(self, question: str) -> Dict:
        """处理混合查询"""
        # 并行执行两种查询
        commodity_result = self.sql_engine.query(question)
        news_result = self.rag_engine.query(question)
        
        # 合并结果
        answers = []
        
        if commodity_result.success and commodity_result.data:
            answers.append("📊 **商品数据**\n" + self._format_commodity_answer(commodity_result.data, question))
        
        if news_result.success and news_result.data:
            answers.append("📰 **相关新闻**\n" + news_result.data["summary"])
        
        return {
            "query_type": "mixed",
            "success": bool(answers),
            "answer": "\n\n".join(answers) if answers else "暂无相关数据",
            "data": {
                "commodity": commodity_result.data,
                "news": news_result.data
            },
            "execution_time_ms": max(commodity_result.execution_time_ms, news_result.execution_time_ms)
        }
    
    def _handle_general(self, question: str) -> Dict:
        """处理通用对话"""
        try:
            response = self.model.generate_content(question)
            return {
                "query_type": "general",
                "success": True,
                "answer": response.text,
                "data": None,
                "execution_time_ms": 0
            }
        except Exception as e:
            return {
                "query_type": "general",
                "success": False,
                "answer": f"对话生成失败: {e}",
                "data": None,
                "execution_time_ms": 0
            }
    
    def _format_commodity_answer(self, data: List[Dict], question: str) -> str:
        """格式化商品查询结果"""
        if not data:
            return "暂无商品数据"

        # 使用 LLM 格式化
        data_text = json.dumps(data[:10], ensure_ascii=False, indent=2, default=str)

        prompt = f"""根据以下商品数据回答用户问题。

数据:
{data_text}

用户问题: {question}

要求:
1. 简洁明了，突出价格和涨跌幅
2. 价格注明单位
3. 涨跌用颜色 emoji: 📈 上涨 📉 下跌 ➡️ 持平
4. 按类别分组展示 (如果多个商品)
5. 如果是同环比数据:
   - 环比和同比必须用百分比格式显示 (如 +5.2%, -3.1%)
   - 如果数据中有 mom_pct (月环比) 或 yoy_pct (同比) 字段，直接使用
   - 如果没有百分比字段但有差值，请用公式计算: (本期-上期)/上期*100
   - 明确标注"环比"和"同比"

回答:"""
        
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            # 降级为简单格式化
            lines = []
            for item in data[:10]:
                name = item.get('chinese_name') or item.get('name', 'Unknown')
                price = item.get('price', 0)
                unit = item.get('price_unit', 'USD')
                change = item.get('change_percent', 0) or 0
                
                emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
                lines.append(f"{emoji} **{name}**: {price} {unit} ({change:+.2f}%)")
            
            return "\n".join(lines)


# ============================================================
# 全局实例
# ============================================================

_router: Optional[HybridQueryRouter] = None


def get_hybrid_router(use_llm_intent: bool = False) -> HybridQueryRouter:
    """获取混合查询路由器实例"""
    global _router
    if _router is None:
        _router = HybridQueryRouter(use_llm_intent=use_llm_intent)
    return _router


def hybrid_query(question: str) -> Dict:
    """
    混合查询入口
    
    Usage:
        from chat_engine.hybrid_query import hybrid_query
        
        result = hybrid_query("黄金现在多少钱？")
        print(result["answer"])
    """
    router = get_hybrid_router()
    return router.route_and_query(question)


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    # 测试用例
    test_questions = [
        "黄金现在多少钱？",
        "原油价格走势怎么样？",
        "最近有什么热门新闻？",
        "知乎上讨论最多的是什么？",
        "铜价和相关新闻",
        "你好"
    ]
    
    router = get_hybrid_router()
    
    for q in test_questions:
        print(f"\n{'='*50}")
        print(f"问题: {q}")
        result = router.route_and_query(q)
        print(f"类型: {result['query_type']}")
        print(f"耗时: {result.get('total_time_ms', 0):.0f}ms")
        print(f"回答:\n{result['answer']}")
