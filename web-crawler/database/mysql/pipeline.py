"""
数据管道核心模块

流程:
1. 采集 → 2. 标准化 → 3. 事务处理 → 4. 列级差分 → 5. 更新快照 → 6. 写历史 → 7. 记变更日志
"""
import uuid
import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict

from .connection import transaction, get_cursor


# ============================================================
# 数据模型
# ============================================================

@dataclass
class CommodityRecord:
    """标准化的商品记录"""
    id: str                          # 唯一标识: gold, silver, oil_brent
    name: str                        # 名称
    chinese_name: Optional[str] = None
    category: Optional[str] = None   # 贵金属/能源/工业金属/农产品
    
    price: Decimal = Decimal('0')
    price_unit: str = 'USD'
    weight_unit: Optional[str] = None
    
    change_percent: Optional[Decimal] = None
    change_value: Optional[Decimal] = None
    
    high_price: Optional[Decimal] = None
    low_price: Optional[Decimal] = None
    open_price: Optional[Decimal] = None
    
    source: Optional[str] = None
    source_url: Optional[str] = None
    
    version_ts: datetime = field(default_factory=datetime.now)
    extra_data: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """转为字典 (用于数据库操作)"""
        d = asdict(self)
        d['price'] = float(self.price) if self.price is not None else 0
        d['change_percent'] = float(self.change_percent) if self.change_percent is not None else None
        d['change_value'] = float(self.change_value) if self.change_value is not None else None
        d['high_price'] = float(self.high_price) if self.high_price is not None else None
        d['low_price'] = float(self.low_price) if self.low_price is not None else None
        d['open_price'] = float(self.open_price) if self.open_price is not None else None
        d['extra_data'] = json.dumps(self.extra_data, ensure_ascii=False) if self.extra_data else '{}'
        return d


@dataclass
class ChangeRecord:
    """变更记录"""
    commodity_id: str
    change_type: str      # INSERT / UPDATE / DELETE
    field_name: str
    old_value: Any
    new_value: Any
    change_summary: str
    version_ts: datetime


# ============================================================
# 数据标准化
# ============================================================

# 商品 ID 映射 (统一不同来源的命名)
COMMODITY_ID_MAP = {
    # 贵金属
    'Gold': 'gold', '黄金': 'gold', 'XAU': 'gold', 'COMEX黄金': 'comex_gold',
    'Silver': 'silver', '白银': 'silver', 'XAG': 'silver', 'COMEX白银': 'comex_silver',
    'Platinum': 'platinum', '铂金': 'platinum',
    'Palladium': 'palladium', '钯金': 'palladium',
    
    # 能源
    'Oil (Brent)': 'oil_brent', '布伦特原油': 'oil_brent',
    'Oil (WTI)': 'oil_wti', 'WTI原油': 'oil_wti',
    'Natural Gas': 'natural_gas', '天然气': 'natural_gas',
    'RBOB Gasoline': 'gasoline', 'RBOB汽油': 'gasoline',
    'Heating Oil': 'heating_oil', '取暖油': 'heating_oil',
    
    # 工业金属
    'Copper': 'copper', '铜': 'copper', 'COMEX铜': 'comex_copper',
    'Aluminium': 'aluminum',  '铝': 'aluminum',
    'Zinc': 'zinc', '锌': 'zinc',
    'Nickel': 'nickel', '镍': 'nickel',
    'Lead': 'lead', '铅': 'lead',
    'Tin': 'tin', '锡': 'tin',
    
    # 农产品
    'Corn': 'corn', '玉米': 'corn',
    'Wheat': 'wheat', '小麦': 'wheat',
    'Soybeans': 'soybeans', '大豆': 'soybeans',
    'Cotton': 'cotton', '棉花': 'cotton',
    'Sugar': 'sugar', '糖': 'sugar',
    'Coffee': 'coffee', '咖啡': 'coffee',
    'Cocoa': 'cocoa', '可可': 'cocoa',
    'Rice': 'rice', '大米': 'rice',
    
    # 肉类
    'Live Cattle': 'live_cattle',
    'Lean Hog': 'lean_hog',
    'Feeder Cattle': 'feeder_cattle',
    'Milk': 'milk',
    
    # 其他软商品
    'Orange Juice': 'orange_juice',
    'Lumber': 'lumber',
    'Oats': 'oats',
    'Palm Oil': 'palm_oil', '棕榈油': 'palm_oil',
    'Soybean Oil': 'soybean_oil',
    'Soybean Meal': 'soybean_meal',
    'Rapeseed': 'rapeseed',
    'Coal': 'coal',
}

