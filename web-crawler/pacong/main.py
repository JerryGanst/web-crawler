#!/usr/bin/env python3
"""
Pacong 爬虫系统主入口
模块化商品数据爬取系统
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from pacong.core import init_config, init_logging, get_logger
from pacong.services import CommodityService
from pacong.scrapers import ScraperFactory


def setup_argument_parser() -> argparse.ArgumentParser:
    """设置命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="🚀 Pacong - 智能数据爬取系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
🎯 快速开始:
  %(prog)s                                    # 运行所有数据源
  %(prog)s --scrapers business_insider        # 运行特定数据源
  %(prog)s --list-scrapers                    # 查看可用数据源
  %(prog)s --log-level DEBUG                  # 调试模式

📝 添加新数据源: 编辑 config/settings.yaml
📊 查看结果: ls reports/
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='配置文件路径'
    )
    
    parser.add_argument(
        '--scrapers', '-s',
        nargs='+',
        help='要使用的爬虫名称列表'
    )
    
    parser.add_argument(
        '--list-scrapers',
        action='store_true',
        help='列出所有可用的爬虫'
    )
    
    parser.add_argument(
        '--output-dir', '-o',
        type=str,
        help='输出目录路径'
    )
    
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='日志级别'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='静默模式，只输出错误'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version='Pacong 2.0 - 模块化爬虫系统'
    )
    
    return parser


def validate_scrapers(scraper_names: List[str]) -> List[str]:
    """验证爬虫名称"""
    available_scrapers = ScraperFactory.list_available_scrapers()
    invalid_scrapers = [name for name in scraper_names if name not in available_scrapers]
    
    if invalid_scrapers:
        print(f"❌ 无效的爬虫名称: {', '.join(invalid_scrapers)}")
        print(f"📋 可用爬虫: {', '.join(available_scrapers)}")
        sys.exit(1)
    
    return scraper_names


def list_scrapers():
    """列出所有可用爬虫"""
    scrapers = ScraperFactory.list_available_scrapers()
    
    print("📋 可用爬虫列表:")
    print("=" * 50)
    
    if not scrapers:
        print("❌ 未找到任何已注册的爬虫")
        return
    
    for i, scraper_name in enumerate(scrapers, 1):
        print(f"{i}. {scraper_name}")
    
    print(f"\n总计: {len(scrapers)} 个爬虫")


def print_summary(result: dict):
    """打印分析摘要"""
    if 'error' in result:
        print(f"❌ 错误: {result['error']}")
        return
    
    summary = result.get('summary', {})
    main_summary = summary.get('summary', {})
    category_stats = summary.get('category_stats', {})
    top_performers = summary.get('top_performers', {})
    
    print("\n" + "=" * 60)
    print("📊 商品数据分析结果摘要")
    print("=" * 60)
    
    # 基本统计
    print(f"📈 总商品数: {main_summary.get('total_commodities', 0)}")
    print(f"📊 平均涨跌幅: {main_summary.get('avg_change_percent', 0):.2f}%")
    print(f"🟢 上涨商品: {main_summary.get('gainers', 0)}")
    print(f"🔴 下跌商品: {main_summary.get('losers', 0)}")
    print(f"⚪ 持平商品: {main_summary.get('unchanged', 0)}")
    print(f"🕐 数据时间: {main_summary.get('data_time', 'N/A')}")
    
    # 分类统计
    if category_stats:
        print(f"\n📋 分类统计:")
        for category, stats in category_stats.items():
            print(f"  {category}: {stats['count']} 个 (平均涨跌: {stats['avg_change']:.2f}%)")
    
    # 表现最佳
    if top_performers:
        top_gainers = top_performers.get('top_gainers', [])
        top_losers = top_performers.get('top_losers', [])
        
        if top_gainers:
            print(f"\n🚀 涨幅榜前5:")
            for i, item in enumerate(top_gainers[:5], 1):
                print(f"  {i}. {item['chinese_name']} ({item['name']}): +{item['change_percent']:.2f}%")
        
        if top_losers:
            print(f"\n📉 跌幅榜前5:")
            for i, item in enumerate(top_losers[:5], 1):
                print(f"  {i}. {item['chinese_name']} ({item['name']}): {item['change_percent']:.2f}%")
    
    # 文件信息
    files = result.get('files', {})
    if files:
        print(f"\n💾 输出文件:")
        for file_type, file_path in files.items():
            print(f"  {file_type.upper()}: {file_path}")


def main():
    """主函数"""
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    try:
        # 初始化配置
        if args.config:
            config = init_config(args.config)
        else:
            config = init_config()
        
        # 覆盖配置
        if args.output_dir:
            config.set('output.reports_dir', args.output_dir)
        
        if args.quiet:
            config.set('logging.level', 'ERROR')
        elif args.log_level:
            config.set('logging.level', args.log_level)
        
        # 初始化日志
        logger = init_logging()
        
        # 打印欢迎信息
        if not args.quiet:
            print("🎯 Pacong 模块化商品数据爬取系统")
            print("=" * 50)
            print("📊 通过模块化架构提供全面的商品数据")
            print()
        
        # 处理命令
        if args.list_scrapers:
            list_scrapers()
            return
        
        # 验证爬虫名称
        scraper_names = None
        if args.scrapers:
            scraper_names = validate_scrapers(args.scrapers)
            logger.info(f"使用指定爬虫: {', '.join(scraper_names)}")
        
        # 创建服务并运行分析
        commodity_service = CommodityService()
        result = commodity_service.run_full_analysis(scraper_names)
        
        # 打印结果
        if not args.quiet:
            print_summary(result)
        
        logger.info("🎉 系统运行完成")
        
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断操作")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 系统错误: {e}")
        if not args.quiet:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 