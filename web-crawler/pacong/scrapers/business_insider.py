"""
Business Insider商品数据爬虫
使用新的模块化架构重构
"""

import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup

from ..core import BaseScraper, WebScrapingMixin, get_config
from ..data import CommodityData


class BusinessInsiderScraper(BaseScraper, WebScrapingMixin):
    """Business Insider商品数据爬虫"""
    
    def __init__(self, **kwargs):
        super().__init__("business_insider", **kwargs)
        
        # 商品中文翻译对照表
        self.commodity_translations = {
            # 贵金属
            'Gold': '黄金',
            'Silver': '白银', 
            'Platinum': '铂金',
            'Palladium': '钯金',
            
            # 能源
            'Natural Gas': '天然气',
            'Natural Gas (Henry Hub)': '天然气(亨利中心)',
            'Heating Oil': '取暖油',
            'Coal': '煤炭',
            'RBOB Gasoline': 'RBOB汽油',
            'Oil (Brent)': '布伦特原油',
            'Oil (WTI)': 'WTI原油',
            'Crude Oil': '原油',
            
            # 工业金属
            'Aluminium': '铝',
            'Lead': '铅',
            'Copper': '铜',
            'Nickel': '镍',
            'Zinc': '锌',
            'Tin': '锡',
            
            # 农产品
            'Cotton': '棉花',
            'Oats': '燕麦',
            'Lumber': '木材',
            'Coffee': '咖啡',
            'Cocoa': '可可',
            'Live Cattle': '活牛',
            'Lean Hog': '瘦肉猪',
            'Corn': '玉米',
            'Feeder Cattle': '饲料牛',
            'Milk': '牛奶',
            'Orange Juice': '橙汁',
            'Palm Oil': '棕榈油',
            'Rapeseed': '油菜籽',
            'Rice': '大米',
            'Soybean Meal': '豆粕',
            'Soybeans': '大豆',
            'Soybean Oil': '豆油',
            'Wheat': '小麦',
            'Sugar': '糖',
        }
    
    def get_data_sources(self) -> List[Dict[str, str]]:
        """获取数据源列表"""
        config = get_config()
        bi_config = config.data_sources.get('business_insider', {})
        
        if not bi_config.get('enabled', True):
            return []
        
        return [{
            'name': 'Business Insider 商品市场',
            'url': bi_config.get('url', 'https://markets.businessinsider.com/commodities'),
            'type': 'commodity'
        }]
    
    def scrape_single_source(self, source: Dict[str, str]) -> List[Dict[str, Any]]:
        """爬取单个数据源"""
        url = source['url']
        self.logger.info(f"开始爬取Business Insider: {url}")
        
        try:
            response = self.get_page(url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            commodities = []
            tables = soup.find_all('table')
            
            self.logger.info(f"发现 {len(tables)} 个数据表格")
            
            for table in tables:
                rows = table.find_all('tr')
                
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        commodity_data = self._extract_commodity_from_row(cells)
                        if commodity_data:
                            commodities.append(commodity_data)
            
            self.logger.info(f"成功提取 {len(commodities)} 条商品数据")
            return commodities
            
        except Exception as e:
            self.logger.error(f"爬取Business Insider失败: {e}")
            return []
    
    def _extract_commodity_from_row(self, cells) -> Dict[str, Any]:
        """从表格行中提取商品数据"""
        try:
            cell_texts = [cell.get_text(strip=True) for cell in cells]
            
            # 提取商品名称
            name = cell_texts[0]
            if (not name or len(name) <= 2 or name.isdigit() or
                'commodity' in name.lower() or 'price' in name.lower()):
                return None
            
            # 提取价格和变化
            price = None
            change = None
            
            for text in cell_texts[1:]:
                # 尝试提取价格
                if price is None and re.search(r'\d+\.?\d*', text):
                    price_match = re.search(r'(\d+,?\d*\.?\d*)', text.replace(',', ''))
                    if price_match:
                        try:
                            price = float(price_match.group(1))
                        except ValueError:
                            continue
                
                # 尝试提取变化
                if change is None and ('%' in text or '+' in text or '-' in text):
                    change = text
            
            if not name or price is None:
                return None
            
            return {
                'name': name,
                'chinese_name': self.commodity_translations.get(name, name),
                'price': price,
                'current_price': price,
                'change': change,
                'source': self.name,
                'category': self._categorize_commodity(name)
            }
            
        except Exception as e:
            self.logger.warning(f"提取商品数据失败: {e}")
            return None
    
    def _categorize_commodity(self, name: str) -> str:
        """为商品分类"""
        name_lower = name.lower()
        
        # 能源类
        energy_keywords = ['oil', 'gas', 'gasoline', 'heating', 'brent', 'wti', 'crude']
        if any(keyword in name_lower for keyword in energy_keywords):
            return "能源"
        
        # 贵金属
        precious_metals = ['gold', 'silver', 'platinum', 'palladium']
        if any(metal in name_lower for metal in precious_metals):
            return "贵金属"
        
        # 工业金属
        industrial_metals = ['copper', 'aluminum', 'aluminium', 'zinc', 'nickel', 'lead', 'tin']
        if any(metal in name_lower for metal in industrial_metals):
            return "工业金属"
        
        # 农产品
        agriculture_keywords = ['corn', 'wheat', 'soybean', 'cotton', 'sugar', 'coffee', 'cocoa', 
                               'cattle', 'hog', 'lumber', 'milk', 'orange', 'palm', 'rapeseed', 'rice']
        if any(keyword in name_lower for keyword in agriculture_keywords):
            return "农产品"
        
        return "其他"
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """验证数据有效性"""
        # 基本字段检查
        if not data.get('name') or not isinstance(data.get('price'), (int, float)):
            return False
        
        # 价格合理性检查
        price = data.get('price', 0)
        if price <= 0 or price > 1000000:
            return False
        
        return True
    
    def clean_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """清洗数据"""
        cleaned_data = super().clean_data(data)
        
        # 处理变化百分比
        change_str = cleaned_data.get('change', '')
        if change_str and '%' in change_str:
            try:
                # 提取百分比数值
                percent_match = re.search(r'([+-]?\d+\.?\d*)%', change_str)
                if percent_match:
                    change_percent = float(percent_match.group(1))
                    cleaned_data['change_percent'] = change_percent
            except (ValueError, AttributeError):
                pass
        
        return cleaned_data 