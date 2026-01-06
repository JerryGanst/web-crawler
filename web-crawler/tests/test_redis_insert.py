# coding=utf-8
import unittest
import sys
import os
from pathlib import Path
import redis

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

# 导入配置
from api.cache import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD

class TestRedisInsert(unittest.TestCase):
    """Redis 数据插入测试类"""
    
    def setUp(self):
        """初始化 Redis 连接"""
        print(f"\n正在连接 Redis: {REDIS_HOST}:{REDIS_PORT} (DB: {REDIS_DB})")
        self.client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5
        )
    
    def test_insert_custom_data(self):
        """测试插入 key:itlong1, value:你好"""
        key = "itlong1"
        value = "你好"
        
        try:
            # 1. 测试连接
            self.client.ping()
            print("✅ Redis 连接成功")
            
            # 2. 写入数据
            print(f"正在写入数据 -> Key: {key}, Value: {value}")
            result = self.client.set(key, value)
            self.assertTrue(result, "写入 Redis 失败")
            
            # 3. 读取验证
            retrieved = self.client.get(key)
            print(f"读取数据结果 -> {retrieved}")
            
            # 4. 断言
            self.assertEqual(retrieved, value, f"数据不匹配: 期望 '{value}', 实际 '{retrieved}'")
            print("✅ 测试通过：数据验证成功")
            
        except redis.ConnectionError as e:
            self.fail(f"无法连接到 Redis: {e}")
        except Exception as e:
            self.fail(f"测试过程中发生错误: {e}")

if __name__ == "__main__":
    unittest.main()
