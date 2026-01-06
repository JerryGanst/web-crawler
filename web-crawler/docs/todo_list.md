# TrendRadar SQLite → MongoDB 迁移任务清单

## 0. 任务清单使用规则

- 原子任务：≤14 字、动词开头、单一语义。
- 状态标识：
  - ✔ 已完成
  - ⏸ 已停滞
  - ✗ 已阻塞
  - Δ 已变更
  - ☐ 未开始
- 每完成一个任务，必须补充：
  - 关联源码位置（`file_path:line_number`）
  - 验证命令与结果摘要（不写测试代码）

## 1. 当前阶段目标

- 冻结技术选型与数据库设计
- 形成可持续更新的任务清单
- 完成数据迁移、索引初始化与读写切换

## 2. 任务列表

| ID | 任务 | 状态 | 源码位置 | 验证命令 | 结果摘要 |
|---|---|---|---|---|---|
| DOC-01 | 输出技术选型文档 | ✔ | `docs/技术选型文档.md:1` | `Get-Item .\docs\技术选型文档.md` | 已生成文档 |
| DOC-02 | 输出数据库设计文档 | ✔ | `database/migrations/init_schema.sql:16` | `Get-Item .\docs\数据库设计文档.md` | 已生成文档 |
| DOC-03 | 输出任务清单文档 | ✔ | `docs/todo_list.md:1` | `Get-Item .\docs\todo_list.md` | 已生成文档 |
| ENV-01 | 引入 MongoDB 依赖 | ✔ | `requirements.txt:7` | `py -c "import pymongo, motor; print(pymongo.__version__, motor.__version__)"` | 已锁定版本；待安装执行命令复核 |
| ENV-02 | 新增 MongoDB 配置 | ✔ | `config/database.yaml:21` | `py -c "import yaml; from pathlib import Path; cfg=yaml.safe_load(Path('config/database.yaml').read_text(encoding='utf-8')) or {}; print('mongodb' in cfg, bool(cfg.get('mongodb', {}).get('enabled')))"` | 已验证 `mongodb.enabled=True` |
| ENV-03 | 约束敏感配置脱敏 | ✔ | `docs/todo_list.md:28` | `py -c "import yaml; from pathlib import Path; cfg=yaml.safe_load(Path('config/database.yaml').read_text(encoding='utf-8')) or {}; m=cfg.get('mongodb', {}) or {}; my=cfg.get('mysql', {}) or {}; print(bool(m.get('username')), bool(m.get('password')), bool(my.get('password')))"` | 输出布尔值，不打印明文 |
| SEC-01 | 清理明文凭据 | Δ | `docs/todo_list.md:28` | `Select-String -Path .\docs\todo_list.md -Pattern "print\(m\.get\('password'" -Quiet` | 应输出 `False`（验证命令不打印明文） |
| DB-01 | 设计集合索引策略 | ✔ | `docs/数据库设计文档.md:49` | `py -c "from pathlib import Path; txt=Path('docs/数据库设计文档.md').read_text(encoding='utf-8'); print('news 索引' in txt and 'platforms' in txt and 'analytics_cache' in txt)"` | 已覆盖核心集合及复合索引 |
| DB-02 | 实现 Mongo 连接模块 | ✔ | `database/connection.py:234` | `py -c "from database.connection import get_mongo_database; db=get_mongo_database(); print(db.name)"` | 已实现连接与 URI 构建 |
| DB-03 | 实现 Mongo 健康检查 | ✔ | `database/manager.py:215` | `py -c "from database.manager import db_manager; print(db_manager.health_check())"` | 已接入 ping 健康检查 |
| DB-04 | 初始化集合索引 | ✔ | `scripts/migrate_sqlite_to_mongo.py:53` | `py .\scripts\migrate_sqlite_to_mongo.py init_indexes` | 创建索引数 `created=19`（与干跑统计一致） |
| REPO-01 | 重写平台仓库层 | ✔ | `database/repositories/platform_repo.py:110` | `py -c "from database.connection import get_mongo_database; from database.repositories.platform_repo import MongoPlatformRepository; db=get_mongo_database(); repo=MongoPlatformRepository(db); print(hasattr(repo,'insert_batch'), hasattr(repo,'get_stats'))"` | 已实现 Mongo 平台仓库与批量写入 |
| REPO-02 | 重写新闻仓库层 | ✔ | `database/repositories/news_repo.py:394` | `py -c "from database.connection import get_mongo_database; from database.repositories.news_repo import MongoNewsRepository; from datetime import datetime; db=get_mongo_database(); repo=MongoNewsRepository(db); print(callable(getattr(repo,'insert_or_update',None)), callable(getattr(repo,'get_platform_stats',None)))"` | 已实现 Mongo 新闻仓库及统计 |
| REPO-03 | 重写关键词仓库层 | ✔ | `database/repositories/news_repo.py:601` | `py -c "from database.connection import get_mongo_database; from database.repositories.news_repo import MongoKeywordMatchRepository; db=get_mongo_database(); repo=MongoKeywordMatchRepository(db); print(callable(getattr(repo,'insert_batch',None)), callable(getattr(repo,'get_keyword_stats',None)))"` | 已实现 Mongo 关键词匹配仓库 |
| REPO-04 | 重写日志仓库层 | ✔ | `database/repositories/log_repo.py:262` | `py -c "from database.connection import get_mongo_database; from database.repositories.log_repo import MongoCrawlLogRepository, MongoPushRecordRepository; db=get_mongo_database(); print(callable(getattr(MongoCrawlLogRepository(db),'get_daily_stats',None)), callable(getattr(MongoPushRecordRepository(db),'get_channel_stats',None)))"` | 已实现 Mongo 爬取日志与推送记录仓库 |
| CACHE-01 | 重写分析缓存后端 | ✔ | `database/cache.py:148` | `py -c "import database.cache as c; print('MongoCache' in dir(c), 'CacheManager' in dir(c))" ; py -m compileall .\database\cache.py` | 输出 `True True`；`compileall` 通过 |
| ROUTE-01 | 替换数据路由入口 | ✔ | `api/routes/data.py:13` | `py -c "from pathlib import Path; txt=Path('api/routes/data.py').read_text(encoding='utf-8'); print('from database.manager import db_manager' in txt)"` | 输出 `True`；数据路由层已改为注入 `db_manager` |
| MIG-01 | 编写迁移脚本框架 | ✔ | `scripts/migrate_sqlite_to_mongo.py:164` | `py -m compileall .\scripts\migrate_sqlite_to_mongo.py; py .\scripts\migrate_sqlite_to_mongo.py counts; py .\scripts\migrate_sqlite_to_mongo.py all --dry-run --limit 5` | 命令通过；counts=0；干跑 inserted/updated 均为 0 |
| MIG-02 | 迁移 platforms 数据 | ✔ | `scripts/migrate_sqlite_to_mongo.py:153` | `py .\scripts\migrate_sqlite_to_mongo.py platforms --dry-run; py .\scripts\migrate_sqlite_to_mongo.py platforms` | 干跑 inserted=0；实际 inserted=0 |
| MIG-03 | 迁移 news 数据 | ✔ | `scripts/migrate_sqlite_to_mongo.py:175` | `py .\scripts\migrate_sqlite_to_mongo.py news --dry-run; py .\scripts\migrate_sqlite_to_mongo.py news` | 干跑 inserted=0 updated=0；实际 inserted=0 updated=0 |
| MIG-04 | 迁移 keyword_matches 数据 | ✔ | `scripts/migrate_sqlite_to_mongo.py:270` | `py .\scripts\migrate_sqlite_to_mongo.py keyword_matches --dry-run; py .\scripts\migrate_sqlite_to_mongo.py keyword_matches` | 干跑 inserted=0 missing_news_ref=0；实际 inserted=0 missing_news_ref=0 |
| MIG-05 | 迁移 crawl_logs 数据 | ✔ | `scripts/migrate_sqlite_to_mongo.py:203` | `py .\\scripts\\migrate_sqlite_to_mongo.py crawl_logs --dry-run; py .\\scripts\\migrate_sqlite_to_mongo.py crawl_logs` | 干跑 inserted=0 updated=0；实际 inserted=0 updated=0 |
| MIG-06 | 迁移 push_records 数据 | ✔ | `scripts/migrate_sqlite_to_mongo.py:319` | `py .\scripts\migrate_sqlite_to_mongo.py push_records --dry-run; py .\scripts\migrate_sqlite_to_mongo.py push_records` | 干跑 inserted=0 updated=0；实际 inserted=0 updated=0 |
| MIG-07 | 迁移 analytics_cache 数据 | ✔ | `scripts/migrate_sqlite_to_mongo.py:374` | `py .\scripts\migrate_sqlite_to_mongo.py analytics_cache --dry-run; py .\scripts\migrate_sqlite_to_mongo.py analytics_cache` | 干跑 inserted=0 updated=0；实际 inserted=0 updated=0 |
| MIG-08 | 校验迁移数据一致 | ✔ | `scripts/migrate_sqlite_to_mongo.py:429` | `py .\scripts\migrate_sqlite_to_mongo.py verify` | ok=True；diff 全为 0 |
| UI-01 | 固化页面风格规范 | ☐ | `docs/技术选型文档.md:1` |  |  |
| CLEAN-01 | 移除 SQLite 初始化 | ✔ | `database/connection.py:31` | `py -m compileall .\database\connection.py ; py -c "from database.connection import DatabaseManager; print(hasattr(DatabaseManager,'_init_database'), hasattr(DatabaseManager,'_split_sql_statements'))"` | 输出 `False False`；SQLite 初始化逻辑已移除 |
| CLEAN-02 | 清理 SQLite 依赖点 | ☐ | `database/connection.py:8` |  |  |
| REL-01 | 输出上线回滚方案 | ☐ | `docs/技术选型文档.md:1` |  |  |
| RUN-01 | 修复后端依赖安装失败 | ✔ | `requirements.txt:1` | `py -m pip install -r requirements.txt` | 已安装成功（含 `aiohttp`） |
| RUN-02 | 启动后端 API 服务 | ✔ | `server.py:51` | `py -m uvicorn server:app --host 0.0.0.0 --port 8000 --reload` | `GET /api/status` 返回 running |
| RUN-03 | 修复前端 Node16 兼容 | ✔ | `frontend/package.json:12` | `npm install` | 依赖降级后可安装 |
| RUN-04 | 启动前端 Dev Server | ✔ | `frontend/package.json:7` | `npm run dev -- --host 0.0.0.0 --port 5173` | Vite 4 启动成功，端口 5173 |
| RUN-05 | 执行启动前验证命令 | ✔ | `frontend/eslint.config.js:5` | `npm run lint`；`py -m compileall -q .` | lint=0 退出；compileall 通过 |
| PERF-01 | 定位20秒超时 | ✔ | `frontend/vite.config.js:95`；`api/routes/data.py:421` | `$ProgressPreference='SilentlyContinue'; Measure-Command { iwr http://localhost:5173/api/data -UseBasicParsing }` | 实测 5173 代理与 8000 后端均毫秒级；20 秒为链路超时阈值 |
| FIX-01 | 修复 typing.List 类型错误 | ✔ | `web/web-crawler/prompts/analysis_prompts_v4.py:613` | `py -m compileall web/web-crawler/prompts/analysis_prompts_v4.py` | 修复 TypeError: Too many arguments for typing.List |
# 数据爬取稳定性测试任务清单

