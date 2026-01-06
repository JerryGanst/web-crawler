#!/usr/bin/env python3
"""
大宗商品数据采集管道

运行方式:
    # 单次运行
    python scripts/run_commodity_pipeline.py
    
    # 指定来源
    python scripts/run_commodity_pipeline.py --source sina
    
    # 持续运行 (每5分钟)
    python scripts/run_commodity_pipeline.py --interval 300

环境变量:
    MYSQL_HOST     - MySQL 主机 (默认 localhost)
    MYSQL_PORT     - MySQL 端口 (默认 3306)
    MYSQL_USER     - MySQL 用户 (默认 root)
    MYSQL_PASSWORD - MySQL 密码
    MYSQL_DATABASE - 数据库名 (默认 trendradar)
"""
import os
import sys
import time
import argparse
from datetime import datetime

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.commodity import CommodityScraper


def run_pipeline(source: str = None, verbose: bool = True):
    """
    运行数据采集管道
    """
    try:
        from database.mysql import process_crawled_data, test_connection
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("请确保已安装依赖: pip install pymysql dbutils")
        return None
    
    # 测试数据库连接
    if not test_connection():
        print("❌ 数据库连接失败，请检查 MySQL 配置")
        return None
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"🚀 开始采集大宗商品数据 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
    
    # 1. 爬取数据
    scraper = CommodityScraper()
    raw_data = scraper.scrape()
    
    if not raw_data:
        print("⚠️ 未获取到数据")
        return None
    
    if verbose:
        print(f"\n📥 采集到 {len(raw_data)} 条原始数据")
    
    # 2. 确定数据来源
    sources = set()
    for item in raw_data:
        src = item.get('source', 'unknown')
        sources.add(src)
    
    # 3. 按来源分组处理
    results = []
    for src in sources:
        src_data = [d for d in raw_data if d.get('source', 'unknown') == src]
        
        if verbose:
            print(f"\n📤 处理来源 [{src}]: {len(src_data)} 条")
        
        # 4. 调用管道处理
        result = process_crawled_data(src_data, source=src)
        results.append(result)
        
        if verbose:
            print(f"   ✅ 新增: {result['inserted']}, 更新: {result['updated']}, "
                  f"无变化: {result['unchanged']}, 错误: {result['errors']}")
            
            # 显示变更摘要
            if result['changes']:
                print(f"\n   📝 变更详情:")
                for change in result['changes'][:5]:  # 只显示前5条
                    print(f"      - {change['summary']}")
                if len(result['changes']) > 5:
                    print(f"      ... 还有 {len(result['changes']) - 5} 条变更")
    
    # 5. 汇总统计
    total_stats = {
        'inserted': sum(r['inserted'] for r in results),
        'updated': sum(r['updated'] for r in results),
        'unchanged': sum(r['unchanged'] for r in results),
        'errors': sum(r['errors'] for r in results),
        'total_changes': sum(len(r['changes']) for r in results),
    }
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"📊 处理完成统计:")
        print(f"   - 新增: {total_stats['inserted']}")
        print(f"   - 更新: {total_stats['updated']}")
        print(f"   - 无变化: {total_stats['unchanged']}")
        print(f"   - 错误: {total_stats['errors']}")
        print(f"   - 总变更数: {total_stats['total_changes']}")
        print(f"{'='*60}\n")
    
    return total_stats


def run_continuous(interval: int = 300, verbose: bool = True):
    """
    持续运行模式
    
    Args:
        interval: 采集间隔 (秒)
    """
    print(f"🔄 进入持续运行模式，间隔 {interval} 秒")
    print("按 Ctrl+C 退出\n")
    
    run_count = 0
    while True:
        try:
            run_count += 1
            print(f"\n🔁 第 {run_count} 次采集")
            
            run_pipeline(verbose=verbose)
            
            print(f"⏰ 等待 {interval} 秒...")
            time.sleep(interval)
            
        except KeyboardInterrupt:
            print("\n\n👋 已停止运行")
            break
        except Exception as e:
            print(f"❌ 运行错误: {e}")
            print(f"⏰ {interval} 秒后重试...")
            time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description='大宗商品数据采集管道')
    parser.add_argument('--source', '-s', help='指定数据来源')
    parser.add_argument('--interval', '-i', type=int, help='持续运行间隔(秒)')
    parser.add_argument('--quiet', '-q', action='store_true', help='安静模式')
    parser.add_argument('--init-db', action='store_true', help='初始化数据库')
    
    args = parser.parse_args()
    
    # 初始化数据库
    if args.init_db:
        from database.mysql import init_database
        init_database()
        return
    
    verbose = not args.quiet
    
    if args.interval:
        run_continuous(interval=args.interval, verbose=verbose)
    else:
        run_pipeline(source=args.source, verbose=verbose)


if __name__ == '__main__':
    main()
