"""
价格历史数据管理
存储和查询大宗商品的历史价格数据（以周为单位）
"""
import json
import redis
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import os


class PriceHistoryManager:
    """价格历史数据管理器"""
    
    def __init__(self):
        # Redis 配置
        self.redis_host = os.environ.get("REDIS_HOST", "localhost")
        self.redis_port = int(os.environ.get("REDIS_PORT", "49907"))
        self.redis_db = int(os.environ.get("REDIS_DB", "0"))
        self.prefix = "trendradar:history:"
        self.client = None
        self._connect()
    
    def _connect(self):
        """连接 Redis"""
        try:
            self.client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                decode_responses=True,
                socket_connect_timeout=5
            )
            self.client.ping()
            print(f"✅ PriceHistory Redis 连接成功")
        except Exception as e:
            print(f"⚠️ PriceHistory Redis 连接失败: {e}")
            self.client = None
    
    def save_daily_price(self, commodity_name: str, price: float, 
                         change_percent: float = 0, source: str = "",
                         date: str = None):
        """
        保存每日价格数据
        
        Args:
            commodity_name: 商品名称（如 COMEX黄金、SMM铜）
            price: 当前价格
            change_percent: 涨跌幅
            source: 数据来源
            date: 日期字符串 YYYY-MM-DD（默认今天）
        """
        if not self.client:
            return False
        
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        key = f"{self.prefix}{commodity_name}"
        
        data = {
            "price": price,
            "change_percent": change_percent,
            "source": source,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            # 使用 HSET 存储，field 为日期
            self.client.hset(key, date, json.dumps(data, ensure_ascii=False))
            # 保留最近30天数据
            self._cleanup_old_data(key, days=30)
            return True
        except Exception as e:
            print(f"保存价格历史失败: {e}")
            return False
    
    def _cleanup_old_data(self, key: str, days: int = 30):
        """清理超过指定天数的旧数据"""
        if not self.client:
            return
        
        try:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            all_dates = self.client.hkeys(key)
            
            for date in all_dates:
                if date < cutoff:
                    self.client.hdel(key, date)
        except Exception:
            pass
    
    def get_history(self, commodity_name: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        获取商品的历史价格数据
        
        Args:
            commodity_name: 商品名称
            days: 获取最近多少天的数据（默认7天/1周）
        
        Returns:
            按日期排序的价格历史列表
        """
        if not self.client:
            return []
        
        key = f"{self.prefix}{commodity_name}"
        
        try:
            all_data = self.client.hgetall(key)
            
            if not all_data:
                return []
            
            # 解析并过滤最近N天
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            history = []
            
            for date, data_str in all_data.items():
                if date >= cutoff:
                    data = json.loads(data_str)
                    history.append({
                        "date": date,
                        "price": data.get("price", 0),
                        "change_percent": data.get("change_percent", 0),
                        "source": data.get("source", "")
                    })
            
            # 按日期排序
            history.sort(key=lambda x: x["date"])
            return history
            
        except Exception as e:
            print(f"获取价格历史失败: {e}")
            return []
    
    def get_all_commodities_history(self, days: int = 7) -> Dict[str, List[Dict]]:
        """
        获取所有商品的历史数据
        
        Args:
            days: 获取最近多少天的数据
        
        Returns:
            {商品名称: 历史数据列表} 的字典
        """
        if not self.client:
            return {}
        
        try:
            # 获取所有历史数据的 key
            pattern = f"{self.prefix}*"
            keys = self.client.keys(pattern)
            
            result = {}
            for key in keys:
                commodity_name = key.replace(self.prefix, "")
                history = self.get_history(commodity_name, days)
                if history:
                    result[commodity_name] = history
            
            return result
            
        except Exception as e:
            print(f"获取所有历史数据失败: {e}")
            return {}
    
    def save_current_prices(self, commodities: List[Dict[str, Any]]):
        """
        批量保存当前价格到历史记录
        
        Args:
            commodities: 从 CommodityScraper 获取的商品列表
        """
        today = datetime.now().strftime("%Y-%m-%d")
        saved_count = 0
        
        for item in commodities:
            name = item.get("chinese_name") or item.get("name")
            price = item.get("price") or item.get("current_price")
            change = item.get("change_percent", 0)
            source = item.get("source", "")
            
            if name and price:
                if self.save_daily_price(name, price, change, source, today):
                    saved_count += 1
        
        print(f"✅ 已保存 {saved_count} 条价格历史记录 ({today})")
        return saved_count


# 全局实例
price_history = PriceHistoryManager()


def save_daily_snapshot():
    """
    保存每日价格快照（用于定时任务）
    """
    from scrapers.commodity import CommodityScraper
    
    scraper = CommodityScraper()
    data = scraper.scrape()
    
    if data:
        price_history.save_current_prices(data)
        return len(data)
    return 0


if __name__ == "__main__":
    # 测试
    saved = save_daily_snapshot()
    print(f"保存了 {saved} 条数据")
    
    # 查询历史
    history = price_history.get_all_commodities_history(days=7)
    print(f"\n历史数据（最近7天）:")
    for name, records in history.items():
        print(f"  {name}: {len(records)} 条记录")
