-- ============================================================
-- TrendRadar MySQL 数据库设计
-- 版本: 1.0
-- 说明: 大宗商品数据管道 - 快照/历史/变更日志三表架构
-- ============================================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS trendradar 
    CHARACTER SET utf8mb4 
    COLLATE utf8mb4_unicode_ci;

USE trendradar;

-- ============================================================
-- 1. 快照表: commodity_latest
-- 说明: 仅存放每个商品的最新数据，支持快速查询
-- ============================================================
CREATE TABLE IF NOT EXISTS commodity_latest (
    -- 主键：商品唯一标识 (如 "gold", "silver", "oil_brent")
    id VARCHAR(64) PRIMARY KEY,
    
    -- 业务字段
    name VARCHAR(128) NOT NULL COMMENT '商品名称',
    chinese_name VARCHAR(128) COMMENT '中文名称',
    category VARCHAR(64) COMMENT '分类: 贵金属/能源/工业金属/农产品',
    
    price DECIMAL(20, 6) NOT NULL COMMENT '当前价格',
    price_unit VARCHAR(32) DEFAULT 'USD' COMMENT '价格货币单位',
    weight_unit VARCHAR(32) COMMENT '重量/数量单位: oz/g/桶/吨',
    
    change_percent DECIMAL(10, 4) COMMENT '涨跌幅(%)',
    change_value DECIMAL(20, 6) COMMENT '涨跌值',
    
    high_price DECIMAL(20, 6) COMMENT '当日最高',
    low_price DECIMAL(20, 6) COMMENT '当日最低',
    open_price DECIMAL(20, 6) COMMENT '开盘价',
    
    source VARCHAR(64) COMMENT '数据来源: sina/business_insider/...',
    source_url VARCHAR(512) COMMENT '来源链接',
    
    -- 时间戳
    version_ts DATETIME(3) NOT NULL COMMENT '数据版本时间(来源时间)',
    as_of_ts DATETIME(3) NOT NULL COMMENT '快照更新时间',
    created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
    
    -- 扩展字段 (存放非标准化数据)
    extra_data JSON COMMENT '其他扩展数据',
    
    INDEX idx_category (category),
    INDEX idx_source (source),
    INDEX idx_version_ts (version_ts)
) ENGINE=InnoDB COMMENT='商品最新快照表';


-- ============================================================
-- 2. 历史表: commodity_history
-- 说明: 存放所有历史版本，支持回溯查询
-- ============================================================
CREATE TABLE IF NOT EXISTS commodity_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    
    -- 商品标识
    commodity_id VARCHAR(64) NOT NULL COMMENT '关联 commodity_latest.id',
    
    -- 业务字段快照 (与 latest 表相同)
    name VARCHAR(128) NOT NULL,
    chinese_name VARCHAR(128),
    category VARCHAR(64),
    
    price DECIMAL(20, 6) NOT NULL,
    price_unit VARCHAR(32) DEFAULT 'USD',
    weight_unit VARCHAR(32),
    
    change_percent DECIMAL(10, 4),
    change_value DECIMAL(20, 6),
    
    high_price DECIMAL(20, 6),
    low_price DECIMAL(20, 6),
    open_price DECIMAL(20, 6),
    
    source VARCHAR(64),
    source_url VARCHAR(512),
    
    -- 时间戳
    version_ts DATETIME(3) NOT NULL COMMENT '数据版本时间',
    recorded_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3) COMMENT '入库时间',
    
    -- 批次标识
    request_id VARCHAR(64) NOT NULL COMMENT '采集批次ID',
    
    extra_data JSON,
    
    -- 唯一约束: 同一商品同一版本只存一次 (幂等)
    UNIQUE KEY uk_commodity_version (commodity_id, version_ts),
    
    INDEX idx_commodity_id (commodity_id),
    INDEX idx_version_ts (version_ts),
    INDEX idx_request_id (request_id),
    INDEX idx_recorded_at (recorded_at)
) ENGINE=InnoDB COMMENT='商品历史存档表';


