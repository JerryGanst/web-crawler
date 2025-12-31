"""
中塑在线 21CP 塑料价格爬虫

API: https://quote.21cp.com/avgMarketAreaProduct/api/listHistory
支持增量和全量获取塑料行情均价数据
"""
import requests
from datetime import datetime, date
from typing import List, Dict, Any, Optional


class Plastic21CPScraper:
    """中塑在线 21CP 塑料价格爬虫"""
    
    API_URL = "https://quote.21cp.com/avgMarketAreaProduct/api/listHistory"
    
    # 产品 SID 映射（avgMarketAreaProductSid）
    # 这些 SID 是每个产品在特定区域的标识
    PRODUCTS = {
        # ABS 系列
        "abs_south": {
            "sid": "749907123932028929",
            "name": "ABS(华南)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/list/303561829995569152-ABS.html"
        },
        "abs_east": {
            "sid": "749907123932028928",  # 修正为中高端国产ABS
            "name": "ABS(华东)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/list/301005776779010048-ABS.html"
        },
        
        # PP 聚丙烯
        "pp_east": {
            "sid": "316956720981139456",
            "name": "PP(华东)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/list/301005776779010048-PP.html"
        },
        "pp_south": {
            "sid": "316956796340199424",
            "name": "PP(华南)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/list/303561829995569152-PP.html"  # 修正URL
        },
        "pp_north": {
            "sid": "316956838132244480",
            "name": "PP(华北)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/list/316927260558942208-PP.html"  # 修正URL
        },
        # PE 聚乙烯
        "pe_east": {
            "sid": "749911919216877568",
            "name": "PE(华东)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/list/301005776779010048-PE.html"
        },
        "pe_south": {
            "sid": "316956834130878465",
            "name": "PE(华南)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/list/303561829995569152-PE.html"  # 修正URL
        },
        "pe_north": {
            "sid": "316956835372392449",
            "name": "PE(华北)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/list/316927260558942208-PE.html"  # 修正URL
        },
        # GPPS 通用级聚苯乙烯 (中高端国产)
        "gpps_east": {
            "sid": "749907578238066688",
            "name": "GPPS(华东)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/detail/749907578238066688--.html"
        },
        "gpps_south": {
            "sid": "749907578238066689",
            "name": "GPPS(华南)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/detail/749907578238066689--.html"
        },
        # GPPS 通用级聚苯乙烯 (中低端国产)
        "gpps_low_east": {
            "sid": "749907373505699840",
            "name": "GPPS低端(华东)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/detail/749907373505699840-20-.html"
        },
        "gpps_low_south": {
            "sid": "749907373505699841",
            "name": "GPPS低端(华南)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/detail/749907373505699841-20-.html"
        },
        # HIPS 高抗冲聚苯乙烯 (中高端国产)
        "hips_east": {
            "sid": "749910931273736192",
            "name": "HIPS(华东)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/detail/749910931273736192-20-.html"
        },
        "hips_south": {
            "sid": "749910931273736193",
            "name": "HIPS(华南)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/detail/749910931273736193-20-.html"
        },
        # HIPS 高抗冲聚苯乙烯 (中低端国产)
        "hips_low_east": {
            "sid": "749908132301430784",
            "name": "HIPS低端(华东)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/detail/749908132301430784-20-.html"
        },
        "hips_low_south": {
            "sid": "749908132301430785",
            "name": "HIPS低端(华南)",
            "category": "塑料",
            "unit": "元/吨",
            "referer": "https://quote.21cp.com/avg_area/detail/749908132301430785-20-.html"
        },
    }
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
        }
    
    def fetch(
        self,
        product: str = "abs_south",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取塑料价格数据
        
        Args:
            product: 产品类型，如 abs_south, abs_east
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
        
        Returns:
            标准化的价格数据列表
        """
        product_info = self.PRODUCTS.get(product)
        if not product_info:
            raise ValueError(f"未知产品: {product}，可用: {list(self.PRODUCTS.keys())}")
        
        params = {
            "avgMarketAreaProductSid": product_info["sid"],
        }
        
        # 添加日期过滤
        if start_date:
            params["quotedPriceDateStart"] = start_date
        if end_date:
            params["quotedPriceDateEnd"] = end_date
        
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
            return self._normalize_records(records, product_info)
            
        except requests.RequestException as e:
            print(f"❌ 21CP 请求失败: {e}")
            return []
        except Exception as e:
            print(f"❌ 21CP 解析失败: {e}")
            return []
    
    def fetch_all_products(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """获取所有产品的价格数据"""
        all_records = []
        for product_key in self.PRODUCTS.keys():
            records = self.fetch(product_key, start_date, end_date)
            all_records.extend(records)
        return all_records
    
    def fetch_incremental(self, product: str = "abs_south") -> List[Dict[str, Any]]:
        """获取今日增量数据"""
        today = date.today().isoformat()
        return self.fetch(product, start_date=today, end_date=today)
    
    def fetch_full_history(
        self, 
        product: str = "abs_south",
        start_date: str = "2020-01-01"
    ) -> List[Dict[str, Any]]:
        """获取全量历史数据（从指定日期至今）"""
        today = date.today().isoformat()
        return self.fetch(product, start_date=start_date, end_date=today)
    
    def _normalize_records(
        self, 
        records: List[Dict], 
        product_info: Dict
    ) -> List[Dict[str, Any]]:
        """标准化数据为统一格式"""
        normalized = []
        product_name = product_info["name"]
        
        for r in records:
            try:
                # 解析日期
                price_date = r.get("quotedPriceDate", "")
                if not price_date:
                    continue
                
                # 解析价格
                price = r.get("quotedPrice")
                if price is None:
                    continue
                
                price = float(price)
                if price <= 0:
                    continue
                
                # 涨跌幅
                change_percent = r.get("updownPercent")
                if change_percent is not None:
                    change_percent = float(change_percent)
                
                # 前一日价格
                pre_price = r.get("preQuotedPrice")
                
                # 处理时间戳: 如果是今天的数据，使用当前时间，否则使用当日末尾
                today_str = date.today().isoformat()
                if price_date == today_str:
                    version_ts = datetime.now()
                else:
                    version_ts = datetime.strptime(price_date + " 23:59:59", "%Y-%m-%d %H:%M:%S")
                
                normalized.append({
                    "name": product_name,
                    "chinese_name": product_name,
                    "price": price,
                    "current_price": price,
                    "change_percent": change_percent,
                    "pre_price": float(pre_price) if pre_price else None,
                    "unit": product_info["unit"],
                    "source": "中塑在线",
                    "category": product_info["category"],
                    "price_date": price_date,
                    "version_ts": version_ts,
                    "extra_data": {
                        "market_area": r.get("marketAreaName"),
                        "sid": r.get("sid"),
                    },
                    "url": product_info["referer"]
                })
                
            except (ValueError, TypeError) as e:
                continue
        
        print(f"✅ 中塑在线: 获取 {len(normalized)} 条 {product_name} 数据")
        return normalized
    
    @classmethod
    def list_products(cls) -> List[str]:
        """列出所有可用产品"""
        return list(cls.PRODUCTS.keys())
    
    @classmethod
    def add_product(cls, key: str, sid: str, name: str, referer: str = "", 
                    category: str = "塑料", unit: str = "元/吨"):
        """动态添加产品"""
        cls.PRODUCTS[key] = {
            "sid": sid,
            "name": name,
            "category": category,
            "unit": unit,
            "referer": referer or f"https://quote.21cp.com/"
        }


# 测试
if __name__ == "__main__":
    scraper = Plastic21CPScraper()
    
    print("可用产品:", scraper.list_products())
    
    # 测试获取 ABS 华南数据
    print("\n=== ABS(华南) 最近数据 ===")
    data = scraper.fetch("abs_south", start_date="2025-12-01")
    for item in data[:5]:
        print(f"{item['price_date']}: {item['price']} {item['unit']} ({item.get('change_percent', 0) or 0:+.2f}%)")
    
    print(f"\n共获取 {len(data)} 条记录")
