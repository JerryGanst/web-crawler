# 🚀 Pacong - 智能网页数据爬取系统

> **零代码扩展** | **配置驱动** | **多源数据** | **自动化分析**

一个完全模块化的数据爬取和分析系统，**无需编程即可添加新的数据源**。

## 📋 核心特点

- 🔧 **零代码扩展**：通过配置文件添加新网站，无需编程
- 🌐 **多种爬取方式**：HTTP请求、浏览器自动化、API接口
- 📊 **智能数据处理**：自动清洗、验证、分类、去重
- 📈 **完整分析报告**：CSV/Excel报表 + 可视化摘要
- ⚙️ **开箱即用**：内置多个常用数据源

---

## 🎯 三种使用方式

### 1️⃣ **直接运行（最简单）**

# 在项目根目录安装所有依赖 (pip会自动处理好系统差异)
pip install -r requirements.txt

# 进入应用目录并运行
cd pacong
python main.py

📋 **结果**：自动爬取所有内置数据源，生成分析报告

### 2️⃣ **选择数据源**
```bash
python main.py --scrapers business_insider sina_finance
python main.py --list-scrapers  # 查看所有可用数据源
```

### 3️⃣ **添加新数据源（零代码）**
编辑 `config/settings.yaml`，添加：
```yaml
simple_scrapers:
  my_new_site:
    enabled: true
    name: "我的新数据源"
    urls: "https://api.example.com/data"
    method: "requests"
```
**就这么简单！** 系统会自动识别和处理新数据源。

---

## 📁 项目结构

```
pacong/                          # 🏠 主目录
├── 🚀 main.py                   # 启动程序（这里开始）
├── ⚙️ config/settings.yaml      # 配置文件（添加新网站）
├── 📊 reports/                  # 输出目录（查看结果）
├── core/                       # 🔧 核心模块（无需修改）
├── scrapers/                   # 🕷️ 爬虫模块
│   ├── business_insider.py     # Business Insider商品数据
│   ├── sina_finance.py         # 新浪财经外汇数据
│   ├── worldbank.py            # 世界银行数据
│   └── simple_generic.py       # 🎯 通用爬虫（配置驱动）
├── data/                       # 📋 数据处理
├── output/                     # 📄 输出格式
└── requirements.txt            # 📦 依赖包
```

**📍 重点文件：**
- **运行程序**：`main.py`
- **添加网站**：`config/settings.yaml`
- **查看结果**：`reports/` 目录

---

## 🌐 内置数据源

| 数据源 | 类型 | 说明 | 爬虫名称 |
|--------|------|------|----------|
| 🏪 **Business Insider** | 商品市场 | 实时商品价格数据 | `business_insider` |
| 💱 **新浪财经** | 外汇汇率 | CNY/TWD汇率数据 | `sina_finance` |
| 🏛️ **世界银行** | 商品指数 | 官方商品价格指数 | `worldbank` |
| 🪙 **CoinGecko演示** | 加密货币 | 比特币/以太坊价格 | `simple_coingecko_test` |

---

## 🔧 添加新数据源

### 📝 配置文件方式（推荐）

在 `config/settings.yaml` 中添加：

```yaml
simple_scrapers:
  # 示例1：API接口
  coinapi_demo:
    enabled: true
    name: "CoinAPI 数据"
    urls: "https://api.coinapi.io/v1/exchanges"
    method: "requests"
    headers:
      "X-CoinAPI-Key": "your-api-key"
  
  # 示例2：网页表格
  yahoo_finance:
    enabled: true  
    name: "Yahoo Finance"
    urls: "https://finance.yahoo.com/commodities"
    method: "requests"
  
  # 示例3：动态网页（需要浏览器）
  complex_site:
    enabled: true
    name: "复杂网站"
    urls: "https://example.com/dynamic-data"
    method: "selenium"  # 使用浏览器渲染
```

### 🎯 支持的网站类型

| 网站类型 | 配置方式 | 示例 |
|----------|----------|------|
| **API接口** | `method: "requests"` | REST API、JSON数据 |
| **静态网页** | `method: "requests"` | 表格数据、HTML内容 |
| **动态网页** | `method: "selenium"` | JavaScript渲染的页面 |
| **桌面自动化** | `method: "rpa"` | 需要模拟真实用户键盘、窗口操作的复杂网站 |

