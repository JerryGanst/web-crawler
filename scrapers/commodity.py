"""
大宗商品数据爬虫
整合 pacong 的 Business Insider 数据源
"""
import requests
import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup

# 商品中英文对照
COMMODITY_TRANSLATIONS = {
    # 贵金属
    'Gold': '黄金', 'Silver': '白银', 'Platinum': '铂金', 'Palladium': '钯金',
    # 能源
    'Oil (Brent)': '布伦特原油', 'Oil (WTI)': 'WTI原油', 'Crude Oil': '原油',
    'Natural Gas': '天然气', 'Heating Oil': '取暖油', 'RBOB Gasoline': 'RBOB汽油',
    # 工业金属
    'Copper': '铜', 'Aluminium': '铝', 'Aluminum': '铝', 'Zinc': '锌',
    'Nickel': '镍', 'Lead': '铅', 'Tin': '锡',
    # 农产品
    'Corn': '玉米', 'Wheat': '小麦', 'Soybeans': '大豆', 'Cotton': '棉花',
    'Sugar': '糖', 'Coffee': '咖啡', 'Cocoa': '可可', 'Rice': '大米',
}

# 商品单位
COMMODITY_UNITS = {
    '黄金': 'USD/盎司', '白银': 'USD/盎司', '铂金': 'USD/盎司', '钯金': 'USD/盎司',
    '布伦特原油': 'USD/桶', 'WTI原油': 'USD/桶', '原油': 'USD/桶',
    '天然气': 'USD/MMBtu', '铜': 'USD/磅', '铝': 'USD/吨',
    '玉米': 'USD/蒲式耳', '小麦': 'USD/蒲式耳', '大豆': 'USD/蒲式耳',
}


