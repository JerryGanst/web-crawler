#!/usr/bin/env python3
"""
中塑在线 21CP WTI 原油历史数据全量入库脚本

用法:
    python scripts/fetch_21cp_full.py                      # 默认从2005-01-01至今
    python scripts/fetch_21cp_full.py --start 2020-01-01   # 从指定日期开始
    python scripts/fetch_21cp_full.py --dry-run            # 只预览，不入库
"""
import sys
import argparse
from pathlib import Path
from datetime import date

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from scrapers.intercrude import InterCrudePriceScraper


def main():
    parser = argparse.ArgumentParser(
        description="中塑在线 21CP WTI 原油全量历史数据入库"
    )
    parser.add_argument(
        "--start", 
        default="2005-01-01",
        help="开始日期 (YYYY-MM-DD), 默认: 2005-01-01"
    )
    parser.add_argument(
        "--end",
        default=None,
        help="结束日期 (YYYY-MM-DD), 默认: 今天"
    )
    parser.add_argument(
        "--product",
        default="wti",
        help="产品类型, 默认: wti"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="每批处理记录数, 默认: 500"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际入库"
    )
    
    args = parser.parse_args()
    
    end_date = args.end or date.today().isoformat()
    
    print(f"""
╔══════════════════════════════════════════════════════╗
║     中塑在线 21CP WTI 原油全量历史数据入库            ║
╠══════════════════════════════════════════════════════╣
║  产品: {args.product:<45}║
║  时间范围: {args.start} → {end_date:<25}║
║  批次大小: {args.batch_size:<41}║
║  模式: {'预览 (DRY RUN)' if args.dry_run else '正式入库':<43}║
╚══════════════════════════════════════════════════════╝
""")
    
    # 1. 获取数据
    print("📥 正在获取历史数据...")
    scraper = InterCrudePriceScraper()
    records = scraper.fetch(
        product=args.product,
        start_date=args.start,
        end_date=end_date
    )
    
    if not records:
        print("❌ 未获取到任何数据")
        return 1
    
    print(f"✅ 共获取 {len(records)} 条记录")
    
    # 按日期排序
    records.sort(key=lambda x: x.get("price_date", ""))
    
    # 预览前几条
    print("\n📋 数据预览 (前5条):")
    print("-" * 60)
    for r in records[:5]:
        change = r.get('change_percent') or 0
        print(f"  {r['price_date']}: ${r['price']:.2f} ({change:+.2f}%)")
    if len(records) > 5:
        print(f"  ... 还有 {len(records) - 5} 条")
    print("-" * 60)
    
    if args.dry_run:
        print("\n🔍 预览模式，不执行入库操作")
        return 0
    
    # 2. 分批入库
    print(f"\n💾 开始分批入库 (每批 {args.batch_size} 条)...")
    from database.mysql.pipeline import CommodityPipeline
    pipeline = CommodityPipeline()
    
    total_inserted = 0
    total_updated = 0
    total_unchanged = 0
    total_errors = 0
    
    for i in range(0, len(records), args.batch_size):
        batch = records[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1
        total_batches = (len(records) + args.batch_size - 1) // args.batch_size
        
        print(f"  处理批次 {batch_num}/{total_batches} ({len(batch)} 条)...", end=" ")
        
        try:
            stats = pipeline.process_batch(batch, source="中塑在线")
            total_inserted += stats.get("inserted", 0)
            total_updated += stats.get("updated", 0)
            total_unchanged += stats.get("unchanged", 0)
            total_errors += stats.get("errors", 0)
            if stats.get("errors", 0) > 0:
                print(f"⚠ 新增:{stats.get('inserted', 0)} 更新:{stats.get('updated', 0)} 错误:{stats.get('errors', 0)}")
            else:
                print(f"✓ 新增:{stats.get('inserted', 0)} 更新:{stats.get('updated', 0)}")
        except Exception as e:
            print(f"✗ 批次错误: {e}")
            import traceback
            traceback.print_exc()
            total_errors += len(batch)
    
    # 3. 汇总
    print(f"""
╔══════════════════════════════════════════════════════╗
║                    入库完成                           ║
╠══════════════════════════════════════════════════════╣
║  总记录数: {len(records):<41}║
║  新增: {total_inserted:<45}║
║  更新: {total_updated:<45}║
║  未变: {total_unchanged:<45}║
║  错误: {total_errors:<45}║
╚══════════════════════════════════════════════════════╝
""")
    
    return 0 if total_errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