# 商品数据流转分析任务清单

2. ✅ **增强 Pipeline 容错机制**
    - 文件：`database/mysql/pipeline.py:258-268`
    - 新增 chinese_name 二次映射逻辑
    - 防止未来出现类似问题
    - 代码位置：`database/mysql/pipeline.py:258-270`

3. ✅ **修正数据库脏数据**
    - 执行 SQL：`UPDATE commodity_latest SET chinese_name = '棕榈油' WHERE id = 'palm_oil'`
    - 影响：1 条记录
    - 验证脚本：`docs/test/fix_palm_oil_chinese_name.py`

**验证结果**：

| 数据表 | name | chinese_name | 状态 |
|:---|:---|:---|:---|
| `commodity_latest` | `Palm Oil` | `棕榈油` ✅ | **已修正** |
| `commodity_history` | `Palm Oil` | `棕榈油` ✅ | 保持正确 |

**相关文件**：
- 源代码：
    - `scrapers/commodity.py` - 新增 Palm Oil 单位配置
    - `database/mysql/pipeline.py` - 增强容错机制
- 测试脚本：
    - `docs/test/check_palm_simple.py` - 验证脚本
    - `docs/test/fix_palm_oil_chinese_name.py` - 修复脚本
- 文档：
    - `docs/test/palm_oil_analysis_report.md` - 问题分析报告

