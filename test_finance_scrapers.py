"""
测试财经爬虫 - 模块2测试
"""
import sys
sys.path.insert(0, '.')

print("=" * 60)
print("🧪 模块2测试：财经数据源")
print("=" * 60)

# 注册财经爬虫
from scrapers.finance import register_finance_scrapers, SinaForexScraper, CoinGeckoScraper, HackerNewsScraper
register_finance_scrapers()

# 测试1：新浪外汇
print("\n📋 测试1：新浪财经外汇数据")
print("-" * 40)

sina_scraper = SinaForexScraper()
results = sina_scraper.scrape()

if results:
    print(f"✅ 成功获取 {len(results)} 条汇率数据")
    for item in results:
        extra = item.get("extra", {})
        print(f"   💰 {item['title']}")
        print(f"      买入: {extra.get('buy_price')} | 卖出: {extra.get('sell_price')}")
else:
    print("❌ 获取失败")

# 测试2：CoinGecko 加密货币
print("\n📋 测试2：CoinGecko 加密货币")
print("-" * 40)

crypto_scraper = CoinGeckoScraper()
results2 = crypto_scraper.scrape()

if results2:
    print(f"✅ 成功获取 {len(results2)} 条加密货币数据")
    for item in results2[:5]:  # 前5条
        extra = item.get("extra", {})
        print(f"   🪙 {item['title']}")
else:
    print("❌ 获取失败")

# 测试3：Hacker News
print("\n📋 测试3：Hacker News 热门")
print("-" * 40)

hn_scraper = HackerNewsScraper()
results3 = hn_scraper.scrape()

if results3:
    print(f"✅ 成功获取 {len(results3)} 条新闻")
    for item in results3[:5]:  # 前5条
        extra = item.get("extra", {})
        print(f"   📰 [{extra.get('score', 0)}分] {item['title'][:50]}...")
        print(f"      🔗 {item['url'][:60]}...")
else:
    print("❌ 获取失败")

# 测试4：通过工厂创建爬虫
print("\n📋 测试4：工厂模式创建爬虫")
print("-" * 40)

from scrapers.factory import ScraperFactory

# 使用注册的爬虫名称创建
scraper = ScraperFactory.create("sina_forex", {})
if scraper:
    print(f"✅ 工厂创建 {scraper.name} 成功")
    data = scraper.scrape()
    print(f"   获取 {len(data)} 条数据")
else:
    print("❌ 工厂创建失败")

print("\n" + "=" * 60)
print("🎉 模块2测试完成！")
print("=" * 60)
