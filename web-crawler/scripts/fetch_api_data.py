import requests
import json
import os

urls = [
    "http://localhost:8000/api/news/finance?include_custom=true",
    "http://localhost:8000/api/news/news?include_custom=true",
    "http://localhost:8000/api/news/tech?include_custom=true",
    "http://localhost:8000/api/news/commodity?include_custom=true",
    "http://localhost:8000/api/news/plastics?include_custom=true",
    "http://localhost:8000/api/customer-news-stats",
    "http://localhost:8000/api/material-news-stats",
    "http://localhost:8000/api/partner-news-stats",
    "http://localhost:8000/api/supplier-news-stats",
    "http://localhost:8000/api/news/supply-chain",
    "http://localhost:8000/api/tariff-news-stats"
]

results = {}

for url in urls:
    try:
        print(f"Fetching {url}...")
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            results[url] = response.json()
        else:
            print(f"Failed to fetch {url}: {response.status_code}")
            results[url] = {"error": response.status_code}
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        results[url] = {"error": str(e)}

with open("api_responses.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("Done. Saved to api_responses.json")
