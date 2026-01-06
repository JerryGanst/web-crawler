#!/usr/bin/env python3
"""
测试Bloomberg商品页面爬取的可行性
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import logging
import json

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_bloomberg_scraping():
    """测试Bloomberg商品页面爬取"""
    
    url = "https://www.bloomberg.com/markets/commodities"
    
    # 设置更真实的请求头
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
        logger.info(f"正在测试Bloomberg连接: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        
        print(f"✅ 连接状态: {response.status_code}")
        print(f"📄 页面大小: {len(response.content)} 字节")
        print(f"🔗 Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
        
        if response.status_code == 200:
            # 保存页面源码供分析
            with open('reports/bloomberg_source.html', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print("💾 页面源码已保存到 reports/bloomberg_source.html")
            
            # 解析页面
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 分析页面结构
            print(f"\n📊 页面结构分析:")
            print(f"   标题: {soup.title.text if soup.title else 'No title'}")
            print(f"   表格数量: {len(soup.find_all('table'))}")
            print(f"   行数 (tr): {len(soup.find_all('tr'))}")
            print(f"   脚本标签: {len(soup.find_all('script'))}")
            
            # 查找可能的数据容器
            data_containers = []
            
            # 1. 查找表格
            tables = soup.find_all('table')
            if tables:
                data_containers.append(('tables', tables))
            
            # 2. 查找Bloomberg特有的数据属性
            bloomberg_data = soup.find_all(attrs={'data-module': True})
            if bloomberg_data:
                data_containers.append(('bloomberg_modules', bloomberg_data))
            
            # 3. 查找class中包含table或data的元素
            data_divs = soup.find_all('div', class_=lambda x: x and (
                'table' in x.lower() or 'data' in x.lower() or 'market' in x.lower()
            ))
            if data_divs:
                data_containers.append(('data_divs', data_divs))
            
            # 4. 查找可能包含JSON数据的script标签
            scripts = soup.find_all('script')
            json_scripts = []
            for script in scripts:
                if script.string and ('commodity' in script.string.lower() or 
                                     'market' in script.string.lower() or
                                     '"price"' in script.string.lower()):
                    json_scripts.append(script)
            
            if json_scripts:
                data_containers.append(('json_scripts', json_scripts))
            
            print(f"\n🔍 发现的数据容器:")
            for container_type, containers in data_containers:
                print(f"   {container_type}: {len(containers)} 个")
            
            # 尝试提取商品数据
            commodities = []
            
            # 方法1: 从表格提取
            for table in tables:
                rows = table.find_all('tr')
                print(f"\n📊 分析表格 (包含 {len(rows)} 行)...")
                
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        cell_texts = [cell.get_text(strip=True) for cell in cells]
                        
                        # 查找商品信息
                        first_cell = cell_texts[0]
                        if (first_cell and len(first_cell) > 2 and 
                            not first_cell.isdigit() and
                            'commodity' not in first_cell.lower() and
                            'price' not in first_cell.lower()):
                            
                            price = None
                            change = None
                            
                            for text in cell_texts[1:]:
                                # 解析价格
                                if re.search(r'\d+\.?\d*', text) and price is None:
                                    price_match = re.search(r'(\d+,?\d*\.?\d*)', text.replace(',', ''))
                                    if price_match:
                                        try:
                                            price = float(price_match.group(1))
                                        except ValueError:
                                            continue
                                
                                # 解析变化
                                if ('%' in text or '+' in text or '-' in text) and change is None:
                                    change = text
                            
                            if first_cell and price is not None:
                                commodities.append({
                                    'name': first_cell,
                                    'price': price,
                                    'change': change,
                                    'source': 'bloomberg.com',
                                    'method': 'table_extraction',
                                    'timestamp': datetime.now().isoformat()
                                })
            
            # 方法2: 查找Bloomberg特定的数据结构
            print(f"\n🔍 尝试Bloomberg特定数据结构...")
            
            # Bloomberg通常使用特定的CSS类名
            bloomberg_rows = soup.find_all('tr', class_=lambda x: x and 'data-table-row' in x)
            if not bloomberg_rows:
                bloomberg_rows = soup.find_all('div', class_=lambda x: x and 'row' in x and 'data' in x)
            
            print(f"   找到Bloomberg数据行: {len(bloomberg_rows)}")
            
            for row in bloomberg_rows:
                try:
                    # 查找名称单元格
                    name_cell = row.find(['td', 'th', 'div'], attrs={'data-type': 'name'})
                    if not name_cell:
                        name_cell = row.find(['td', 'th', 'div'], class_=lambda x: x and 'name' in x)
                    
                    # 查找价格单元格
                    price_cell = row.find(['td', 'div'], attrs={'data-type': 'value'})
                    if not price_cell:
                        price_cell = row.find(['td', 'div'], class_=lambda x: x and 'price' in x)
                    
                    # 查找变化单元格
                    change_cell = row.find(['td', 'div'], attrs={'data-type': 'percentChange'})
                    if not change_cell:
                        change_cell = row.find(['td', 'div'], class_=lambda x: x and 'change' in x)
                    
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
                                'price': price,
                                'change': change_text,
                                'source': 'bloomberg.com',
                                'method': 'bloomberg_structure',
                                'timestamp': datetime.now().isoformat()
                            })
                            
                except Exception as e:
                    logger.warning(f"解析Bloomberg行失败: {e}")
                    continue
            
            # 方法3: 尝试从JavaScript数据中提取
            print(f"\n🔍 尝试从JavaScript数据提取...")
            
            for script in json_scripts[:3]:  # 只检查前3个脚本以避免过长输出
                script_text = script.string
                if script_text:
                    try:
                        # 查找可能的JSON对象
                        json_matches = re.findall(r'\{[^{}]*"price"[^{}]*\}', script_text)
                        if json_matches:
                            print(f"   发现 {len(json_matches)} 个可能的JSON价格对象")
                        
                        # 查找商品名称和价格的模式
                        commodity_patterns = re.findall(r'"([A-Z]{2,})"[^"]*"(\d+\.?\d*)"', script_text)
                        if commodity_patterns:
                            print(f"   发现 {len(commodity_patterns)} 个商品模式")
                            
                    except Exception as e:
                        logger.warning(f"解析JavaScript失败: {e}")
            
            print(f"\n📈 提取结果:")
            if commodities:
                print(f"✅ 成功提取 {len(commodities)} 条商品数据")
                
                # 显示样例数据
                print("\n🎯 样例数据:")
                for i, commodity in enumerate(commodities[:5]):
                    print(f"   {i+1}. {commodity['name']}: ${commodity['price']} ({commodity.get('change', 'N/A')}) [{commodity['method']}]")
                
                # 保存数据
                df = pd.DataFrame(commodities)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                csv_file = f'reports/bloomberg_test_{timestamp}.csv'
                df.to_csv(csv_file, index=False, encoding='utf-8-sig')
                print(f"\n💾 数据已保存到: {csv_file}")
                
                return True, commodities
            else:
                print("❌ 未能提取到有效的商品数据")
                print("   可能原因:")
                print("   - Bloomberg使用复杂的JavaScript动态加载")
                print("   - 需要登录或订阅访问")
                print("   - 有反爬虫保护机制")
                print("   - 数据结构与预期不符")
                
                # 分析页面内容以提供更多信息
                if 'javascript' in response.text.lower() and 'react' in response.text.lower():
                    print("   - 检测到React应用，需要JavaScript渲染")
                
                if 'login' in response.text.lower() or 'subscription' in response.text.lower():
                    print("   - 可能需要登录或订阅")
                
                return False, []
        else:
            print(f"❌ 访问失败，状态码: {response.status_code}")
            if response.status_code == 403:
                print("   可能被防火墙或反爬虫系统阻止")
            elif response.status_code == 429:
                print("   请求过于频繁，被限流")
            
            return False, []
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
        return False, []
    except Exception as e:
        print(f"❌ 处理异常: {e}")
        return False, []

def main():
    """主函数"""
    print("🚀 Bloomberg 商品数据爬取测试")
    print("=" * 50)
    print("目标网站: https://www.bloomberg.com/markets/commodities")
    print()
    
    success, data = test_bloomberg_scraping()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 测试结果: Bloomberg爬取可行")
        print(f"📊 获取数据: {len(data)} 条")
        print("💡 建议: 可以直接使用HTTP请求进行数据获取")
    else:
        print("⚠️ 测试结果: Bloomberg需要特殊处理")
        print("💡 建议:")
        print("   1. 使用Selenium等工具处理JavaScript渲染")
        print("   2. 考虑使用已有的applescript_scraper.py")
        print("   3. 使用cdp_scraper.py (Chrome DevTools Protocol)")
        print("   4. 或考虑Bloomberg API(需要付费)")

if __name__ == "__main__":
    main() 