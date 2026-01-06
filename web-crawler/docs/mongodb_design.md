# TrendRadar MongoDB 数据库设计方案

## 一、为什么选择 MongoDB

### 优势
| 特性 | MongoDB | SQLite |
|------|---------|--------|
| **数据模型** | 文档型，灵活 Schema | 关系型，固定 Schema |
| **扩展性** | 水平扩展，支持分片 | 单机限制 |
| **JSON 原生** | 原生支持，无需转换 | 需要序列化 |
| **全文搜索** | 内置支持 | 需要扩展 |
| **聚合分析** | 强大的聚合管道 | 基础 SQL |
| **地理空间** | 原生支持 | 不支持 |

### 适用场景
- ✅ 新闻数据结构灵活（不同平台字段差异大）
- ✅ 需要高效的全文搜索
- ✅ 时序数据聚合分析
- ✅ 可能的分布式部署需求

---

## 二、集合设计 (Collections)

### 2.1 news（新闻主表）
```javascript
{
  _id: ObjectId("..."),
  
  // 基础信息
  platform_id: "zhihu",           // 平台ID
  platform_name: "知乎",          // 平台名称
  category: "social",             // 分类: finance/news/social/tech
  
  // 内容信息
  title: "新闻标题...",           // 标题
  title_hash: "md5_hash",         // 标题哈希（去重用）
  url: "https://...",             // 原文链接
  mobile_url: "https://...",      // 移动端链接
  
  // 排名信息
  ranks: [1, 2, 3],               // 历史排名记录
  current_rank: 1,                // 当前排名
  hot_value: 12345,               // 热度值（如有）
  
  // 时间信息
  first_seen_at: ISODate("..."),  // 首次出现时间
  last_seen_at: ISODate("..."),   // 最后出现时间
  crawled_at: ISODate("..."),     // 爬取时间
  published_at: ISODate("..."),   // 发布时间（如有）
  
  // 统计信息
  appearance_count: 5,            // 出现次数
  weight_score: 85.6,             // 权重分数
  
  // 扩展字段
  extra: {
    author: "作者名",
    comments: 1234,
    likes: 5678
  },
  
  // 关键词匹配
  matched_keywords: ["AI", "人工智能"],
  
  // 索引辅助字段
  date_key: "2025-12-02",         // 日期键（分区用）
  hour_key: "2025-12-02-10"       // 小时键（细粒度查询）
}
```

**索引设计：**
```javascript
// 复合索引 - 平台+日期查询
db.news.createIndex({ platform_id: 1, date_key: 1 })

// 复合索引 - 分类+时间范围
db.news.createIndex({ category: 1, crawled_at: -1 })

// 唯一索引 - 去重
db.news.createIndex({ platform_id: 1, title_hash: 1, date_key: 1 }, { unique: true })

// 全文索引 - 搜索
db.news.createIndex({ title: "text" }, { default_language: "none" })

// TTL 索引 - 自动清理（可选，30天后删除）
db.news.createIndex({ crawled_at: 1 }, { expireAfterSeconds: 2592000 })
```

---

### 2.2 platforms（平台配置表）
```javascript
{
  _id: "zhihu",                    // 平台ID
  name: "知乎",                    // 显示名称
  category: "social",              // 分类
  enabled: true,                   // 是否启用
  
  // 爬取配置
  crawl_config: {
    api_type: "newsnow",           // API类型
    interval_ms: 1000,             // 爬取间隔
    max_retries: 3,                // 最大重试
    timeout_ms: 10000              // 超时时间
  },
  
  // 统计信息
  stats: {
    total_crawled: 12345,          // 总爬取数
    last_crawled_at: ISODate("..."),
    avg_news_per_crawl: 25,
    success_rate: 0.98
  },
  
  created_at: ISODate("..."),
  updated_at: ISODate("...")
}
```

---

### 2.3 crawl_logs（爬取日志表）
```javascript
{
  _id: ObjectId("..."),
  task_id: "uuid-...",             // 任务ID
  
  // 执行信息
  started_at: ISODate("..."),
  finished_at: ISODate("..."),
  duration_ms: 12345,
  
  // 结果统计
  platforms_crawled: ["zhihu", "weibo", "douyin"],
  total_news: 150,
  new_news: 45,
  failed_platforms: ["toutiao"],
  
  // 状态
  status: "success",               // success/partial/failed
  error_message: null,
  
  // 详细日志
  platform_results: [
    {
      platform_id: "zhihu",
      status: "success",
      news_count: 50,
      new_count: 15,
      duration_ms: 2345
    }
  ]
}
```

---

### 2.4 keyword_matches（关键词匹配记录）
```javascript
{
  _id: ObjectId("..."),
  news_id: ObjectId("..."),        // 关联新闻
  keyword_group: "AI 人工智能",    // 匹配的关键词组
  keywords_matched: ["AI", "人工智能"],
  matched_at: ISODate("..."),
  
  // 冗余字段（避免 JOIN）
  title: "新闻标题...",
  platform_id: "zhihu",
  date_key: "2025-12-02"
}
```

