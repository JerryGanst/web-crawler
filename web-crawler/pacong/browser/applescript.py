"""
AppleScript浏览器控制模块
提供通过AppleScript控制Chrome浏览器的功能
"""

import subprocess
import time
import logging
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def execute_applescript(script: str, timeout: int = 60) -> str:
    """
    执行AppleScript脚本并返回输出
    
    Args:
        script: AppleScript脚本内容
        timeout: 超时时间（秒）
        
    Returns:
        str: 脚本执行结果
        
    Raises:
        subprocess.CalledProcessError: 脚本执行失败
        subprocess.TimeoutExpired: 执行超时
    """
    try:
        process = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            check=True,
            timeout=timeout
        )
        
        if process.stderr:
            logger.warning(f"AppleScript警告: {process.stderr}")
            
        return process.stdout.strip()
        
    except subprocess.CalledProcessError as e:
        logger.error(f"AppleScript执行失败: {e.stderr}")
        
        # 检查常见错误
        if '(-1743)' in e.stderr or 'not allowed assistive access' in e.stderr:
            logger.error("权限错误：需要自动化权限。请在系统设置 > 隐私与安全 > 自动化中授权。")
        elif '(-600)' in e.stderr or "application isn't running" in e.stderr:
            logger.error("Google Chrome未运行。请先启动Chrome浏览器。")
            
        raise
        
    except subprocess.TimeoutExpired:
        logger.error(f"AppleScript执行超时（{timeout}秒）")
        raise
        
    except Exception as e:
        logger.error(f"AppleScript执行异常: {e}")
        raise


def chrome_applescript_scraper(url: str, wait_seconds: int = 15, scroll_times: int = 3) -> str:
    """
    使用AppleScript控制Chrome获取页面内容
    
    Args:
        url: 目标URL
        wait_seconds: 等待页面加载的时间
        scroll_times: 滚动次数
        
    Returns:
        str: 页面HTML内容
    """
    try:
        logger.info(f"使用AppleScript打开URL: {url}")
        
        # 1. 打开URL
        open_script = f'tell application "Google Chrome" to open location "{url}"'
        execute_applescript(open_script)
        
        # 2. 调整窗口大小（最小化干扰）
        time.sleep(2)
        logger.info("调整Chrome窗口大小...")
        
        try:
            resize_script = '''
            tell application "Finder" to get bounds of window of desktop
            set screenDimensions to the result
            set screenWidth to item 3 of screenDimensions
            set screenHeight to item 4 of screenDimensions
            
            tell application "Google Chrome"
                activate
                try
                    set bounds of front window to {screenWidth - 1, screenHeight - 1, screenWidth, screenHeight}
                on error
                    set bounds of front window to {100, 100, 101, 101}
                end try
            end tell
            '''
            execute_applescript(resize_script)
            logger.info("窗口大小调整完成")
            
        except Exception as e:
            logger.warning(f"窗口调整失败，继续使用默认窗口: {e}")
        
        # 3. 等待页面加载
        logger.info(f"等待页面加载 ({wait_seconds}秒)...")
        time.sleep(wait_seconds)
        
        # 4. 滚动页面加载所有数据
        if scroll_times > 0:
            logger.info(f"滚动页面加载完整数据...")
            
            try:
                for i in range(scroll_times):
                    scroll_script = '''
                    tell application "Google Chrome" 
                        execute active tab of front window javascript "window.scrollBy(0, window.innerHeight);"
                    end tell
                    '''
                    execute_applescript(scroll_script)
                    logger.info(f"第 {i+1}/{scroll_times} 次滚动完成")
                    time.sleep(2)
                
                logger.info("再等待5秒确保数据加载完毕...")
                time.sleep(5)
                
            except Exception as e:
                logger.warning(f"滚动失败，可能只获取到部分数据: {e}")
        
        # 5. 获取页面HTML
        logger.info("获取页面HTML内容...")
        get_html_script = '''
        tell application "Google Chrome" 
            execute active tab of front window javascript "document.documentElement.outerHTML"
        end tell
        '''
        html_content = execute_applescript(get_html_script)
        
        if not html_content:
            logger.error("未能获取到HTML内容")
            return ""
        
        logger.info(f"成功获取 {len(html_content)} 字节的HTML内容")
        return html_content
        
    except Exception as e:
        logger.error(f"AppleScript爬取失败: {e}")
        return ""


def chrome_get_page_data(url: str, javascript_code: str) -> str:
    """
    使用AppleScript控制Chrome执行JavaScript并获取结果
    
    Args:
        url: 目标URL
        javascript_code: 要执行的JavaScript代码
        
    Returns:
        str: JavaScript执行结果
    """
    try:
        # 导航到URL
        navigate_script = f'''
        tell application "Google Chrome"
            if not (exists window 1) then
                make new window
            end if
            set URL of active tab of front window to "{url}"
        end tell
        '''
        execute_applescript(navigate_script)
        
        # 等待页面加载
        time.sleep(10)
        
        # 执行JavaScript
        js_script = f'''
        tell application "Google Chrome"
            execute active tab of front window javascript "{javascript_code}"
        end tell
        '''
        
        result = execute_applescript(js_script)
        return result
        
    except Exception as e:
        logger.error(f"执行JavaScript失败: {e}")
        return ""


def chrome_check_running() -> bool:
    """
    检查Chrome是否正在运行
    
    Returns:
        bool: Chrome是否运行
    """
    try:
        check_script = '''
        tell application "System Events"
            exists (processes where name is "Google Chrome")
        end tell
        '''
        result = execute_applescript(check_script)
        return result.lower() == 'true'
        
    except Exception:
        return False


def chrome_start_if_needed() -> bool:
    """
    如果Chrome未运行则启动它
    
    Returns:
        bool: 是否成功启动或Chrome已在运行
    """
    try:
        if chrome_check_running():
            logger.info("Chrome已在运行")
            return True
        
        logger.info("启动Chrome浏览器...")
        start_script = 'tell application "Google Chrome" to activate'
        execute_applescript(start_script)
        
        # 等待Chrome启动
        time.sleep(3)
        
        return chrome_check_running()
        
    except Exception as e:
        logger.error(f"启动Chrome失败: {e}")
        return False 