# 分类映射
CATEGORY_MAP = {
    'gold': '贵金属', 'comex_gold': '贵金属', 'silver': '贵金属', 'comex_silver': '贵金属',
    'platinum': '贵金属', 'palladium': '贵金属',
    'oil_brent': '能源', 'oil_wti': '能源', 'natural_gas': '能源', 
    'gasoline': '能源', 'heating_oil': '能源',
    'copper': '工业金属', 'comex_copper': '工业金属', 'aluminum': '工业金属',
    'zinc': '工业金属', 'nickel': '工业金属', 'lead': '工业金属', 'tin': '工业金属',
    'corn': '农产品', 'wheat': '农产品', 'soybeans': '农产品',
    'cotton': '农产品', 'sugar': '农产品', 'coffee': '农产品',
    'cocoa': '农产品', 'rice': '农产品', 'orange_juice': '农产品',
    'palm_oil': '农产品', 'soybean_oil': '农产品', 'soybean_meal': '农产品',
    'rapeseed': '农产品', 'oats': '农产品', 'milk': '农产品',
    'live_cattle': '农产品', 'lean_hog': '农产品', 'feeder_cattle': '农产品',
    'lumber': '其他', 'coal': '能源',
}


def standardize_record(raw: Dict[str, Any], source: str) -> Optional[CommodityRecord]:
    """
    标准化原始记录
    
    Args:
        raw: 爬虫输出的原始数据
        source: 数据来源标识
    
    Returns:
        标准化的 CommodityRecord，无效数据返回 None
    """
    # 获取商品名称
    name = raw.get('name') or raw.get('chinese_name') or ''
    if not name:
        return None
    
    # 标准化 ID
    commodity_id = COMMODITY_ID_MAP.get(name, name.lower().replace(' ', '_'))
    
    price = raw.get('price') or raw.get('current_price') or 0
    try:
        price = Decimal(str(price))
    except:
        return None  # 价格无效，丢弃
    
    if price <= 0:
        return None
    
    # 获取版本时间
    version_ts = raw.get('version_ts') or raw.get('timestamp') or datetime.now()
    if isinstance(version_ts, str):
        try:
            version_ts = datetime.fromisoformat(version_ts.replace('Z', '+00:00'))
        except:
            version_ts = datetime.now()
    
    # 获取标准英文名称 (如果存在)
    display_name_map = {
        'platinum': 'Platinum',
        'palladium': 'Palladium',
        'gold': 'Gold',
        'silver': 'Silver',
        'oil_brent': 'Oil (Brent)',
        'oil_wti': 'Oil (WTI)',
        'natural_gas': 'Natural Gas',
        'copper': 'Copper',
        'aluminum': 'Aluminium',
        'zinc': 'Zinc',
        'nickel': 'Nickel',
        'lead': 'Lead',
        'tin': 'Tin',
        'corn': 'Corn',
        'wheat': 'Wheat',
        'corn': 'Corn',
        'wheat': 'Wheat',
        'soybeans': 'Soybeans',
        'cocoa': 'Cocoa',
        'rice': 'Rice',
        'coffee': 'Coffee',
        'cotton': 'Cotton',
        'sugar': 'Sugar',
        'live_cattle': 'Live Cattle',
        'lean_hog': 'Lean Hog',
        'feeder_cattle': 'Feeder Cattle',
        'milk': 'Milk',
        'orange_juice': 'Orange Juice',
        'lumber': 'Lumber',
        'oats': 'Oats',
        'palm_oil': 'Palm Oil',
        'soybean_oil': 'Soybean Oil',
        'soybean_meal': 'Soybean Meal',
        'rapeseed': 'Rapeseed',
        'coal': 'Coal'
    }
    
    # 优先使用英文名称
    final_name = display_name_map.get(commodity_id, name)
    
    # 构建标准记录
    return CommodityRecord(
        id=commodity_id,
        name=final_name,
        chinese_name=raw.get('chinese_name', name),
        category=CATEGORY_MAP.get(commodity_id, raw.get('category', '其他')),
        price=price,
        price_unit=raw.get('price_unit', 'USD'),
        weight_unit=raw.get('weight_unit') or raw.get('unit', '').replace('USD/', '').replace('CNY/', ''),
        change_percent=Decimal(str(raw['change_percent'])) if raw.get('change_percent') is not None else None,
        change_value=Decimal(str(raw['change_value'])) if raw.get('change_value') is not None else None,
        high_price=Decimal(str(raw['high_price'])) if raw.get('high_price') is not None else None,
        low_price=Decimal(str(raw['low_price'])) if raw.get('low_price') is not None else None,
        open_price=Decimal(str(raw['open_price'])) if raw.get('open_price') is not None else None,
        source=source,
        source_url=raw.get('url') or raw.get('source_url'),
        version_ts=version_ts,
        extra_data={k: v for k, v in raw.items() if k not in [
            'name', 'chinese_name', 'category', 'price', 'current_price',
            'price_unit', 'weight_unit', 'unit', 'change_percent', 'change_value',
            'high_price', 'low_price', 'open_price', 'url', 'source_url', 
            'version_ts', 'timestamp'
        ]}
    )


