"""
Selenium浏览器控制器
提供通过Selenium WebDriver控制浏览器的功能
"""

import time
import logging
from typing import Optional, List
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException

logger = logging.getLogger(__name__)


class SeleniumController:
    """Selenium浏览器控制器"""
    
    def __init__(self, browser_type: str = 'chrome', headless: bool = True):
        self.browser_type = browser_type
        self.headless = headless
        self.driver = None
    
    def setup_driver(self):
        """设置WebDriver"""
        try:
            if self.browser_type.lower() == 'chrome':
                self._setup_chrome_driver()
            else:
                raise WebDriverException(f"不支持的浏览器类型: {self.browser_type}")
                
        except ImportError as e:
            logger.error(f"缺少必要的Selenium库: {e}")
            logger.error("请安装: pip install undetected-chromedriver selenium")
            raise
        except Exception as e:
            logger.error(f"WebDriver初始化失败: {e}")
            raise
    
    def _setup_chrome_driver(self):
        """设置Chrome驱动"""
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.chrome.options import Options
            
            options = Options()
            
            if self.headless:
                options.add_argument("--headless")
            
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            self.driver = uc.Chrome(options=options)
            self.driver.set_page_load_timeout(60)
            self.driver.implicitly_wait(10)
            
            logger.info("Chrome WebDriver已初始化")
            
        except ImportError:
            logger.error("需要安装 undetected-chromedriver: pip install undetected-chromedriver")
            raise
    
    def get_page(self, url: str, wait_for_element: Optional[tuple] = None, wait_timeout: int = 20) -> str:
        """
        获取页面内容
        
        Args:
            url: 目标URL
            wait_for_element: 等待的元素 (By.ID, "element_id")
            wait_timeout: 等待超时时间
            
        Returns:
            str: 页面HTML内容
        """
        if not self.driver:
            self.setup_driver()
        
        try:
            logger.info(f"正在访问: {url}")
            self.driver.get(url)
            
            if wait_for_element:
                logger.info(f"等待元素出现: {wait_for_element}")
                WebDriverWait(self.driver, wait_timeout).until(
                    EC.presence_of_element_located(wait_for_element)
                )
            else:
                # 默认等待页面加载
                time.sleep(5)
            
            return self.driver.page_source
            
        except TimeoutException:
            logger.error(f"等待元素 {wait_for_element} 超时")
            return self.driver.page_source  # 返回当前内容
        except Exception as e:
            logger.error(f"获取页面失败: {e}")
            return ""
    
    def scroll_page(self, times: int = 3, pause: float = 2.0):
        """
        滚动页面
        
        Args:
            times: 滚动次数
            pause: 每次滚动后的暂停时间
        """
        if not self.driver:
            logger.error("WebDriver未初始化")
            return
        
        try:
            for i in range(times):
                self.driver.execute_script("window.scrollBy(0, window.innerHeight);")
                logger.info(f"第 {i+1}/{times} 次滚动完成")
                time.sleep(pause)
                
        except Exception as e:
            logger.error(f"滚动页面失败: {e}")
    
    def execute_script(self, script: str):
        """
        执行JavaScript脚本
        
        Args:
            script: JavaScript代码
            
        Returns:
            Any: 执行结果
        """
        if not self.driver:
            logger.error("WebDriver未初始化")
            return None
        
        try:
            return self.driver.execute_script(script)
        except Exception as e:
            logger.error(f"执行JavaScript失败: {e}")
            return None
    
    def find_elements(self, by: By, value: str) -> List:
        """
        查找页面元素
        
        Args:
            by: 查找方式
            value: 查找值
            
        Returns:
            List: 找到的元素列表
        """
        if not self.driver:
            logger.error("WebDriver未初始化")
            return []
        
        try:
            return self.driver.find_elements(by, value)
        except Exception as e:
            logger.error(f"查找元素失败: {e}")
            return []
    
    def wait_for_element(self, by: By, value: str, timeout: int = 20):
        """
        等待元素出现
        
        Args:
            by: 查找方式
            value: 查找值
            timeout: 超时时间
            
        Returns:
            WebElement: 找到的元素
        """
        if not self.driver:
            logger.error("WebDriver未初始化")
            return None
        
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            return element
        except TimeoutException:
            logger.error(f"等待元素超时: {by}, {value}")
            return None
        except Exception as e:
            logger.error(f"等待元素失败: {e}")
            return None
    
    def close(self):
        """关闭浏览器"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver已关闭")
            except:
                pass
            finally:
                self.driver = None


def scrape_with_selenium(url: str, 
                        wait_for_element: Optional[tuple] = None,
                        scroll_times: int = 3,
                        headless: bool = True) -> str:
    """
    使用Selenium抓取页面的便捷函数
    
    Args:
        url: 目标URL
        wait_for_element: 等待的元素
        scroll_times: 滚动次数
        headless: 是否无头模式
        
    Returns:
        str: 页面HTML内容
    """
    controller = SeleniumController(headless=headless)
    
    try:
        # 获取页面内容
        html_content = controller.get_page(url, wait_for_element)
        
        # 滚动页面
        if scroll_times > 0:
            controller.scroll_page(scroll_times)
            time.sleep(3)  # 等待内容加载
            html_content = controller.driver.page_source
        
        return html_content
        
    finally:
        # 清理资源
        controller.close() 