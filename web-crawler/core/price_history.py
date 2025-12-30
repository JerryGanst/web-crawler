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
                         date: str = None, source_url: str = None, 
                         extra_data: Dict = {}):
        """
        保存每日价格数据 (通过标准 Pipeline 处理)
        
        Args:
            commodity_name: 商品名称
            price: 当前价格
            change_percent: 涨跌幅
            source: 数据来源
            date: 日期字符串 YYYY-MM-DD
            source_url: 来源 URL (新增)
            extra_data: 额外数据字典 (新增)
        """
        try:
            from database.mysql.pipeline import get_pipeline
            
            # 1. 构造标准数据字典
            if date is None:
                date = datetime.now().strftime("%Y-%m-%d")
            
            # 处理时间
            if isinstance(date, str):
                try:
                    # 尝试解析 YYYY-MM-DD
                    date_obj = datetime.strptime(date, "%Y-%m-%d")
                    # 设置为当天最后时刻，或当前时刻? Pipeline default is now.
                    # 保持兼容这里的语义，如果传入了 date，应该是该 date 的数据
                    # 这里设置为 date 的 23:59:59 或者当前时间?
                    # 如果 date 是今天，用当前时间；如果是过去，用 23:59:59?
                    # 简单起见，如果 date 是str，视为 version_ts 的日期部分
                    if date == datetime.now().strftime("%Y-%m-%d"):
                        version_ts = datetime.now()
                    else:
                        version_ts = date_obj.replace(hour=23, minute=59, second=59)
                except:
                    version_ts = datetime.now()
            elif isinstance(date, datetime):
                version_ts = date
            else:
                version_ts = datetime.now()
                
            raw_record = {
                "name": commodity_name,
                "chinese_name": commodity_name, # Pipeline 会再次尝试标准化
                "price": price,
                "change_percent": change_percent,
                "source": source,
                "version_ts": version_ts.isoformat(),
                "url": source_url,
                **extra_data
            }
            
            # 2. 调用 Pipeline
            # 注意: pipeline.process_batch 接受 list
            result = get_pipeline().process_batch([raw_record], source or "price_history_api")
            
            if result['inserted'] > 0 or result['updated'] > 0 or result['unchanged'] > 0:
                return True
            if result['errors'] > 0:
                print(f"⚠️ Pipeline 处理 {commodity_name} 失败: errors > 0")
                return False
                
            return True
            
        except Exception as e:
            print(f"⚠️ 保存价格历史失败 (Pipeline): {e}")
            import traceback
            traceback.print_exc()
            return False
    
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
            
            # 计算截止日期(按 record_date 筛选)
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            # 使用窗口函数,每天每来源取最新版本
            # 关键: 使用表中的 record_date 字段,而非 DATE(version_ts)
            sql = """
                WITH ranked_records AS (
                    SELECT 
                        record_date,
                        price,
                        change_percent,
                        source,
                        version_ts,
                        ROW_NUMBER() OVER (
                            PARTITION BY record_date, source
                            ORDER BY version_ts DESC
                        ) as rn
                    FROM commodity_history
                    WHERE (name = %s OR chinese_name = %s)
                      AND record_date >= %s
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
            # 计算截止日期(按 record_date 筛选)
            cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            
            # 使用窗口函数批量查询,每个商品每天每来源取最新版本
            # 关键: 使用表中的 record_date 字段,而非 DATE(version_ts)
            sql = """
                WITH ranked_records AS (
                    SELECT 
                        commodity_id,
                        name,
                        chinese_name,
                        record_date,
                        price,
                        change_percent,
                        source,
                        version_ts,
                        ROW_NUMBER() OVER (
                            PARTITION BY commodity_id, record_date, source
                            ORDER BY version_ts DESC
                        ) as rn
                    FROM commodity_history
                    WHERE record_date >= %s
                )
                SELECT commodity_id, name, chinese_name, record_date, price, change_percent, source
                FROM ranked_records
                WHERE rn = 1
                ORDER BY commodity_id, record_date ASC
            """
            
            with get_cursor() as cursor:
                cursor.execute(sql, (cutoff_date,))
                rows = cursor.fetchall()
                
                # 预定义ID到英文显示名称的映射 (修正旧数据)
                id_to_english = {
                    # 贵金属
                    'gold': 'Gold',
                    'comex_gold': 'COMEX Gold',
                    'silver': 'Silver',
                    'comex_silver': 'COMEX Silver',
                    'palladium': 'Palladium',
                    'platinum': 'Platinum',
                    
                    # 能源
                    'oil_brent': 'Oil (Brent)',
                    'oil_wti': 'Oil (WTI)',
                    'natural_gas': 'Natural Gas',
                    'gasoline': 'RBOB Gasoline',
                    'heating_oil': 'Heating Oil',
                    
                    # 工业金属
                    'copper': 'Copper',
                    'comex_copper': 'COMEX Copper',
                    'aluminum': 'Aluminium',
                    'nickel': 'Nickel',
                    'zinc': 'Zinc',
                    'lead': 'Lead',
                    'tin': 'Tin'
                }

                for row in rows:
                    keys = set()
                    if row['chinese_name']: keys.add(row['chinese_name'])
                    if row['name']: keys.add(row['name'])
                    if row['commodity_id']: 
                        keys.add(row['commodity_id'])
                        # 补充标准英文名
                        if row['commodity_id'] in id_to_english:
                            keys.add(id_to_english[row['commodity_id']])
                    
                    date_str = row['record_date'].strftime("%Y-%m-%d") if hasattr(row['record_date'], 'strftime') else str(row['record_date'])
                    
                    item = {
                        "date": date_str,
                        "price": float(row['price']),
                        "change_percent": float(row['change_percent'] or 0),
                        "source": row['source'] or ""
                    }
                    
                    for k in keys:
                        if k not in result:
                            result[k] = []
                        result[k].append(item)

            
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
                # 提取额外字段
                url = item.get("url") or item.get("source_url")
                # 排除已知字段作为 extra_data
                exclude_keys = {
                    'name', 'chinese_name', 'price', 'current_price', 
                    'change_percent', 'source', 'url', 'source_url', 'timestamp', 'date'
                }
                extra = {k: v for k, v in item.items() if k not in exclude_keys}
                
                if self.save_daily_price(name, price, change, source, today, 
                                       source_url=url, extra_data=extra):
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
