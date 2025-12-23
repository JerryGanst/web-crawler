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
        self.redis_password = os.environ.get("REDIS_PASSWORD", None)
        
        # 尝试从配置文件加载
        try:
            from pathlib import Path
            import yaml
            config_path = Path(__file__).resolve().parent.parent / "config" / "database.yaml"
            if config_path.exists():
                with open(config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    redis_conf = data.get("redis", {})
                    if redis_conf:
                        self.redis_host = os.environ.get("REDIS_HOST", redis_conf.get("host", self.redis_host))
                        self.redis_port = int(os.environ.get("REDIS_PORT", redis_conf.get("port", self.redis_port)))
                        self.redis_db = int(os.environ.get("REDIS_DB", redis_conf.get("db", self.redis_db)))
                        self.redis_password = os.environ.get("REDIS_PASSWORD", redis_conf.get("password", self.redis_password))
        except Exception as e:
            print(f"⚠️ 加载 Redis 配置失败: {e}")

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
                password=self.redis_password,
                decode_responses=True,
                socket_connect_timeout=5
            )
            self.client.ping()
            print(f"✅ PriceHistory Redis 连接成功: {self.redis_host}:{self.redis_port}")
        except Exception as e:
            print(f"⚠️ PriceHistory Redis 连接失败: {e}")
            self.client = None
    
    def save_daily_price(self, commodity_name: str, price: float, 
                         change_percent: float = 0, source: str = "",
                         date: str = None):
        """
        保存每日价格数据（同步保存到 Redis 和 MySQL）
        
        Args:
            commodity_name: 商品名称（如 COMEX黄金、SMM铜）
            price: 当前价格
            change_percent: 涨跌幅
            source: 数据来源
            date: 日期字符串 YYYY-MM-DD（默认今天）
        """
        success = False
        
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        # 1. 保存到 Redis (保持原有逻辑)
        if self.client:
            try:
                key = f"{self.prefix}{commodity_name}"
                data = {
                    "price": price,
                    "change_percent": change_percent,
                    "source": source,
                    "timestamp": datetime.now().isoformat()
                }
                self.client.hset(key, date, json.dumps(data, ensure_ascii=False))
                success = True
            except Exception as e:
                print(f"⚠️ 保存价格历史到 Redis 失败: {e}")
        
        # 2. 保存到 MySQL (新增)
        try:
            from database.mysql.connection import get_cursor
            sql = """
                INSERT INTO commodity_price_history 
                (name, price, change_percent, source, record_date)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                price = VALUES(price),
                change_percent = VALUES(change_percent),
                source = VALUES(source),
                created_at = CURRENT_TIMESTAMP(3)
            """
            with get_cursor(commit=True) as cursor:
                cursor.execute(sql, (
                    commodity_name, 
                    price, 
                    change_percent, 
                    source, 
                    date
                ))
            success = True
            # print(f"✅ 价格历史已存入 MySQL: {commodity_name} ({date})")
        except Exception as e:
            print(f"⚠️ 保存价格历史到 MySQL 失败: {e}")
            # 如果 Redis 成功，视为整体成功，但记录 MySQL 错误
            if not success:
                return False
                
        return success
    
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
        策略：Redis 优先，Miss 后查询 MySQL 并回写 Redis
        
        Args:
            commodity_name: 商品名称
            days: 获取最近多少天的数据（默认7天/1周）
        
        Returns:
            按日期排序的价格历史列表
        """
        if not self.client:
            return []
        
        key = f"{self.prefix}{commodity_name}"
        history = []
        
        # 1. 尝试从 Redis 获取
        try:
            all_data = self.client.hgetall(key)
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            # Bug修复: 检查数据完整性 (Read Repair)
            # 如果 Redis 数据量明显少于预期（例如少于 days 且少于 4 条），则认为缓存不完整，继续走 MySQL 补全
            
            redis_history = []
            if all_data:
                for date, data_str in all_data.items():
                    # 兼容 bytes 类型
                    if isinstance(date, bytes):
                        date = date.decode('utf-8')
                    if isinstance(data_str, bytes):
                        data_str = data_str.decode('utf-8')
                        
                    if date >= cutoff:
                        data = json.loads(data_str)
                        redis_history.append({
                            "date": date,
                            "price": data.get("price", 0),
                            "change_percent": data.get("change_percent", 0),
                            "source": data.get("source", "")
                        })
                
                redis_history.sort(key=lambda x: x["date"])
                
                # 简单判定策略：
                # 如果 Redis 返回的数据条数足够多（>= days 或 >= 4），则认为缓存命中且完整
                # 否则视为“部分缺失”，穿透到 MySQL 进行合并和回写
                if len(redis_history) >= days or (redis_history and len(redis_history) >= 4):
                     return redis_history
            
            if redis_history:
                print(f"ℹ️ Redis 数据可能不完整 ({len(redis_history)} 条), 尝试从 MySQL 补全...")

        except Exception as e:
            print(f"⚠️ Redis 获取价格历史失败: {e}")
            redis_history = []


        # 2. Redis 未命中或失败，尝试从 MySQL 获取 (降级策略)
        try:
            from database.mysql.connection import get_cursor
            print(f"🔄 Redis Miss ({commodity_name}) -> 从 MySQL 读取历史数据...")
            
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            sql = """
                SELECT record_date, price, change_percent, source 
                FROM commodity_price_history 
                WHERE name = %s AND record_date >= %s
                ORDER BY record_date ASC
            """
            
            mysql_history = []
            redis_mapping = {}  # 用于批量更新 Redis
            
            with get_cursor() as cursor:
                cursor.execute(sql, (commodity_name, cutoff_date))
                rows = cursor.fetchall()
                
                for row in rows:
                    date_str = row['record_date'].strftime("%Y-%m-%d") if hasattr(row['record_date'], 'strftime') else str(row['record_date'])
                    
                    item = {
                        "date": date_str,
                        "price": float(row['price']),
                        "change_percent": float(row['change_percent'] or 0),
                        "source": row['source'] or ""
                    }
                    mysql_history.append(item)
                    
                    # 准备 Redis 数据
                    cache_data = {
                        "price": item["price"],
                        "change_percent": item["change_percent"],
                        "source": item["source"],
                        "timestamp": datetime.now().isoformat()
                    }
                    redis_mapping[date_str] = json.dumps(cache_data, ensure_ascii=False)
            
            # 3. 批量回写 Redis (Cache-Aside)
            if redis_mapping and self.client:
                try:
                    # 使用 hset 的 mapping 参数进行批量写入 (redis-py 3.0+)
                    self.client.hset(key, mapping=redis_mapping)
                except Exception as re:
                    print(f"⚠️ 批量回写 Redis 失败: {re}")
            
            if mysql_history:
                print(f"✅ 从 MySQL 恢复了 {len(mysql_history)} 条记录 ({commodity_name})")
                return mysql_history
                
        except Exception as e:
            print(f"❌ MySQL 获取价格历史失败: {e}")
            
        return []
    
    def get_all_commodities_history(self, days: int = 7) -> Dict[str, List[Dict]]:
        """
        获取所有商品的历史数据
        
        Args:
            days: 获取最近多少天的数据
        
        Returns:
            {商品名称: 历史数据列表} 的字典
        """
        result = {}
        commodity_names = set()
        
        # 1. 获取商品名单 (优先从 MySQL 获取全量名单，确保不漏掉 Redis 中缺失的商品)
        # 修复 Bug: 之前只遍历 Redis keys，导致 Redis 丢失 key 时无法触发 get_history 的 MySQL 降级回写
        try:
            from database.mysql.connection import get_cursor
            with get_cursor() as cursor:
                cursor.execute("SELECT DISTINCT name FROM commodity_price_history")
                rows = cursor.fetchall()
                for row in rows:
                    commodity_names.add(row['name'])
        except Exception as e:
            print(f"⚠️ MySQL 获取商品列表失败: {e}")
            
            # MySQL 失败时，降级从 Redis Keys 获取
            if self.client:
                try:
                    pattern = f"{self.prefix}*"
                    keys = self.client.keys(pattern)
                    for key in keys:
                        if isinstance(key, bytes):
                            key = key.decode('utf-8')
                        name = key.replace(self.prefix, "")
                        commodity_names.add(name)
                except Exception as re:
                    print(f"❌ Redis 获取 Keys 失败: {re}")

        # 2. 遍历获取数据
        # get_history 方法内部实现了 "Redis 优先 -> MySQL 降级 -> 回写 Redis" 的逻辑
        # 只要这里传入了商品名，就能自动修复 Redis 中缺失的数据
        for name in commodity_names:
            try:
                history = self.get_history(name, days)
                if history:
                    result[name] = history
            except Exception as e:
                print(f"⚠️ 获取商品 {name} 历史失败: {e}")
                
        return result
    
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
