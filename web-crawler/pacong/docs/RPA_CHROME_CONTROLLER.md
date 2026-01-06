# 跨平台RPA Chrome控制器使用指南

## 📋 概述

`RPAChromeMCP` 是一个跨平台的Chrome浏览器自动化控制器，集成了AppleScript、Selenium、CDP（Chrome DevTools Protocol）等多种控制方式，提供统一的API接口进行浏览器自动化操作。

## 🏗️ 架构设计

### 核心组件

```
RPAChromeMCP
├── PlatformController (抽象基类)
├── AppleScriptController (macOS)
├── WindowsController (Windows - 待实现)
├── LinuxController (Linux - 待实现)
└── 集成控制器
    ├── SeleniumController
    └── CDPController
```

### 设计特点

- **跨平台兼容**: 自动检测操作系统并选择最佳控制方式
- **多控制器集成**: 融合AppleScript、Selenium、CDP的优势
- **异步编程**: 基于asyncio的异步操作
- **错误处理**: 完善的异常处理和错误恢复机制
- **扩展性**: 模块化设计，易于添加新的平台支持

## 🚀 快速开始

### 基本使用

```python
import asyncio
from pacong.browser.rpa_chrome_controller import RPAChromeMCP

async def basic_example():
    # 创建RPA控制器
    rpa = RPAChromeMCP()
    
    # 打开网页
    await rpa.open_url("https://www.google.com")
    
    # 等待页面加载
    await rpa.sleep(2)
    
    # 获取页面标题
    title = await rpa.execute_in_devtools("document.title")
    print(f"页面标题: {title}")

# 运行示例
asyncio.run(basic_example())
```

### 便捷函数

```python
from pacong.browser.rpa_chrome_controller import quick_open_url, quick_execute_js

# 快速打开URL
success = await quick_open_url("https://www.example.com")

# 快速执行JavaScript
result = await quick_execute_js("document.title")
```

## 📖 API 参考

### RPAChromeMCP 类

#### 初始化

```python
RPAChromeMCP(controller_type: Optional[ControllerType] = None)
```

**参数:**
- `controller_type`: 指定控制器类型，可选值：
  - `ControllerType.APPLESCRIPT`: 强制使用AppleScript
  - `ControllerType.SELENIUM`: 强制使用Selenium
  - `ControllerType.CDP`: 强制使用CDP
  - `None`: 自动选择（推荐）

#### 核心方法

##### 页面导航

```python
async def open_url(self, url: str) -> bool
```
打开指定URL

**参数:**
- `url`: 要打开的网址

**返回:**
- `bool`: 是否成功打开

**示例:**
```python
success = await rpa.open_url("https://www.google.com")
```

##### JavaScript执行

```python
async def execute_in_devtools(self, code: str) -> Any
```
在开发者工具中执行JavaScript代码

**参数:**
- `code`: JavaScript代码字符串

**返回:**
- `Any`: 代码执行结果

**示例:**
```python
# 获取页面标题
title = await rpa.execute_in_devtools("document.title")

# 获取页面URL
url = await rpa.execute_in_devtools("window.location.href")

# 执行复杂操作
result = await rpa.execute_in_devtools("""
    const links = Array.from(document.querySelectorAll('a'))
                      .map(a => a.href);
    return links.length;
""")
```

## 🎯 实际应用场景

### 1. 网页数据采集

```python
async def scrape_news():
    rpa = RPAChromeMCP()
    
    # 打开新闻网站
    await rpa.open_url("https://news.example.com")
    await rpa.sleep(3)
    
    # 获取新闻标题
    titles = await rpa.execute_in_devtools("""
        Array.from(document.querySelectorAll('.news-title'))
             .map(el => el.textContent.trim())
    """)
    
    return titles
```

### 2. 自动化测试

```python
async def test_login():
    rpa = RPAChromeMCP()
    
    # 打开登录页面
    await rpa.open_url("https://app.example.com/login")
    
    # 填写用户名
    await rpa.click_element('#username')
    await rpa.controller.type_text("testuser")
    
    # 填写密码
    await rpa.click_element('#password')
    await rpa.controller.type_text("password")
    
    # 点击登录按钮
    await rpa.click_element('#login-btn')
    
    # 验证登录成功
    await rpa.sleep(2)
    success = await rpa.wait_for_element('.dashboard', timeout=10)
    
    return success
```

## ⚙️ 配置选项

### 平台特定配置

#### macOS (AppleScript)

```python
# 使用指定的控制器类型
rpa = RPAChromeMCP(controller_type=ControllerType.APPLESCRIPT)
```

**注意事项:**
- 需要在"系统设置 > 隐私与安全 > 自动化"中授权终端/Python应用
- 确保Chrome浏览器已安装

## 🔧 故障排除

### 常见问题

#### 1. Chrome激活失败

**问题**: `无法激活Chrome浏览器`

**解决方案:**
- 确保Chrome已安装且可以正常启动
- 检查系统自动化权限设置
- 尝试手动打开Chrome后再运行脚本

#### 2. 权限错误 (macOS)

**问题**: `需要自动化权限`

**解决方案:**
1. 打开"系统设置"
2. 进入"隐私与安全" > "自动化"
3. 为终端或Python应用授权控制Chrome

---

**跨平台RPA Chrome控制器** - 让浏览器自动化更简单、更强大！
