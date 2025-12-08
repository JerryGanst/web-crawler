"""
Plasway 行业消息多分区爬虫
支持多分区、分页、简单的时间解析（相对/绝对）
"""
import time
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from bs4 import BeautifulSoup

from .base import BaseScraper


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

    def scrape(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        seen_titles: Set[str] = set()

        for rule in self.sections:
            section_name = rule.get("name", "")
            url_tmpl = rule.get("url_template")
            if not url_tmpl:
                continue

            for page in range(1, self.max_pages + 1):
                # 注意：fetch() 内部已有 rate_limit_delay，这里不再重复 sleep
                url = url_tmpl.format(page=page)
                resp = self.fetch(url)
                if not resp:
                    break

                batch = self._parse_page(resp.text, rule, section_name, seen_titles)
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

            # Section 之间额外等待，降低连续请求的 pattern 识别风险
            time.sleep(random.uniform(2.0, 4.0))

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

            link = anchor.get("href", "")
            title = anchor.get_text(strip=True)

            # 有些页面中 <a> 文本为空，标题实际在摘要区域，做降级回退
            if not title:
                fallback_sel = fields.get("title_fallback") or ".item-content span"
                fb_el = elem.select_one(fallback_sel)
                if fb_el:
                    title = fb_el.get_text(strip=True)

            if not title or not link or title in seen_titles:
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

            item = {
                "title": title,
                "url": link,
                "extra": {"section": section_name},
            }
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