---

## 📋 待处理任务

### 高优先级
*暂无*

### 中优先级
*暂无*

### 低优先级
*暂无*

---

## 📝 问题记录

### Palm Oil chinese_name 映射错误 (已解决)

- **时间**: 2025-12-30
- **模块**: 数据管道 / 商品爬虫
- **环境**: MySQL (commodity_latest 表)
- **现象**: commodity_latest 表中 Palm Oil 的 chinese_name 字段为 "Palm Oil"（英文），应为"棕榈油"
- **复现步骤**:
    1. 执行 Business Insider 爬虫
    2. 查询 `SELECT chinese_name FROM commodity_latest WHERE id = 'palm_oil'`
    3. 返回 "Palm Oil" 而非 "棕榈油"
- **根因分类**: 配置缺失 + 数据脏写
- **修复方案**:
    1. 补全 `COMMODITY_UNITS` 配置
    2. 增强 Pipeline 容错机制（chinese_name 二次映射）
    3. 修正数据库脏数据
- **影响评估**: 低（仅影响前端显示，不影响核心功能）
- **源码位置**:
    - `scrapers/commodity.py:62` - 单位配置
    - `database/mysql/pipeline.py:258-270` - 容错逻辑
- **后续防线**: Pipeline 已增加容错机制，即使爬虫数据缺失 chinese_name，也会自动从翻译表映射

---

## 🔗 快速链接

- 项目文档：`/docs`
- 测试脚本：`/docs/test`
- 问题记录：本文档"问题记录"章节
