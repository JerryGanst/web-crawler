"""
上海有色金属网(SMM)爬虫
抓取有色金属行业新闻和资讯
"""
import requests
import re
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from datetime import datetime


class SMMScraper:
    """上海有色金属网爬虫"""
    
    def __init__(self, name: str = None, config: Dict = None):
        """
        初始化爬虫
        
        Args:
            name: 爬虫名称（工厂模式传入）
            config: 爬虫配置（工厂模式传入）
        """
        self.name = name or "smm_news"
        self.config = config or {}
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        self.base_url = 'https://news.smm.cn'
    
    def scrape(self, limit: int = 30) -> List[Dict[str, Any]]:
        """
        爬取SMM新闻
        
        Args:
            limit: 最大返回条数
            
        Returns:
            新闻列表
        """
        news_items = []
        
        # 抓取新闻列表页
        news_items.extend(self._scrape_news_list(limit))
        
        return news_items[:limit]
    
    def _scrape_news_list(self, limit: int) -> List[Dict[str, Any]]:
        """抓取新闻列表"""
        url = f'{self.base_url}/'
        news_items = []
        
        try:
            resp = requests.get(url, headers=self.headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # 查找新闻链接
            links = soup.find_all('a', href=re.compile(r'/news/\d+'))
            seen_titles = set()
            
            for link in links:
                if len(news_items) >= limit:
                    break
                    
                text = link.get_text(strip=True)
                href = link.get('href')
                
                # 过滤无效内容
                if not text or len(text) < 10 or not href:
                    continue
                
                # 去除"原创"前缀
                if text.startswith('原创'):
                    text = text[2:]
                
                # 避免重复
                if text in seen_titles:
                    continue
                seen_titles.add(text)
                
                # 构建完整URL
                full_url = f'{self.base_url}{href}' if href.startswith('/') else href
                
                # 提取分类
                category = self._extract_category(text)
                
                news_items.append({
                    'title': text,
                    'url': full_url,
                    'source': '上海有色网',
                    'category': category,
                    'pubDate': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                })
            
            print(f"✅ 上海有色网: 获取 {len(news_items)} 条新闻")
            
        except Exception as e:
            print(f"❌ 上海有色网爬取失败: {e}")
        
        return news_items
    
    def _extract_category(self, title: str) -> str:
        """从标题提取分类"""
        # 金属分类关键词
        categories = {
            '铜': '铜',
            '铝': '铝',
            '锌': '锌',
            '铅': '铅',
            '镍': '镍',
            '锡': '锡',
            '稀土': '稀土',
            '钴': '钴',
            '锂': '锂',
            '金': '贵金属',
            '银': '贵金属',
            '钢铁': '钢铁',
            '储能': '新能源',
            '电池': '新能源',
            '光伏': '新能源',
        }
        
        for keyword, category in categories.items():
            if keyword in title:
                return category
        
        return '有色金属'
    
    def scrape_metal_prices(self) -> List[Dict[str, Any]]:
        """
        尝试抓取金属价格（需要登录，可能返回空）
        注意：SMM价格数据需要会员登录才能查看
        """
        prices = []
        
        # 尝试从行情页面获取公开信息
        metals = [
            ('copper', '铜'),
            ('aluminum', '铝'),
            ('zinc', '锌'),
            ('lead', '铅'),
            ('nickel', '镍'),
            ('tin', '锡'),
        ]
        
        for metal_en, metal_cn in metals:
            try:
                url = f'https://hq.smm.cn/{metal_en}'
                resp = requests.get(url, headers=self.headers, timeout=10)
                
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    
                    # 尝试提取表格数据
                    tables = soup.find_all('table')
                    for table in tables[:3]:
                        rows = table.find_all('tr')
                        for row in rows[1:3]:  # 跳过表头
                            cells = row.find_all(['td', 'th'])
                            if len(cells) >= 4:
                                name = cells[0].get_text(strip=True)
                                price_range = cells[1].get_text(strip=True)
                                
                                # 检查是否需要登录
                                if '未登录' not in price_range and price_range:
                                    prices.append({
                                        'name': name,
                                        'metal': metal_cn,
                                        'price_range': price_range,
                                        'source': '上海有色网',
                                    })
                                    break
                        if prices:
                            break
                            
            except Exception as e:
                print(f"获取{metal_cn}价格失败: {e}")
        
        return prices


# 测试
if __name__ == '__main__':
    scraper = SMMScraper()
    
    print("\n=== 抓取上海有色网新闻 ===\n")
    news = scraper.scrape(limit=20)
    
    for i, item in enumerate(news, 1):
        print(f"{i}. [{item['category']}] {item['title'][:50]}")
        print(f"   {item['url']}\n")
    
    print(f"\n共抓取 {len(news)} 条新闻")