class CommodityScraper:
    """大宗商品数据爬虫"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
    
    def scrape(self) -> List[Dict[str, Any]]:
        """爬取大宗商品数据"""
        commodities = []
        
        # 从新浪期货获取数据（更可靠）
        sina_data = self._scrape_sina_commodities()
        commodities.extend(sina_data)
        
        # 从上海有色网获取金属价格
        smm_data = self._scrape_smm_prices()
        commodities.extend(smm_data)
        
        # 从 Business Insider 获取补充数据
        bi_data = self._scrape_business_insider()
        commodities.extend(bi_data)
        
        return commodities
    
    def _scrape_business_insider(self) -> List[Dict[str, Any]]:
        """爬取 Business Insider 大宗商品数据"""
        url = 'https://markets.businessinsider.com/commodities'
        commodities = []
        
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, 'html.parser')
            
            # 查找商品表格
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        data = self._extract_from_row(cells)
                        if data:
                            commodities.append(data)
            
            print(f"✅ Business Insider: 获取 {len(commodities)} 条数据")
            
        except Exception as e:
            print(f"❌ Business Insider 爬取失败: {e}")
        
        return commodities
    
    def _scrape_sina_commodities(self) -> List[Dict[str, Any]]:
        """从新浪获取大宗商品数据"""
        commodities = []
        
        # 新浪期货数据接口
        urls = [
            ('https://hq.sinajs.cn/list=hf_GC', '黄金', 'COMEX黄金'),
            ('https://hq.sinajs.cn/list=hf_SI', '白银', 'COMEX白银'),
            ('https://hq.sinajs.cn/list=hf_CL', '原油', 'WTI原油'),
            ('https://hq.sinajs.cn/list=hf_NG', '天然气', '天然气'),
            ('https://hq.sinajs.cn/list=hf_HG', '铜', 'COMEX铜'),
        ]
        
        for url, cn_name, full_name in urls:
            try:
                headers = {**self.headers, 'Referer': 'https://finance.sina.com.cn'}
                resp = requests.get(url, headers=headers, timeout=10)
                
                if resp.status_code == 200:
                    text = resp.text
                    # 解析新浪数据格式: var hq_str_hf_GC="当前价,空,开盘价,最高价,昨收盘,最低价,时间,..."
                    match = re.search(r'"([^"]+)"', text)
                    if match:
                        parts = match.group(1).split(',')
                        if len(parts) >= 5 and parts[0]:
                            price = float(parts[0])
                            prev_close = float(parts[4]) if parts[4] else price
                            # 计算涨跌幅
                            change_percent = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0
                            
                            commodities.append({
                                'name': full_name,
                                'chinese_name': full_name,
                                'price': price,
                                'current_price': price,
                                'change_percent': round(change_percent, 2),
                                'unit': COMMODITY_UNITS.get(cn_name, 'USD'),
                                'source': '新浪期货',
                                'category': self._categorize(cn_name),
                                'url': f'https://finance.sina.com.cn/futures/quotes/{url.split("=")[1]}.shtml'
                            })
            except Exception as e:
                print(f"新浪 {cn_name} 获取失败: {e}")
        
        print(f"✅ 新浪期货: 获取 {len(commodities)} 条数据")
        return commodities
    
    def _extract_from_row(self, cells) -> Dict[str, Any]:
        """从表格行提取数据"""
        try:
            cell_texts = [c.get_text(strip=True) for c in cells]
            name = cell_texts[0]
            
            # 过滤无效数据
            if not name or len(name) <= 2 or name.isdigit():
                return None
            if 'commodity' in name.lower() or 'price' in name.lower():
                return None
            
            # 提取价格
            price = None
            change = None
            
            # 先提取变化百分比，避免混淆
            for text in cell_texts[1:]:
                if change is None and '%' in text:
                    change = text
            
            # 然后提取价格（排除已识别的变化百分比）
            for text in cell_texts[1:]:
                if text == change:
                    continue
                if price is None and re.search(r'\d+\.?\d*', text):
                    # 排除纯百分比数字（小于10的浮点数可能是百分比）
                    match = re.search(r'(\d+[\d,]*\.?\d*)', text.replace(',', ''))
                    if match:
                        try:
                            val = float(match.group(1))
                            # 价格通常大于10，过滤掉百分比
                            if val > 10:
                                price = val
                                break
                        except ValueError:
                            continue
            
            if not name or price is None:
                return None
            
            chinese_name = COMMODITY_TRANSLATIONS.get(name, name)
            
            # 提取变化百分比
            change_percent = 0
            if change and '%' in change:
                match = re.search(r'([+-]?\d+\.?\d*)%', change)
                if match:
                    change_percent = float(match.group(1))
            
            return {
                'name': name,
                'chinese_name': chinese_name,
                'price': price,
                'current_price': price,
                'change': change,
                'change_percent': change_percent,
                'unit': COMMODITY_UNITS.get(chinese_name, 'USD'),
                'source': 'Business Insider',
                'category': self._categorize(name),
                'url': f'https://markets.businessinsider.com/commodities/{name.lower().replace(" ", "-")}'
            }
        except Exception:
            return None
    
    def _scrape_smm_prices(self) -> List[Dict[str, Any]]:
        """从上海有色网获取金属价格"""
        prices = []
        
        # SMM 有色金属价格页面
        metals = [
            ('copper', '铜', 'SMM铜'),
            ('aluminum', '铝', 'SMM铝'),
            ('zinc', '锌', 'SMM锌'),
            ('lead', '铅', 'SMM铅'),
            ('nickel', '镍', 'SMM镍'),
            ('tin', '锡', 'SMM锡'),
        ]
        
        for metal_en, metal_cn, full_name in metals:
            try:
                url = f'https://hq.smm.cn/{metal_en}'
                resp = requests.get(url, headers=self.headers, timeout=10)
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    
                    # 查找价格表格
                    tables = soup.find_all('table')
                    for table in tables[:3]:
                        rows = table.find_all('tr')
                        for row in rows[1:5]:  # 跳过表头
                            cells = row.find_all(['td', 'th'])
                            if len(cells) >= 2:
                                name_cell = cells[0].get_text(strip=True)
                                price_cell = cells[1].get_text(strip=True) if len(cells) > 1 else ''
                                
                                # 检查是否需要登录
                                if '未登录' in price_cell or not price_cell:
                                    continue
                                
                                # 提取价格范围
                                price_match = re.search(r'(\d+[\d,]*)', price_cell.replace(',', ''))
                                if price_match:
                                    try:
                                        price = float(price_match.group(1))
                                        if price > 100:  # 过滤无效价格
                                            prices.append({
                                                'name': name_cell or full_name,
                                                'chinese_name': name_cell or full_name,
                                                'price': price,
                                                'current_price': price,
                                                'change_percent': 0,
                                                'unit': '元/吨',
                                                'source': '上海有色网',
                                                'category': '工业金属',
                                                'url': url
                                            })
                                            break
                                    except ValueError:
                                        continue
                        if any(p.get('chinese_name', '').startswith(metal_cn) for p in prices):
                            break
                            
            except Exception as e:
                print(f"SMM {metal_cn}获取失败: {e}")
        
        print(f"✅ 上海有色网: 获取 {len(prices)} 条价格数据")
        return prices
    
    def _categorize(self, name: str) -> str:
        """商品分类"""
        name_lower = name.lower()
        
        if any(k in name_lower for k in ['gold', 'silver', 'platinum', 'palladium', '黄金', '白银', '铂金', '钯金']):
            return '贵金属'
        if any(k in name_lower for k in ['oil', 'gas', 'brent', 'wti', '原油', '天然气']):
            return '能源'
        if any(k in name_lower for k in ['copper', 'aluminum', 'zinc', 'nickel', '铜', '铝', '锌', '镍']):
            return '工业金属'
        if any(k in name_lower for k in ['corn', 'wheat', 'soybean', 'cotton', 'sugar', '玉米', '小麦', '大豆']):
            return '农产品'
        
        return '其他'


# 测试
if __name__ == '__main__':
    scraper = CommodityScraper()
    data = scraper.scrape()
    for item in data[:10]:
        print(f"{item['chinese_name']}: {item['price']} {item.get('unit', '')} ({item.get('change_percent', 0):+.2f}%)")
