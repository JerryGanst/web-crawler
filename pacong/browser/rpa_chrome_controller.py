"""
跨平台RPA Chrome控制器
整合AppleScript、Selenium、CDP和系统自动化功能
提供统一的跨平台浏览器控制接口
"""

import platform
import asyncio
import time
import logging
import subprocess
import shutil
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, Union
from enum import Enum

try:
    import pyautogui
except ImportError:
    pyautogui = None

from .applescript import execute_applescript
from .selenium_controller import SeleniumController
from .cdp import CDPController

logger = logging.getLogger(__name__)


class ControllerType(Enum):
    """控制器类型枚举"""
    APPLESCRIPT = "applescript"
    SELENIUM = "selenium"
    CDP = "cdp"
    AUTO_IT = "autoit"
    XDOTOOL = "xdotool"


class PlatformController(ABC):
    """平台控制器抽象基类"""
    
    @abstractmethod
    async def activate_chrome(self) -> bool:
        """激活Chrome浏览器"""
        pass
    
    @abstractmethod
    async def send_keys(self, keys: List[str]) -> bool:
        """发送组合键"""
        pass
    
    @abstractmethod
    async def send_key(self, key: str) -> bool:
        """发送单个按键"""
        pass
    
    @abstractmethod
    async def type_text(self, text: str) -> bool:
        """输入文本"""
        pass
    
    @abstractmethod
    async def execute_in_devtools(self, code: str) -> Any:
        """在开发者工具中执行代码"""
        pass


class AppleScriptController(PlatformController):
    """macOS AppleScript控制器"""
    
    def __init__(self):
        self.cdp_controller = CDPController()
    
    async def activate_chrome(self) -> bool:
        """激活Chrome浏览器"""
        script = '''
        tell application "Google Chrome"
            activate
            if (count of windows) = 0 then
                make new window
            end if
        end tell
        '''
        try:
            execute_applescript(script)
            await asyncio.sleep(0.5)
            return True
        except Exception as e:
            logger.error(f"激活Chrome失败: {e}")
            return False
    
    async def send_keys(self, keys: List[str]) -> bool:
        """发送组合键"""
        # --- 明确的按键映射 ---
        # 为了跨平台兼容性和表达清晰性：
        # - 'cmd' 和 'ctrl' 都映射到macOS的主功能键 'command'。
        # - 'control' 用于明确指定macOS的 'Control' 键。
        key_mapping = {
            'cmd': 'command',
            'ctrl': 'command',    # 便利性映射: 'ctrl' -> 'command'
            'control': 'control', # 明确性映射: 'control' -> 'control'
            'shift': 'shift',
            'alt': 'option',
            'option': 'option',
            'enter': 'return',
            'return': 'return'
        }
        
        mapped_keys = [key_mapping.get(key.lower(), key) for key in keys]
        key_combination = ' down, '.join(mapped_keys) + ' down'
        
        # AppleScript 需要一个反向的 up 序列
        up_sequence = ' up, '.join(reversed(mapped_keys)) + ' up'
        
        script = f'''
        tell application "System Events"
            key down {{{key_combination}}}
            key up {{{up_sequence}}}
        end tell
        '''
        
        try:
            execute_applescript(script)
            await asyncio.sleep(0.2)
            return True
        except Exception as e:
            logger.error(f"发送组合键失败: {e}")
            return False
    
    async def send_key(self, key: str) -> bool:
        """发送单个按键"""
        key_mapping = {
            'enter': 'return',
            'escape': 'escape',
            'tab': 'tab',
            'space': 'space'
        }
        
        mapped_key = key_mapping.get(key.lower(), key)
        
        script = f'''
        tell application "System Events"
            key code (if "{mapped_key}" = "return" then 36 else if "{mapped_key}" = "escape" then 53 else if "{mapped_key}" = "tab" then 48 else if "{mapped_key}" = "space" then 49 else 0)
        end tell
        '''
        
        try:
            execute_applescript(script)
            await asyncio.sleep(0.1)
            return True
        except Exception as e:
            logger.error(f"发送按键失败: {e}")
            return False
    
    async def type_text(self, text: str) -> bool:
        """输入文本"""
        # 转义特殊字符
        escaped_text = text.replace('"', '\\"').replace('\\', '\\\\')
        
        script = f'''
        tell application "System Events"
            keystroke "{escaped_text}"
        end tell
        '''
        
        try:
            execute_applescript(script)
            await asyncio.sleep(0.1)
            return True
        except Exception as e:
            logger.error(f"输入文本失败: {e}")
            return False
    
    async def execute_in_devtools(self, code: str) -> Any:
        """在开发者工具中执行代码"""
        try:
            # 使用CDP控制器执行
            if not self.cdp_controller.is_chrome_running():
                logger.info("启动Chrome进行CDP连接...")
                self.cdp_controller.start_chrome(headless=False)
            
            result = await self.cdp_controller.execute_js(code)
            return result
        except Exception as e:
            logger.error(f"在开发者工具执行代码失败: {e}")
            return None


