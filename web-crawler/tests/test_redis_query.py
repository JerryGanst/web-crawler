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

class TestRedisQuery(unittest.TestCase):
    """Redis 数据查询测试类"""
    
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
    
    def test_query_itlong1(self):
        """测试查询 key:itlong1"""
        key = "itlong1"
        expected_value = "你好"
        
        try:
            # 1. 测试连接
            self.client.ping()
            print("✅ Redis 连接成功")
            
            # 2. 查询数据
            print(f"正在查询 Key: {key}")
            if not self.client.exists(key):
                self.fail(f"❌ Key '{key}' 不存在")
                
            value = self.client.get(key)
            print(f"查询结果 -> Value: {value}")
            
            # 3. 验证值
            self.assertEqual(value, expected_value, f"❌ 数据不匹配: 期望 '{expected_value}', 实际 '{value}'")
            print("✅ 验证通过：数据正确")
            
        except redis.ConnectionError as e:
            self.fail(f"无法连接到 Redis: {e}")
        except Exception as e:
            self.fail(f"测试过程中发生错误: {e}")

if __name__ == "__main__":
    unittest.main()
