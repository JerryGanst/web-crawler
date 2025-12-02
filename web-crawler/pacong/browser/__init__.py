"""
pacong.browser - 浏览器控制模块
提供多种浏览器控制方式：Selenium、AppleScript、Chrome DevTools Protocol、跨平台RPA控制
"""

from .applescript import execute_applescript, chrome_applescript_scraper
from .cdp import CDPController
from .selenium_controller import SeleniumController
from .rpa_chrome_controller import (
    RPAChromeMCP, 
    ControllerType, 
    create_rpa_controller,
    quick_open_url,
    quick_execute_js
)

__all__ = [
    'execute_applescript',
    'chrome_applescript_scraper', 
    'CDPController',
    'SeleniumController',
    'RPAChromeMCP',
    'ControllerType',
    'create_rpa_controller',
    'quick_open_url',
    'quick_execute_js'
] 