class WindowsController(PlatformController):
    """
    Windows自动化控制器，使用pyautogui
    """

    def __init__(self):
        """初始化Windows控制器，检查pyautogui是否安装"""
        self.cdp_controller = CDPController()
        if not pyautogui:
            logger.error("pyautogui is not installed. Please run 'pip install pyautogui' to use WindowsController.")
            raise ImportError("pyautogui is required for WindowsController.")

    async def activate_chrome(self) -> bool:
        """激活Chrome浏览器"""
        try:
            # 查找所有Chrome窗口
            chrome_windows = [win for win in pyautogui.getWindowsWithTitle("Google Chrome") if win.title.endswith("Google Chrome")]
            if chrome_windows:
                # 激活第一个找到的窗口
                window = chrome_windows[0]
                if not window.isActive:
                    window.activate()
                logger.info(f"Activated existing Chrome window: {window.title}")
                await asyncio.sleep(0.5)
                return True
            else:
                # 如果没有找到窗口，则启动新窗口
                logger.info("No active Chrome window found, launching a new one.")
                subprocess.Popen("start chrome", shell=True)
                await asyncio.sleep(2)  # 等待浏览器启动
                return True
        except Exception as e:
            logger.error(f"Failed to activate or launch Chrome on Windows: {e}")
            return False

    async def send_keys(self, keys: List[str]) -> bool:
        """发送组合键"""
        # --- 明确的按键映射 ---
        # 别名 'cmd' 和 'control' 都映射到Windows的主功能键 'ctrl'。
        # 'win' 键用于访问Windows徽标键。
        key_mapping = {
            'cmd': 'ctrl',      # 便利性映射
            'control': 'ctrl',    # 便利性映射
            'ctrl': 'ctrl',
            'win': 'win',
            'shift': 'shift',
            'alt': 'alt'
        }
        # pyautogui使用单独的函数处理组合键
        modifier_keys = [key_mapping.get(key.lower()) for key in keys if key.lower() in key_mapping]
        character_keys = [key for key in keys if key.lower() not in key_mapping]
        
        try:
            for key in modifier_keys:
                if key: pyautogui.keyDown(key)
            
            for key in character_keys:
                pyautogui.press(key)

            for key in reversed(modifier_keys):
                if key: pyautogui.keyUp(key)
                
            await asyncio.sleep(0.1)
            return True
        except Exception as e:
            logger.error(f"Failed to send keys on Windows: {e}")
            return False

    async def send_key(self, key: str) -> bool:
        """发送单个按键"""
        try:
            pyautogui.press(key)
            await asyncio.sleep(0.1)
            return True
        except Exception as e:
            logger.error(f"Failed to send key '{key}' on Windows: {e}")
            return False

    async def type_text(self, text: str) -> bool:
        """输入文本"""
        try:
            pyautogui.typewrite(text, interval=0.01)
            await asyncio.sleep(0.1)
            return True
        except Exception as e:
            logger.error(f"Failed to type text on Windows: {e}")
            return False

    async def execute_in_devtools(self, code: str) -> Any:
        """在开发者工具中执行代码（通过CDP）"""
        try:
            if not self.cdp_controller.is_chrome_running():
                logger.info("Starting Chrome for CDP connection...")
                self.cdp_controller.start_chrome(headless=False)
            
            result = await self.cdp_controller.execute_js(code)
            return result
        except Exception as e:
            logger.error(f"Failed to execute code in DevTools on Windows: {e}")
            return None


