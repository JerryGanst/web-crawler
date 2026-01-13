"""
Bloomberg商品数据爬虫
使用AppleScript控制Chrome获取JavaScript渲染后的页面
"""

import re
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Bloomberg商品URL
BLOOMBERG_COMMODITIES_URL = "https://www.bloomberg.com/markets/commodities"

# 商品中文翻译
COMMODITY_TRANSLATIONS = {
    'Gold': '黄金',
    'Silver': '白银',
    'Platinum': '铂金',
    'Palladium': '钯金',
    'Copper': '铜',
    'Aluminium': '铝',
    'Aluminum': '铝',
    'Zinc': '锌',
    'Nickel': '镍',
    'Lead': '铅',
    'Tin': '锡',
    'Oil (Brent)': '布伦特原油',
    'Oil (WTI)': 'WTI原油',
    'Crude Oil': '原油',
    'Natural Gas': '天然气',
    'Corn': '玉米',
    'Wheat': '小麦',
    'Soybeans': '大豆',
    'Cotton': '棉花',
    'Sugar': '糖',
    'Coffee': '咖啡',
    'Cocoa': '可可',
}

# 商品单位映射（Bloomberg使用的单位）
COMMODITY_UNITS = {
    # 贵金属 - USD/盎司
    'Gold': 'USD/盎司',
    'Silver': 'USD/盎司',
    'Platinum': 'USD/盎司',
    'Palladium': 'USD/盎司',

    # 工业金属 - USD/吨 (LME价格)
    'Copper': 'USD/吨',
    'Aluminium': 'USD/吨',
    'Aluminum': 'USD/吨',
    'Zinc': 'USD/吨',
    'Nickel': 'USD/吨',
    'Lead': 'USD/吨',
    'Tin': 'USD/吨',

    # 能源
    'Oil (Brent)': 'USD/桶',
    'Oil (WTI)': 'USD/桶',
    'Crude Oil': 'USD/桶',
    'Natural Gas': 'USD/MMBtu',

    # 农产品
    'Corn': 'USc/蒲式耳',
    'Wheat': 'USc/吨',
    'Soybeans': 'USc/蒲式耳',
    'Cotton': 'USc/磅',
    'Sugar': 'USc/磅',
    'Coffee': 'USc/磅',
    'Cocoa': 'USD/吨',
}


def categorize_commodity(name: str) -> str:
    """为商品分类"""
    name_lower = name.lower()

    # 贵金属
    if any(m in name_lower for m in ['gold', 'silver', 'platinum', 'palladium']):
        return "贵金属"

    # 能源
    if any(e in name_lower for e in ['oil', 'gas', 'brent', 'wti', 'crude']):
        return "能源"

    # 工业金属
    if any(m in name_lower for m in ['copper', 'aluminum', 'aluminium', 'zinc', 'nickel', 'lead', 'tin']):
        return "工业金属"

    # 农产品
    if any(a in name_lower for a in ['corn', 'wheat', 'soybean', 'cotton', 'sugar', 'coffee', 'cocoa']):
        return "农产品"

    return "其他"


