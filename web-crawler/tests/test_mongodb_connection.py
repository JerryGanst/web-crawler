import unittest
import os
import yaml
import sys
from urllib.parse import quote_plus

try:
    from pymongo import MongoClient
except ModuleNotFoundError:
    MongoClient = None

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

class TestMongoDBConnection(unittest.TestCase):
    """MongoDB 连接与基础功能测试"""

    def setUp(self):
        """测试前准备：加载配置"""
        self.config = self._load_config()
        self.client = None

    def tearDown(self):
        """测试清理：关闭连接"""
        if self.client:
            self.client.close()

    def _load_config(self):
        """读取配置文件"""
        try:
            config_path = os.path.join(PROJECT_ROOT, 'config', 'database.yaml')
            if not os.path.exists(config_path):
                self.fail(f"Config file not found at: {config_path}")
                
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self.fail(f"Error loading config: {e}")

    def _get_mongo_cfg(self):
        if MongoClient is None:
            self.skipTest('未安装 pymongo，已跳过 MongoDB 测试')
        mongo_cfg = self.config.get('mongodb', {})
        if not mongo_cfg:
            self.skipTest('database.yaml 未配置 mongodb 节点')
        if not mongo_cfg.get('enabled', False):
            self.skipTest('database.yaml 中 mongodb.enabled=false')

        host = mongo_cfg.get('host')
        port = mongo_cfg.get('port')
        if not host or not port:
            self.fail(f"MongoDB host 或 port 缺失: host={host}, port={port}")
        return mongo_cfg

    def _build_mongo_uri(self, mongo_cfg: dict) -> str:
        host = mongo_cfg.get('host')
        port = mongo_cfg.get('port')
        username = mongo_cfg.get('username')
        password = mongo_cfg.get('password')
        database = mongo_cfg.get('database', 'admin')
        auth_source = mongo_cfg.get('authentication_source', 'admin')

        if username and password:
            return f"mongodb://{quote_plus(username)}:{quote_plus(password)}@{host}:{port}/{database}?authSource={auth_source}"
        return f"mongodb://{host}:{port}/{database}"

    def _get_target_db(self, client: MongoClient, mongo_cfg: dict):
        database = mongo_cfg.get('database', 'admin')
        dbs = client.list_database_names()
        if database == 'admin' and 'trendradar' in dbs:
            return client['trendradar']
        return client[database]

    def _sample_tencent_file_doc(self) -> dict:
        return {
            'ownerId': '222',
            'createTime': '2025-12-02 09:04:01',
            'fileSize': 1066,
            'level': 2,
            'parentId': 'ROxCayevWEWapnTsEs',
            '_class': 'org.example.ai_api.Bean.Entity.TencentFile',
        }

    def test_tencent_file_insert(self):
        """插入一条 tencentFile 示例数据"""
        print("\n=== MongoDB tencentFile Insert ===")

        mongo_cfg = self._get_mongo_cfg()
        uri = self._build_mongo_uri(mongo_cfg)
        password = mongo_cfg.get('password')
        print(f"Connecting with URI: {(uri.replace(password, '******') if password else uri)}")

        try:
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            info = self.client.server_info()
            print(f"Connected. Server version: {info.get('version')}")

            db = self._get_target_db(self.client, mongo_cfg)
            print(f"Using database: {db.name}")

            collection = db['tencentFile']
            document = self._sample_tencent_file_doc()
            existing_doc = collection.find_one({'ownerId': document['ownerId']})
            if existing_doc:
                print(f"ownerId 已存在，跳过新增：{document['ownerId']}")
                print("Existing document:")
                print(existing_doc)
                self.assertEqual(existing_doc['ownerId'], document['ownerId'])
                return
            print("Inserting document:")
            print(document)

            result = collection.insert_one(document)
            print(f"Insert OK. _id={result.inserted_id}")
            self.assertIsNotNone(result.inserted_id)

            inserted_doc = collection.find_one({'_id': result.inserted_id})
            print("Inserted document:")
            print(inserted_doc)

            self.assertEqual(inserted_doc['ownerId'], document['ownerId'])
            self.assertEqual(inserted_doc['fileSize'], document['fileSize'])
            self.assertEqual(inserted_doc['_class'], document['_class'])
        except Exception as e:
            self.fail(f"插入失败: {e}")

    def test_query_latest_tencent_file(self):
        """查询 tencentFile 集合中最新新增的数据"""
        print("\n=== MongoDB tencentFile Query Latest ===")

        mongo_cfg = self._get_mongo_cfg()
        uri = self._build_mongo_uri(mongo_cfg)
        password = mongo_cfg.get('password')
        print(f"Connecting with URI: {(uri.replace(password, '******') if password else uri)}")

        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        try:
            client.server_info()

            db = self._get_target_db(client, mongo_cfg)
            print(f"Using database: {db.name}")

            collection = db['tencentFile']
            sample = self._sample_tencent_file_doc()
            criteria = {'ownerId': sample['ownerId']}
            print(f"Query criteria: {criteria}")

            results = list(collection.find(criteria).sort('_id', -1).limit(1))
            if not results:
                insert_result = collection.insert_one(sample)
                print(f"ownerId 不存在，已新增一条用于查询. _id={insert_result.inserted_id}")
                results = list(collection.find({'_id': insert_result.inserted_id}).limit(1))

            self.assertTrue(results)
            latest_doc = results[0]
            print("Latest document:")
            print(latest_doc)

            self.assertEqual(latest_doc['ownerId'], sample['ownerId'])
            self.assertEqual(latest_doc['_class'], sample['_class'])
            self.assertTrue(isinstance(latest_doc.get('fileSize'), int))
        finally:
            client.close()

if __name__ == '__main__':
    unittest.main(verbosity=2)
