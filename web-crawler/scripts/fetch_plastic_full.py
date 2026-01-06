#!/usr/bin/env python3
"""
中塑在线 21CP 塑料价格历史数据全量入库脚本

用法:
    python scripts/fetch_plastic_full.py                     # 获取所有产品
    python scripts/fetch_plastic_full.py --product abs_south # 指定产品
    python scripts/fetch_plastic_full.py --start 2020-01-01  # 指定开始日期
    python scripts/fetch_plastic_full.py --discover          # 发现更多产品SID
    python scripts/fetch_plastic_full.py --dry-run           # 只预览，不入库
"""
import sys
import argparse
from pathlib import Path
from datetime import date

# 添加项目根目录到路径
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from scrapers.plastic21cp import Plastic21CPScraper


def discover_product_sids():
    """
    使用 Playwright 发现更多产品的 SID
    访问页面并提取 API 调用中的 avgMarketAreaProductSid
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ 需要安装 playwright: pip install playwright && playwright install chromium")
        return []
    
    import time
    import re
    
    # 已知的产品页面
    product_pages = [
        ("ABS", "https://quote.21cp.com/avg_area/list/303561829995569152-ABS.html"),
        # 可以添加更多页面
    ]
    
    discovered = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        
        for product_name, url in product_pages:
            page = context.new_page()
            sids = []
            
            def on_response(response):
                if 'avgMarketAreaProduct/api/listHistory' in response.url:
                    try:
                        match = re.search(r'avgMarketAreaProductSid=(\d+)', response.url)
                        if match:
                            sid = match.group(1)
                            # 获取响应数据以提取区域名称
                            data = response.json()
                            if data.get('code') == 200 and data.get('data'):
                                area = data['data'][0].get('marketAreaName', '未知区域')
                                sids.append({
                                    'sid': sid,
                                    'area': area,
                                    'product': product_name
                                })
                    except:
                        pass
            
            page.on('response', on_response)
            
            print(f"📡 扫描 {product_name} 页面...")
            page.goto(url, timeout=30000)
            time.sleep(5)
            
            discovered.extend(sids)
            page.close()
        
        browser.close()
    
    return discovered


def main():
    parser = argparse.ArgumentParser(
        description="中塑在线 21CP 塑料价格全量历史数据入库"
    )
    parser.add_argument(
        "--product",
        default=None,
        help="产品类型 (如 abs_south)，默认处理所有产品"
    )
    parser.add_argument(
        "--start", 
        default="2020-01-01",
        help="开始日期 (YYYY-MM-DD), 默认: 2020-01-01"
    )
    parser.add_argument(
        "--end",
        default=None,
        help="结束日期 (YYYY-MM-DD), 默认: 今天"
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
    parser.add_argument(
        "--discover",
        action="store_true",
        help="发现更多产品 SID"
    )
    parser.add_argument(
        "--to-redis",
        action="store_true",
        help="同时写入 Redis 历史缓存"
    )
    
    args = parser.parse_args()
    
    # 发现模式
    if args.discover:
        print("🔍 发现产品 SID...")
        discovered = discover_product_sids()
        if discovered:
            print(f"\n发现 {len(discovered)} 个产品:")
            for item in discovered:
                print(f"  {item['product']}({item['area']}): {item['sid']}")
            print("\n将以上 SID 添加到 scrapers/plastic21cp.py 的 PRODUCTS 字典中")
        else:
            print("未发现新产品")
        return 0
    
    end_date = args.end or date.today().isoformat()
    scraper = Plastic21CPScraper()
    
    # 确定要处理的产品
    if args.product:
        products = [args.product]
    else:
        products = scraper.list_products()
    
    print(f"""
╔══════════════════════════════════════════════════════╗
║     中塑在线 21CP 塑料价格全量历史数据入库            ║
╠══════════════════════════════════════════════════════╣
║  产品: {', '.join(products):<45}║
║  时间范围: {args.start} → {end_date:<25}║
║  批次大小: {args.batch_size:<41}║
║  模式: {'预览 (DRY RUN)' if args.dry_run else '正式入库':<43}║
╚══════════════════════════════════════════════════════╝
""")
    
    total_inserted = 0
    total_updated = 0
    total_records = 0
    
    for product in products:
        print(f"\n📥 正在获取 {product} 历史数据...")
        records = scraper.fetch(product, start_date=args.start, end_date=end_date)
        
        if not records:
            print(f"  ⚠️ 未获取到数据")
            continue
        
        total_records += len(records)
        
        # 按日期排序
        records.sort(key=lambda x: x.get("price_date", ""))
        
        # 预览前几条
        print(f"  📋 数据预览 (前3条):")
        for r in records[:3]:
            change = r.get('change_percent') or 0
            print(f"    {r['price_date']}: ¥{r['price']:.2f} ({change:+.2f}%)")
        if len(records) > 3:
            print(f"    ... 还有 {len(records) - 3} 条")
        
        if args.dry_run:
            continue
        
        # 入库 MySQL
        print(f"\n  💾 开始入库...")
        try:
            from database.mysql.pipeline import CommodityPipeline
            pipeline = CommodityPipeline()
            
            for i in range(0, len(records), args.batch_size):
                batch = records[i:i + args.batch_size]
                batch_num = i // args.batch_size + 1
                total_batches = (len(records) + args.batch_size - 1) // args.batch_size
                
                print(f"    处理批次 {batch_num}/{total_batches} ({len(batch)} 条)...", end=" ")
                
                stats = pipeline.process_batch(batch, source="中塑在线")
                total_inserted += stats.get("inserted", 0)
                total_updated += stats.get("updated", 0)
                print(f"✓ 新增:{stats.get('inserted', 0)} 更新:{stats.get('updated', 0)}")
                
        except Exception as e:
            print(f"  ❌ 入库失败: {e}")
        
        # 写入 Redis
        if args.to_redis:
            print(f"\n  📡 写入 Redis...")
            try:
                from core.price_history import PriceHistoryManager
                pm = PriceHistoryManager()
                
                product_info = scraper.PRODUCTS.get(product, {})
                redis_name = product_info.get("name", product)
                
                for r in records:
                    pm.save_daily_price(
                        commodity_name=redis_name,
                        price=r["price"],
                        change_percent=r.get("change_percent") or 0,
                        source="中塑在线",
                        date=r["price_date"]
                    )
                print(f"    ✅ 已写入 {len(records)} 条到 Redis")
            except Exception as e:
                print(f"    ❌ Redis 写入失败: {e}")
    
    if args.dry_run:
        print(f"\n🔍 预览模式，未执行入库操作")
        print(f"   共获取 {total_records} 条记录")
    else:
        print(f"""
╔══════════════════════════════════════════════════════╗
║                    入库完成                           ║
╠══════════════════════════════════════════════════════╣
║  总记录数: {total_records:<41}║
║  新增: {total_inserted:<45}║
║  更新: {total_updated:<45}║
╚══════════════════════════════════════════════════════╝
""")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
