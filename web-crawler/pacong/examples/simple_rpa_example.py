#!/usr/bin/env python3
"""
简单的RPA Chrome控制器使用示例
演示基本的浏览器自动化操作
"""

import asyncio
import sys
from pathlib import Path

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent))

from browser.rpa_chrome_controller import RPAChromeMCP


async def simple_example():
    """简单的使用示例"""
    print("🚀 启动跨平台RPA Chrome控制器")
    
    # 创建RPA控制器
    rpa = RPAChromeMCP()
    
    try:
        # 1. 打开Google
        print("\n📖 步骤1: 打开Google首页")
        success = await rpa.open_url("https://www.google.com")
        
        if success:
            print("✅ 成功打开Google")
            
            # 等待页面加载
            await rpa.sleep(3)
            
            # 2. 获取页面信息
            print("\n📊 步骤2: 获取页面信息")
            
            # 获取页面标题
            title = await rpa.execute_in_devtools("document.title")
            print(f"📄 页面标题: {title}")
            
            # 获取页面URL
            url = await rpa.execute_in_devtools("window.location.href")
            print(f"🔗 页面URL: {url}")
            
            # 获取页面中链接数量
            link_count = await rpa.execute_in_devtools("""
                document.querySelectorAll('a').length
            """)
            print(f"🔗 页面链接数: {link_count}")
            
            # 3. 等待搜索框出现并交互
            print("\n🔍 步骤3: 查找搜索框")
            search_exists = await rpa.wait_for_element('input[name="q"]', timeout=10)
            
            if search_exists:
                print("✅ 找到搜索框")
                
                # 点击搜索框
                if await rpa.click_element('input[name="q"]'):
                    print("✅ 成功点击搜索框")
                    
                    # 输入搜索内容
                    await rpa.sleep(1)
                    search_text = "Python RPA自动化"
                    
                    if await rpa.controller.type_text(search_text):
                        print(f"✅ 成功输入: {search_text}")
                        
                        # 按回车搜索
                        if await rpa.controller.send_key('enter'):
                            print("✅ 执行搜索")
                            
                            # 等待搜索结果
                            await rpa.sleep(3)
                            
                            # 获取搜索结果页标题
                            result_title = await rpa.execute_in_devtools("document.title")
                            print(f"📄 搜索结果页标题: {result_title}")
                
            else:
                print("❌ 未找到搜索框")
            
            print("\n🎉 示例执行完成!")
            
        else:
            print("❌ 无法打开Google")
            
    except Exception as e:
        print(f"💥 示例执行异常: {e}")
        return False
    
    return True


async def main():
    """主函数"""
    print("=" * 50)
    print("🎭 简单RPA Chrome控制器示例")
    print("=" * 50)
    
    try:
        success = await simple_example()
        
        if success:
            print("\n✅ 示例执行成功")
        else:
            print("\n❌ 示例执行失败")
            
    except KeyboardInterrupt:
        print("\n👋 用户中断操作")
    except Exception as e:
        print(f"\n💥 程序异常: {e}")


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())
