"""
按分类爬取新闻并推送（统一数据源版本）
用法:
  python crawl_by_category.py finance   # 只爬财经类（含自定义数据源）
  python crawl_by_category.py news      # 只爬新闻类
  python crawl_by_category.py tech      # 只爬科技类（含 Hacker News）
  python crawl_by_category.py all       # 爬所有分类
  
  python crawl_by_category.py finance --no-custom  # 不含自定义数据源
"""
import sys
import yaml

# 加载配置
with open("config/config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# 企业微信 webhook
WEWORK_URL = config.get("notification", {}).get("webhooks", {}).get("wework_url", "")

def get_platforms_by_category(category: str) -> list:
    """根据分类获取平台列表"""
    platforms = config.get("platforms", [])
    if category == "all":
        return platforms
    return [p for p in platforms if p.get("category") == category]

def fetch_data(platform_id: str, max_retries: int = 2) -> dict:
    """从 API 获取数据，支持重试"""
    url = f"https://newsnow.busiyi.world/api/s?id={platform_id}&latest"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
    }
    
    for retry in range(max_retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") in ["success", "cache"]:
                # 转换 items 为 data 格式
                if "items" in data:
                    data["data"] = data["items"]
                return data
        except Exception as e:
            if retry < max_retries:
                wait = random.uniform(2, 4) + retry * 2
                time.sleep(wait)
    return {}

def crawl_category(category: str) -> list:
    """爬取指定分类的所有平台"""
    platforms = get_platforms_by_category(category)
    if not platforms:
        print(f"❌ 未找到分类: {category}")
        return []
    
    category_name = config.get("categories", {}).get(category, {}).get("name", category)
    print(f"\n📂 正在爬取【{category_name}】分类 ({len(platforms)} 个平台)")
    print("=" * 50)
    
    all_news = []
    for p in platforms:
        pid = p["id"]
        pname = p["name"]
        print(f"  🔄 {pname} ({pid})...", end=" ")
        
        data = fetch_data(pid)
        if data and "data" in data:
            items = data["data"]
            for item in items:
                item["platform"] = pid
                item["platform_name"] = pname
                item["category"] = category
            all_news.extend(items)
            status = "最新" if data.get("status") == "success" else "缓存"
            print(f"✅ {len(items)} 条 ({status})")
        else:
            print("❌ 失败")
        
        time.sleep(random.uniform(0.5, 1.5))
    
    print(f"\n📊 共获取 {len(all_news)} 条新闻")
    return all_news

def push_to_wework(news_list: list, category: str):
    """推送到企业微信（分批发送，保留链接）"""
    if not WEWORK_URL:
        print("❌ 未配置企业微信 webhook")
        return
    
    if not news_list:
        print("❌ 没有新闻可推送")
        return
    
    category_name = config.get("categories", {}).get(category, {}).get("name", category)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 按平台分组
    by_platform = {}
    for news in news_list:
        pname = news.get("platform_name", "未知")
        if pname not in by_platform:
            by_platform[pname] = []
        by_platform[pname].append(news)
    
    # 构建分批消息（每批一个平台，保留链接）
    batches = []
    batch_num = 1
    
    for pname, items in by_platform.items():
        lines = [f"## 📊 {category_name}热点 ({now}) [{batch_num}]\n"]
        lines.append(f"### 📰 {pname}")
        for i, item in enumerate(items[:10], 1):
            title = item.get("title", "")
            url = item.get("url") or item.get("mobileUrl") or ""
            if url:
                lines.append(f"{i}. [{title}]({url})")
            else:
                lines.append(f"{i}. {title}")
        batches.append("\n".join(lines))
        batch_num += 1
    
    print(f"\n📤 正在推送到企业微信（共 {len(batches)} 批）...")
    
    success_count = 0
    for i, batch in enumerate(batches, 1):
        resp = requests.post(WEWORK_URL, json={
            "msgtype": "markdown",
            "markdown": {"content": batch}
        })
        
        if resp.status_code == 200 and resp.json().get("errcode") == 0:
            success_count += 1
        else:
            print(f"  ❌ 第 {i} 批失败: {resp.text}")
        
        if i < len(batches):
            time.sleep(1)  # 避免发送过快
    
    print(f"✅ 推送完成！成功 {success_count}/{len(batches)} 批")

def main():
    if len(sys.argv) < 2:
        print("用法: python crawl_by_category.py <category> [--no-custom]")
        print("可用分类: finance, news, social, tech, all")
        print("\n选项:")
        print("  --no-custom    不使用自定义爬虫（仅 newsnow API）")
        print("  --unified      使用统一数据源（推荐，含自定义爬虫）")
        return
    
    category = sys.argv[1].lower()
    include_custom = "--no-custom" not in sys.argv
    use_unified = "--unified" in sys.argv or include_custom
    
    if use_unified:
        # 使用统一数据源管理器（新方式）
        from scrapers.unified import UnifiedDataSource
        ds = UnifiedDataSource()
        
        if category == "all":
            for cat in ["finance", "news", "social", "tech"]:
                data = ds.crawl_category(cat, include_custom=include_custom)
                if data:
                    ds.push_to_wework(data, cat, WEWORK_URL)
        else:
            data = ds.crawl_category(category, include_custom=include_custom)
            if data:
                ds.push_to_wework(data, category, WEWORK_URL)
    else:
        # 旧方式（仅 newsnow）
        if category == "all":
            for cat in ["finance", "news", "social", "tech"]:
                news = crawl_category(cat)
                if news:
                    push_to_wework(news, cat)
        else:
            news = crawl_category(category)
            if news:
                push_to_wework(news, category)

if __name__ == "__main__":
    main()
