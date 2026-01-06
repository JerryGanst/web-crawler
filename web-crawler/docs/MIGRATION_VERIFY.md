# MongoDB 迁移验证与部署说明

本文档用于指导如何验证 Redis -> MongoDB 的存储改造，并提供相关部署说明。

## 一、 改造概述

本项目已完成核心数据存储层的改造，实现了以下目标：
1.  **双重存储**：爬虫数据现在同时写入 Redis（缓存）和 MongoDB（持久化归档）。
2.  **读取降级**：API 接口优先读取 Redis 缓存，若未命中则自动从 MongoDB 加载最新数据并回写 Redis。
3.  **增量写入**：爬虫任务仅增量写入新数据，避免重复。

---

## 二、 验证步骤

### 1. 环境准备
确保相关服务已启动：
*   Redis 服务 (默认端口 6379)
*   MongoDB 服务 (默认端口 27017 或配置文件指定端口)
*   Python 依赖已安装: `pip install -r requirements.txt` (确保包含 `pymongo`, `beanie`, `motor`)

### 2. 写入验证 (爬虫 -> MongoDB)
**目标**：确认爬虫数据能正确写入 MongoDB。

1.  **触发爬虫**：
    等待定时任务执行，或手动调用爬虫接口（如果已暴露）。
    或者运行以下 Python 代码片段手动触发（需在项目根目录下）：
    ```python
    # 模拟手动触发大宗商品爬虫
    from api.scheduler import scheduler
    scheduler._crawl_commodity_data()
    ```

2.  **检查 MongoDB**：
    使用 MongoDB 客户端（如 Compass 或命令行）连接数据库，查询 `news` 和 `commodities` 集合。
    ```javascript
    // MongoDB Shell
    use order_system  // 或配置的数据库名
    db.news.find().sort({_id: -1}).limit(1)
    db.commodities.find().sort({_id: -1}).limit(1)
    ```
    **预期结果**：应能查看到最新的数据文档。

3.  **检查日志**：
    查看控制台输出，应包含类似 `✅ [定时] ... 归档到 MongoDB` 的日志。

### 3. 读取降级验证 (Redis Miss -> MongoDB -> Redis)
**目标**：确认当 Redis 无数据时，API 能从 MongoDB 恢复数据。

1.  **清除缓存**：
    手动删除 Redis 中的某个 Key，例如 `news:finance`。
    ```bash
    redis-cli DEL news:finance
    ```

2.  **调用接口**：
    访问对应的新闻接口：
    `GET http://localhost:5173/api/news/finance`

3.  **观察结果**：
    *   **API 响应**：应正常返回数据，且 `from_archive` 字段为 `true` (如果代码中添加了该标记)。
    *   **控制台日志**：应出现 `🔄 [API] ... 缓存未命中，从 MongoDB 加载 ...` 的提示。
    *   **Redis**：再次检查 Redis，Key `news:finance` 应该已被重新写入。

---

## 三、 部署说明

### 1. 依赖安装
确保生产环境安装了最新的依赖包：
```bash
pip install -r requirements.txt
```
*注意：需确保 `pymongo`, `motor`, `beanie` 等 MongoDB 相关库已包含在内。*

### 2. 配置文件
检查 `config/database.yaml` (或环境变量)，确保 MongoDB 连接配置正确：
```yaml
mongodb:
  enabled: true
  host: "10.180.116.172"  # 生产环境 IP
  port: 27070
  username: "root"
  password: "..."
  database: "admin"       # 认证库
```

### 3. 索引创建 (自动)
本项目使用 `Beanie` ODM，在应用启动时（`server.py` 初始化阶段）会自动检查并创建必要的索引。
**关键索引**：
*   `News`: `platform_id`, `title_hash`, `crawl_date`, `category`
*   `Commodity`: `name`, `date`

---

## 四、 常见问题排查

*   **Q: MongoDB 连接失败？**
    *   A: 检查 `database.yaml` 中的 IP、端口、用户名密码是否正确。检查防火墙是否允许连接。

*   **Q: 数据写入了 Redis 但没写入 MongoDB？**
    *   A: 检查 `config.py` 或 `database.yaml` 中 `mongodb.enabled` 是否为 `true`。检查日志中是否有 `MongoDB 归档失败` 的错误信息。

*   **Q: 接口返回 "暂无数据"？**
    *   A: 如果 Redis 和 MongoDB 都为空，接口会触发后台爬取。请稍等片刻后刷新。
