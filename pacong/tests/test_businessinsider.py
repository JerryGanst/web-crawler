#!/usr/bin/env python3
"""
简单测试Business Insider商品页面爬取的可行性
"""

import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_businessinsider_scraping():
    """测试Business Insider商品页面爬取"""
    
    url = "https://markets.businessinsider.com/commodities"
    
    # 设置请求头模拟真实浏览器
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    
    try:
        logger.info(f"正在测试连接: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        
        print(f"✅ 连接状态: {response.status_code}")
        print(f"📄 页面大小: {len(response.content)} 字节")
        print(f"🔗 Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
        
        if response.status_code == 200:
            # 解析页面
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 保存页面源码供分析
            with open('reports/businessinsider_source.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify())
            print("💾 页面源码已保存到 reports/businessinsider_source.html")
            
            # 分析页面结构
            print(f"\n📊 页面结构分析:")
            print(f"   标题: {soup.title.text if soup.title else 'No title'}")
            print(f"   表格数量: {len(soup.find_all('table'))}")
            print(f"   行数 (tr): {len(soup.find_all('tr'))}")
            
            # 尝试提取商品数据
            commodities = []
            
            # 查找表格数据
            tables = soup.find_all('table')
            print(f"\n🔍 找到 {len(tables)} 个表格，正在分析...")
            
            for i, table in enumerate(tables):
                rows = table.find_all('tr')
                print(f"   表格 {i+1}: {len(rows)} 行")
                
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        cell_texts = [cell.get_text(strip=True) for cell in cells]
                        
                        # 简单过滤，查找包含商品信息的行
                        first_cell = cell_texts[0]
                        if (first_cell and 
                            len(first_cell) > 2 and 
                            not first_cell.isdigit() and
                            'commodity' not in first_cell.lower() and
                            'price' not in first_cell.lower()):
                            
                            # 查找价格信息
                            price = None
                            change = None
                            
                            for text in cell_texts[1:]:
                                # 尝试解析价格
                                if re.search(r'\d+\.?\d*', text) and price is None:
                                    price_match = re.search(r'(\d+,?\d*\.?\d*)', text.replace(',', ''))
                                    if price_match:
                                        try:
                                            price = float(price_match.group(1))
                                        except ValueError:
                                            continue
                                
                                # 查找变化百分比
                                if ('%' in text or '+' in text or '-' in text) and change is None:
                                    change = text
                            
                            if first_cell and price is not None:
                                commodities.append({
                                    'name': first_cell,
                                    'price': price,
                                    'change': change,
                                    'source': 'businessinsider.com',
                                    'timestamp': datetime.now().isoformat()
                                })
            
            print(f"\n📈 提取结果:")
            if commodities:
                print(f"✅ 成功提取 {len(commodities)} 条商品数据")
                
                # 显示前几条数据
                print("\n🎯 样例数据:")
                for i, commodity in enumerate(commodities[:5]):
                    print(f"   {i+1}. {commodity['name']}: ${commodity['price']} ({commodity.get('change', 'N/A')})")
                
                # 保存到CSV
                df = pd.DataFrame(commodities)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                csv_file = f'reports/businessinsider_test_{timestamp}.csv'
                df.to_csv(csv_file, index=False, encoding='utf-8-sig')
                print(f"\n💾 数据已保存到: {csv_file}")
                
                return True, commodities
            else:
                print("❌ 未能提取到有效的商品数据")
                print("   可能原因:")
                print("   - 页面使用JavaScript动态加载数据")
                print("   - 数据结构与预期不符")
                print("   - 需要登录或有反爬措施")
                
                return False, []
        else:
            print(f"❌ 访问失败，状态码: {response.status_code}")
            return False, []
            
    except requests.exceptions.RequestException as e:
        print(f"❌ 网络请求失败: {e}")
        return False, []
    except Exception as e:
        print(f"❌ 处理异常: {e}")
        return False, []

def main():
    """主函数"""
    print("🚀 Business Insider 商品数据爬取测试")
    print("=" * 50)
    print("目标网站: https://markets.businessinsider.com/commodities")
    print()
    
    success, data = test_businessinsider_scraping()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 测试结果: 爬取可行")
        print(f"📊 获取数据: {len(data)} 条")
    else:
        print("⚠️ 测试结果: 需要进一步优化")
        print("💡 建议: 考虑使用Selenium等工具进行动态爬取")

if __name__ == "__main__":
    main() 