# coding=utf-8
"""
MongoDB Checkpointer

为 LangGraph 提供 MongoDB 持久化存储。
支持会话历史的持久化和恢复。

兼容 LangGraph 新版 API (dumps_typed/loads_typed)
"""

import logging
from datetime import datetime
from typing import Any, Dict, Iterator, Optional, Tuple, List, Sequence

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    SerializerProtocol,
    ChannelVersions,
)
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)


class MongoDBCheckpointer(BaseCheckpointSaver):
    """
    MongoDB 实现的 LangGraph Checkpointer

    将对话状态持久化到 MongoDB，支持：
    - 会话历史保存
    - 会话恢复
    - 多会话管理

    兼容 LangGraph 新版序列化器 API
    """

    def __init__(
        self,
        db,
        collection_name: str = "chat_checkpoints",
        serde: Optional[SerializerProtocol] = None
    ):
        """
        初始化 MongoDB Checkpointer

        Args:
            db: MongoDB 数据库实例
            collection_name: 集合名称
            serde: 序列化器
        """
        super().__init__(serde=serde)
        self.db = db
        self.collection = db[collection_name]

        # 创建索引
        self._ensure_indexes()

    def _ensure_indexes(self):
        """创建必要的索引"""
        try:
            # 复合索引：thread_id + checkpoint_id
            self.collection.create_index([
                ("thread_id", 1),
                ("checkpoint_id", 1)
            ], unique=True)

            # thread_id 索引（用于查询）
            self.collection.create_index("thread_id")

            # 时间索引（用于清理过期数据）
            self.collection.create_index("created_at")

            logger.info("MongoDB 索引创建成功")
        except Exception as e:
            logger.warning(f"创建索引失败（可能已存在）: {e}")

    def _serialize(self, data: Any) -> bytes:
        """序列化数据，兼容新旧 API"""
        if hasattr(self.serde, 'dumps_typed'):
            # 新版 API
            return self.serde.dumps_typed(data)
        elif hasattr(self.serde, 'dumps'):
            # 旧版 API
            return self.serde.dumps(data)
        else:
            import json
            return json.dumps(data).encode('utf-8')

    def _deserialize(self, data: bytes) -> Any:
        """反序列化数据，兼容新旧 API"""
        if hasattr(self.serde, 'loads_typed'):
            # 新版 API
            return self.serde.loads_typed(data)
        elif hasattr(self.serde, 'loads'):
            # 旧版 API
            return self.serde.loads(data)
        else:
            import json
            return json.loads(data.decode('utf-8'))

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """
        获取检查点

        Args:
            config: 运行配置，包含 thread_id

        Returns:
            CheckpointTuple 或 None
        """
        thread_id = config["configurable"].get("thread_id")
        checkpoint_id = config["configurable"].get("checkpoint_id")

        if not thread_id:
            return None

        try:
            # 查询条件
            query = {"thread_id": thread_id}
            if checkpoint_id:
                query["checkpoint_id"] = checkpoint_id

            # 获取最新的检查点
            doc = self.collection.find_one(
                query,
                sort=[("created_at", -1)]
            )

            if not doc:
                return None

            # 反序列化检查点
            checkpoint = self._deserialize(doc["checkpoint_data"])
            metadata = doc.get("metadata", {})

            # 获取 pending_writes
            pending_writes = []
            if "pending_writes" in doc:
                for pw in doc["pending_writes"]:
                    pending_writes.append((
                        pw["task_id"],
                        pw["channel"],
                        self._deserialize(pw["value"])
                    ))

            return CheckpointTuple(
                config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": config["configurable"].get("checkpoint_ns", ""),
                        "checkpoint_id": doc["checkpoint_id"]
                    }
                },
                checkpoint=checkpoint,
                metadata=metadata,
                parent_config={
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": config["configurable"].get("checkpoint_ns", ""),
                        "checkpoint_id": doc.get("parent_checkpoint_id")
                    }
                } if doc.get("parent_checkpoint_id") else None,
                pending_writes=pending_writes
            )

        except Exception as e:
            logger.error(f"获取检查点失败: {e}")
            return None

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """异步获取检查点（调用同步方法）"""
        return self.get_tuple(config)

    def list(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ) -> Iterator[CheckpointTuple]:
        """
        列出检查点

        Args:
            config: 运行配置
            filter: 过滤条件
            before: 在此之前的检查点
            limit: 返回数量限制

        Yields:
            CheckpointTuple
        """
        if not config:
            return

        thread_id = config["configurable"].get("thread_id")
        if not thread_id:
            return

        try:
            query = {"thread_id": thread_id}

            if filter:
                query.update(filter)

            cursor = self.collection.find(query).sort("created_at", -1)

            if limit:
                cursor = cursor.limit(limit)

            for doc in cursor:
                checkpoint = self._deserialize(doc["checkpoint_data"])
                metadata = doc.get("metadata", {})

                yield CheckpointTuple(
                    config={
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": config["configurable"].get("checkpoint_ns", ""),
                            "checkpoint_id": doc["checkpoint_id"]
                        }
                    },
                    checkpoint=checkpoint,
                    metadata=metadata,
                    parent_config={
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": config["configurable"].get("checkpoint_ns", ""),
                            "checkpoint_id": doc.get("parent_checkpoint_id")
                        }
                    } if doc.get("parent_checkpoint_id") else None
                )

        except Exception as e:
            logger.error(f"列出检查点失败: {e}")

    async def alist(
        self,
        config: Optional[RunnableConfig],
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = None,
    ):
        """异步列出检查点"""
        for item in self.list(config, filter=filter, before=before, limit=limit):
            yield item

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """
        保存检查点

        Args:
            config: 运行配置
            checkpoint: 检查点数据
            metadata: 元数据
            new_versions: 新版本信息

        Returns:
            更新后的配置
        """
        thread_id = config["configurable"].get("thread_id")
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")

        if not thread_id:
            raise ValueError("thread_id is required")

        try:
            # 序列化检查点
            checkpoint_data = self._serialize(checkpoint)

            # 保存到 MongoDB
            doc = {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "parent_checkpoint_id": parent_checkpoint_id,
                "checkpoint_data": checkpoint_data,
                "metadata": metadata,
                "created_at": datetime.utcnow(),
                "versions": dict(new_versions) if new_versions else {}
            }

            # 使用 upsert 保存
            self.collection.update_one(
                {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id
                },
                {"$set": doc},
                upsert=True
            )

            logger.debug(f"保存检查点: thread={thread_id}, checkpoint={checkpoint_id}")

            return {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint_id
                }
            }

        except Exception as e:
            logger.error(f"保存检查点失败: {e}")
            raise

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """异步保存检查点"""
        return self.put(config, checkpoint, metadata, new_versions)

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """
        保存写入操作

        Args:
            config: 运行配置
            writes: 写入操作列表
            task_id: 任务ID
        """
        thread_id = config["configurable"].get("thread_id")
        checkpoint_id = config["configurable"].get("checkpoint_id")

        if not thread_id or not checkpoint_id:
            return

        try:
            # 将写入操作保存为单独的文档
            for channel, value in writes:
                self.collection.update_one(
                    {
                        "thread_id": thread_id,
                        "checkpoint_id": checkpoint_id
                    },
                    {
                        "$push": {
                            "pending_writes": {
                                "task_id": task_id,
                                "channel": channel,
                                "value": self._serialize(value),
                                "created_at": datetime.utcnow()
                            }
                        }
                    }
                )

        except Exception as e:
            logger.error(f"保存写入操作失败: {e}")

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],
        task_id: str,
    ) -> None:
        """异步保存写入操作"""
        self.put_writes(config, writes, task_id)

    def delete_thread(self, thread_id: str) -> int:
        """
        删除会话的所有检查点

        Args:
            thread_id: 会话ID

        Returns:
            删除的文档数
        """
        try:
            result = self.collection.delete_many({"thread_id": thread_id})
            logger.info(f"删除会话 {thread_id} 的 {result.deleted_count} 个检查点")
            return result.deleted_count
        except Exception as e:
            logger.error(f"删除会话失败: {e}")
            return 0

    async def adelete_thread(self, thread_id: str) -> int:
        """异步删除会话"""
        return self.delete_thread(thread_id)

    def get_all_threads(self, limit: int = 100) -> List[Dict]:
        """
        获取所有会话

        Args:
            limit: 返回数量限制

        Returns:
            会话列表
        """
        try:
            pipeline = [
                {"$group": {
                    "_id": "$thread_id",
                    "last_updated": {"$max": "$created_at"},
                    "checkpoint_count": {"$sum": 1}
                }},
                {"$sort": {"last_updated": -1}},
                {"$limit": limit}
            ]

            return list(self.collection.aggregate(pipeline))
        except Exception as e:
            logger.error(f"获取会话列表失败: {e}")
            return []

    def cleanup_old_checkpoints(self, days: int = 30) -> int:
        """
        清理过期的检查点

        Args:
            days: 保留天数

        Returns:
            删除的文档数
        """
        from datetime import timedelta

        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            result = self.collection.delete_many({
                "created_at": {"$lt": cutoff}
            })
            logger.info(f"清理了 {result.deleted_count} 个过期检查点")
            return result.deleted_count
        except Exception as e:
            logger.error(f"清理检查点失败: {e}")
            return 0


