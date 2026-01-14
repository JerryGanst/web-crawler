# coding=utf-8
"""
数据模型定义
使用 dataclass 定义数据结构，便于类型检查和序列化
"""

import json
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any


@dataclass
class News:
    """新闻数据模型"""
    
    platform_id: str
    title: str
    url: str = ""
    mobile_url: str = ""
    current_rank: int = 0
    ranks_history: List[int] = field(default_factory=list)
    hot_value: int = 0
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    crawled_at: Optional[datetime] = None
    crawl_date: str = ""
    published_at: Optional[datetime] = None
    appearance_count: int = 1
    weight_score: float = 0.0
    category: str = ""
    extra_data: Dict[str, Any] = field(default_factory=dict)
    id: Optional[int] = None
    
    # 新增字段：数据来源（如 newsnow, jin10 等）
    source: str = ""
    # 新增字段：平台名称（如 金十数据, 财联社深度 等）
    platform_name: str = ""
    # 新增字段：摘要/内容片段
    summary: str = ""
    
    def __post_init__(self):
        if self.crawled_at is None:
            self.crawled_at = datetime.now()
        if not self.crawl_date and self.crawled_at:
            self.crawl_date = self.crawled_at.strftime("%Y-%m-%d")
        if self.first_seen_at is None:
            self.first_seen_at = self.crawled_at
        if self.last_seen_at is None:
            self.last_seen_at = self.crawled_at
            
        # 尝试从 extra_data 自动填充 source 和 platform_name
        if not self.source and self.extra_data:
            self.source = self.extra_data.get('source', '')
        if not self.platform_name and self.extra_data:
            self.platform_name = self.extra_data.get('platform_name', '')
    
    @property
    def title_hash(self) -> str:
        """
        生成规范化的标题哈希

        规范化步骤：
        1. 去除首尾空格
        2. 合并连续空白字符为单个空格
        3. 移除常见干扰符号（引号、括号等）

        这样可以避免因空格/标点差异导致的重复存储
        """
        import re
        # 1. 去除首尾空格
        normalized = self.title.strip()
        # 2. 合并连续空白字符
        normalized = re.sub(r'\s+', ' ', normalized)
        # 3. 移除干扰符号（保守处理，只移除常见的）
        normalized = re.sub(r'[【】\[\]「」『』""''《》<>]', '', normalized)
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()
    
    @property
    def ranks_json(self) -> str:
        """排名历史的 JSON 字符串"""
        return json.dumps(self.ranks_history)
    
    @property
    def extra_json(self) -> str:
        """扩展数据的 JSON 字符串"""
        return json.dumps(self.extra_data, ensure_ascii=False)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    def to_db_tuple(self) -> tuple:
        """转换为数据库插入元组"""
        return (
            self.platform_id,
            self.title,
            self.title_hash,
            self.url,
            self.mobile_url,
            self.current_rank,
            self.ranks_json,
            self.hot_value,
            self.first_seen_at.isoformat() if self.first_seen_at else None,
            self.last_seen_at.isoformat() if self.last_seen_at else None,
            self.crawled_at.isoformat() if self.crawled_at else None,
            self.crawl_date,
            self.published_at.isoformat() if self.published_at else None,
            self.appearance_count,
            self.weight_score,
            self.category,
            self.extra_json,
            # 新增字段的数据库映射 (注意：如果使用MySQL，表结构也需要更新；MongoDB则直接支持)
            self.source,
            self.platform_name,
            self.summary
        )
    
    @classmethod
    def from_db_row(cls, row) -> 'News':
        """从数据库行创建实例"""
        # 兼容旧表结构，如果行中没有新字段，提供默认值
        return cls(
            id=row['id'],
            platform_id=row['platform_id'],
            title=row['title'],
            url=row['url'] or "",
            mobile_url=row['mobile_url'] or "",
            current_rank=row['current_rank'] or 0,
            ranks_history=json.loads(row['ranks_history']) if row['ranks_history'] else [],
            hot_value=row['hot_value'] or 0,
            first_seen_at=datetime.fromisoformat(row['first_seen_at']) if row['first_seen_at'] else None,
            last_seen_at=datetime.fromisoformat(row['last_seen_at']) if row['last_seen_at'] else None,
            crawled_at=datetime.fromisoformat(row['crawled_at']) if row['crawled_at'] else None,
            crawl_date=row['crawl_date'] or "",
            published_at=datetime.fromisoformat(row['published_at']) if row.get('published_at') else None,
            appearance_count=row['appearance_count'] or 1,
            weight_score=row['weight_score'] or 0.0,
            category=row['category'] or "",
            extra_data=json.loads(row['extra_data']) if row['extra_data'] else {},
            # 安全读取新字段
            source=row.get('source', ''),
            platform_name=row.get('platform_name', ''),
            summary=row.get('summary', '')
        )


