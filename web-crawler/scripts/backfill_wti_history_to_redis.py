#!/usr/bin/env python3
"""
一次性脚本：从 MySQL 的 commodity_history 回填 WTI 原油（oil_wti）历史数据到 Redis

用途：
    python scripts/backfill_wti_history_to_redis.py           # 默认全量 2005-01-01 至今
    python scripts/backfill_wti_history_to_redis.py --start 2010-01-01 --end 2020-12-31
    python scripts/backfill_wti_history_to_redis.py --dry-run # 只预览，不写入 Redis

说明：
- 数据来源：MySQL 表 commodity_history 中 commodity_id = 'oil_wti'
- 写入目标：Redis Hash key = trendradar:history:WTI原油
- 不使用 PriceHistoryManager.save_daily_price，以避免 30 天自动清理逻辑，
  但复用相同的 Redis 连接与数据结构格式。
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, date
from collections import OrderedDict
import json

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from database.mysql.connection import get_cursor  # type: ignore
from core.price_history import PriceHistoryManager  # type: ignore


def fetch_wti_history_from_mysql(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """从 MySQL 的 commodity_history 中读取 oil_wti 全历史/区间数据"""
    conditions = ["commodity_id = %s"]
    params: list = ["oil_wti"]

    if start_date:
        conditions.append("version_ts >= %s")
        params.append(f"{start_date} 00:00:00")
    if end_date:
        conditions.append("version_ts <= %s")
        params.append(f"{end_date} 23:59:59")

    where_clause = " AND ".join(conditions)

    sql = f"""
        SELECT commodity_id, price, change_percent, source, version_ts
        FROM commodity_history
        WHERE {where_clause}
        ORDER BY version_ts ASC
    """

    with get_cursor() as cursor:
        cursor.execute(sql, params)
        rows = cursor.fetchall()

    return rows or []


def group_by_date(rows: list[dict]) -> "OrderedDict[str, dict]":
    """按日期分组，保留每天最后一条记录"""
    by_date: dict[str, dict] = {}

    for r in rows:
        ts: datetime = r["version_ts"]
        d = ts.date().isoformat()
        # 简单策略：后来的覆盖先前的，得到当日最新价格
        by_date[d] = {
            "price": float(r["price"]),
            "change_percent": float(r["change_percent"]) if r["change_percent"] is not None else 0.0,
            "source": r.get("source") or "中塑在线",
        }

    # 按日期排序
    ordered = OrderedDict()
    for d in sorted(by_date.keys()):
        ordered[d] = by_date[d]
    return ordered


def backfill_to_redis(
    history_by_date: "OrderedDict[str, dict]",
    redis_name: str = "WTI原油",
    dry_run: bool = False,
) -> None:
    """将按日历史数据写入 Redis Hash trendradar:history:<redis_name>"""
    ph = PriceHistoryManager()
    if not ph.client:
        print("❌ Redis 连接不可用，终止回填")
        return

    key = f"{ph.prefix}{redis_name}"
    total = len(history_by_date)
    print(f"\n🔁 准备回填到 Redis: key={key}, 共 {total} 天")

    written = 0
    for i, (d, rec) in enumerate(history_by_date.items(), start=1):
        data = {
            "price": rec["price"],
            "change_percent": rec["change_percent"],
            "source": rec["source"],
            "timestamp": datetime.now().isoformat(),
        }

        if dry_run:
            if i <= 5:
                print(f"  [DRY] {d}: {data}")
        else:
            ph.client.hset(key, d, json.dumps(data, ensure_ascii=False))
            written += 1
            if i % 500 == 0 or i == total:
                print(f"  已写入 {written}/{total} 天")

    if dry_run:
        print("\n🔍 预览模式，未实际写入 Redis")
    else:
        print(f"\n✅ 回填完成，写入 {written} 天到 {key}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="从 MySQL commodity_history 回填 WTI 原油历史到 Redis"
    )
    parser.add_argument(
        "--start",
        help="开始日期 YYYY-MM-DD，默认从最早记录开始",
        default=None,
    )
    parser.add_argument(
        "--end",
        help="结束日期 YYYY-MM-DD，默认到今天",
        default=None,
    )
    parser.add_argument(
        "--redis-name",
        help="Redis 中使用的商品名称 (即前端使用的名称)",
        default="WTI原油",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅预览，不写入 Redis",
    )

    args = parser.parse_args()

    end = args.end or date.today().isoformat()

    print(
        """
╔══════════════════════════════════════════════════════╗
║    从 MySQL 回填 WTI 原油历史数据到 Redis            ║
╠══════════════════════════════════════════════════════╣
║  commodity_id:  oil_wti                             ║
║  Redis 名称:   {redis_name:<43}║
║  时间范围:     {start} → {end:<25}║
║  模式:         {mode:<45}║
╚══════════════════════════════════════════════════════╝
""".format(
            redis_name=args.redis_name,
            start=args.start or "<最早记录>",
            end=end,
            mode="预览 (DRY RUN)" if args.dry_run else "正式回填",
        )
    )

    print("📥 从 MySQL 读取历史数据...")
    rows = fetch_wti_history_from_mysql(args.start, end)
    if not rows:
        print("❌ MySQL 未返回任何记录 (oil_wti)")
        return 1

    print(f"✅ 共获取 {len(rows)} 条历史记录")

    history_by_date = group_by_date(rows)
    print(f"📅 覆盖 {len(history_by_date)} 个交易日，从 {next(iter(history_by_date.keys()))} 到 {next(reversed(history_by_date.keys()))}")

    # 预览前几天
    print("\n📋 按日聚合预览 (前5天):")
    print("-" * 60)
    for i, (d, rec) in enumerate(history_by_date.items()):
        if i >= 5:
            break
        print(f"  {d}: price={rec['price']:.2f}, change={rec['change_percent']:+.2f}%, source={rec['source']}")
    print("-" * 60)

    backfill_to_redis(history_by_date, redis_name=args.redis_name, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
