import requests

api_url = "https://quote.21cp.com/interCrudePrice/api/list"
params = {
    "quotedPriceDateStart": "2025-12-01",
    # today
    "quotedPriceDateEnd": "2025-12-08",
    # wit 原油
    "productSid": "158651161505726464",
}
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
    "Referer": "https://quote.21cp.com/crude_centre/list/158651161505726464--.html",
    "X-Requested-With": "XMLHttpRequest",
    "Accept": "*/*",
}

resp = requests.get(api_url, params=params, headers=headers, timeout=10)

print("status:", resp.status_code)
print("request headers:", resp.request.headers)  # 确认这里没有 Cookie
print("body snippet:")
print(resp)

# sample response body:
# {
#     "code": 200,
#     "msg": "操作成功",
#     "data": [
#         {
#             "quotedPriceDate": "2025-12-08",
#             "quotedPriceMin": 63.06,
#             "quotedPriceMax": 64.09,
#             "updownPrice": 0.49,
#             "quotedPrice": 63.75,
#             "isClosed": 0,
#             "remark": ""
#         },
#         {
#             "quotedPriceDate": "2025-12-05",
#             "quotedPriceMin": 62.53,
#             "quotedPriceMax": 63.62,
#             "updownPrice": 0.59,
#             "quotedPrice": 63.26,
#             "isClosed": 0,
#             "remark": ""
#         },
#         {
#             "quotedPriceDate": "2025-12-04",
#             "quotedPriceMin": 62.18,
#             "quotedPriceMax": 63.37,
#             "updownPrice": 0.22,
#             "quotedPrice": 62.67,
#             "isClosed": 0,
#             "remark": ""
#         },
#         {
#             "quotedPriceDate": "2025-12-03",
#             "quotedPriceMin": 62.17,
#             "quotedPriceMax": 63.35,
#             "updownPrice": -0.72,
#             "quotedPrice": 62.45,
#             "isClosed": 0,
#             "remark": ""
#         },
#         {
#             "quotedPriceDate": "2025-12-02",
#             "quotedPriceMin": 62.69,
#             "quotedPriceMax": 63.82,
#             "updownPrice": 0.79,
#             "quotedPrice": 63.17,
#             "isClosed": 0,
#             "remark": "换月"
#         },
#         {
#             "quotedPriceDate": "2025-12-01",
#             "quotedPriceMin": 63.05,
#             "quotedPriceMax": 63.76,
#             "updownPrice": -0.14,
#             "quotedPrice": 63.20,
#             "isClosed": 0,
#             "remark": ""
#         }
#     ]
# }