# ==================== 工厂函数 ====================

def get_mongo_checkpointer(
    mongo_uri: str = None,
    db_name: str = "trendradar",
    collection_name: str = "chat_checkpoints",
    required: bool = True
) -> Optional[MongoDBCheckpointer]:
    """
    获取 MongoDB Checkpointer 实例

    Args:
        mongo_uri: MongoDB 连接 URI
        db_name: 数据库名称
        collection_name: 集合名称
        required: 是否强制要求连接成功，默认 True

    Returns:
        MongoDBCheckpointer 实例

    Raises:
        ConnectionError: 当 required=True 且无法连接时抛出异常
    """
    try:
        from pymongo import MongoClient
        import os
        import yaml
        from pathlib import Path

        # 尝试从配置文件读取 MongoDB 连接信息
        config_path = Path(__file__).parent.parent / "config" / "database.yaml"
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}

            mongo_config = config.get('mongodb', {})
            if mongo_config.get('enabled', True):
                host = mongo_config.get('host', 'localhost')
                port = mongo_config.get('port', 27017)
                username = mongo_config.get('username')
                password = mongo_config.get('password')
                auth_source = mongo_config.get('authentication_source', 'admin')

                if username and password:
                    mongo_uri = f"mongodb://{username}:{password}@{host}:{port}/{db_name}?authSource={auth_source}"
                else:
                    mongo_uri = f"mongodb://{host}:{port}"

                db_name = mongo_config.get('database', db_name)

        # 回退到环境变量或默认值
        if not mongo_uri:
            mongo_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        db = client[db_name]

        # 测试连接
        db.command("ping")
        logger.info(f"MongoDB 连接成功: {db_name}")

        return MongoDBCheckpointer(db, collection_name)

    except Exception as e:
        error_msg = f"无法连接 MongoDB: {e}"
        logger.error(error_msg)
        if required:
            raise ConnectionError(error_msg)
        return None
