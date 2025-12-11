# TrendRadar 项目结构

> 热点新闻聚合与推送服务

## 📁 目录说明

```
TrendRadar/
│
├── server.py           # 🌐 FastAPI 后端 API (端口 8000)
├── main.py             # 🖥️ CLI 主程序（爬取+分析+推送）
│
├── scrapers/           # 🕷️ 国内财经爬虫 (requests)
│   ├── unified.py      # 统一数据源入口
│   ├── finance.py      # 财经新闻
│   ├── commodity.py    # 大宗商品
│   └── smm.py          # 上海有色网
│
├── pacong/             # 🌍 高级爬虫系统（浏览器自动化）
│   ├── browser/        # AppleScript/Selenium/CDP 控制
│   ├── scrapers/       # Bloomberg/BusinessInsider/世界银行
│   └── main.py         # 独立入口
│
├── core/               # 📦 核心模块
│   ├── config.py       # 配置管理
│   ├── analyzer.py     # 数据分析
│   ├── statistics.py   # 词频统计
│   ├── data_processor.py
│   ├── notifiers/      # 通知推送
│   └── reporters/      # 报告生成
│
├── database/           # 💾 数据库
│   ├── mysql/          # MySQL 连接
│   └── repositories/   # 数据仓库
│
├── config/             # ⚙️ 配置文件
│   ├── config.yaml     # 主配置
│   └── scrapers.yaml   # 爬虫配置
│
├── mcp_server/         # 🤖 MCP 服务（AI 工具）
├── scripts/            # 📜 脚本工具
├── tests/              # 🧪 测试用例
├── docs/               # 📚 文档
│
└── frontend/           # ⚛️ React 前端 (端口 5173)
```

## 🚀 快速启动

### 方式一：一键启动（推荐）

```bash
# 使用启动脚本同时启动前后端
./start.sh
```

### 方式二：手动启动

```bash
# 1. 启动后端 API (端口 8000)
uv run uvicorn server:app --host 0.0.0.0 --port 8000

# 2. 新开终端，启动前端 (端口 5173)
cd frontend
npm run dev
```

### 方式三：仅运行 CLI

```bash
# 运行命令行爬取分析
python main.py
```

### 访问地址

| 服务 | 地址 | 说明 |
|------|------|------|
| **前端界面** | http://localhost:5173 | React 可视化界面 |
| **后端 API** | http://localhost:8000 | FastAPI 数据接口 |
| **API 文档** | http://localhost:8000/docs | Swagger 文档 |

## 🔑 两套爬虫说明

| 目录 | 用途 | 特点 |
|------|------|------|
| `scrapers/` | 国内财经网站 | 基于 requests，简单快速 |
| `pacong/` | 国际网站/反爬站点 | 支持 AppleScript/Selenium/CDP |

## ⚙️ 配置文件

- `config/config.yaml` - 主配置（API密钥、推送等）
- `config/scrapers.yaml` - 爬虫数据源配置
- `pacong/config/settings.yaml` - 高级爬虫配置

## 📡 API 端点

- `GET /api/news/{category}` - 获取新闻
- `GET /api/data` - 大宗商品数据
- `GET /api/news/supply-chain` - 供应链新闻
- `GET /api/cache/status` - Redis 缓存状态
- `POST /api/generate-analysis` - AI 分析报告
- `GET /api/reader/{news_id}` - 新闻阅读器（用于需登录的外部站点）

## 🆕 最新更新 (2025-12-10)

### 塑料子分类TAB与区域折线图

- 塑料分类新增子TAB：ABS、PP、PE、PS、PVC、PA66、PC、PET
- 每个子TAB显示该大类下的商品数量
- 切换子TAB自动选中对应商品
- 区域价格折线图：华东/华南/华北多条折线同时展示

### 中塑在线爬虫 (plastic21cp.py)

- 新增 PP、PE、PS 的华南、华北区域价格数据
- 支持多区域数据合并显示
- 历史价格数据缓存到 Redis

### MongoDB 集成

- 新增 MongoDB 存储层用于大宗商品历史数据
- 支持增量更新和批量写入
- 数据去重和标准化处理

## 📅 历史更新 (2025-12-08)

### 商品价格解析修复

- 修复 Business Insider 价格解析错误（移除错误的 `val>10` 过滤）
- 正确解析美分单位（USc）的农产品价格（棉花、咖啡、糖等）

### Plasway 爬虫优化

- 切换到 `requests` 模式（AppleScript 被 WAF 拦截）
- 新增文章阅读器功能：爬取内容保存到 Redis，用户点击直接阅读
- URL 规范化：避免用户访问需登录的子域名

### 数据看板级联筛选

- 重构筛选器顺序：国家 → 商品（从左到右）
- 选择国家后自动过滤商品列表
- 切换国家时自动选择该国家的商品