---

## 📊 输出结果

运行后会生成：

### 📄 **CSV文件** (`reports/commodity_data_YYYYMMDD_HHMMSS.csv`)
标准表格格式，包含：名称、价格、涨跌幅、来源、时间等

### 📈 **Excel报表** (`reports/commodity_data_YYYYMMDD_HHMMSS.xlsx`)
多工作表报告：数据总览、分类统计、详细数据

### 🖥️ **控制台摘要**
```
📊 商品数据分析结果摘要
============================================================
📈 总商品数: 25
📊 平均涨跌幅: +1.23%
🟢 上涨商品: 15
🔴 下跌商品: 10

📋 分类统计:
  能源: 8 个 (平均涨跌: +2.1%)
  贵金属: 4 个 (平均涨跌: -0.5%)
  农产品: 13 个 (平均涨跌: +1.8%)

💾 输出文件:
  📄 CSV: reports/commodity_data_20250722_143052.csv
  📈 EXCEL: reports/commodity_data_20250722_143052.xlsx
```

---

## ⚡ 快速上手

### 🔥 **30秒快速体验**

git clone <repo-url>
cd Large
pip install -r requirements.txt

cd pacong
python main.py --scrapers simple_coingecko_test

### 🎯 **常用命令**

# 在项目根目录执行
# 查看所有可用数据源
python pacong/main.py --list-scrapers

# 运行特定数据源
python pacong/main.py --scrapers business_insider sina_finance

# 调试模式（查看详细过程）
python pacong/main.py --log-level DEBUG

# 自定义输出目录
python pacong/main.py --output-dir ./my-reports

# 静默模式（只显示错误）
python pacong/main.py --quiet

---

## 🛠️ 高级配置

### 🔧 **详细字段配置**
```yaml
simple_scrapers:
  advanced_example:
    enabled: true
    name: "高级示例"
    urls: "https://api.example.com/data"
    method: "requests"
    
    # 自定义请求头
    headers:
      "User-Agent": "MyBot 1.0"
      "Authorization": "Bearer your-token"
    
    # 数据验证
    required_fields: ["name", "current_price"]
    
    # 特殊处理（可选）
    wait_time: 3  # 仅selenium模式
```

### 🌐 **多URL支持**
```yaml
multi_source:
  enabled: true
  name: "多源数据"
  urls:
    - "https://site1.com/api/data"
    - "https://site2.com/api/prices"
    - "https://site3.com/markets"
  method: "requests"
```

---

## 🔍 故障排除

### ❓ **常见问题**

**Q: 添加新网站后没有数据？**
```bash
# 启用调试模式查看详细信息
python main.py --log-level DEBUG --scrapers your_scraper_name
```

**Q: 某些网站需要浏览器？**
```yaml
your_scraper:
  method: "selenium"  # 改为浏览器模式
  wait_time: 5        # 增加等待时间
```

**Q: 需要特殊的请求头？**
```yaml
your_scraper:
  headers:
    "User-Agent": "Mozilla/5.0..."
    "Referer": "https://example.com"
```

### 🔧 **系统要求**
- **Python**: 3.8+
- **Chrome浏览器**: 最新版本（selenium/rpa模式需要）
- **内存**: 512MB+
- **系统**: macOS / Linux / Windows
- **RPA模式依赖**:
  - **Linux**: 需要预先安装 `xdotool` (`sudo apt-get install xdotool`)
  - **Windows**: 需要 `pyautogui` (已在`requirements.txt`中)

---

## 🤝 贡献 & 支持

- 🐛 **报告问题**：[GitHub Issues](链接)
- 💡 **功能建议**：欢迎提出新想法
- 🔧 **代码贡献**：Fork & Pull Request
- 📖 **文档改进**：帮助完善说明

---

## 📄 许可证

保留所有权利 (All Rights Reserved) - 允许个人学习和使用，未经授权禁止任何形式的重新分发或商业用途。

---

**🎯 核心理念：让数据爬取变得简单直接，无需重复开发！**

⭐ **如果这个项目对您有帮助，请给个Star支持！** 