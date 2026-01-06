## MongoDB 初始化插入数据示例

### 1. platforms 集合

```json
[
  {
    "name": "示例平台A",
    "category": "news",
    "enabled": true,
    "api_type": "http",
    "crawl_interval_ms": 600000,
    "max_retries": 3,
    "last_crawled_at": null,
    "total_crawled": 0,
    "success_rate": 0.0,
    "created_at": "2025-01-01T00:00:00",
    "updated_at": "2025-01-01T00:00:00"
  }
]
```

插入方式（Python）：

```python
from database.connection import get_mongo_database

db = get_mongo_database()
db["platforms"].insert_many([
    {
        "name": "示例平台A",
        "category": "news",
        "enabled": True,
        "api_type": "http",
        "crawl_interval_ms": 600_000,
        "max_retries": 3,
        "last_crawled_at": None,
        "total_crawled": 0,
        "success_rate": 0.0,
        "created_at": "2025-01-01T00:00:00",
        "updated_at": "2025-01-01T00:00:00",
    }
])
```

### 2. news 集合

```json
[
  {
    "platform_id": null,
    "title": "示例新闻标题",
    "title_hash": "示例:使用database.connection.generate_title_hash生成",
    "url": "https://example.com/news/1",
    "category": "macro",
    "content": "示例新闻正文",
    "source": "示例来源",
    "crawl_date": "2025-01-01",
    "published_at": "2025-01-01T08:00:00",
    "weight_score": 0.0,
    "created_at": "2025-01-01T08:00:00",
    "updated_at": "2025-01-01T08:00:00"
  }
]
```

插入方式（Python）：

```python
from database.connection import get_mongo_database, generate_title_hash

db = get_mongo_database()
title = "示例新闻标题"
db["news"].insert_one(
    {
        "platform_id": None,
        "title": title,
        "title_hash": generate_title_hash(title),
        "url": "https://example.com/news/1",
        "category": "macro",
        "content": "示例新闻正文",
        "source": "示例来源",
        "crawl_date": "2025-01-01",
        "published_at": "2025-01-01T08:00:00",
        "weight_score": 0.0,
        "created_at": "2025-01-01T08:00:00",
        "updated_at": "2025-01-01T08:00:00",
    }
)
```

### 3. keyword_matches 集合

```json
[
  {
    "news_id": null,
    "keyword_group": "示例分组",
    "keywords_matched": ["示例", "关键字"],
    "matched_at": "2025-01-01T08:01:00",
    "title": "示例新闻标题",
    "platform_id": null,
    "crawl_date": "2025-01-01"
  }
]
```

插入方式（Python）：

```python
from database.connection import get_mongo_database

db = get_mongo_database()
db["keyword_matches"].insert_one(
    {
        "news_id": None,
        "keyword_group": "示例分组",
        "keywords_matched": ["示例", "关键字"],
        "matched_at": "2025-01-01T08:01:00",
        "title": "示例新闻标题",
        "platform_id": None,
        "crawl_date": "2025-01-01",
    }
)
```

### 4. crawl_logs 集合

```json
[
  {
    "task_id": "example-task-1",
    "started_at": "2025-01-01T08:00:00",
    "finished_at": "2025-01-01T08:05:00",
    "duration_ms": 300000,
    "platforms_crawled": ["示例平台A"],
    "total_news": 1,
    "new_news": 1,
    "failed_platforms": [],
    "status": "success",
    "error_message": null,
    "platform_results": []
  }
]
```

插入方式（Python）：

```python
from database.connection import get_mongo_database

db = get_mongo_database()
db["crawl_logs"].insert_one(
    {
        "task_id": "example-task-1",
        "started_at": "2025-01-01T08:00:00",
        "finished_at": "2025-01-01T08:05:00",
        "duration_ms": 300000,
        "platforms_crawled": ["示例平台A"],
        "total_news": 1,
        "new_news": 1,
        "failed_platforms": [],
        "status": "success",
        "error_message": None,
        "platform_results": [],
    }
)
```

### 5. push_records 集合

```json
[
  {
    "channel": "wecom",
    "report_type": "daily",
    "status": "success",
    "error_message": null,
    "news_count": 1,
    "keyword_groups": ["示例分组"],
    "message_batches": 1,
    "message_hash": "example-message-hash",
    "pushed_at": "2025-01-01T09:00:00",
    "push_date": "2025-01-01"
  }
]
```

插入方式（Python）：

```python
from database.connection import get_mongo_database

db = get_mongo_database()
db["push_records"].insert_one(
    {
        "channel": "wecom",
        "report_type": "daily",
        "status": "success",
        "error_message": None,
        "news_count": 1,
        "keyword_groups": ["示例分组"],
        "message_batches": 1,
        "message_hash": "example-message-hash",
        "pushed_at": "2025-01-01T09:00:00",
        "push_date": "2025-01-01",
    }
)
```

### 6. analytics_cache 集合

```json
[
  {
    "cache_key": "analysis:demo",
    "payload": {
      "summary": "示例分析结果",
      "items": []
    },
    "created_at": "2025-01-01T10:00:00",
    "expires_at": "2025-01-02T10:00:00"
  }
]
```

插入方式（Python）：

```python
from database.connection import get_mongo_database

db = get_mongo_database()
db["analytics_cache"].insert_one(
    {
        "cache_key": "analysis:demo",
        "payload": {
            "summary": "示例分析结果",
            "items": [],
        },
        "created_at": "2025-01-01T10:00:00",
        "expires_at": "2025-01-02T10:00:00",
    }
)
```