class LinuxController(PlatformController):
    """Linux自动化控制器，使用xdotool"""
    
    def __init__(self):
        """初始化Linux控制器，检查xdotool是否存在"""
        self.cdp_controller = CDPController()
        if not shutil.which("xdotool"):
            logger.error("xdotool not found. Please install it using 'sudo apt-get install xdotool' or similar command for your distribution.")
            raise EnvironmentError("xdotool is required for LinuxController.")

    def _run_command(self, command: list) -> bool:
        """执行shell命令"""
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True)
            logger.debug(f"Executed xdotool command: {' '.join(command)}. Output: {result.stdout}")
            return True
        except FileNotFoundError:
            logger.error(f"Command not found: {command[0]}. Is it installed and in your PATH?")
            return False
        except subprocess.CalledProcessError as e:
            logger.error(f"Command failed: {' '.join(command)}. Error: {e.stderr}")
            return False
        except Exception as e:
            logger.error(f"An unexpected error occurred while running command: {' '.join(command)}. Error: {e}")
            return False

    async def activate_chrome(self) -> bool:
        """激活Chrome浏览器"""
        # 尝试激活现有窗口
        script = "search --onlyvisible --class google-chrome windowactivate"
        try:
            # 尝试使用xdotool激活窗口
            subprocess.run(["xdotool"] + script.split(), check=True, capture_output=True, text=True)
            logger.info("Activated existing Chrome window.")
            await asyncio.sleep(0.5)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            # 如果窗口不存在或xdotool命令失败，则尝试启动新窗口
            logger.info("No active Chrome window found or xdotool failed, launching a new one.")
            
            # 尝试常见的浏览器可执行文件
            chrome_executables = ["google-chrome", "google-chrome-stable", "chromium-browser"]
            for executable in chrome_executables:
                if shutil.which(executable):
                    try:
                        subprocess.Popen([executable, "--new-window"], start_new_session=True)
                        await asyncio.sleep(2)  # 等待浏览器启动
                        logger.info(f"Launched Chrome using '{executable}'.")
                        return True
                    except Exception as e:
                        logger.warning(f"Failed to launch Chrome with '{executable}': {e}")
                        continue
            
            logger.error(f"Could not find or launch any of a known Chrome executable: {chrome_executables}")
            return False

    async def send_keys(self, keys: List[str]) -> bool:
        """发送组合键"""
        # 确保跨平台的 'cmd' 和 'control' 键在Linux上被映射为 'ctrl'
        mapped_keys = ['ctrl' if key.lower() in ('cmd', 'control') else key for key in keys]
        key_combination = '+'.join(mapped_keys)
        command = ["xdotool", "key", key_combination]
        return self._run_command(command)

    async def send_key(self, key: str) -> bool:
        """发送单个按键"""
        key_mapping = {
            'enter': 'Return',
            'escape': 'Escape',
            'tab': 'Tab',
            'space': 'space'
        }
        mapped_key = key_mapping.get(key.lower(), key)
        command = ["xdotool", "key", mapped_key]
        return self._run_command(command)

    async def type_text(self, text: str) -> bool:
        """输入文本"""
        command = ["xdotool", "type", text]
        return self._run_command(command)

    async def execute_in_devtools(self, code: str) -> Any:
        """在开发者工具中执行代码（通过CDP）"""
        try:
            # 逻辑与AppleScriptController完全相同，依赖CDPController
            if not self.cdp_controller.is_chrome_running():
                logger.info("Starting Chrome for CDP connection...")
                self.cdp_controller.start_chrome(headless=False)
            
            result = await self.cdp_controller.execute_js(code)
            return result
        except Exception as e:
            logger.error(f"Failed to execute code in DevTools: {e}")
            return None


