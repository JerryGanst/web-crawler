-- TrendRadar 数据库初始化脚本
-- SQLite 版本

-- 启用外键约束
PRAGMA foreign_keys = ON;

-- 启用 WAL 模式（提高并发性能）
PRAGMA journal_mode = WAL;

-- 设置繁忙超时（毫秒）
PRAGMA busy_timeout = 5000;

-- ============================================
-- 平台表 (先创建，被 news 引用)
-- ============================================
CREATE TABLE IF NOT EXISTS platforms (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    category VARCHAR(20),                   -- finance/news/social/tech
    enabled INTEGER DEFAULT 1,              -- SQLite 用 INTEGER 表示 BOOLEAN
    api_type VARCHAR(50) DEFAULT 'newsnow', -- API 类型
    crawl_interval_ms INTEGER DEFAULT 1000, -- 爬取间隔(毫秒)
    max_retries INTEGER DEFAULT 3,          -- 最大重试次数
    last_crawled_at DATETIME,
    total_crawled INTEGER DEFAULT 0,        -- 总爬取数
    success_rate REAL DEFAULT 1.0,          -- 成功率
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- 新闻表 (核心表)
-- ============================================
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_id VARCHAR(50) NOT NULL,       -- 平台ID: zhihu, weibo等
    title TEXT NOT NULL,                    -- 标题
    title_hash VARCHAR(64),                 -- 标题MD5哈希（去重用）
    url TEXT,                               -- 原文链接
    mobile_url TEXT,                        -- 移动端链接
    
    -- 排名信息
    current_rank INTEGER,                   -- 当前排名
    ranks_history TEXT,                     -- 历史排名 JSON: [1,2,3]
    hot_value INTEGER,                      -- 热度值
    
    -- 时间信息
    first_seen_at DATETIME,                 -- 首次出现时间
    last_seen_at DATETIME,                  -- 最后出现时间
    crawled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    crawl_date VARCHAR(10),                 -- 爬取日期 YYYY-MM-DD（索引优化）
    published_at DATETIME,                  -- 发布时间（如有）
    
    -- 统计信息
    appearance_count INTEGER DEFAULT 1,     -- 出现次数
    weight_score REAL DEFAULT 0,            -- 权重分数
    
    -- 分类和扩展
    category VARCHAR(20),                   -- finance/news/social/tech
    extra_data TEXT,                        -- JSON 扩展字段
    
    -- 外键
    FOREIGN KEY (platform_id) REFERENCES platforms(id) ON DELETE CASCADE,
    
    -- 唯一约束：同平台同日同标题哈希
    UNIQUE(platform_id, title_hash, crawl_date)
);

-- ============================================
-- 关键词匹配记录
-- ============================================
CREATE TABLE IF NOT EXISTS keyword_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id INTEGER NOT NULL,
    keyword_group VARCHAR(200),             -- 匹配的关键词组
    keywords_matched TEXT,                  -- JSON: ["AI", "人工智能"]
    matched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    -- 冗余字段（避免 JOIN）
    title TEXT,
    platform_id VARCHAR(50),
    crawl_date VARCHAR(10),
    
    FOREIGN KEY (news_id) REFERENCES news(id) ON DELETE CASCADE
);

-- ============================================
-- 爬取任务日志
-- ============================================
CREATE TABLE IF NOT EXISTS crawl_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id VARCHAR(50) NOT NULL,           -- 任务UUID
    
    -- 执行信息
    started_at DATETIME NOT NULL,
    finished_at DATETIME,
    duration_ms INTEGER,                    -- 执行时长(毫秒)
    
    -- 结果统计
    platforms_crawled TEXT,                 -- JSON: ["zhihu", "weibo"]
    total_news INTEGER DEFAULT 0,
    new_news INTEGER DEFAULT 0,
    failed_platforms TEXT,                  -- JSON: ["toutiao"]
    
    -- 状态
    status VARCHAR(20) NOT NULL,            -- pending/running/success/partial/failed
    error_message TEXT,
    
    -- 详细日志
    platform_results TEXT                   -- JSON 数组
);

-- ============================================
-- 推送记录
-- ============================================
CREATE TABLE IF NOT EXISTS push_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- 推送信息
    channel VARCHAR(20) NOT NULL,           -- feishu/dingtalk/wework/telegram/email/ntfy/bark
    report_type VARCHAR(50),                -- 当日汇总/实时增量
    
    -- 状态
    status VARCHAR(20) NOT NULL,            -- pending/success/failed/partial
    error_message TEXT,
    
    -- 内容摘要
    news_count INTEGER DEFAULT 0,
    keyword_groups TEXT,                    -- JSON: ["AI", "比特币"]
    message_batches INTEGER DEFAULT 1,
    message_hash VARCHAR(64),               -- 消息哈希（去重用）
    
    -- 时间
    pushed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    push_date VARCHAR(10)                   -- 推送日期（用于每日一推检查）
);

-- ============================================
-- 分析缓存表
-- ============================================
CREATE TABLE IF NOT EXISTS analytics_cache (
    cache_key VARCHAR(200) PRIMARY KEY,     -- 缓存键
    cache_type VARCHAR(50),                 -- trend/platform/keyword
    
    -- 缓存内容
    result TEXT NOT NULL,                   -- JSON 结果
    
    -- TTL
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL            -- 过期时间
);

-- ============================================
-- 索引优化
-- ============================================

-- 新闻表索引
CREATE INDEX IF NOT EXISTS idx_news_platform_date ON news(platform_id, crawl_date);
CREATE INDEX IF NOT EXISTS idx_news_platform_category_date ON news(platform_id, category, crawl_date DESC);
CREATE INDEX IF NOT EXISTS idx_news_crawl_date ON news(crawl_date DESC);
CREATE INDEX IF NOT EXISTS idx_news_category ON news(category);
CREATE INDEX IF NOT EXISTS idx_news_title_hash ON news(title_hash);
CREATE INDEX IF NOT EXISTS idx_news_weight ON news(weight_score DESC);

-- 关键词匹配索引
CREATE INDEX IF NOT EXISTS idx_keyword_matches_news_id ON keyword_matches(news_id);
CREATE INDEX IF NOT EXISTS idx_keyword_matches_keyword ON keyword_matches(keyword_group);
CREATE INDEX IF NOT EXISTS idx_keyword_matches_date ON keyword_matches(crawl_date DESC);

-- 爬取日志索引
CREATE INDEX IF NOT EXISTS idx_crawl_logs_started_at ON crawl_logs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_crawl_logs_status ON crawl_logs(status, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_crawl_logs_task_id ON crawl_logs(task_id);

-- 推送记录索引
CREATE INDEX IF NOT EXISTS idx_push_records_channel_date ON push_records(channel, push_date);
CREATE INDEX IF NOT EXISTS idx_push_records_pushed_at ON push_records(pushed_at DESC);

-- 分析缓存索引（TTL 清理用）
CREATE INDEX IF NOT EXISTS idx_analytics_cache_expires ON analytics_cache(expires_at);

-- ============================================
-- 触发器：自动更新 updated_at
-- ============================================
CREATE TRIGGER IF NOT EXISTS platforms_updated_at
    AFTER UPDATE ON platforms
    FOR EACH ROW
BEGIN
    UPDATE platforms SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
