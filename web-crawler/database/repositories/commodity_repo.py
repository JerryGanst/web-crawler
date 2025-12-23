from typing import List, Dict, Any, Optional
from datetime import datetime
from pymongo import ASCENDING, DESCENDING

class CommodityRepository:
    """大宗商品数据仓库"""
    
    def __init__(self, mongo_db):
        self._db = mongo_db
        self._col = self._db["commodities"]
        self._ensure_indexes()
        
    def _ensure_indexes(self):
        """创建必要的索引"""
        # 1. 唯一索引：防止同一批次、同一商品重复
        # batch_id 是批次号，name 是商品名
        self._col.create_index(
            [("batch_id", ASCENDING), ("name", ASCENDING)],
            unique=True,
            background=True
        )
        
        # 2. 查询最新数据的索引：按批次时间倒序
        self._col.create_index(
            [("crawl_time", DESCENDING)],
            background=True
        )
        
        # 3. 按分类查询
        self._col.create_index(
            [("category", ASCENDING), ("crawl_time", DESCENDING)],
            background=True
        )

    def save_batch(self, items: List[Dict[str, Any]], batch_id: str = None) -> int:
        """
        保存一批商品数据
        :param items: 商品数据列表
        :param batch_id: 批次号（如果不传则自动生成）
        :return: 插入数量
        """
        if not items:
            return 0
            
        now = datetime.now()
        crawl_time = now.isoformat()
        if not batch_id:
            batch_id = f"batch_{int(now.timestamp())}"
            
        # 准备文档
        docs = []
        for item in items:
            doc = item.copy()
            doc.update({
                "batch_id": batch_id,
                "crawl_time": crawl_time,
                "created_at": now
            })
            docs.append(doc)
            
        # 批量插入
        try:
            result = self._col.insert_many(docs, ordered=False)
            return len(result.inserted_ids)
        except Exception as e:
            # 如果部分插入失败（例如唯一键冲突），我们记录日志但不阻断
            print(f"⚠️ [CommodityRepository] 部分数据插入失败: {e}")
            return 0

    def get_latest_batch(self) -> List[Dict[str, Any]]:
        """
        获取commodities最新的一批数据
        :return: 商品列表
        """
        # 1. 先查最新的 batch_id
        latest = self._col.find_one(
            {}, 
            sort=[("crawl_time", DESCENDING)],
            projection={"batch_id": 1}
        )
        
        if not latest:
            return []
            
        batch_id = latest["batch_id"]
        
        # 2. 查该批次的所有数据
        cursor = self._col.find(
            {"batch_id": batch_id},
            projection={"_id": 0, "created_at": 0, "batch_id": 0} # 返回时不带内部字段
        )
        
        return list(cursor)

    def get_history(self, name: str, days: int = 30) -> List[Dict[str, Any]]:
        """
        获取指定商品的历史价格
        """
        # TODO: 后续可扩展为查询 price_history 集合，目前先查 commodities 快照
        pass
