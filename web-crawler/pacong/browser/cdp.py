"""
Chrome DevTools Protocol (CDP) 控制器
提供通过CDP协议控制Chrome浏览器的功能
"""

import asyncio
import json
import requests
import websockets
import subprocess
import tempfile
import shutil
import logging
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class CDPController:
    """Chrome DevTools Protocol控制器"""
    
    def __init__(self, debug_port: int = 9222, chrome_path: Optional[str] = None):
        self.debug_port = debug_port
        self.chrome_path = chrome_path or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        self.base_url = f"http://localhost:{debug_port}"
        self.chrome_process = None
        self.temp_dir = None
        
    def start_chrome(self, headless: bool = True) -> bool:
        """
        启动Chrome浏览器
        
        Args:
            headless: 是否无头模式
            
        Returns:
            bool: 是否启动成功
        """
        try:
            if self.is_chrome_running():
                logger.info("Chrome调试端口已在运行")
                return True
            
            self.temp_dir = tempfile.mkdtemp()
            
            command = [
                self.chrome_path,
                f"--remote-debugging-port={self.debug_port}",
                f"--user-data-dir={self.temp_dir}",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
            
            if headless:
                command.append("--headless")
            
            logger.info("启动Chrome浏览器...")
            self.chrome_process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # 等待Chrome启动
            max_wait_seconds = 15
            for i in range(max_wait_seconds):
                if self.is_chrome_running():
                    logger.info("Chrome调试端口已就绪")
                    return True
                import time
                time.sleep(1)
            
            logger.error(f"在 {max_wait_seconds} 秒内无法连接到Chrome调试端口")
            return False
            
        except Exception as e:
            logger.error(f"启动Chrome失败: {e}")
            return False
    
    def is_chrome_running(self) -> bool:
        """
        检查Chrome调试端口是否可用
        
        Returns:
            bool: 是否可用
        """
        try:
            response = requests.get(f"{self.base_url}/json/version", timeout=1)
            return response.status_code == 200
        except:
            return False
    
    def stop_chrome(self):
        """停止Chrome浏览器"""
        if self.chrome_process:
            logger.info("终止Chrome进程...")
            self.chrome_process.terminate()
            self.chrome_process.wait()
            self.chrome_process = None
        
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)
            logger.info("清理临时目录")
    
    async def scrape_page(self, url: str, wait_seconds: int = 15) -> str:
        """
        使用CDP抓取页面内容
        
        Args:
            url: 目标URL
            wait_seconds: 等待时间
            
        Returns:
            str: 页面HTML内容
        """
        tab = None
        try:
            # 创建新标签页
            response = requests.put(f"{self.base_url}/json/new")
            response.raise_for_status()
            tab = response.json()
            ws_url = tab['webSocketDebuggerUrl']
            
            logger.info(f"新标签页已创建: {tab['id']}")
            
            async with websockets.connect(ws_url, max_size=None) as websocket:
                # 启用Page和Runtime域
                await websocket.send(json.dumps({"id": 1, "method": "Page.enable"}))
                await websocket.send(json.dumps({"id": 2, "method": "Runtime.enable"}))
                await websocket.recv()  # ack 1
                await websocket.recv()  # ack 2

                # 导航到URL
                logger.info(f"正在导航到: {url}")
                await websocket.send(json.dumps({
                    "id": 3, 
                    "method": "Page.navigate", 
                    "params": {"url": url}
                }))

                # 等待页面加载事件
                load_event_received = False
                while not load_event_received:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                        data = json.loads(message)
                        if data.get("method") == "Page.loadEventFired":
                            load_event_received = True
                            logger.info("页面初始加载事件已触发")
                    except asyncio.TimeoutError:
                        logger.warning("等待页面加载事件超时，继续...")
                        break

                # 等待动态内容加载
                logger.info(f"等待 {wait_seconds} 秒让动态内容加载...")
                await asyncio.sleep(wait_seconds)

                # 获取页面HTML
                logger.info("获取页面HTML内容...")
                await websocket.send(json.dumps({
                    "id": 4, 
                    "method": "Runtime.evaluate",
                    "params": {"expression": "document.documentElement.outerHTML"}
                }))

                html_content = ""
                while True:
                    response = await websocket.recv()
                    data = json.loads(response)
                    if data.get('id') == 4 and 'result' in data:
                        html_content = data['result']['result'].get('value', '')
                        logger.info(f"成功获取 {len(html_content)} 字节的HTML内容")
                        break

                return html_content

        except Exception as e:
            logger.error(f"CDP抓取失败: {e}")
            return ""
            
        finally:
            # 关闭标签页
            if tab and tab.get('id'):
                try:
                    requests.delete(f"{self.base_url}/json/close/{tab['id']}")
                    logger.info(f"已关闭标签页: {tab['id']}")
                except:
                    pass
    
    async def execute_javascript(self, tab_id: str, js_code: str) -> Any:
        """
        在指定标签页执行JavaScript
        
        Args:
            tab_id: 标签页ID
            js_code: JavaScript代码
            
        Returns:
            Any: 执行结果
        """
        try:
            # 获取WebSocket URL
            response = requests.get(f"{self.base_url}/json")
            tabs = response.json()
            
            target_tab = None
            for tab in tabs:
                if tab['id'] == tab_id:
                    target_tab = tab
                    break
            
            if not target_tab:
                logger.error(f"未找到标签页: {tab_id}")
                return None
            
            async with websockets.connect(target_tab['webSocketDebuggerUrl']) as websocket:
                await websocket.send(json.dumps({
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {"expression": js_code}
                }))
                
                response = await websocket.recv()
                data = json.loads(response)
                
                if 'result' in data and 'result' in data['result']:
                    return data['result']['result'].get('value')
                
        except Exception as e:
            logger.error(f"执行JavaScript失败: {e}")
            
        return None
    
    def get_tabs(self) -> list:
        """
        获取所有标签页列表
        
        Returns:
            list: 标签页信息列表
        """
        try:
            response = requests.get(f"{self.base_url}/json")
            return response.json()
        except Exception as e:
            logger.error(f"获取标签页列表失败: {e}")
            return []
    
    def create_tab(self, url: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        创建新标签页
        
        Args:
            url: 可选的初始URL
            
        Returns:
            Dict: 标签页信息
        """
        try:
            endpoint = f"{self.base_url}/json/new"
            if url:
                endpoint += f"?{url}"
            
            response = requests.put(endpoint)
            response.raise_for_status()
            
            tab_info = response.json()
            logger.info(f"创建新标签页: {tab_info['id']}")
            return tab_info
            
        except Exception as e:
            logger.error(f"创建标签页失败: {e}")
            return None
    
    def close_tab(self, tab_id: str) -> bool:
        """
        关闭指定标签页
        
        Args:
            tab_id: 标签页ID
            
        Returns:
            bool: 是否成功关闭
        """
        try:
            response = requests.delete(f"{self.base_url}/json/close/{tab_id}")
            success = response.status_code == 200
            if success:
                logger.info(f"已关闭标签页: {tab_id}")
            return success
            
        except Exception as e:
            logger.error(f"关闭标签页失败: {e}")
            return False


async def scrape_with_cdp(url: str, wait_seconds: int = 15, headless: bool = True) -> str:
    """
    使用CDP抓取页面的便捷函数
    
    Args:
        url: 目标URL
        wait_seconds: 等待时间
        headless: 是否无头模式
        
    Returns:
        str: 页面HTML内容
    """
    controller = CDPController()
    
    try:
        # 启动Chrome
        if not await controller.start_chrome(headless=headless):
            logger.error("无法启动Chrome")
            return ""
        
        # 抓取页面
        html_content = await controller.scrape_page(url, wait_seconds)
        return html_content
        
    finally:
        # 清理资源
        controller.stop_chrome() 