**索引：**
```javascript
db.keyword_matches.createIndex({ keyword_group: 1, date_key: -1 })
db.keyword_matches.createIndex({ news_id: 1 })
```

---

### 2.5 push_records（推送记录表）
```javascript
{
  _id: ObjectId("..."),
  
  // 推送信息
  channel: "feishu",               // feishu/dingtalk/wework/telegram/email
  report_type: "当日汇总",
  
  // 状态
  status: "success",               // success/failed/partial
  error_message: null,
  
  // 内容摘要
  news_count: 50,
  keyword_groups: ["AI", "比特币"],
  message_batches: 3,
  
  // 时间
  pushed_at: ISODate("..."),
  
  // 日期键（用于每日一推检查）
  date_key: "2025-12-02"
}
```

**索引：**
```javascript
db.push_records.createIndex({ channel: 1, date_key: 1 })
db.push_records.createIndex({ pushed_at: -1 })
```

---

### 2.6 analytics_cache（分析缓存表）
```javascript
{
  _id: "trend_AI_2025-12-02",      // 自定义键
  cache_type: "trend_analysis",
  
  // 缓存内容
  topic: "AI",
  date_range: {
    start: "2025-11-26",
    end: "2025-12-02"
  },
  result: { /* 分析结果 */ },
  
  // TTL
  created_at: ISODate("..."),
  expires_at: ISODate("...")       // 缓存过期时间
}
```

**TTL 索引：**
```javascript
db.analytics_cache.createIndex({ expires_at: 1 }, { expireAfterSeconds: 0 })
```

---

## 三、常用查询模式

### 3.1 获取最新新闻
```javascript
db.news.find({
  date_key: "2025-12-02",
  category: "finance"
})
.sort({ crawled_at: -1 })
.limit(50)
```

### 3.2 热点趋势聚合
```javascript
db.news.aggregate([
  { $match: { 
    title: { $regex: "AI", $options: "i" },
    crawled_at: { $gte: ISODate("2025-11-26"), $lte: ISODate("2025-12-02") }
  }},
  { $group: {
    _id: "$date_key",
    count: { $sum: 1 },
    avg_rank: { $avg: "$current_rank" }
  }},
  { $sort: { _id: 1 }}
])
```

### 3.3 平台对比
```javascript
db.news.aggregate([
  { $match: { date_key: "2025-12-02" }},
  { $group: {
    _id: "$platform_id",
    total: { $sum: 1 },
    unique_titles: { $addToSet: "$title_hash" }
  }},
  { $project: {
    platform: "$_id",
    total: 1,
    unique_count: { $size: "$unique_titles" }
  }}
])
```

---

## 四、数据迁移策略

### Phase 1: 双写期
- 保留文件存储
- 同时写入 MongoDB
- 验证数据一致性

### Phase 2: 读切换
- 读取优先 MongoDB
- 文件作为备份

### Phase 3: 完全迁移
- 停止文件写入
- 历史数据批量导入
- 清理旧文件（保留备份）

---

## 五、Python 依赖

```toml
# pyproject.toml 新增
dependencies = [
    # ... 现有依赖
    "motor>=3.3.0",           # 异步 MongoDB 驱动
    "pymongo>=4.6.0",         # 同步 MongoDB 驱动
    "beanie>=1.25.0",         # ODM（可选，类似 ORM）
]
```

---

## 六、代码结构建议

```
database/
├── __init__.py
├── connection.py         # MongoDB 连接管理
├── models/
│   ├── __init__.py
│   ├── news.py           # News 模型
│   ├── platform.py       # Platform 模型
│   └── crawl_log.py      # CrawlLog 模型
├── repositories/
│   ├── __init__.py
│   ├── news_repo.py      # 新闻数据操作
│   ├── platform_repo.py  # 平台配置操作
│   └── analytics_repo.py # 分析数据操作
└── migrations/
    └── init_indexes.py   # 初始化索引脚本
```

---

## 七、部署选项

| 选项 | 适用场景 | 成本 |
|------|----------|------|
| **MongoDB Atlas (M0)** | 开发/小规模 | 免费 |
| **MongoDB Atlas (M10+)** | 生产环境 | $57+/月 |
| **自托管 Docker** | 个人服务器 | 服务器成本 |
| **本地开发** | 开发测试 | 免费 |

### Docker 部署示例
```yaml
# docker-compose.yml
services:
  mongodb:
    image: mongo:7.0
    ports:
      - "27017:27017"
    volumes:
      - mongodb_data:/data/db
    environment:
      MONGO_INITDB_ROOT_USERNAME: trendradar
      MONGO_INITDB_ROOT_PASSWORD: your_password

volumes:
  mongodb_data:
```
