"""
世界银行商品数据爬虫
下载和解析世界银行商品价格指数Excel文件
"""

from typing import List, Dict, Any
import pandas as pd
from datetime import datetime
from io import BytesIO

from ..core import BaseScraper, WebScrapingMixin
from ..data import CommodityData


class WorldBankScraper(BaseScraper, WebScrapingMixin):
    """世界银行商品数据爬虫"""
    
    def __init__(self, **kwargs):
        super().__init__("worldbank", **kwargs)
        
        # 世界银行数据URL
        self.data_url = "https://thedocs.worldbank.org/en/doc/18675f1d1639c7a34d463f59263ba0a2-0050012025/related/CMO-Historical-Data-Monthly.xlsx"
        
        # 目标工作表名称
        self.target_sheets = [
            'Monthly Indices',
            'Monthly Prices',
            'Annual Indices',
            'Annual Prices'
        ]
        
        # 商品分类映射
        self.commodity_mapping = {
            'Energy': '能源',
            'Non-energy': '非能源',
            'Agriculture': '农业',
            'Beverages': '饮料',
            'Food': '食品',
            'Raw Materials': '原材料',
            'Fertilizers': '化肥',
            'Metals and Minerals': '金属矿物',
            'Precious Metals': '贵金属',
            'Base Metals': '基本金属'
        }
    
    def get_data_sources(self) -> List[Dict[str, str]]:
        """获取数据源列表"""
        return [{
            "name": "worldbank_excel",
            "url": self.data_url,
            "type": "excel"
        }]
    
    def scrape_single_source(self, source: Dict[str, str]) -> List[Dict[str, Any]]:
        """爬取单个数据源"""
        if source["type"] == "excel":
            return self._download_and_parse_excel(source["url"])
        return []
    
    def _download_and_parse_excel(self, url: str) -> List[Dict[str, Any]]:
        """下载和解析Excel文件"""
        try:
            self.logger.info(f"正在下载世界银行Excel文件: {url}")
            
            # 使用更长的超时时间下载Excel文件
            response = self.make_request(url, timeout=60)
            
            if not response or response.status_code != 200:
                self.logger.error(f"下载失败，状态码: {response.status_code if response else 'None'}")
                return []
            
            self.logger.info(f"Excel文件下载成功，大小: {len(response.content)} 字节")
            
            # 使用BytesIO读取Excel内容
            excel_content = BytesIO(response.content)
            xls = pd.ExcelFile(excel_content)
            
            self.logger.info(f"Excel工作表: {xls.sheet_names}")
            
            all_data = []
            
            # 处理每个目标工作表
            for sheet_name in self.target_sheets:
                if sheet_name in xls.sheet_names:
                    self.logger.info(f"正在解析工作表: {sheet_name}")
                    sheet_data = self._parse_sheet(xls, sheet_name)
                    all_data.extend(sheet_data)
                else:
                    self.logger.warning(f"工作表 {sheet_name} 不存在")
            
            self.logger.info(f"成功解析 {len(all_data)} 条数据")
            return all_data
            
        except Exception as e:
            self.logger.error(f"下载和解析Excel文件失败: {e}")
            return []
    
    def _parse_sheet(self, xls: pd.ExcelFile, sheet_name: str) -> List[Dict[str, Any]]:
        """解析单个工作表"""
        try:
            # 尝试不同的header位置
            for header_row in [0, 1, 2, 3, 4, 5, 6]:
                try:
                    df = pd.read_excel(xls, sheet_name=sheet_name, header=header_row)
                    
                    # 检查是否有有效的数据列
                    if len(df.columns) > 1 and not df.empty:
                        self.logger.info(f"工作表 {sheet_name} 使用header={header_row}解析成功")
                        return self._extract_commodity_data(df, sheet_name)
                        
                except Exception:
                    continue
            
            self.logger.warning(f"无法找到合适的header位置解析工作表: {sheet_name}")
            return []
            
        except Exception as e:
            self.logger.error(f"解析工作表 {sheet_name} 失败: {e}")
            return []
    
    def _extract_commodity_data(self, df: pd.DataFrame, sheet_name: str) -> List[Dict[str, Any]]:
        """从DataFrame中提取商品数据"""
        data = []
        
        try:
            # 获取第一列作为商品名称列
            name_column = df.columns[0]
            
            # 查找包含商品类别的行
            for index, row in df.iterrows():
                commodity_name = str(row[name_column]).strip()
                
                # 跳过空值和NaN
                if pd.isna(commodity_name) or commodity_name == '' or commodity_name == 'nan':
                    continue
                
                # 检查是否是已知的商品类别
                chinese_name = self.commodity_mapping.get(commodity_name, commodity_name)
                
                # 获取最新的价格数据（取最后一个非空的数值列）
                price = None
                date_str = None
                
                # 从右到左查找最新的价格数据
                for col in reversed(df.columns[1:]):
                    try:
                        value = row[col]
                        if pd.notna(value) and isinstance(value, (int, float)):
                            price = float(value)
                            date_str = str(col)
                            break
                    except:
                        continue
                
                if price is not None:
                    data.append({
                        'name': commodity_name,
                        'chinese_name': chinese_name,
                        'price': price,
                        'date': date_str,
                        'sheet': sheet_name,
                        'category': self._categorize_commodity(commodity_name),
                        'source': 'worldbank',
                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
            
            self.logger.info(f"从工作表 {sheet_name} 提取了 {len(data)} 条数据")
            return data
            
        except Exception as e:
            self.logger.error(f"提取商品数据失败: {e}")
            return []
    
    def validate_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """验证数据"""
        valid_data = []
        
        for item in data:
            # 检查必需字段
            if all(key in item for key in ['name', 'price', 'timestamp']):
                # 验证价格是有效数字
                try:
                    price = float(item['price'])
                    if price >= 0:  # 价格应该非负
                        valid_data.append(item)
                except (ValueError, TypeError):
                    continue
        
        return valid_data
    
    def clean_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """清理数据"""
        cleaned_data = []
        
        for item in data:
            cleaned_item = {
                'name': item.get('name', ''),
                'chinese_name': item.get('chinese_name', item.get('name', '')),
                'price': float(item.get('price', 0)),
                'unit': 'Index' if 'Indices' in item.get('sheet', '') else 'Price',
                'date': item.get('date', ''),
                'category': item.get('category', '其他'),
                'sheet_source': item.get('sheet', ''),
                'source': 'worldbank',
                'timestamp': item.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            }
            
            cleaned_data.append(cleaned_item)
        
        return cleaned_data
    
    def _categorize_commodity(self, name: str) -> str:
        """对商品进行分类"""
        name_lower = name.lower()
        
        if any(word in name_lower for word in ['energy', 'oil', 'gas', 'coal']):
            return '能源'
        elif any(word in name_lower for word in ['agriculture', 'food', 'beverage']):
            return '农产品'
        elif any(word in name_lower for word in ['metal', 'gold', 'silver', 'copper']):
            return '金属'
        elif any(word in name_lower for word in ['fertilizer']):
            return '化肥'
        else:
            return '其他' 