-- ============================================================
-- 3. 变更日志表: change_log
-- 说明: 记录每个字段的变更，供 LLM 消费
-- ============================================================
CREATE TABLE IF NOT EXISTS change_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    
    -- 变更标识
    request_id VARCHAR(64) NOT NULL COMMENT '采集批次ID',
    commodity_id VARCHAR(64) NOT NULL COMMENT '商品ID',
    
    -- 变更类型
    change_type ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL COMMENT '变更类型',
    
    -- 字段级变更
    field_name VARCHAR(64) COMMENT '变更字段名',
    old_value TEXT COMMENT '旧值',
    new_value TEXT COMMENT '新值',
    
    -- 时间
    version_ts DATETIME(3) NOT NULL COMMENT '数据版本时间',
    created_at DATETIME(3) DEFAULT CURRENT_TIMESTAMP(3),
    
    -- 变更摘要 (便于 LLM 快速理解)
    change_summary VARCHAR(256) COMMENT '变更描述，如: 黄金价格从2650上涨至2680',
    
    INDEX idx_request_id (request_id),
    INDEX idx_commodity_id (commodity_id),
    INDEX idx_change_type (change_type),
    INDEX idx_version_ts (version_ts),
    INDEX idx_created_at (created_at),
    INDEX idx_field_name (field_name)
) ENGINE=InnoDB COMMENT='变更日志表';


-- ============================================================
-- 4. 采集批次表: crawl_batch
-- 说明: 记录每次采集的元信息
-- ============================================================
CREATE TABLE IF NOT EXISTS crawl_batch (
    request_id VARCHAR(64) PRIMARY KEY COMMENT '批次ID',
    
    source VARCHAR(64) NOT NULL COMMENT '数据源',
    category VARCHAR(64) COMMENT '采集分类',
    
    total_records INT DEFAULT 0 COMMENT '采集总数',
    inserted_count INT DEFAULT 0 COMMENT '新增数',
    updated_count INT DEFAULT 0 COMMENT '更新数',
    unchanged_count INT DEFAULT 0 COMMENT '无变化数',
    error_count INT DEFAULT 0 COMMENT '错误数',
    
    started_at DATETIME(3) NOT NULL,
    finished_at DATETIME(3),
    
    status ENUM('RUNNING', 'SUCCESS', 'PARTIAL', 'FAILED') DEFAULT 'RUNNING',
    error_message TEXT,
    
    INDEX idx_source (source),
    INDEX idx_status (status),
    INDEX idx_started_at (started_at)
) ENGINE=InnoDB COMMENT='采集批次记录表';


-- ============================================================
-- 5. 视图: 最新变更 (供 LLM 消费)
-- ============================================================
CREATE OR REPLACE VIEW v_recent_changes AS
SELECT 
    cl.request_id,
    cl.commodity_id,
    cl.change_type,
    cl.field_name,
    cl.old_value,
    cl.new_value,
    cl.change_summary,
    cl.version_ts,
    ch.name,
    ch.chinese_name,
    ch.category,
    ch.price,
    ch.price_unit,
    ch.weight_unit
FROM change_log cl
LEFT JOIN commodity_history ch 
    ON cl.commodity_id = ch.commodity_id 
    AND cl.version_ts = ch.version_ts
ORDER BY cl.created_at DESC;


-- ============================================================
-- 6. 视图: 价格变动摘要 (供前端展示)
-- ============================================================
CREATE OR REPLACE VIEW v_price_changes AS
SELECT 
    commodity_id,
    field_name,
    CAST(old_value AS DECIMAL(20,6)) as old_price,
    CAST(new_value AS DECIMAL(20,6)) as new_price,
    CAST(new_value AS DECIMAL(20,6)) - CAST(old_value AS DECIMAL(20,6)) as price_diff,
    ROUND((CAST(new_value AS DECIMAL(20,6)) - CAST(old_value AS DECIMAL(20,6))) / 
          NULLIF(CAST(old_value AS DECIMAL(20,6)), 0) * 100, 2) as change_pct,
    change_summary,
    version_ts,
    created_at
FROM change_log
WHERE field_name = 'price' AND change_type = 'UPDATE'
ORDER BY created_at DESC;
