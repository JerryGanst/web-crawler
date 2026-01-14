"""
pacong.browser - 浏览器控制模块
提供多种浏览器控制方式：Selenium、AppleScript、Chrome DevTools Protocol、跨平台RPA控制
"""

# AppleScript模块 - 无外部依赖，始终可用
from .applescript import (
    execute_applescript,
    chrome_applescript_scraper,
    chrome_start_if_needed,
    chrome_check_running
)

# 延迟导入其他模块（可能需要额外依赖）
def __getattr__(name):
    """延迟导入需要额外依赖的模块"""
    if name == 'CDPController':
        from .cdp import CDPController
        return CDPController
    elif name == 'SeleniumController':
        from .selenium_controller import SeleniumController
        return SeleniumController
    elif name in ('RPAChromeMCP', 'ControllerType', 'create_rpa_controller',
                  'quick_open_url', 'quick_execute_js'):
        from . import rpa_chrome_controller
        return getattr(rpa_chrome_controller, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    'execute_applescript',
    'chrome_applescript_scraper',
    'chrome_start_if_needed',
    'chrome_check_running',
    'CDPController',
    'SeleniumController',
    'RPAChromeMCP',
    'ControllerType',
    'create_rpa_controller',
    'quick_open_url',
    'quick_execute_js'
] 