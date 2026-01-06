# coding=utf-8
"""
MySQL 数据管道单元测试
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from decimal import Decimal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCommodityRecord(unittest.TestCase):
    """测试商品记录模型"""
    
    def test_create_record(self):
        """测试创建记录"""
        from database.mysql.pipeline import CommodityRecord
        
        record = CommodityRecord(
            id='gold',
            name='Gold',
            chinese_name='黄金',
            category='贵金属',
            price=Decimal('2650.50'),
            price_unit='USD',
            weight_unit='oz'
        )
        
        self.assertEqual(record.id, 'gold')
        self.assertEqual(record.price, Decimal('2650.50'))
        self.assertEqual(record.category, '贵金属')
    
    def test_to_dict(self):
        """测试转换为字典"""
        from database.mysql.pipeline import CommodityRecord
        
        record = CommodityRecord(
            id='silver',
            name='Silver',
            price=Decimal('31.25'),
            change_percent=Decimal('1.5'),
        )
        
        d = record.to_dict()
        
        self.assertEqual(d['id'], 'silver')
        self.assertEqual(d['price'], 31.25)
        self.assertEqual(d['change_percent'], 1.5)
        self.assertIsInstance(d['extra_data'], str)


class TestDataStandardization(unittest.TestCase):
    """测试数据标准化"""
    
    def test_standardize_valid_record(self):
        """测试标准化有效记录"""
        from database.mysql.pipeline import standardize_record
        
        raw = {
            'name': 'Gold',
            'price': 2650.50,
            'change_percent': 1.2,
            'source': 'test',
            'url': 'http://example.com'
        }
        
        record = standardize_record(raw, source='test_source')
        
        self.assertIsNotNone(record)
        self.assertEqual(record.id, 'gold')
        self.assertEqual(record.price, Decimal('2650.5'))
        self.assertEqual(record.source, 'test_source')
    
    def test_standardize_invalid_price(self):
        """测试无效价格返回 None"""
        from database.mysql.pipeline import standardize_record
        
        raw = {'name': 'Gold', 'price': 0}
        record = standardize_record(raw, source='test')
        self.assertIsNone(record)
        
        raw2 = {'name': 'Gold', 'price': -100}
        record2 = standardize_record(raw2, source='test')
        self.assertIsNone(record2)
    
    def test_standardize_missing_name(self):
        """测试缺失名称返回 None"""
        from database.mysql.pipeline import standardize_record
        
        raw = {'price': 100}
        record = standardize_record(raw, source='test')
        self.assertIsNone(record)
    
    def test_standardize_batch(self):
        """测试批量标准化"""
        from database.mysql.pipeline import standardize_batch
        
        raw_records = [
            {'name': 'Gold', 'price': 2650},
            {'name': 'Silver', 'price': 31},
            {'name': 'Invalid', 'price': 0},  # 无效
            {'price': 100},  # 无名称
        ]
        
        request_id, records = standardize_batch(raw_records, source='test')
        
        self.assertIn('test_', request_id)
        self.assertEqual(len(records), 2)  # 只有2条有效
        self.assertEqual(records[0].id, 'gold')
        self.assertEqual(records[1].id, 'silver')
    
    def test_id_mapping(self):
        """测试商品 ID 映射"""
        from database.mysql.pipeline import standardize_record
        
        # 测试中文名映射
        record1 = standardize_record({'name': '黄金', 'price': 100}, source='test')
        self.assertEqual(record1.id, 'gold')
        
        # 测试英文名映射
        record2 = standardize_record({'name': 'Oil (Brent)', 'price': 100}, source='test')
        self.assertEqual(record2.id, 'oil_brent')


class TestColumnDiff(unittest.TestCase):
    """测试列级差分"""
    
    def test_diff_new_record(self):
        """测试新增记录"""
        from database.mysql.pipeline import diff_records, CommodityRecord
        
        new_record = CommodityRecord(
            id='gold',
            name='Gold',
            chinese_name='黄金',
            price=Decimal('2650')
        )
        
        changes = diff_records(None, new_record)
        
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0].change_type, 'INSERT')
        self.assertEqual(changes[0].field_name, '*')
    
    def test_diff_price_change(self):
        """测试价格变更"""
        from database.mysql.pipeline import diff_records, CommodityRecord
        
        old_record = {
            'id': 'gold',
            'price': 2650.00,
            'change_percent': 1.0,
        }
        
        new_record = CommodityRecord(
            id='gold',
            name='Gold',
            chinese_name='黄金',
            price=Decimal('2680'),
            change_percent=Decimal('1.5')
        )
        
        changes = diff_records(old_record, new_record)
        
        # 应该有2个变更: price 和 change_percent
        self.assertEqual(len(changes), 2)
        
        price_change = next(c for c in changes if c.field_name == 'price')
        self.assertEqual(price_change.change_type, 'UPDATE')
        self.assertIn('2650', price_change.old_value)
        self.assertIn('2680', price_change.new_value)
    
    def test_diff_no_change(self):
        """测试无变更"""
        from database.mysql.pipeline import diff_records, CommodityRecord
        
        old_record = {
            'price': 2650.00,
            'change_percent': 1.0,
            'high_price': None,
            'low_price': None,
            'open_price': None,
            'change_value': None,
        }
        
        new_record = CommodityRecord(
            id='gold',
            name='Gold',
            price=Decimal('2650.00'),
            change_percent=Decimal('1.0')
        )
        
        changes = diff_records(old_record, new_record)
        self.assertEqual(len(changes), 0)


class TestChangeSummary(unittest.TestCase):
    """测试变更摘要生成"""
    
    def test_price_increase_summary(self):
        """测试价格上涨摘要"""
        from database.mysql.pipeline import _generate_change_summary
        
        summary = _generate_change_summary('黄金', 'price', 2650, 2680)
        
        self.assertIn('黄金', summary)
        self.assertIn('上涨', summary)
        self.assertIn('2650', summary)
        self.assertIn('2680', summary)
    
    def test_price_decrease_summary(self):
        """测试价格下跌摘要"""
        from database.mysql.pipeline import _generate_change_summary
        
        summary = _generate_change_summary('白银', 'price', 32, 30)
        
        self.assertIn('白银', summary)
        self.assertIn('下跌', summary)


class TestQueryInterface(unittest.TestCase):
    """测试查询接口（Mock 测试）"""
    
    @patch('database.mysql.pipeline.get_cursor')
    def test_get_latest_prices(self, mock_cursor):
        """测试获取最新价格"""
        from database.mysql.pipeline import get_latest_prices
        
        # 设置 Mock
        mock_ctx = MagicMock()
        mock_cursor.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_ctx.fetchall.return_value = [
            {'id': 'gold', 'price': 2650},
            {'id': 'silver', 'price': 31}
        ]
        
        results = get_latest_prices()
        
        self.assertEqual(len(results), 2)
        mock_ctx.execute.assert_called()
    
    @patch('database.mysql.pipeline.get_cursor')
    def test_get_recent_changes(self, mock_cursor):
        """测试获取最近变更"""
        from database.mysql.pipeline import get_recent_changes
        
        mock_ctx = MagicMock()
        mock_cursor.return_value.__enter__ = MagicMock(return_value=mock_ctx)
        mock_cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_ctx.fetchall.return_value = []
        
        results = get_recent_changes(limit=10)
        
        self.assertIsInstance(results, list)


class TestCommodityPipeline(unittest.TestCase):
    """测试数据管道"""
    
    @patch('database.mysql.pipeline.transaction')
    def test_pipeline_process_batch(self, mock_transaction):
        """测试批量处理"""
        from database.mysql.pipeline import CommodityPipeline
        
        # Mock 事务
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # 无旧记录
        mock_transaction.return_value.__enter__ = MagicMock(return_value=(mock_conn, mock_cursor))
        mock_transaction.return_value.__exit__ = MagicMock(return_value=False)
        
        pipeline = CommodityPipeline()
        
        raw_records = [
            {'name': 'Gold', 'price': 2650, 'source': 'test'},
            {'name': 'Silver', 'price': 31, 'source': 'test'},
        ]
        
        result = pipeline.process_batch(raw_records, source='test_source')
        
        self.assertIn('request_id', result)
        self.assertEqual(result['total'], 2)


if __name__ == '__main__':
    unittest.main()
