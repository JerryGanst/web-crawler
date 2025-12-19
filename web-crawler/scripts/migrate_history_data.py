import asyncio
import json
import logging
import sys
import os
from datetime import datetime
from typing import List, Dict

# 将项目根目录添加到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from redis import Redis
from database.manager import db_manager
from database.models import News
from api.cache import CACHE_TTL

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MigrateHistory")

# Redis 配置 (需与 database.yaml 保持一致)
REDIS_HOST = "10.180.248.145"
REDIS_PORT = 6379
REDIS_DB = 0

class HistoryMigrator:
    """历史数据迁移器：将 Redis 中的旧数据同步到 MongoDB"""
    
    def __init__(self):
        self.redis = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
        if not db_manager.mongodb_enabled:
            raise RuntimeError("MongoDB 未启用，无法迁移")
        self.news_repo = db_manager.news_repo
        self.commodity_repo = db_manager.commodity_repo

    def migrate_news(self):
        """迁移新闻数据 (news:*)"""
        logger.info("📰 开始迁移新闻数据...")
        cursor = '0'
        total = 0
        
        while True:
            cursor, keys = self.redis.scan(cursor=cursor, match="news:*", count=100)
            if not keys:
                if cursor == '0':
                    break
                continue
                
            for key in keys:
                try:
                    # 读取 Redis 数据
                    raw_data = self.redis.get(key)
                    if not raw_data:
                        continue
                    
                    data = json.loads(raw_data)
                    category = data.get("category", key.split(":")[-1])
                    items = data.get("data", [])
                    
                    if not items:
                        continue

                    # 转换为 News 对象
                    news_objects = []
                    for item in items:
                        # 处理时间
                        p_time = item.get("time")
                        published_at = None
                        if p_time:
                            try:
                                if isinstance(p_time, str):
                                    published_at = datetime.fromisoformat(p_time.replace('Z', '+00:00'))
                                else:
                                    published_at = datetime.now() # 无法解析则使用当前时间
                            except:
                                published_at = datetime.now()
                        else:
                            published_at = datetime.now()

                        # source 字段兼容
                        source = item.get("source", "")
                        extra_data = item.copy()
                        extra_data["source"] = source

                        news = News(
                            platform_id=item.get("platform", "unknown"),
                            title=item.get("title", ""),
                            url=item.get("url", ""),
                            published_at=published_at,
                            category=category,
                            extra_data=extra_data
                        )
                        news_objects.append(news)
                    
                    # 批量写入 MongoDB (会自动去重)
                    inserted, updated = self.news_repo.insert_batch(news_objects)
                    logger.info(f"✅ 处理 Key {key}: {len(items)} 条 -> 新增 {inserted}, 更新 {updated}")
                    total += len(items)
                    
                except Exception as e:
                    logger.error(f"❌ 处理 Key {key} 失败: {e}")
            
            if cursor == '0':
                break
        
        logger.info(f"📰 新闻数据迁移完成，共处理 {total} 条记录")

    def migrate_commodity(self):
        """迁移大宗商品数据 (data:commodity)"""
        logger.info("📊 开始迁移大宗商品数据...")
        key = "data:commodity"
        
        try:
            raw_data = self.redis.get(key)
            if not raw_data:
                logger.warning("⚠️ Redis 中未找到 data:commodity")
                return
                
            data = json.loads(raw_data)
            items = data.get("data", [])
            
            if items:
                # 写入 MongoDB
                count = self.commodity_repo.save_batch(items)
                logger.info(f"✅ 大宗商品数据迁移完成: {count} 条")
            else:
                logger.info("⚠️ 大宗商品数据为空")
                
        except Exception as e:
            logger.error(f"❌ 大宗商品数据迁移失败: {e}")

    def run(self):
        try:
            self.migrate_news()
            self.migrate_commodity()
            logger.info("🎉 所有历史数据迁移任务完成！")
        except Exception as e:
            logger.critical(f"⛔ 迁移过程中发生严重错误: {e}")

if __name__ == "__main__":
    migrator = HistoryMigrator()
    migrator.run()
