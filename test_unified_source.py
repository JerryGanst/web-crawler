"""
测试统一数据源 - 模块3测试
"""
import sys
sys.path.insert(0, '.')

print("=" * 60)
print("🧪 模块3测试：统一数据源 + 推送系统")
print("=" * 60)

from scrapers.unified import UnifiedDataSource

# 初始化
ds = UnifiedDataSource()

# 测试1：爬取财经分类（含自定义爬虫）
print("\n📋 测试1：爬取财经分类")
print("-" * 40)

finance_data = ds.crawl_category("finance", include_custom=True)

if finance_data:
    # 统计数据来源
    sources = {}
    for item in finance_data:
        src = item.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
    
    print(f"\n📊 数据来源统计:")
    for src, count in sources.items():
        print(f"   {src}: {count} 条")
    
    # 显示部分数据
    print(f"\n📰 部分数据预览:")
    for item in finance_data[:5]:
        title = item.get("title", "")[:50]
        platform = item.get("platform_name", item.get("platform", ""))
        print(f"   [{platform}] {title}...")
else:
    print("❌ 获取失败")

# 测试2：推送到企业微信（可选）
print("\n📋 测试2：推送到企业微信")
print("-" * 40)

import yaml
with open("config/config.yaml", 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

webhook_url = config.get("notification", {}).get("webhooks", {}).get("wework_url", "")

if webhook_url:
    # 只推送自定义数据源的数据（避免重复推送）
    custom_data = [item for item in finance_data if item.get("source") == "custom"]
    
    if custom_data:
        print(f"📤 推送 {len(custom_data)} 条自定义数据源数据...")
        ds.push_to_wework(custom_data, "finance", webhook_url)
    else:
        print("没有自定义数据源数据")
else:
    print("⚠️ 未配置企业微信 webhook，跳过推送测试")

print("\n" + "=" * 60)
print("🎉 模块3测试完成！")
print("=" * 60)