def standardize_batch(raw_records: List[Dict], source: str) -> Tuple[str, List[CommodityRecord]]:
    """
    批量标准化
    
    Returns:
        (request_id, standardized_records)
    """
    request_id = f"{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    
    records = []
    for raw in raw_records:
        record = standardize_record(raw, source)
        if record:
            records.append(record)
    
    return request_id, records


# ============================================================
# 列级差分
# ============================================================

# 需要比对的字段
DIFF_FIELDS = [
    'price', 'change_percent', 'change_value',
    'high_price', 'low_price', 'open_price'
]


def diff_records(old: Optional[Dict], new: CommodityRecord) -> List[ChangeRecord]:
    """
    比对新旧记录，返回变更列表
    
    Args:
        old: 旧记录 (从 commodity_latest 读取)
        new: 新记录
    
    Returns:
        变更记录列表
    """
    changes = []
    new_dict = new.to_dict()
    
    if old is None:
        # 新增记录
        changes.append(ChangeRecord(
            commodity_id=new.id,
            change_type='INSERT',
            field_name='*',
            old_value=None,
            new_value=json.dumps(new_dict, ensure_ascii=False, default=str),
            change_summary=f"新增商品: {new.chinese_name or new.name}, 价格 {new.price} {new.price_unit}",
            version_ts=new.version_ts
        ))
        return changes
    
    # 更新记录 - 逐字段比对
    for field in DIFF_FIELDS:
        old_val = old.get(field)
        new_val = new_dict.get(field)
        
        # 类型转换处理
        if old_val is not None:
            old_val = float(old_val) if isinstance(old_val, Decimal) else old_val
        if new_val is not None:
            new_val = float(new_val) if isinstance(new_val, Decimal) else new_val
        
        # 比较 (考虑精度)
        if old_val is None and new_val is None:
            continue
        if old_val is not None and new_val is not None:
            if abs(float(old_val or 0) - float(new_val or 0)) < 0.0001:
                continue
        
        # 生成变更摘要
        summary = _generate_change_summary(new.chinese_name or new.name, field, old_val, new_val)
        
        changes.append(ChangeRecord(
            commodity_id=new.id,
            change_type='UPDATE',
            field_name=field,
            old_value=str(old_val) if old_val is not None else None,
            new_value=str(new_val) if new_val is not None else None,
            change_summary=summary,
            version_ts=new.version_ts
        ))
    
    return changes


