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

## 测试执行
- [x] 创建测试脚本 `scripts/test_scraper_stability.py:1-120`
- [x] 执行10次API调用(3分钟内)
- [x] 记录每次爬取结果

## 数据分析
- [x] 统计各数据源成功率
- [x] 分析数据条数分布
- [x] 识别不稳定数据源

## 报告生成
- [x] 生成数据分析报告 `docs/爬虫稳定性分析报告.md`
- [x] 展示各数据源统计
- [x] 提供优化建议

---

**目标**: 验证 `scrapers/commodity.py:43` 的 `scrape()` 方法在多次调用中的稳定性
**测试方式**: 10次调用 `/api/data?refresh=true`，间隔18秒
**验证命令**: `python scripts/test_scraper_stability.py`
