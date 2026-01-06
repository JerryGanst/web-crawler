"""
新浪财经爬虫
集成多种API策略和AppleScript方法获取外汇数据
"""

import re
import json
import subprocess
from typing import List, Dict, Any
from datetime import datetime

from ..core import BaseScraper, WebScrapingMixin, BrowserScrapingMixin
from ..data import ForexData


class SinaFinanceScraper(BaseScraper, WebScrapingMixin, BrowserScrapingMixin):
    """新浪财经外汇数据爬虫"""
    
    def __init__(self, **kwargs):
        super().__init__("sina_finance", **kwargs)
        self.base_url = "https://finance.sina.com.cn/money/forex/hq/CNYTWD.shtml"
        
        # API变体列表
        self.api_variants = [
            "https://hq.sinajs.cn/list=fx_scnytwd",
            "http://hq.sinajs.cn/list=fx_scnytwd", 
            "https://hq.sinajs.cn/?list=fx_scnytwd",
            "https://hq.sinajs.cn/rn=1234567890&list=fx_scnytwd",
            "https://vip.stock.finance.sina.com.cn/forex/api/jsonp.php/var%20_fx_scnytwd=/ForexService.getForexPrice?symbol=fx_scnytwd",
        ]
    
    def get_data_sources(self) -> List[Dict[str, str]]:
        """获取数据源列表"""
        sources = []
        
        # API数据源
        for i, api_url in enumerate(self.api_variants):
            sources.append({
                "name": f"sina_api_{i+1}",
                "url": api_url,
                "type": "api"
            })
        
        # 网页数据源
        sources.append({
            "name": "sina_webpage",
            "url": self.base_url,
            "type": "webpage"
        })
        
        return sources
    
    def scrape_single_source(self, source: Dict[str, str]) -> List[Dict[str, Any]]:
        """爬取单个数据源"""
        if source["type"] == "api":
            return self._scrape_api(source["url"])
        elif source["type"] == "webpage":
            return self._scrape_webpage(source["url"])
        else:
            return []
    
    def _scrape_api(self, api_url: str) -> List[Dict[str, Any]]:
        """通过API获取数据"""
        try:
            self.logger.info(f"正在测试API: {api_url}")
            
            # 增强请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Connection': 'keep-alive',
                'Referer': 'https://finance.sina.com.cn/money/forex/',
                'X-Requested-With': 'XMLHttpRequest'
            }
            
            response = self.make_request(api_url, headers=headers)
            
            if response and response.status_code == 200 and response.text.strip():
                self.logger.info(f"API响应成功: {len(response.text)} 字符")
                
                # 解析API响应
                parsed_data = self._parse_hq_response(response.text)
                if parsed_data:
                    return [parsed_data]
            
        except Exception as e:
            self.logger.warning(f"API {api_url} 失败: {e}")
        
        return []
    
    def _scrape_webpage(self, url: str) -> List[Dict[str, Any]]:
        """通过AppleScript控制浏览器获取网页数据"""
        try:
            self.logger.info("使用AppleScript方法获取网页数据")
            
            applescript = f'''
            tell application "Google Chrome"
                if not (exists window 1) then
                    make new window
                end if
                
                set URL of active tab of front window to "{url}"
                delay 10
                
                set pageSource to execute active tab of front window javascript "
                    var attempts = 0;
                    var maxAttempts = 50;
                    
                    function waitForData() {{
                        attempts++;
                        
                        var priceElement = document.querySelector('.price h5');
                        if (priceElement && priceElement.textContent.trim()) {{
                            return JSON.stringify({{
                                price: priceElement.textContent.trim(),
                                title: document.title,
                                found: true
                            }});
                        }}
                        
                        if (attempts < maxAttempts) {{
                            setTimeout(waitForData, 200);
                            return '';
                        }} else {{
                            return JSON.stringify({{found: false, attempts: attempts}});
                        }}
                    }}
                    
                    waitForData();
                "
                
                return pageSource
            end tell
            '''
            
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0 and result.stdout.strip():
                self.logger.info("AppleScript成功获取数据")
                
                try:
                    data = json.loads(result.stdout.strip())
                    if data.get('found'):
                        return [{
                            'currency_pair': 'CNY/TWD',
                            'current_price': float(data.get('price', '').replace(',', '')),
                            'source': 'applescript_chrome',
                            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }]
                except json.JSONDecodeError:
                    # 直接数据
                    return [{
                        'raw_data': result.stdout.strip(),
                        'source': 'applescript_chrome',
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }]
            else:
                self.logger.warning(f"AppleScript失败: {result.stderr}")
                
        except Exception as e:
            self.logger.error(f"AppleScript方法失败: {e}")
        
        return []
    
    def _parse_hq_response(self, response_text: str) -> Dict[str, Any]:
        """解析新浪行情API响应"""
        try:
            # 新浪行情API格式：var hq_str_fx_scnytwd="人民币新台币,0.2313,0.2314,0.2313,2024-01-22,15:30:00";
            pattern = r'var\s+hq_str_[^=]+=\s*"([^"]+)"'
            match = re.search(pattern, response_text)
            
            if match:
                data_str = match.group(1)
                parts = data_str.split(',')
                
                if len(parts) >= 6:
                    return {
                        'currency_pair': parts[0],
                        'bid_price': float(parts[1]) if parts[1] else 0.0,
                        'ask_price': float(parts[2]) if parts[2] else 0.0,
                        'current_price': float(parts[3]) if parts[3] else 0.0,
                        'date': parts[4],
                        'time': parts[5],
                        'source': 'sina_hq_api',
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
        except Exception as e:
            self.logger.error(f"解析行情数据失败: {e}")
        
        return None
    
    def validate_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """验证数据"""
        valid_data = []
        
        for item in data:
            # 检查必需字段
            if 'currency_pair' in item and 'timestamp' in item:
                # 验证价格数据
                if 'current_price' in item and item['current_price'] > 0:
                    valid_data.append(item)
                elif 'bid_price' in item and item['bid_price'] > 0:
                    valid_data.append(item)
                elif 'raw_data' in item:  # 原始数据也保留
                    valid_data.append(item)
        
        return valid_data
    
    def clean_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """清理数据"""
        cleaned_data = []
        
        for item in data:
            # 统一字段名
            cleaned_item = {
                'currency_pair': item.get('currency_pair', 'CNY/TWD'),
                'chinese_name': '人民币兑新台币',
                'bid_price': item.get('bid_price', 0.0),
                'ask_price': item.get('ask_price', 0.0),
                'current_price': item.get('current_price', 0.0),
                'date': item.get('date', ''),
                'time': item.get('time', ''),
                'source': item.get('source', 'sina_finance'),
                'timestamp': item.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            }
            
            # 如果有原始数据，也保留
            if 'raw_data' in item:
                cleaned_item['raw_data'] = item['raw_data']
            
            cleaned_data.append(cleaned_item)
        
        return cleaned_data
    
    def _categorize_currency(self, currency_pair: str) -> str:
        """分类货币对"""
        if 'CNY' in currency_pair and 'TWD' in currency_pair:
            return '人民币汇率'
        elif 'CNY' in currency_pair:
            return '人民币汇率'
        else:
            return '其他汇率' 