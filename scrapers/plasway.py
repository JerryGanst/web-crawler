"""
Plasway 行业消息多分区爬虫
支持多分区、分页、简单的时间解析（相对/绝对）
优先使用 AppleScript 控制 Chrome 获取页面，回退到 requests
"""
import time
import random
import platform
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urlunparse

from .base import BaseScraper

logger = logging.getLogger(__name__)


class PlaswaySectionScraper(BaseScraper):
    """
    按分区配置的 Plasway 行业新闻爬虫
    配置示例（custom_scrapers.yaml）：
    plasway_industry:
      sections:
        - name: "market"
          url_template: "https://plasway.com/news/market?web=new&page={page}"
          container: ".news-item"
          fields:
            title: "h1 a"
            url: "h1 a"
            time: ".item-bottom p:nth-of-type(2) span:nth-of-type(1)"
            summary: ".item-content"
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        config.setdefault("display_name", "Plasway行业消息")
        config.setdefault("category", "finance")
        super().__init__(name, config)

        self.sections: List[Dict[str, Any]] = config.get("sections", [])
        self.max_pages: int = config.get("max_pages", 3)
        self.date_cutoff_days: Optional[int] = config.get("date_cutoff_days", 7)
        
        # 爬取模式：applescript / requests / auto
        # auto = macOS 上优先 AppleScript，其他系统用 requests
        self.scrape_mode: str = config.get("scrape_mode", "auto")
        self._applescript_available: Optional[bool] = None
        
        # 反检测优化参数
        self.max_requests_per_run: int = config.get("max_requests_per_run", 20)  # 单次运行最大请求数
        self.shuffle_sections: bool = config.get("shuffle_sections", True)  # 随机化 section 顺序
        self.skip_probability: float = config.get("skip_probability", 0.1)  # 10% 概率跳过某页（模拟人类）
        self.min_delay: float = config.get("min_delay", 2.0)  # 最小延迟
        self.max_delay: float = config.get("max_delay", 5.0)  # 最大延迟
        self._request_count: int = 0  # 请求计数器

    def _load_applescript_module(self):
        """动态加载 applescript 模块（绕过 __init__.py 的 selenium 依赖）"""
        import importlib.util
        import os
        
        module_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "pacong", "browser", "applescript.py"
        )
        spec = importlib.util.spec_from_file_location("applescript", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _check_applescript_available(self) -> bool:
        """检查 AppleScript 是否可用（macOS + Chrome 运行中）"""
        if self._applescript_available is not None:
            return self._applescript_available
        
        if platform.system() != "Darwin":
            self._applescript_available = False
            return False
        
        try:
            applescript = self._load_applescript_module()
            if not applescript.chrome_check_running():
                logger.info("🌍 Chrome 未运行，尝试启动...")
                if not applescript.chrome_start_if_needed():
                    logger.warning("⚠️ Chrome 启动失败，回退到 requests")
                    self._applescript_available = False
                    return False
            self._applescript_available = True
            return True
        except Exception as e:
            logger.warning(f"⚠️ AppleScript 不可用: {e}，回退到 requests")
            self._applescript_available = False
            return False

    def _fetch_with_applescript(self, url: str, wait_seconds: int = 8) -> Optional[str]:
        """使用 AppleScript 控制 Chrome 获取页面 HTML"""
        try:
            applescript = self._load_applescript_module()
            
            # 导航到 URL（复用当前 Tab，避免打开太多窗口）
            navigate_script = f'''
            tell application "Google Chrome"
                if not (exists window 1) then
                    make new window
                end if
                set URL of active tab of front window to "{url}"
            end tell
            '''
            applescript.execute_applescript(navigate_script)
            
            # 等待页面加载
            time.sleep(wait_seconds)
            
            # 获取 HTML
            get_html_script = '''
            tell application "Google Chrome"
                execute active tab of front window javascript "document.documentElement.outerHTML"
            end tell
            '''
            html_content = applescript.execute_applescript(get_html_script)
            
            if html_content:
                logger.debug(f"✅ AppleScript 获取 {len(html_content)} 字节")
                return html_content
            return None
            
        except Exception as e:
            logger.warning(f"⚠️ AppleScript 请求失败: {e}")
            return None

    def _should_use_applescript(self) -> bool:
        """决定是否使用 AppleScript"""
        if self.scrape_mode == "requests":
            return False
        if self.scrape_mode == "applescript":
            return self._check_applescript_available()
        # auto 模式：macOS 上优先 AppleScript
        return self._check_applescript_available()

    def _human_like_delay(self, base_min: float = None, base_max: float = None):
        """模拟人类行为的随机延迟，偶尔有较长停顿"""
        min_d = base_min or self.min_delay
        max_d = base_max or self.max_delay
        
        # 5% 概率有较长停顿（模拟人类阅读/分心）
        if random.random() < 0.05:
            delay = random.uniform(8.0, 15.0)
            logger.debug(f"💤 模拟人类较长停顿: {delay:.1f}s")
        else:
            delay = random.uniform(min_d, max_d)
        
        time.sleep(delay)

    def scrape(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen_titles: Set[str] = set()
        self._request_count = 0  # 重置计数器
        
        use_applescript = self._should_use_applescript()
        if use_applescript:
            print(f"  🍎 使用 AppleScript 模式爬取 Plasway")
        else:
            print(f"  📡 使用 Requests 模式爬取 Plasway")
        
        # 随机化 section 顺序，打破固定访问模式
        sections_to_scrape = list(self.sections)
        if self.shuffle_sections:
            random.shuffle(sections_to_scrape)
            logger.debug(f"🔀 Section 顺序已随机化")

        for rule in sections_to_scrape:
            # 检查是否达到请求上限
            if self._request_count >= self.max_requests_per_run:
                logger.info(f"⚠️ 达到请求上限 ({self.max_requests_per_run})，提前结束")
                break
            
            section_name = rule.get("name", "")
            url_tmpl = rule.get("url_template")
            if not url_tmpl:
                continue

            for page in range(1, self.max_pages + 1):
                # 检查请求上限
                if self._request_count >= self.max_requests_per_run:
                    break
                
                # 随机跳过某些页面（模拟人类不会看完每一页）
                if page > 1 and random.random() < self.skip_probability:
                    logger.debug(f"⏩ 随机跳过 {section_name} 第 {page} 页")
                    continue
                
                url = url_tmpl.format(page=page)
                html_content: Optional[str] = None
                
                if use_applescript:
                    # AppleScript 模式
                    html_content = self._fetch_with_applescript(url, wait_seconds=8)
                    if not html_content:
                        # AppleScript 失败，回退到 requests
                        logger.warning(f"⚠️ AppleScript 失败，回退 requests: {url}")
                        resp = self.fetch(url)
                        html_content = resp.text if resp else None
                else:
                    # Requests 模式
                    resp = self.fetch(url)
                    html_content = resp.text if resp else None
                
                self._request_count += 1
                
                if not html_content:
                    break

                batch = self._parse_page(html_content, rule, section_name, seen_titles)
                if not batch:
                    break

                # 如果全部过旧且设置了截止天数，则提前停止
                if self.date_cutoff_days:
                    newest_recent = any(
                        not self._is_older_than_cutoff(it.get("timestamp"))
                        for it in batch
                    )
                    if not newest_recent:
                        break

                items.extend(batch)
                
                # 人类化延迟（AppleScript 模式略短，因为已有页面加载等待）
                if use_applescript:
                    self._human_like_delay(1.0, 3.0)
                else:
                    self._human_like_delay()

            # Section 之间额外等待（更长）
            self._human_like_delay(3.0, 6.0)
        
        logger.info(f"✅ 完成 {self._request_count} 个请求，获取 {len(items)} 条数据")
        return [self.standardize_item(it) for it in items]

    def _parse_page(
        self,
        html: str,
        rule: Dict[str, Any],
        section_name: str,
        seen_titles: Set[str],
    ) -> List[Dict[str, Any]]:
        container_selector = rule.get("container", ".news-item")
        fields = rule.get("fields", {})
        title_sel = fields.get("title", "h1 a")
        url_sel = fields.get("url", "h1 a")
        time_sel = fields.get("time")
        summary_sel = fields.get("summary")
        source_sel = fields.get("source")

        soup = BeautifulSoup(html, "html.parser")
        elements = soup.select(container_selector)
        results: List[Dict[str, Any]] = []

        for elem in elements:
            # 基础链接
            anchor = elem.select_one(url_sel)
            if not anchor:
                continue

            original_link = anchor.get("href", "")
            title = anchor.get_text(strip=True)

            # 有些页面中 <a> 文本为空，标题实际在摘要区域的第一行，做降级回退
            if not title:
                fallback_sel = fields.get("title_fallback") or ".item-content span"
                fb_el = elem.select_one(fallback_sel)
                if fb_el:
                    full_text = fb_el.get_text(strip=True)
                    # 标题通常是第一行，用换行或多空格分隔
                    # 取第一行作为标题（限制长度避免拿到整个summary）
                    first_line = full_text.split('\n')[0].strip()
                    # 如果第一行仍然太长（超过100字符），可能是用空格分隔
                    if len(first_line) > 100:
                        parts = first_line.split('   ')  # Plasway用多空格分隔
                        first_line = parts[0].strip() if parts else first_line[:100]
                    title = first_line if len(first_line) <= 100 else first_line[:100]

            if not title or not original_link or title in seen_titles:
                continue

            seen_titles.add(title)

            published_at = None
            if time_sel:
                time_el = elem.select_one(time_sel)
                if time_el:
                    published_at = self._parse_time_text(time_el.get_text(strip=True))

            summary = None
            if summary_sel:
                sum_el = elem.select_one(summary_sel)
                if sum_el:
                    summary = sum_el.get_text(strip=True)

            source = None
            if source_sel:
                src_el = elem.select_one(source_sel)
                if src_el:
                    source = src_el.get_text(strip=True)

            # 生成唯一 ID（用于阅读器）
            news_id = hashlib.md5(f"{title}{original_link}".encode()).hexdigest()[:12]
            
            # 提取文章内容（摘要 + 正文）
            full_content = self._extract_article_content(elem, summary_sel)
            
            # 决定最终 URL：有内容用阅读器，否则用分类页
            if full_content:
                final_url = f"http://localhost:8000/api/reader/{news_id}"
                content_available = True
            else:
                final_url = self._normalize_url(original_link, section_name)
                content_available = False
            
            item = {
                "title": title,
                "url": final_url,
                "id": news_id,
                "extra": {
                    "section": section_name,
                    "content_available": content_available,
                    "original_url": original_link,
                },
            }
            
            # 保存内容到缓存（用于阅读器）
            if full_content:
                self._save_content_to_cache(news_id, {
                    "title": title,
                    "content": full_content,
                    "section": section_name,
                    "source": source or "Plasway",
                    "timestamp": published_at.isoformat() if published_at else None,
                    "original_url": original_link,
                })
            
            if published_at:
                item["timestamp"] = published_at.isoformat()
            if summary:
                item["extra"]["summary"] = summary
            if source:
                item["extra"]["source"] = source

            # 如果有时间限制且过旧，跳过
            if self.date_cutoff_days and self._is_older_than_cutoff(item.get("timestamp")):
                continue

            results.append(item)

        return results

    def _parse_time_text(self, text: str) -> Optional[datetime]:
        """
        解析类似“3天前”“2小时前”或“2024-12-05 10:30”这样的时间。
        """
        if not text:
            return None

        now = datetime.now()
        try:
            if "天前" in text:
                days = int(text.replace("天前", "").strip() or 0)
                return now - timedelta(days=days)
            if "小时前" in text:
                hours = int(text.replace("小时前", "").strip() or 0)
                return now - timedelta(hours=hours)
            if "分钟前" in text:
                minutes = int(text.replace("分钟前", "").strip() or 0)
                return now - timedelta(minutes=minutes)
            # 绝对日期
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d"):
                try:
                    return datetime.strptime(text, fmt)
                except ValueError:
                    continue
        except Exception:
            return None
        return None

    def _is_older_than_cutoff(self, iso_ts: Optional[str]) -> bool:
        if not iso_ts or not self.date_cutoff_days:
            return False
        try:
            dt = datetime.fromisoformat(iso_ts)
        except Exception:
            return False
        return (datetime.now() - dt).days > self.date_cutoff_days

    def _extract_article_content(self, elem, summary_sel: Optional[str] = None) -> Optional[str]:
        """提取文章的主要内容"""
        try:
            content_parts = []
            
            # 尝试多种选择器提取内容
            content_selectors = [
                summary_sel,
                '.item-content',
                '.article-body',
                '.content',
                '.news-content',
                'p',
            ]
            
            for sel in content_selectors:
                if not sel:
                    continue
                content_elem = elem.select_one(sel)
                if content_elem:
                    text = content_elem.get_text(strip=True)
                    if text and len(text) > 20:  # 至少20字符
                        content_parts.append(text)
                        break
            
            if content_parts:
                return "\n\n".join(content_parts)
            return None
        except Exception as e:
            logger.warning(f"提取内容失败: {e}")
            return None

    def _save_content_to_cache(self, news_id: str, data: dict):
        """保存文章内容到 Redis 缓存"""
        try:
            import redis
            import json
            import os
            
            redis_host = os.environ.get("REDIS_HOST", "localhost")
            redis_port = int(os.environ.get("REDIS_PORT", "49907"))
            
            client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
            key = f"trendradar:reader:{news_id}"
            
            # 保存7天
            client.setex(key, 7 * 24 * 3600, json.dumps(data, ensure_ascii=False))
            logger.debug(f"✅ 保存文章内容: {news_id}")
        except Exception as e:
            logger.warning(f"保存内容到缓存失败: {e}")

    def _normalize_url(self, url: str, section_name: str = "") -> str:
        """
        规范化 Plasway URL
        
        由于 Plasway 文章页面需要登录，将 URL 改为对应分类的列表页
        """
        # Plasway 文章需要登录，改为链接到分类页面（需要 ?web=new 参数）
        section_urls = {
            "market": "https://www.plasway.com/news/market?web=new",
            "innovation": "https://www.plasway.com/news/innovation?web=new", 
            "policy": "https://www.plasway.com/news/policy?web=new",
            "viewpoint": "https://www.plasway.com/news/viewpoint?web=new",
            "industry": "https://www.plasway.com/news/industry?web=new",
        }
        
        # 返回对应分类页面，如果没有匹配则返回主页
        return section_urls.get(section_name, "https://www.plasway.com/news?web=new")
