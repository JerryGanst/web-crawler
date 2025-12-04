"""
跨平台RPA Chrome控制器演示脚本
展示如何使用RPAChromeMCP进行浏览器自动化操作
"""

import asyncio
import logging
from pathlib import Path
import sys

# 添加项目根目录到path
sys.path.append(str(Path(__file__).parent.parent))

from browser.rpa_chrome_controller import RPAChromeMCP, ControllerType

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def demo_basic_navigation():
    """演示基本的导航功能"""
    print("\n🚀 演示基本导航功能")
    
    # 创建RPA控制器
    rpa = RPAChromeMCP()
    
    try:
        # 打开Google
        success = await rpa.open_url("https://www.google.com")
        if success:
            print("✅ 成功打开Google")
            
            # 等待页面加载
            await rpa.sleep(2)
            
            # 获取页面标题
            title = await rpa.execute_in_devtools("document.title")
            print(f"📄 页面标题: {title}")
            
            return True
        else:
            print("❌ 打开Google失败")
            return False
            
    except Exception as e:
        logger.error(f"基本导航演示失败: {e}")
        return False


async def demo_search_functionality():
    """演示搜索功能"""
    print("\n🔍 演示搜索功能")
    
    rpa = RPAChromeMCP()
    
    try:
        # 打开Google
        if not await rpa.open_url("https://www.google.com"):
            print("❌ 无法打开Google")
            return False
        
        # 等待页面加载
        await rpa.sleep(3)
        
        # 等待搜索框出现
        search_box_exists = await rpa.wait_for_element('input[name="q"]', timeout=10)
        if not search_box_exists:
            print("❌ 搜索框未找到")
            return False
        
        print("✅ 找到搜索框")
        
        # 点击搜索框
        if await rpa.click_element('input[name="q"]'):
            print("✅ 成功点击搜索框")
            
            # 等待一下
            await rpa.sleep(1)
            
            # 输入搜索内容
            if await rpa.controller.type_text("Python RPA自动化测试"):
                print("✅ 成功输入搜索内容")
                
                # 按回车搜索
                if await rpa.controller.send_key('enter'):
                    print("✅ 成功执行搜索")
                    
                    # 等待搜索结果
                    await rpa.sleep(3)
                    
                    # 获取搜索结果页面标题
                    title = await rpa.execute_in_devtools("document.title")
                    print(f"📄 搜索结果页标题: {title}")
                    
                    return True
        
        return False
        
    except Exception as e:
        logger.error(f"搜索功能演示失败: {e}")
        return False


async def demo_page_interaction():
    """演示页面交互功能"""
    print("\n🎯 演示页面交互功能")
    
    rpa = RPAChromeMCP()
    
    try:
        # 打开一个简单的测试页面
        if not await rpa.open_url("https://httpbin.org/html"):
            print("❌ 无法打开测试页面")
            return False
        
        # 等待页面加载
        await rpa.sleep(3)
        
        # 获取页面内容
        content = await rpa.get_page_content()
        if content:
            print("✅ 成功获取页面内容")
            print(f"📄 页面长度: {len(content)} 字符")
        
        # 获取标题文本
        title_text = await rpa.get_element_text('h1')
        if title_text:
            print(f"📝 页面标题: {title_text}")
        
        # 滚动到页面底部
        if await rpa.scroll_to_bottom():
            print("✅ 成功滚动到页面底部")
        
        return True
        
    except Exception as e:
        logger.error(f"页面交互演示失败: {e}")
        return False


async def demo_devtools_execution():
    """演示开发者工具代码执行"""
    print("\n🛠️ 演示开发者工具代码执行")
    
    rpa = RPAChromeMCP()
    
    try:
        # 打开任意网页
        if not await rpa.open_url("https://www.example.com"):
            print("❌ 无法打开示例页面")
            return False
        
        # 等待页面加载
        await rpa.sleep(3)
        
        # 执行各种JavaScript代码
        test_cases = [
            ("获取页面URL", "window.location.href"),
            ("获取页面标题", "document.title"),
            ("获取用户代理", "navigator.userAgent"),
            ("获取页面高度", "document.body.scrollHeight"),
            ("获取当前时间", "new Date().toLocaleString()"),
        ]
        
        for description, code in test_cases:
            result = await rpa.execute_in_devtools(code)
            if result is not None:
                print(f"✅ {description}: {result}")
            else:
                print(f"❌ {description}: 执行失败")
        
        # 执行复杂的JavaScript代码
        complex_code = """
        (() => {
            const stats = {
                url: window.location.href,
                title: document.title,
                links: document.querySelectorAll('a').length,
                images: document.querySelectorAll('img').length,
                scripts: document.querySelectorAll('script').length,
                timestamp: new Date().toISOString()
            };
            return JSON.stringify(stats, null, 2);
        })();
        """
        
        stats = await rpa.execute_in_devtools(complex_code)
        if stats:
            print("✅ 页面统计信息:")
            print(stats)
        
        return True
        
    except Exception as e:
        logger.error(f"开发者工具演示失败: {e}")
        return False


async def demo_error_handling():
    """演示错误处理"""
    print("\n⚠️ 演示错误处理")
    
    rpa = RPAChromeMCP()
    
    try:
        # 尝试打开无效URL
        success = await rpa.open_url("invalid-url")
        if not success:
            print("✅ 正确处理了无效URL")
        
        # 尝试点击不存在的元素
        success = await rpa.click_element('#non-existent-element')
        if not success:
            print("✅ 正确处理了不存在的元素")
        
        # 尝试执行错误的JavaScript
        result = await rpa.execute_in_devtools("this.is.invalid.javascript")
        if result is None:
            print("✅ 正确处理了错误的JavaScript")
        
        return True
        
    except Exception as e:
        logger.error(f"错误处理演示失败: {e}")
        return False


async def main():
    """主演示函数"""
    print("🎭 跨平台RPA Chrome控制器演示")
    print("=" * 50)
    
    # 运行所有演示
    demos = [
        ("基本导航", demo_basic_navigation),
        ("搜索功能", demo_search_functionality),
        ("页面交互", demo_page_interaction),
        ("开发者工具", demo_devtools_execution),
        ("错误处理", demo_error_handling),
    ]
    
    results = []
    
    for name, demo_func in demos:
        print(f"\n🎬 开始运行: {name}")
        try:
            success = await demo_func()
            results.append((name, success))
            if success:
                print(f"✅ {name} - 演示成功")
            else:
                print(f"❌ {name} - 演示失败")
        except Exception as e:
            print(f"💥 {name} - 演示异常: {e}")
            results.append((name, False))
        
        # 演示间隔
        await asyncio.sleep(2)
    
    # 输出总结
    print("\n📊 演示结果总结")
    print("=" * 30)
    
    success_count = 0
    for name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{name}: {status}")
        if success:
            success_count += 1
    
    total_count = len(results)
    print(f"\n📈 总计: {success_count}/{total_count} 个演示成功")
    print(f"📊 成功率: {success_count/total_count*100:.1f}%")


if __name__ == "__main__":
    # 运行演示
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 演示被用户中断")
    except Exception as e:
        print(f"\n💥 演示发生异常: {e}")
        logger.exception("演示异常详情")