def _generate_change_summary(name: str, field: str, old_val: Any, new_val: Any) -> str:
    """生成变更摘要"""
    field_names = {
        'price': '价格',
        'change_percent': '涨跌幅',
        'change_value': '涨跌值',
        'high_price': '最高价',
        'low_price': '最低价',
        'open_price': '开盘价',
    }
    
    field_cn = field_names.get(field, field)
    
    if field == 'price' and old_val and new_val:
        diff = float(new_val) - float(old_val)
        pct = diff / float(old_val) * 100 if float(old_val) != 0 else 0
        direction = '上涨' if diff > 0 else '下跌'
        return f"{name}{field_cn}{direction}: {old_val:.2f} → {new_val:.2f} ({pct:+.2f}%)"
    
    return f"{name}{field_cn}变更: {old_val} → {new_val}"


# ============================================================
# 数据管道主流程
# ============================================================

class CommodityPipeline:
    """商品数据管道"""
    
    def process_batch(self, raw_records: List[Dict], source: str) -> Dict:
        """
        处理一批采集数据
        
        Args:
            raw_records: 爬虫输出的原始数据列表
            source: 数据来源
        
        Returns:
            处理结果统计
        """
        # 1. 标准化
        request_id, records = standardize_batch(raw_records, source)
        
        if not records:
            return {
                'request_id': request_id,
                'total': 0,
                'inserted': 0,
                'updated': 0,
                'unchanged': 0,
                'errors': len(raw_records),
                'changes': []
            }
        
        # 统计
        stats = {
            'request_id': request_id,
            'total': len(records),
            'inserted': 0,
            'updated': 0,
            'unchanged': 0,
            'errors': 0,
            'changes': []
        }
        
        # 2. 开启事务处理
        with transaction() as (conn, cursor):
            # 记录批次开始
            self._start_batch(cursor, request_id, source, len(records))
            
            for record in records:
                try:
                    # 3. 读取旧值并加锁
                    old_record = self._read_and_lock(cursor, record.id)
                    
                    # 4. 时间判断
                    if old_record:
                        old_ts = old_record.get('as_of_ts')
                        if old_ts and record.version_ts < old_ts:
                            # 迟到数据，只写历史，不更新快照
                            self._write_history(cursor, record, request_id)
                            stats['unchanged'] += 1
                            continue
                    
                    
                    # 5. 列级差分
                    changes = diff_records(old_record, record)
                    
                    # 7. 写历史存档 (无论是否有变更，都尝试更新今日历史，确保 heartbeat)
                    self._write_history(cursor, record, request_id)
                    
                    if not changes:
                        # 无变化，但更新 heartbeat (timestamp)
                        self._update_heartbeat(cursor, record.id, record.version_ts)
                        stats['unchanged'] += 1
                        continue
                    
                    # 6. 更新快照
                    if old_record is None:
                        self._insert_latest(cursor, record)
                        stats['inserted'] += 1
                    else:
                        # 只更新变化的列
                        changed_fields = [c.field_name for c in changes if c.field_name != '*']
                        if changed_fields:
                            self._update_latest(cursor, record, changed_fields)
                            stats['updated'] += 1
                        else:
                            # INSERT 类型 (新增)
                            self._insert_latest(cursor, record)
                            stats['inserted'] += 1
                    
                    # 8. 记录变更日志
                    for change in changes:
                        self._write_change_log(cursor, request_id, change)
                        stats['changes'].append({
                            'commodity_id': change.commodity_id,
                            'field': change.field_name,
                            'summary': change.change_summary
                        })
                    
                except Exception as e:
                    stats['errors'] += 1
                    print(f"处理 {record.id} 失败: {e}")
            
            # 更新批次状态
            self._finish_batch(cursor, request_id, stats)
        
        return stats
    
    def _read_and_lock(self, cursor, commodity_id: str) -> Optional[Dict]:
        """读取并锁定快照记录"""
        cursor.execute(
            "SELECT * FROM commodity_latest WHERE id = %s FOR UPDATE",
            (commodity_id,)
        )
        return cursor.fetchone()
    
    def _insert_latest(self, cursor, record: CommodityRecord):
        """插入新快照"""
        data = record.to_dict()
        cursor.execute("""
            INSERT INTO commodity_latest 
            (id, name, chinese_name, category, price, price_unit, weight_unit,
             change_percent, change_value, high_price, low_price, open_price,
             source, source_url, version_ts, as_of_ts, extra_data)
            VALUES 
            (%(id)s, %(name)s, %(chinese_name)s, %(category)s, %(price)s, %(price_unit)s, %(weight_unit)s,
             %(change_percent)s, %(change_value)s, %(high_price)s, %(low_price)s, %(open_price)s,
             %(source)s, %(source_url)s, %(version_ts)s, %(version_ts)s, %(extra_data)s)
        """, data)
    
    def _update_latest(self, cursor, record: CommodityRecord, changed_fields: List[str]):
        """精确更新快照 (只更新变化的列)"""
        data = record.to_dict()
        
        # 构建 UPDATE 语句
        set_clauses = []
        params = []
        
        for field in changed_fields:
            if field in data:
                set_clauses.append(f"{field} = %s")
                params.append(data[field])
        
        # 总是更新时间戳
        set_clauses.append("as_of_ts = %s")
        params.append(data['version_ts'])
        set_clauses.append("version_ts = %s")
        params.append(data['version_ts'])
        
        params.append(record.id)
        
        sql = f"UPDATE commodity_latest SET {', '.join(set_clauses)} WHERE id = %s"
        sql = f"UPDATE commodity_latest SET {', '.join(set_clauses)} WHERE id = %s"
        cursor.execute(sql, params)

    def _update_heartbeat(self, cursor, commodity_id: str, version_ts: datetime):
        """仅更新时间戳 (心跳)"""
        cursor.execute("""
            UPDATE commodity_latest 
            SET as_of_ts = %s, version_ts = %s
            WHERE id = %s
        """, (version_ts, version_ts, commodity_id))
    
    def _write_history(self, cursor, record: CommodityRecord, request_id: str):
        """写入历史存档 (每天只保留一条最新)"""
        data = record.to_dict()
        data['commodity_id'] = record.id
        data['request_id'] = request_id
        # 新增 record_date (截取 version_ts 的日期部分)
        data['record_date'] = record.version_ts.date()
        
        cursor.execute("""
            INSERT INTO commodity_history 
            (commodity_id, name, chinese_name, category, price, price_unit, weight_unit,
             change_percent, change_value, high_price, low_price, open_price,
             source, source_url, record_date, version_ts, request_id, extra_data)
            VALUES 
            (%(commodity_id)s, %(name)s, %(chinese_name)s, %(category)s, %(price)s, %(price_unit)s, %(weight_unit)s,
             %(change_percent)s, %(change_value)s, %(high_price)s, %(low_price)s, %(open_price)s,
             %(source)s, %(source_url)s, %(record_date)s, %(version_ts)s, %(request_id)s, %(extra_data)s)
            ON DUPLICATE KEY UPDATE 
                name = IF(VALUES(version_ts) >= version_ts, VALUES(name), name),
                chinese_name = IF(VALUES(version_ts) >= version_ts, VALUES(chinese_name), chinese_name),
                price = IF(VALUES(version_ts) >= version_ts, VALUES(price), price),
                change_percent = IF(VALUES(version_ts) >= version_ts, VALUES(change_percent), change_percent),
                change_value = IF(VALUES(version_ts) >= version_ts, VALUES(change_value), change_value),
                high_price = IF(VALUES(version_ts) >= version_ts, VALUES(high_price), high_price),
                low_price = IF(VALUES(version_ts) >= version_ts, VALUES(low_price), low_price),
                version_ts = IF(VALUES(version_ts) >= version_ts, VALUES(version_ts), version_ts),
                request_id = IF(VALUES(version_ts) >= version_ts, VALUES(request_id), request_id),
                recorded_at = CURRENT_TIMESTAMP(3)
        """, data)
    
    def _write_change_log(self, cursor, request_id: str, change: ChangeRecord):
        """写入变更日志"""
        cursor.execute("""
            INSERT INTO change_log 
            (request_id, commodity_id, change_type, field_name, old_value, new_value, 
             version_ts, change_summary)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            request_id,
            change.commodity_id,
            change.change_type,
            change.field_name,
            change.old_value,
            change.new_value,
            change.version_ts,
            change.change_summary
        ))
    
    def _start_batch(self, cursor, request_id: str, source: str, total: int):
        """记录批次开始"""
        cursor.execute("""
            INSERT INTO crawl_batch (request_id, source, total_records, started_at, status)
            VALUES (%s, %s, %s, NOW(3), 'RUNNING')
        """, (request_id, source, total))
    
    def _finish_batch(self, cursor, request_id: str, stats: Dict):
        """更新批次状态"""
        status = 'SUCCESS' if stats['errors'] == 0 else 'PARTIAL' if stats['updated'] + stats['inserted'] > 0 else 'FAILED'
        cursor.execute("""
            UPDATE crawl_batch 
            SET finished_at = NOW(3), 
                status = %s,
                inserted_count = %s,
                updated_count = %s,
                unchanged_count = %s,
                error_count = %s
            WHERE request_id = %s
        """, (status, stats['inserted'], stats['updated'], stats['unchanged'], stats['errors'], request_id))


# ============================================================
# 查询接口
# ============================================================

def get_latest_prices(category: Optional[str] = None) -> List[Dict]:
    """获取最新价格"""
    with get_cursor() as cursor:
        if category:
            cursor.execute(
                "SELECT * FROM commodity_latest WHERE category = %s ORDER BY id",
                (category,)
            )
        else:
            cursor.execute("SELECT * FROM commodity_latest ORDER BY category, id")
        return cursor.fetchall()


def get_price_history(commodity_id: str, start_time: datetime = None, end_time: datetime = None) -> List[Dict]:
    """获取价格历史"""
    with get_cursor() as cursor:
        sql = "SELECT * FROM commodity_history WHERE commodity_id = %s"
        params = [commodity_id]
        
        if start_time:
            sql += " AND version_ts >= %s"
            params.append(start_time)
        if end_time:
            sql += " AND version_ts <= %s"
            params.append(end_time)
        
        sql += " ORDER BY version_ts DESC"
        cursor.execute(sql, params)
        return cursor.fetchall()


def get_commodities_by_date(target_date: datetime = None) -> List[Dict]:
    """
    获取指定日期的所有商品历史记录
    (用于当 commodity_latest 缺失时，从历史归档中恢复当天数据)
    """
    if target_date is None:
        target_date = datetime.now()
        
    date_str = target_date.strftime("%Y-%m-%d")
    
    with get_cursor() as cursor:
        # 简单查询指定日期的记录
        cursor.execute(
            "SELECT * FROM commodity_history WHERE record_date = %s",
            (date_str,)
        )
        return cursor.fetchall()


def get_recent_changes(request_id: str = None, limit: int = 100) -> List[Dict]:
    """获取最近变更 (供 LLM 消费)"""
    with get_cursor() as cursor:
        if request_id:
            cursor.execute(
                "SELECT * FROM v_recent_changes WHERE request_id = %s ORDER BY version_ts DESC",
                (request_id,)
            )
        else:
            cursor.execute(
                "SELECT * FROM v_recent_changes ORDER BY version_ts DESC LIMIT %s",
                (limit,)
            )
        return cursor.fetchall()


def get_price_changes(hours: int = 24) -> List[Dict]:
    """获取价格变动 (供前端展示)"""
    with get_cursor() as cursor:
        cursor.execute("""
            SELECT * FROM v_price_changes 
            WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s HOUR)
            ORDER BY created_at DESC
        """, (hours,))
        return cursor.fetchall()


# ============================================================
# 便捷入口
# ============================================================

# 全局 Pipeline 实例
_pipeline: Optional[CommodityPipeline] = None


def get_pipeline() -> CommodityPipeline:
    """获取 Pipeline 实例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = CommodityPipeline()
    return _pipeline


def process_crawled_data(raw_records: List[Dict], source: str) -> Dict:
    """
    处理爬取的数据 (对外接口)
    
    Usage:
        from database.mysql.pipeline import process_crawled_data
        
        # 爬虫输出
        data = scraper.scrape()
        
        # 写入数据库
        result = process_crawled_data(data, source='business_insider')
        print(f"新增: {result['inserted']}, 更新: {result['updated']}")
    """
    return get_pipeline().process_batch(raw_records, source)
