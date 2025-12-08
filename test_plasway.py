import requests
from bs4 import BeautifulSoup

url = "https://www.plasway.com/news/market?web=new&page=1"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://plasway.com/",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}
r = requests.get(url, headers=headers, timeout=15)
print("status:", r.status_code, "len:", len(r.text))

soup = BeautifulSoup(r.text, "html.parser")

# 测试不同的 container selector
containers = [
    ".tabs-news-box .news-item-content",
    ".news-item-content",
]

for sel in containers:
    items = soup.select(sel)
    print(f"\n--- selector: {sel} ---")
    print(f"items count: {len(items)}")
    if items:
        first = items[0]
        # 打印第一个 item 的 HTML 片段
        print(f"first item HTML: {str(first)[:600]}...")
        
        # 测试 title 提取
        a = first.select_one("h1 a")
        if a:
            print(f"title text: '{a.get_text(strip=True)}'")
            print(f"title href: {a.get('href')}")
        else:
            print("h1 a not found")
        
        # 测试 time 提取
        time_el = first.select_one(".item-bottom span:nth-of-type(1)")
        if time_el:
            print(f"time text: '{time_el.get_text(strip=True)}'")
        else:
            print(".item-bottom span not found")