@dataclass
class Platform:
    """平台配置模型"""
    
    id: str
    name: str
    category: str = ""
    enabled: bool = True
    api_type: str = "newsnow"
    crawl_interval_ms: int = 1000
    max_retries: int = 3
    last_crawled_at: Optional[datetime] = None
    total_crawled: int = 0
    success_rate: float = 1.0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_db_tuple(self) -> tuple:
        """转换为数据库插入元组"""
        return (
            self.id,
            self.name,
            self.category,
            1 if self.enabled else 0,
            self.api_type,
            self.crawl_interval_ms,
            self.max_retries,
            self.last_crawled_at.isoformat() if self.last_crawled_at else None,
            self.total_crawled,
            self.success_rate,
        )
    
    @classmethod
    def from_db_row(cls, row) -> 'Platform':
        """从数据库行创建实例"""
        return cls(
            id=row['id'],
            name=row['name'],
            category=row['category'] or "",
            enabled=bool(row['enabled']),
            api_type=row['api_type'] or "newsnow",
            crawl_interval_ms=row['crawl_interval_ms'] or 1000,
            max_retries=row['max_retries'] or 3,
            last_crawled_at=datetime.fromisoformat(row['last_crawled_at']) if row['last_crawled_at'] else None,
            total_crawled=row['total_crawled'] or 0,
            success_rate=row['success_rate'] or 1.0,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )


@dataclass
class KeywordMatch:
    """关键词匹配记录模型"""
    
    news_id: int
    keyword_group: str
    keywords_matched: List[str] = field(default_factory=list)
    matched_at: Optional[datetime] = None
    title: str = ""
    platform_id: str = ""
    crawl_date: str = ""
    id: Optional[int] = None
    
    def __post_init__(self):
        if self.matched_at is None:
            self.matched_at = datetime.now()
    
    @property
    def keywords_json(self) -> str:
        return json.dumps(self.keywords_matched, ensure_ascii=False)
    
    def to_db_tuple(self) -> tuple:
        return (
            self.news_id,
            self.keyword_group,
            self.keywords_json,
            self.matched_at.isoformat() if self.matched_at else None,
            self.title,
            self.platform_id,
            self.crawl_date,
        )
    
    @classmethod
    def from_db_row(cls, row) -> 'KeywordMatch':
        return cls(
            id=row['id'],
            news_id=row['news_id'],
            keyword_group=row['keyword_group'] or "",
            keywords_matched=json.loads(row['keywords_matched']) if row['keywords_matched'] else [],
            matched_at=datetime.fromisoformat(row['matched_at']) if row['matched_at'] else None,
            title=row['title'] or "",
            platform_id=row['platform_id'] or "",
            crawl_date=row['crawl_date'] or "",
        )


@dataclass
class CrawlLog:
    """爬取任务日志模型"""
    
    task_id: str
    status: str  # pending/running/success/partial/failed
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: int = 0
    platforms_crawled: List[str] = field(default_factory=list)
    total_news: int = 0
    new_news: int = 0
    failed_platforms: List[str] = field(default_factory=list)
    error_message: str = ""
    platform_results: List[Dict] = field(default_factory=list)
    id: Optional[int] = None
    
    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.now()
    
    def to_db_tuple(self) -> tuple:
        return (
            self.task_id,
            self.started_at.isoformat() if self.started_at else None,
            self.finished_at.isoformat() if self.finished_at else None,
            self.duration_ms,
            json.dumps(self.platforms_crawled),
            self.total_news,
            self.new_news,
            json.dumps(self.failed_platforms),
            self.status,
            self.error_message,
            json.dumps(self.platform_results, ensure_ascii=False),
        )
    
    @classmethod
    def from_db_row(cls, row) -> 'CrawlLog':
        return cls(
            id=row['id'],
            task_id=row['task_id'],
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,
            finished_at=datetime.fromisoformat(row['finished_at']) if row['finished_at'] else None,
            duration_ms=row['duration_ms'] or 0,
            platforms_crawled=json.loads(row['platforms_crawled']) if row['platforms_crawled'] else [],
            total_news=row['total_news'] or 0,
            new_news=row['new_news'] or 0,
            failed_platforms=json.loads(row['failed_platforms']) if row['failed_platforms'] else [],
            status=row['status'],
            error_message=row['error_message'] or "",
            platform_results=json.loads(row['platform_results']) if row['platform_results'] else [],
        )