def extract_from_table(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """从HTML表格中提取商品数据"""
    commodities = []
    tables = soup.find_all('table')

    for table in tables:
        rows = table.find_all('tr')

        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 3:
                continue

            cell_texts = [cell.get_text(strip=True) for cell in cells]
            first_cell = cell_texts[0]

            # 过滤无效行
            if (not first_cell or len(first_cell) <= 2 or
                first_cell.isdigit() or
                'commodity' in first_cell.lower() or
                'price' in first_cell.lower()):
                continue

            price = None
            change = None

            for text in cell_texts[1:]:
                # 提取价格
                if price is None and re.search(r'\d+\.?\d*', text):
                    price_match = re.search(r'(\d+,?\d*\.?\d*)', text.replace(',', ''))
                    if price_match:
                        try:
                            price = float(price_match.group(1))
                        except ValueError:
                            continue

                # 提取变化
                if change is None and ('%' in text or '+' in text or '-' in text):
                    change = text

            if first_cell and price is not None:
                commodities.append({
                    'name': first_cell,
                    'chinese_name': COMMODITY_TRANSLATIONS.get(first_cell, first_cell),
                    'price': price,
                    'current_price': price,
                    'change': change,
                    'source': 'Bloomberg',
                    'category': categorize_commodity(first_cell),
                    'unit': COMMODITY_UNITS.get(first_cell, 'USD'),
                    'method': 'table_extraction',
                    'timestamp': datetime.now().isoformat()
                })

    return commodities


def extract_from_bloomberg_structure(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """从Bloomberg特定数据结构中提取数据"""
    commodities = []

    # Bloomberg 通常使用特定的CSS类名
    bloomberg_rows = soup.find_all('tr', class_=lambda x: x and 'data-table-row' in str(x))
    if not bloomberg_rows:
        bloomberg_rows = soup.find_all('div', class_=lambda x: x and 'row' in str(x) and 'data' in str(x))

    for row in bloomberg_rows:
        try:
            # 查找名称单元格
            name_cell = row.find(['td', 'th', 'div'], attrs={'data-type': 'name'})
            if not name_cell:
                name_cell = row.find(['td', 'th', 'div'], class_=lambda x: x and 'name' in str(x))

            # 查找价格单元格
            price_cell = row.find(['td', 'div'], attrs={'data-type': 'value'})
            if not price_cell:
                price_cell = row.find(['td', 'div'], class_=lambda x: x and 'price' in str(x))

            # 查找变化单元格
            change_cell = row.find(['td', 'div'], attrs={'data-type': 'percentChange'})
            if not change_cell:
                change_cell = row.find(['td', 'div'], class_=lambda x: x and 'change' in str(x))

            if name_cell and price_cell:
                name = name_cell.get_text(strip=True)
                price_text = price_cell.get_text(strip=True)
                change_text = change_cell.get_text(strip=True) if change_cell else None

                # 解析价格
                price_match = re.search(r'(\d+,?\d*\.?\d*)', price_text.replace(',', ''))
                if price_match:
                    price = float(price_match.group(1))

                    commodities.append({
                        'name': name,
                        'chinese_name': COMMODITY_TRANSLATIONS.get(name, name),
                        'price': price,
                        'current_price': price,
                        'change': change_text,
                        'source': 'Bloomberg',
                        'category': categorize_commodity(name),
                        'unit': COMMODITY_UNITS.get(name, 'USD'),
                        'method': 'bloomberg_structure',
                        'timestamp': datetime.now().isoformat()
                    })

        except Exception as e:
            logger.warning(f"解析Bloomberg行失败: {e}")
            continue

    return commodities


def extract_from_json_scripts(soup: BeautifulSoup) -> List[Dict[str, Any]]:
    """从页面JavaScript数据中提取商品数据"""
    commodities = []
    scripts = soup.find_all('script')

    for script in scripts:
        script_text = script.string
        if not script_text:
            continue

        # 查找包含商品数据的脚本
        if not any(keyword in script_text.lower() for keyword in ['commodity', 'market', 'price']):
            continue

        try:
            # 查找可能的JSON价格对象
            json_matches = re.findall(r'\{[^{}]*"price"[^{}]*\}', script_text)

            for match in json_matches:
                try:
                    # 尝试提取数据
                    name_match = re.search(r'"name"\s*:\s*"([^"]+)"', match)
                    price_match = re.search(r'"price"\s*:\s*(\d+\.?\d*)', match)

                    if name_match and price_match:
                        name = name_match.group(1)
                        price = float(price_match.group(1))

                        commodities.append({
                            'name': name,
                            'chinese_name': COMMODITY_TRANSLATIONS.get(name, name),
                            'price': price,
                            'current_price': price,
                            'source': 'Bloomberg',
                            'category': categorize_commodity(name),
                            'unit': COMMODITY_UNITS.get(name, 'USD'),
                            'method': 'json_extraction',
                            'timestamp': datetime.now().isoformat()
                        })
                except Exception:
                    continue

        except Exception as e:
            logger.warning(f"解析JSON脚本失败: {e}")

    return commodities


def scrape_bloomberg() -> List[Dict[str, Any]]:
    """
    使用AppleScript爬取Bloomberg商品数据

    Returns:
        商品数据列表
    """
    try:
        # 导入AppleScript浏览器控制模块
        from pacong.browser.applescript import chrome_applescript_scraper, chrome_start_if_needed

        # 确保Chrome运行
        if not chrome_start_if_needed():
            logger.error("无法启动Chrome浏览器")
            return []

        logger.info(f"开始爬取Bloomberg: {BLOOMBERG_COMMODITIES_URL}")

        # 使用AppleScript获取页面（等待15秒，滚动3次以加载所有数据）
        html_content = chrome_applescript_scraper(
            BLOOMBERG_COMMODITIES_URL,
            wait_seconds=15,
            scroll_times=3
        )

        if not html_content:
            logger.error("未能获取Bloomberg页面内容")
            return []

        logger.info(f"成功获取 {len(html_content)} 字节的页面内容")

        # 解析HTML
        soup = BeautifulSoup(html_content, 'html.parser')

        # 使用多种方法提取数据
        commodities = []

        # 方法1: 从表格提取
        table_data = extract_from_table(soup)
        if table_data:
            logger.info(f"从表格提取了 {len(table_data)} 条数据")
            commodities.extend(table_data)

        # 方法2: 从Bloomberg特定结构提取
        bloomberg_data = extract_from_bloomberg_structure(soup)
        if bloomberg_data:
            logger.info(f"从Bloomberg结构提取了 {len(bloomberg_data)} 条数据")
            commodities.extend(bloomberg_data)

        # 方法3: 从JSON脚本提取
        json_data = extract_from_json_scripts(soup)
        if json_data:
            logger.info(f"从JSON脚本提取了 {len(json_data)} 条数据")
            commodities.extend(json_data)

        # 去重（按名称）
        seen = set()
        unique_commodities = []
        for item in commodities:
            if item['name'] not in seen:
                seen.add(item['name'])
                unique_commodities.append(item)

        logger.info(f"Bloomberg爬取完成: 共 {len(unique_commodities)} 条唯一数据")
        return unique_commodities

    except ImportError as e:
        logger.error(f"导入AppleScript模块失败: {e}")
        logger.info("尝试使用HTTP请求作为备选方案...")
        return scrape_bloomberg_http()
    except Exception as e:
        logger.error(f"Bloomberg爬取失败: {e}")
        return []


def scrape_bloomberg_http() -> List[Dict[str, Any]]:
    """
    HTTP请求备选方案（可能无法获取JavaScript渲染的内容）
    """
    import requests

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }

    try:
        logger.info(f"使用HTTP请求爬取Bloomberg: {BLOOMBERG_COMMODITIES_URL}")
        response = requests.get(BLOOMBERG_COMMODITIES_URL, headers=headers, timeout=30)

        if response.status_code != 200:
            logger.error(f"Bloomberg HTTP请求失败: {response.status_code}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')

        # 尝试提取数据
        commodities = []
        commodities.extend(extract_from_table(soup))
        commodities.extend(extract_from_bloomberg_structure(soup))
        commodities.extend(extract_from_json_scripts(soup))

        # 去重
        seen = set()
        unique_commodities = []
        for item in commodities:
            if item['name'] not in seen:
                seen.add(item['name'])
                unique_commodities.append(item)

        logger.info(f"Bloomberg HTTP爬取完成: {len(unique_commodities)} 条数据")
        return unique_commodities

    except Exception as e:
        logger.error(f"Bloomberg HTTP爬取失败: {e}")
        return []


# 测试入口
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = scrape_bloomberg()

    print(f"\n获取到 {len(data)} 条Bloomberg数据:")
    for item in data[:10]:
        print(f"  {item['name']}: {item['price']} {item['unit']} ({item['source']})")
