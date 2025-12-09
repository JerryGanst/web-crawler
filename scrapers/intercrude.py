"""
中塑在线 21CP 原油价格爬虫

API: https://quote.21cp.com/interCrudePrice/api/list
支持增量和全量获取
"""
import requests
from datetime import datetime, date
from typing import List, Dict, Any, Optional


class InterCrudePriceScraper:
    """中塑在线 21CP 原油价格爬虫"""
    
    API_URL = "https://quote.21cp.com/interCrudePrice/api/list"
    
    # 产品 SID 映射
    PRODUCTS = {
        "wti": {
            "sid": "158651161505726464",
            "name": "WTI原油",
            "referer": "https://quote.21cp.com/crude_centre/list/158651161505726464--.html"
        }
    }
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
        }
    
    def fetch(
        self,
        product: str = "wti",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取原油价格数据
        
        Args:
            product: 产品类型，默认 wti
            start_date: 开始日期 YYYY-MM-DD，默认今天
            end_date: 结束日期 YYYY-MM-DD，默认今天
        
        Returns:
            标准化的价格数据列表
        """
        product_info = self.PRODUCTS.get(product)
        if not product_info:
            raise ValueError(f"未知产品: {product}")
        
        today = date.today().isoformat()
        start = start_date or today
        end = end_date or today
        
        params = {
            "quotedPriceDateStart": start,
            "quotedPriceDateEnd": end,
            "productSid": product_info["sid"],
        }
        
        headers = {
            **self.headers,
            "Referer": product_info["referer"],
        }
        
        try:
            resp = requests.get(
                self.API_URL,
                params=params,
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") != 200:
                print(f"❌ 21CP API 返回错误: {data.get('msg', 'Unknown error')}")
                return []
            
            records = data.get("data", [])
            return self._normalize_records(records, product_info["name"])
            
        except requests.RequestException as e:
            print(f"❌ 21CP 请求失败: {e}")
            return []
        except Exception as e:
            print(f"❌ 21CP 解析失败: {e}")
            return []
    
    def fetch_incremental(self, product: str = "wti") -> List[Dict[str, Any]]:
        """获取今日增量数据"""
        today = date.today().isoformat()
        return self.fetch(product, start_date=today, end_date=today)
    
    def fetch_full_history(
        self, 
        product: str = "wti",
        start_date: str = "2005-01-01"
    ) -> List[Dict[str, Any]]:
        """获取全量历史数据（从指定日期至今）"""
        today = date.today().isoformat()
        return self.fetch(product, start_date=start_date, end_date=today)
    
    def _normalize_records(
        self, 
        records: List[Dict], 
        product_name: str
    ) -> List[Dict[str, Any]]:
        """标准化数据为统一格式"""
        normalized = []
        
        for r in records:
            try:
                # 解析日期
                price_date = r.get("quotedPriceDate", "")
                if not price_date:
                    continue
                
                # 解析价格 (API 返回 quotedPrice)
                price = r.get("quotedPrice")
                if price is None:
                    continue
                
                price = float(price)
                if price <= 0:
                    continue
                
                # 解析涨跌值 (API 返回 updownPrice，需计算涨跌幅)
                updown_price = r.get("updownPrice")
                change_percent = None
                if updown_price is not None and price > 0:
                    # 根据涨跌值计算涨跌幅
                    prev_price = price - float(updown_price)
                    if prev_price > 0:
                        change_percent = (float(updown_price) / prev_price) * 100
                
                # 价格区间 (API 返回 quotedPriceMax/quotedPriceMin)
                high_price = r.get("quotedPriceMax")
                low_price = r.get("quotedPriceMin")
                
                normalized.append({
                    "name": product_name,
                    "chinese_name": product_name,
                    "price": price,
                    "current_price": price,
                    "change_percent": change_percent,
                    "high_price": float(high_price) if high_price else None,
                    "low_price": float(low_price) if low_price else None,
                    "unit": "USD/桶",
                    "source": "中塑在线",
                    "category": "能源",
                    "price_date": price_date,
                    "version_ts": datetime.strptime(price_date, "%Y-%m-%d"),
                    "extra_data": {
                        "product_sid": r.get("productSid"),
                        "price_range": r.get("priceRange"),
                    },
                    "url": "https://quote.21cp.com/crude_centre/list/158651161505726464--.html"
                })
                
            except (ValueError, TypeError):
                continue
        
        print(f"✅ 中塑在线: 获取 {len(normalized)} 条 {product_name} 数据")
        return normalized


# 测试
if __name__ == "__main__":
    scraper = InterCrudePriceScraper()
    
    # 测试增量
    print("=== 增量数据 ===")
    data = scraper.fetch_incremental()
    for item in data:
        print(f"{item['price_date']}: {item['price']} {item['unit']} ({item.get('change_percent', 0):+.2f}%)")
