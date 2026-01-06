#!/usr/bin/env python3
"""
中塑在线产品SID查找工具

用法:
    python scripts/find_21cp_products.py GPPS
    python scripts/find_21cp_products.py HIPS
    python scripts/find_21cp_products.py --list  # 列出所有已配置产品
"""
import sys
import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from scrapers.plastic21cp import Plastic21CPScraper


def list_products():
    """列出所有已配置的产品"""
    scraper = Plastic21CPScraper()
    print("已配置的塑料产品:")
    print("-" * 60)
    for key, config in scraper.PRODUCTS.items():
        print(f"  {key:<15} -> {config['name']:<15} (SID: {config['sid'][:20]}...)")


def search_product(keyword: str):
    """搜索产品（需要手动提供SID）"""
    print(f"""
要添加 {keyword} 产品到爬虫配置，请按以下步骤操作：

1. 打开浏览器访问：https://quote.21cp.com/
2. 搜索或导航到 {keyword} 产品页面
3. 打开浏览器开发者工具 (F12) -> Network 标签
4. 刷新页面，找到 listHistory API 请求
5. 复制 avgMarketAreaProductSid 参数值

然后在 scrapers/plastic21cp.py 的 PRODUCTS 字典中添加：

    "{keyword.lower()}_east": {{
        "sid": "你获取的SID",
        "name": "{keyword}(华东)",
        "category": "塑料",
        "unit": "元/吨",
        "referer": "https://quote.21cp.com/avg_area/list/XXX-{keyword}.html"
    }},
    "{keyword.lower()}_south": {{
        "sid": "华南区域的SID",
        "name": "{keyword}(华南)",
        "category": "塑料",
        "unit": "元/吨",
        "referer": "https://quote.21cp.com/avg_area/list/XXX-{keyword}.html"
    }},
    "{keyword.lower()}_north": {{
        "sid": "华北区域的SID",
        "name": "{keyword}(华北)",
        "category": "塑料",
        "unit": "元/吨",
        "referer": "https://quote.21cp.com/avg_area/list/XXX-{keyword}.html"
    }},
""")


def main():
    parser = argparse.ArgumentParser(description="中塑在线产品SID查找工具")
    parser.add_argument("keyword", nargs="?", help="要搜索的产品关键词 (如 GPPS, HIPS)")
    parser.add_argument("--list", "-l", action="store_true", help="列出所有已配置产品")
    
    args = parser.parse_args()
    
    if args.list:
        list_products()
    elif args.keyword:
        search_product(args.keyword)
    else:
        parser.print_help()
        print("\n当前已配置产品:")
        list_products()


if __name__ == "__main__":
    main()
