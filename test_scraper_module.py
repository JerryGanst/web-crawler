"""
测试爬虫模块 - 模块1测试
"""
import sys
sys.path.insert(0, '.')

from scrapers.base import ConfigDrivenScraper

print("=" * 60)
print("🧪 模块1测试：爬虫基础框架")
print("=" * 60)

# 测试1：使用配置驱动爬虫爬取 CoinGecko API
print("\n📋 测试1：配置驱动爬虫 - CoinGecko API")
print("-" * 40)

coingecko_config = {
    "display_name": "CoinGecko",
    "category": "finance",
    "urls": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd",
    "method": "requests",
    "parser": "json",
    "headers": {
        "Accept": "application/json",
    },
}

scraper = ConfigDrivenScraper("coingecko", coingecko_config)
results = scraper.scrape()

if results:
    print(f"✅ 成功获取 {len(results)} 条数据")
    for item in results:
        print(f"   - {item}")
else:
    print("❌ 获取失败")

# 测试2：使用配置驱动爬虫爬取华尔街见闻
print("\n📋 测试2：配置驱动爬虫 - 华尔街见闻 (newsnow API)")
print("-" * 40)

wallstreet_config = {
    "display_name": "华尔街见闻",
    "category": "finance",
    "urls": "https://newsnow.busiyi.world/api/s?id=wallstreetcn-hot&latest",
    "method": "requests",
    "parser": "json",
    "json_path": "items",
    "field_mapping": {
        "title": "title",
        "url": "url",
    },
}

scraper2 = ConfigDrivenScraper("wallstreetcn", wallstreet_config)
results2 = scraper2.scrape()

if results2:
    print(f"✅ 成功获取 {len(results2)} 条新闻")
    for item in results2[:5]:  # 只显示前5条
        print(f"   📰 {item['title'][:40]}...")
        print(f"      🔗 {item['url']}")
else:
    print("❌ 获取失败")

# 测试3：测试工厂类
print("\n📋 测试3：工厂类创建爬虫")
print("-" * 40)

from scrapers.factory import ScraperFactory

# 直接用配置创建
scraper3 = ScraperFactory.create("test_scraper", {
    "display_name": "测试爬虫",
    "urls": "https://api.coingecko.com/api/v3/ping",
    "parser": "json",
})

if scraper3:
    print(f"✅ 工厂创建成功: {scraper3.name}")
    result = scraper3.scrape()
    print(f"   返回数据: {result}")
else:
    print("❌ 工厂创建失败")

print("\n" + "=" * 60)
print("🎉 模块1测试完成！")
print("=" * 60)
