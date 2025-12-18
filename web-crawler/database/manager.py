"""
统一数据库管理器
负责根据数据类型路由到 MongoDB 或 MySQL
"""
import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List

# 配置路径
CONFIG_PATH = Path(__file__).parent.parent / "config" / "database.yaml"


class DatabaseManager:
    """
    双数据库管理器
    
    Usage:
        from database.manager import db_manager
        
        # 写入新闻 (写入 MongoDB)
        db_manager.write_news(news_data)
        
        # 写入商品数据 (自动路由到 MySQL)
        db_manager.write_commodity(commodity_data)
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._config = self._load_config()
        self._mongo_db = None
        self._mongo_error = None
        self._mysql_pipeline = None
        self._initialized = True
        
        print(f"📦 数据库管理器初始化")
        print(f"   MongoDB: {'✅ 启用' if self._config.get('mongodb', {}).get('enabled') else '❌ 禁用'}")
        print(f"   MySQL:  {'✅ 启用' if self._config.get('mysql', {}).get('enabled') else '❌ 禁用'}")
    
    def _load_config(self) -> Dict:
        """加载配置"""
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return {
            'mongodb': {'enabled': True},
            'mysql': {'enabled': False},
        }

    @property
    def mongodb_enabled(self) -> bool:
        return self._config.get("mongodb", {}).get("enabled", False)

    @property
    def mongo(self):
        if not self.mongodb_enabled:
            return None
        if self._mongo_error is not None:
            return None
        if self._mongo_db is None:
            try:
                from database.connection import get_mongo_database

                self._mongo_db = get_mongo_database(self._config.get("mongodb", {}))
            except Exception as e:
                self._mongo_error = str(e)
                self._mongo_db = None
                return None
        return self._mongo_db

    def _require_mongo(self):
        if not self.mongodb_enabled:
            raise RuntimeError("MongoDB 未启用")
        db = self.mongo
        if db is None:
            if self._mongo_error:
                raise RuntimeError(f"MongoDB 连接失败: {self._mongo_error}")
            raise RuntimeError("MongoDB 不可用")
        return db
    
    @property
    def news_repo(self):
        from database.repositories.news_repo import MongoNewsRepository

        return MongoNewsRepository(self._require_mongo())

    @property
    def keyword_match_repo(self):
        from database.repositories.news_repo import MongoKeywordMatchRepository

        return MongoKeywordMatchRepository(self._require_mongo())
    
    @property
    def platform_repo(self):
        from database.repositories.platform_repo import MongoPlatformRepository

        return MongoPlatformRepository(self._require_mongo())

    @property
    def crawl_log_repo(self):
        from database.repositories.log_repo import MongoCrawlLogRepository

        return MongoCrawlLogRepository(self._require_mongo())

    @property
    def push_record_repo(self):
        from database.repositories.log_repo import MongoPushRecordRepository

        return MongoPushRecordRepository(self._require_mongo())
    
    def write_news(self, news_list: List[Any]) -> Dict:
        """
        写入新闻数据 → MongoDB
        
        Returns:
            {'inserted': int, 'updated': int}
        """
        if not news_list:
            return {'inserted': 0, 'updated': 0}
        
        inserted, updated = self.news_repo.insert_batch(news_list)
        return {'inserted': inserted, 'updated': updated}
    
    def get_news(self, category: str = None, limit: int = 100) -> List[Dict]:
        """
        获取新闻 ← MongoDB
        """
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        return self.news_repo.find_by_date(today, category=category, limit=limit)
    
    # ==================== MySQL 接口 ====================
    
    @property
    def mysql_enabled(self) -> bool:
        """MySQL 是否启用"""
        return self._config.get('mysql', {}).get('enabled', False)
    
    @property  
    def mysql_pipeline(self):
        """获取 MySQL 管道"""
        if not self.mysql_enabled:
            return None
        
        if self._mysql_pipeline is None:
            try:
                from database.mysql.pipeline import CommodityPipeline
                self._mysql_pipeline = CommodityPipeline()
            except ImportError as e:
                print(f"⚠️ MySQL 模块导入失败: {e}")
                return None
            except Exception as e:
                print(f"⚠️ MySQL 连接失败: {e}")
                return None
        
        return self._mysql_pipeline
    
    def write_commodity(self, raw_records: List[Dict], source: str) -> Optional[Dict]:
        """
        写入商品数据 → MySQL
        
        Returns:
            处理结果统计，MySQL 不可用时返回 None
        """
        if not self.mysql_enabled:
            print("⚠️ MySQL 未启用，商品数据未写入")
            return None
        
        pipeline = self.mysql_pipeline
        if pipeline is None:
            return None
        
        return pipeline.process_batch(raw_records, source)
    
    def get_commodity_latest(self, category: str = None) -> List[Dict]:
        """
        获取最新商品价格 ← MySQL
        """
        if not self.mysql_enabled:
            return []
        
        try:
            from database.mysql.pipeline import get_latest_prices
            return get_latest_prices(category)
        except Exception as e:
            print(f"⚠️ 获取商品数据失败: {e}")
            return []
    
    def get_commodity_changes(self, hours: int = 24) -> List[Dict]:
        """
        获取商品变更日志 ← MySQL (供 LLM)
        """
        if not self.mysql_enabled:
            return []
        
        try:
            from database.mysql.pipeline import get_price_changes
            return get_price_changes(hours)
        except Exception as e:
            print(f"⚠️ 获取变更日志失败: {e}")
            return []
    
    # ==================== 健康检查 ====================
    
    def health_check(self) -> Dict:
        """检查数据库健康状态"""
        status = {
            'sqlite': {
                'enabled': False,
                'status': 'disabled',
            },
            'mongodb': {'enabled': self.mongodb_enabled, 'status': 'unknown'},
            'mysql': {'enabled': self.mysql_enabled, 'status': 'unknown'}
        }

        if self.mongodb_enabled:
            db = self.mongo
            if db is None:
                if self._mongo_error:
                    status['mongodb']['status'] = 'error'
                    status['mongodb']['error'] = self._mongo_error
                else:
                    status['mongodb']['status'] = 'disabled'
            else:
                try:
                    db.command("ping")
                    status['mongodb']['status'] = 'healthy'
                    status['mongodb']['database'] = db.name
                except Exception as e:
                    status['mongodb']['status'] = 'error'
                    status['mongodb']['error'] = str(e)
        else:
            status['mongodb']['status'] = 'disabled'
        
        # 检查 MySQL
        if self.mysql_enabled:
            try:
                from database.mysql.connection import test_connection
                if test_connection():
                    status['mysql']['status'] = 'healthy'
                else:
                    status['mysql']['status'] = 'disconnected'
            except Exception as e:
                status['mysql']['status'] = 'error'
                status['mysql']['error'] = str(e)
        else:
            status['mysql']['status'] = 'disabled'
        
        return status


# 全局实例
db_manager = DatabaseManager()


# 便捷函数
def get_db_manager() -> DatabaseManager:
    """获取数据库管理器"""
    return db_manager
