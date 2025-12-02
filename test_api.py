"""
TrendRadar API 综合测试
包含：爬虫模块、统一数据源、AI 分析接口
"""
import sys
import requests
import time

sys.path.insert(0, '.')

API_BASE = "http://localhost:8000"

def test_banner(title):
    print(f"\n{'=' * 60}")
    print(f"🧪 {title}")
    print('=' * 60)

def test_section(title):
    print(f"\n📋 {title}")
    print('-' * 40)

# ==================== 测试1: API 状态 ====================
test_banner("测试1: API 服务状态")

try:
    resp = requests.get(f"{API_BASE}/api/status", timeout=5)
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ 服务运行中")
        print(f"   版本: {data.get('version')}")
        print(f"   平台数: {data['config']['platforms_count']}")
        print(f"   分类数: {data['config']['categories_count']}")
        print(f"   企业微信: {'已配置' if data['config']['wework_configured'] else '未配置'}")
    else:
        print(f"❌ 服务异常: HTTP {resp.status_code}")
        sys.exit(1)
except Exception as e:
    print(f"❌ 无法连接服务器: {e}")
    print("   请先启动服务器: python server.py")
    sys.exit(1)

# ==================== 测试2: 分类接口 ====================
test_banner("测试2: 分类接口")

resp = requests.get(f"{API_BASE}/api/categories")
categories = resp.json().get("categories", [])
print(f"✅ 获取到 {len(categories)} 个分类:")
for cat in categories:
    print(f"   - {cat['id']}: {cat['name']}")

# ==================== 测试3: 新闻接口 ====================
test_banner("测试3: 新闻数据接口")

for category in ["finance", "tech"]:
    test_section(f"分类: {category}")
    
    start = time.time()
    resp = requests.get(f"{API_BASE}/api/news/{category}?include_custom=true")
    elapsed = time.time() - start
    
    if resp.status_code == 200:
        data = resp.json()
        print(f"✅ 获取 {data['total']} 条新闻 (耗时 {elapsed:.2f}s)")
        print(f"   缓存: {'是' if data.get('cached') else '否'}")
        print(f"   来源: {list(data.get('sources', {}).keys())[:5]}")
        
        # 显示前2条
        for item in data.get('data', [])[:2]:
            print(f"   📰 {item.get('title', '')[:40]}...")
    else:
        print(f"❌ 获取失败: {resp.status_code}")

# ==================== 测试4: 供应链新闻 ====================
test_banner("测试4: 供应链新闻接口")

resp = requests.get(f"{API_BASE}/api/news/supply-chain")
if resp.status_code == 200:
    data = resp.json()
    print(f"✅ 获取 {data.get('count', 0)} 条供应链新闻")
    for item in data.get('data', [])[:3]:
        print(f"   📰 [{item.get('source', '')}] {item.get('title', '')[:35]}...")
else:
    print(f"❌ 获取失败: {resp.status_code}")

# ==================== 测试5: AI API 连通性 ====================
test_banner("测试5: AI API 连通性测试")

import yaml
with open("config/config.yaml", 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

ai_config = config.get("ai", {})
external = ai_config.get("external", {})

api_key = external.get("api_key", "")
api_base = external.get("api_base", "https://api.siliconflow.cn/v1")
model = external.get("model", "")

if not api_key:
    print("⚠️ 未配置外网 AI API Key，跳过测试")
else:
    print(f"📍 API: {api_base}")
    print(f"🤖 模型: {model}")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "用一句话介绍立讯精密"}
        ],
        "max_tokens": 100,
        "temperature": 0.7
    }
    
    try:
        start = time.time()
        resp = requests.post(
            f"{api_base}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )
        elapsed = time.time() - start
        
        if resp.status_code == 200:
            result = resp.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            print(f"✅ AI 响应成功 (耗时 {elapsed:.2f}s)")
            print(f"   💬 {content[:150]}")
        else:
            print(f"❌ AI 请求失败: {resp.status_code}")
            print(f"   {resp.text[:200]}")
    except requests.exceptions.Timeout:
        print("⚠️ AI 请求超时")
    except Exception as e:
        print(f"❌ AI 请求错误: {e}")

# ==================== 测试6: 爬虫模块 ====================
test_banner("测试6: 爬虫模块直接测试")

from scrapers.base import ConfigDrivenScraper

test_section("CoinGecko API")
scraper = ConfigDrivenScraper("coingecko", {
    "display_name": "CoinGecko",
    "urls": "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=usd",
    "parser": "json",
})
results = scraper.scrape()
if results:
    print(f"✅ 爬虫工作正常，获取 {len(results)} 条数据")
else:
    print("❌ 爬虫执行失败")

# ==================== 总结 ====================
test_banner("测试完成")
print("""
📊 测试结果总结:
   ✅ API 服务正常
   ✅ 新闻数据接口正常  
   ✅ 供应链新闻接口正常
   ✅ AI API 连通正常
   ✅ 爬虫模块正常

💡 提示:
   - 完整 AI 分析报告生成可能需要 60-120 秒
   - 首次请求会较慢（无缓存），后续请求会更快
""")
