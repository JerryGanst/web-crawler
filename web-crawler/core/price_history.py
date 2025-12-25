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
        保存每日价格数据（仅保存到 MySQL）
        
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
        
        # 保存到 MySQL commodity_history 表
        try:
            from database.mysql.connection import get_cursor
            import re
            import uuid
            
            # 生成 commodity_id（从commodity_name推断或查询commodity_latest）
            commodity_id = None
            chinese_name = commodity_name
            english_name = None
            category = None
            
            # 先尝试从 commodity_latest 查询元数据
            with get_cursor() as cursor:
                cursor.execute("""
                    SELECT id, name, chinese_name, category
                    FROM commodity_latest
                    WHERE name = %s OR chinese_name = %s
                    LIMIT 1
                """, (commodity_name, commodity_name))
                
                row = cursor.fetchone()
                if row:
                    commodity_id = row['id']
                    english_name = row['name']
                    chinese_name = row['chinese_name'] or commodity_name
                    category = row['category']
            
            # 如果找不到，生成commodity_id
            if not commodity_id:
                # 判断是中文还是英文
                is_chinese = bool(re.search(r'[\u4e00-\u9fff]', commodity_name))
                if is_chinese:
                    # 中文映射
                    id_map = {
                        '钯金': 'palladium', '铂金': 'platinum', '黄金': 'gold',
                        '白银': 'silver', '铜': 'copper', '铝': 'aluminum',
                        '锌': 'zinc', '镍': 'nickel', '铅': 'lead', '锡': 'tin'
                    }
                    commodity_id = next((v for k, v in id_map.items() if k in commodity_name), 
                                       commodity_name.lower().replace(' ', '_'))
                    chinese_name = commodity_name
                else:
                    commodity_id = commodity_name.lower().replace(' ', '_').replace('-', '_')
                    english_name = commodity_name
            
            # 构建 version_ts (日期 + 当前时间)
            if isinstance(date, str):
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
            else:
                date_obj = date
            version_ts = datetime.combine(date_obj, datetime.now().time())
            
            # 生成 request_id
            request_id = f"price_history_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
            
            # 插入 commodity_history
            sql = """
                INSERT INTO commodity_history 
                (commodity_id, name, chinese_name, category,
                 price, price_unit, change_percent,
                 source, version_ts, record_date, request_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    price = VALUES(price),
                    change_percent = VALUES(change_percent),
                    source = VALUES(source),
                    version_ts = VALUES(version_ts),
                    recorded_at = CURRENT_TIMESTAMP(3)
            """
            
            with get_cursor(commit=True) as cursor:
                cursor.execute(sql, (
                    commodity_id,
                    english_name or commodity_name,
                    chinese_name,
                    category,
                    price,
                    'USD',  # 默认USD
                    change_percent,
                    source or 'price_history',
                    version_ts,
                    date_obj,
                    request_id
                ))
            
            success = True
        except Exception as e:
            print(f"⚠️ 保存价格历史到 MySQL 失败: {e}")
            import traceback
            traceback.print_exc()
            return False
                
        return success
    
    def get_history(self, commodity_name: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        获取商品的历史价格数据 (仅查询 MySQL)
        
        Args:
            commodity_name: 商品名称
            days: 获取最近多少天的数据（默认7天/1周）
        
        Returns:
            按日期排序的价格历史列表
        """
        mysql_history = []
        try:
            from database.mysql.connection import get_cursor
            
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
            
            # 使用窗口函数，每天取最新版本
            sql = """
                WITH ranked_records AS (
                    SELECT 
                        DATE(version_ts) as record_date,
                        price,
                        change_percent,
                        source,
                        version_ts,
                        ROW_NUMBER() OVER (
                            PARTITION BY DATE(version_ts)
                            ORDER BY version_ts DESC
                        ) as rn
                    FROM commodity_history
                    WHERE (name = %s OR chinese_name = %s)
                      AND version_ts >= %s
                )
                SELECT record_date, price, change_percent, source
                FROM ranked_records
                WHERE rn = 1
                ORDER BY record_date ASC
            """
            
            with get_cursor() as cursor:
                cursor.execute(sql, (commodity_name, commodity_name, cutoff_date))
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
            
            return mysql_history
                
        except Exception as e:
            print(f"❌ MySQL 获取价格历史失败: {e}")
            import traceback
            traceback.print_exc()
            
        return []
    
    def get_all_commodities_history(self, days: int = 7) -> Dict[str, List[Dict]]:
        """
        获取所有商品的历史数据 (直接查询 MySQL，不走 Redis)
        
        Args:
            days: 获取最近多少天的数据
        
        Returns:
            {商品名称: 历史数据列表} 的字典
        """
        from database.mysql.connection import get_cursor
        result = {}
        
        try:
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
            
            # 使用窗口函数批量查询，按天取最新
            sql = """
                WITH ranked_records AS (
                    SELECT 
                        chinese_name,
                        DATE(version_ts) as record_date,
                        price,
                        change_percent,
                        source,
                        version_ts,
                        ROW_NUMBER() OVER (
                            PARTITION BY chinese_name, DATE(version_ts)
                            ORDER BY version_ts DESC
                        ) as rn
                    FROM commodity_history
                    WHERE version_ts >= %s
                )
                SELECT chinese_name, record_date, price, change_percent, source
                FROM ranked_records
                WHERE rn = 1
                ORDER BY chinese_name, record_date ASC
            """
            
            with get_cursor() as cursor:
                cursor.execute(sql, (cutoff_date,))
                rows = cursor.fetchall()
                
                for row in rows:
                    name = row['chinese_name']
                    if name not in result:
                        result[name] = []
                    
                    date_str = row['record_date'].strftime("%Y-%m-%d") if hasattr(row['record_date'], 'strftime') else str(row['record_date'])
                    
                    result[name].append({
                        "date": date_str,
                        "price": float(row['price']),
                        "change_percent": float(row['change_percent'] or 0),
                        "source": row['source'] or ""
                    })
            
            print(f"✅ 从 MySQL 批量获取了 {sum(len(v) for v in result.values())} 条历史记录")
            
        except Exception as e:
            print(f"❌ MySQL Batch 获取价格历史失败: {e}")
            import traceback
            traceback.print_exc()
            
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