class RPAChromeMCP:
    """跨平台RPA Chrome控制器"""
    
    def __init__(self, controller_type: Optional[ControllerType] = None):
        """
        初始化RPA控制器
        
        Args:
            controller_type: 指定控制器类型，如果为None则自动选择
        """
        self.platform = platform.system().lower()
        self.controller_type = controller_type
        self.controller: PlatformController = self._create_controller()
        
        # 定义平台特定的快捷键
        self.meta_key = 'cmd' if self.platform == 'darwin' else 'ctrl'
        
        logger.info(f"初始化RPA控制器 - 平台: {self.platform}, 控制器: {type(self.controller).__name__}")
    
    def _create_controller(self) -> PlatformController:
        """创建平台控制器"""
        if self.controller_type:
            # 使用指定的控制器类型
            if self.controller_type == ControllerType.APPLESCRIPT:
                return AppleScriptController()
            elif self.controller_type == ControllerType.AUTO_IT:
                return WindowsController()
            elif self.controller_type == ControllerType.XDOTOOL:
                return LinuxController()
        
        # 根据平台自动选择最佳控制器
        if self.platform == 'darwin':  # macOS
            return AppleScriptController()
        elif self.platform == 'windows':
            return WindowsController()
        elif self.platform == 'linux':
            return LinuxController()
        else:
            logger.warning(f"不支持的平台: {self.platform}，使用默认AppleScript控制器")
            return AppleScriptController()
    
    async def open_url(self, url: str) -> bool:
        """
        打开URL
        
        Args:
            url: 要打开的URL
            
        Returns:
            bool: 是否成功
        """
        try:
            logger.info(f"打开URL: {url}")
            
            # 激活Chrome
            if not await self.controller.activate_chrome():
                logger.error("无法激活Chrome浏览器")
                return False
            
            # 打开地址栏 (Cmd+L / Ctrl+L) - 使用平台特定的meta_key
            if not await self.controller.send_keys([self.meta_key, 'l']):
                logger.error("无法打开地址栏")
                return False
            
            await asyncio.sleep(0.3)
            
            # 输入URL
            if not await self.controller.type_text(url):
                logger.error("无法输入URL")
                return False
            
            await asyncio.sleep(0.2)
            
            # 按回车
            if not await self.controller.send_key('enter'):
                logger.error("无法按回车键")
                return False
            
            logger.info("成功打开URL")
            return True
            
        except Exception as e:
            logger.error(f"打开URL失败: {e}")
            return False
    
    async def execute_in_devtools(self, code: str) -> Any:
        """
        在开发者工具中执行代码
        
        Args:
            code: 要执行的JavaScript代码
            
        Returns:
            Any: 执行结果
        """
        try:
            logger.info("在开发者工具中执行代码")
            
            # 确保Chrome已激活
            await self.controller.activate_chrome()
            
            # 打开开发者工具 (Cmd+Shift+J / Ctrl+Shift+J) - 使用平台特定的meta_key
            if not await self.controller.send_keys([self.meta_key, 'shift', 'j']):
                logger.error("无法打开开发者工具")
                return None
            
            await asyncio.sleep(1.0)  # 等待开发者工具加载
            
            # 执行代码
            result = await self.controller.execute_in_devtools(code)
            return result
            
        except Exception as e:
            logger.error(f"在开发者工具执行代码失败: {e}")
            return None
    
    async def sleep(self, seconds: float) -> None:
        """等待指定时间"""
        await asyncio.sleep(seconds)
    
    async def get_page_content(self) -> Optional[str]:
        """获取页面内容"""
        code = "document.documentElement.outerHTML"
        return await self.execute_in_devtools(code)
    
    async def click_element(self, selector: str) -> bool:
        """点击元素"""
        code = f"""
        const element = document.querySelector('{selector}');
        if (element) {{
            element.click();
            true;
        }} else {{
            false;
        }}
        """
        result = await self.execute_in_devtools(code)
        return bool(result)
    
    async def get_element_text(self, selector: str) -> Optional[str]:
        """获取元素文本"""
        code = f"""
        const element = document.querySelector('{selector}');
        element ? element.textContent : null;
        """
        return await self.execute_in_devtools(code)
    
    async def scroll_to_bottom(self) -> bool:
        """滚动到页面底部"""
        code = "window.scrollTo(0, document.body.scrollHeight); true;"
        result = await self.execute_in_devtools(code)
        return bool(result)
    
    async def wait_for_element(self, selector: str, timeout: int = 10) -> bool:
        """等待元素出现"""
        code = f"""
        new Promise((resolve) => {{
            const check = () => {{
                const element = document.querySelector('{selector}');
                if (element) {{
                    resolve(true);
                }} else {{
                    setTimeout(check, 100);
                }}
            }};
            check();
            setTimeout(() => resolve(false), {timeout * 1000});
        }});
        """
        result = await self.execute_in_devtools(code)
        return bool(result)


# 便捷函数
async def create_rpa_controller(controller_type: Optional[ControllerType] = None) -> RPAChromeMCP:
    """创建RPA控制器实例"""
    return RPAChromeMCP(controller_type)


async def quick_open_url(url: str) -> bool:
    """快速打开URL"""
    controller = await create_rpa_controller()
    return await controller.open_url(url)


async def quick_execute_js(code: str) -> Any:
    """快速执行JavaScript代码"""
    controller = await create_rpa_controller()
    return await controller.execute_in_devtools(code)


# 使用示例
if __name__ == "__main__":
    async def main():
        # 创建RPA控制器
        rpa = RPAChromeMCP()
        
        # 打开网页
        success = await rpa.open_url("https://www.google.com")
        if success:
            print("✅ 成功打开Google")
            
            # 等待页面加载
            await rpa.sleep(2)
            
            # 获取页面标题
            title = await rpa.execute_in_devtools("document.title")
            print(f"📄 页面标题: {title}")
            
            # 点击搜索框
            await rpa.click_element('input[name="q"]')
            
            # 输入搜索内容
            await rpa.controller.type_text("Python RPA自动化")
            
            # 按回车搜索
            await rpa.controller.send_key('enter')
            
            print("🔍 完成搜索")
        else:
            print("❌ 打开网页失败")
    
    # 运行示例
    asyncio.run(main())