@dataclass
class PushRecord:
    """推送记录模型"""

    channel: str  # feishu/dingtalk/wework/telegram/email/ntfy/bark
    status: str  # pending/success/failed/partial
    report_type: str = ""
    error_message: str = ""
    news_count: int = 0
    keyword_groups: List[str] = field(default_factory=list)
    message_batches: int = 1
    message_hash: str = ""
    pushed_at: Optional[datetime] = None
    push_date: str = ""
    id: Optional[int] = None

    def __post_init__(self):
        if self.pushed_at is None:
            self.pushed_at = datetime.now()
        if not self.push_date and self.pushed_at:
            self.push_date = self.pushed_at.strftime("%Y-%m-%d")

    @property
    def keyword_groups_json(self) -> str:
        return json.dumps(self.keyword_groups, ensure_ascii=False)

    def to_db_tuple(self) -> tuple:
        return (
            self.channel,
            self.report_type,
            self.status,
            self.error_message,
            self.news_count,
            self.keyword_groups_json,
            self.message_batches,
            self.message_hash,
            self.pushed_at.isoformat() if self.pushed_at else None,
            self.push_date,
        )

    @classmethod
    def from_db_row(cls, row) -> 'PushRecord':
        return cls(
            id=row['id'],
            channel=row['channel'],
            report_type=row['report_type'] or "",
            status=row['status'],
            error_message=row['error_message'] or "",
            news_count=row['news_count'] or 0,
            keyword_groups=json.loads(row['keyword_groups']) if row['keyword_groups'] else [],
            message_batches=row['message_batches'] or 1,
            message_hash=row['message_hash'] or "",
            pushed_at=datetime.fromisoformat(row['pushed_at']) if row['pushed_at'] else None,
            push_date=row['push_date'] or "",
        )


# ==================== RSS 数据模型 (TrendRadar v4.0+ 融合) ====================

@dataclass
class RSSFeed:
    """RSS 订阅源配置模型"""

    id: str
    name: str
    url: str
    category: str = ""
    enabled: bool = True
    max_items: int = 20
    last_fetch_at: Optional[datetime] = None
    error_count: int = 0
    last_error: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'RSSFeed':
        """从配置字典创建实例"""
        return cls(
            id=config.get('id', ''),
            name=config.get('name', ''),
            url=config.get('url', ''),
            category=config.get('category', ''),
            enabled=config.get('enabled', True),
            max_items=config.get('max_items', 20),
        )


@dataclass
class RSSItem:
    """RSS 文章数据模型"""

    feed_id: str
    title: str
    url: str = ""
    summary: str = ""
    author: str = ""
    published_at: Optional[datetime] = None
    crawled_at: Optional[datetime] = None
    crawl_date: str = ""
    feed_name: str = ""
    category: str = ""
    tags: List[str] = field(default_factory=list)
    extra_data: Dict[str, Any] = field(default_factory=dict)
    id: Optional[str] = None

    def __post_init__(self):
        if self.crawled_at is None:
            self.crawled_at = datetime.now()
        if not self.crawl_date and self.crawled_at:
            self.crawl_date = self.crawled_at.strftime("%Y-%m-%d")

    @property
    def title_hash(self) -> str:
        """生成标题哈希，用于去重"""
        return hashlib.md5(self.title.encode('utf-8')).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        data = asdict(self)
        # 处理 datetime 字段
        if self.published_at:
            data['published_at'] = self.published_at.isoformat()
        if self.crawled_at:
            data['crawled_at'] = self.crawled_at.isoformat()
        return data

    @classmethod
    def from_mongo_doc(cls, doc: Dict[str, Any]) -> 'RSSItem':
        """从 MongoDB 文档创建实例"""
        published_at = doc.get('published_at')
        crawled_at = doc.get('crawled_at')

        # 处理 datetime 字段
        if isinstance(published_at, str):
            try:
                published_at = datetime.fromisoformat(published_at)
            except:
                published_at = None

        if isinstance(crawled_at, str):
            try:
                crawled_at = datetime.fromisoformat(crawled_at)
            except:
                crawled_at = None

        return cls(
            id=str(doc.get('_id', '')),
            feed_id=doc.get('feed_id', ''),
            title=doc.get('title', ''),
            url=doc.get('url', ''),
            summary=doc.get('summary', ''),
            author=doc.get('author', ''),
            published_at=published_at,
            crawled_at=crawled_at,
            crawl_date=doc.get('crawl_date', ''),
            feed_name=doc.get('feed_name', ''),
            category=doc.get('category', ''),
            tags=doc.get('tags', []),
            extra_data=doc.get('extra_data', {}),
        )
