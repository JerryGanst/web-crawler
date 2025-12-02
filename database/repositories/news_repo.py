# coding=utf-8
"""
新闻数据仓库
提供新闻数据的 CRUD 操作
"""

import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple

from ..connection import DatabaseManager, get_db
from ..models import News, KeywordMatch


class NewsRepository:
    """新闻数据仓库"""
    
    def __init__(self, db: DatabaseManager = None):
        self.db = db or get_db()
    
    def insert(self, news: News) -> int:
        """插入单条新闻"""
        sql = """
            INSERT INTO news (
                platform_id, title, title_hash, url, mobile_url,
                current_rank, ranks_history, hot_value,
                first_seen_at, last_seen_at, crawled_at, crawl_date,
                published_at, appearance_count, weight_score, category, extra_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, news.to_db_tuple())
            return cursor.lastrowid
    
    def insert_or_update(self, news: News) -> Tuple[int, bool]:
        """
        插入或更新新闻
        
        Returns:
            (news_id, is_new): 新闻ID和是否为新增
        """
        # 检查是否已存在
        existing = self.find_by_title_hash(
            news.platform_id, 
            news.title_hash, 
            news.crawl_date
        )
        
        if existing:
            # 更新现有记录
            self.update_appearance(
                existing.id,
                news.current_rank,
                news.last_seen_at
            )
            return existing.id, False
        else:
            # 插入新记录
            news_id = self.insert(news)
            return news_id, True
    
    def insert_batch(self, news_list: List[News]) -> Tuple[int, int]:
        """
        批量插入新闻（使用 INSERT OR IGNORE）
        
        Returns:
            (inserted_count, updated_count)
        """
        inserted = 0
        updated = 0
        
        for news in news_list:
            try:
                news_id, is_new = self.insert_or_update(news)
                if is_new:
                    inserted += 1
                else:
                    updated += 1
            except Exception as e:
                print(f"插入新闻失败: {news.title[:30]}... - {e}")
        
        return inserted, updated
    
    def update_appearance(
        self, 
        news_id: int, 
        new_rank: int = None,
        last_seen_at: datetime = None
    ) -> None:
        """更新新闻出现记录"""
        sql = """
            UPDATE news SET
                appearance_count = appearance_count + 1,
                last_seen_at = ?,
                current_rank = COALESCE(?, current_rank),
                ranks_history = (
                    CASE 
                        WHEN ranks_history IS NULL THEN json_array(?)
                        ELSE json_insert(ranks_history, '$[#]', ?)
                    END
                )
            WHERE id = ?
        """
        last_seen = last_seen_at or datetime.now()
        with self.db.get_connection() as conn:
            conn.execute(sql, (
                last_seen.isoformat(),
                new_rank,
                new_rank,
                new_rank,
                news_id
            ))
    
    def find_by_id(self, news_id: int) -> Optional[News]:
        """根据 ID 查找新闻"""
        sql = "SELECT * FROM news WHERE id = ?"
        row = self.db.fetch_one(sql, (news_id,))
        return News.from_db_row(row) if row else None
    
    def find_by_title_hash(
        self, 
        platform_id: str, 
        title_hash: str,
        crawl_date: str
    ) -> Optional[News]:
        """根据平台、标题哈希和日期查找新闻"""
        sql = """
            SELECT * FROM news 
            WHERE platform_id = ? AND title_hash = ? AND crawl_date = ?
        """
        row = self.db.fetch_one(sql, (platform_id, title_hash, crawl_date))
        return News.from_db_row(row) if row else None
    
    def find_by_date(
        self, 
        crawl_date: str = None,
        platform_id: str = None,
        category: str = None,
        limit: int = 100
    ) -> List[News]:
        """按日期查询新闻"""
        if crawl_date is None:
            crawl_date = datetime.now().strftime("%Y-%m-%d")
        
        conditions = ["crawl_date = ?"]
        params = [crawl_date]
        
        if platform_id:
            conditions.append("platform_id = ?")
            params.append(platform_id)
        
        if category:
            conditions.append("category = ?")
            params.append(category)
        
        sql = f"""
            SELECT * FROM news 
            WHERE {' AND '.join(conditions)}
            ORDER BY weight_score DESC, current_rank ASC
            LIMIT ?
        """
        params.append(limit)
        
        rows = self.db.fetch_all(sql, tuple(params))
        return [News.from_db_row(row) for row in rows]
    
    def find_new_since(
        self,
        since_time: datetime,
        platform_ids: List[str] = None
    ) -> List[News]:
        """查找指定时间之后的新增新闻"""
        conditions = ["first_seen_at > ?"]
        params = [since_time.isoformat()]
        
        if platform_ids:
            placeholders = ','.join(['?' for _ in platform_ids])
            conditions.append(f"platform_id IN ({placeholders})")
            params.extend(platform_ids)
        
        sql = f"""
            SELECT * FROM news 
            WHERE {' AND '.join(conditions)}
            ORDER BY first_seen_at DESC
        """
        rows = self.db.fetch_all(sql, tuple(params))
        return [News.from_db_row(row) for row in rows]
    
    def search_by_keyword(
        self, 
        keyword: str,
        crawl_date: str = None,
        limit: int = 50
    ) -> List[News]:
        """按关键词搜索新闻"""
        conditions = ["title LIKE ?"]
        params = [f"%{keyword}%"]
        
        if crawl_date:
            conditions.append("crawl_date = ?")
            params.append(crawl_date)
        
        sql = f"""
            SELECT * FROM news 
            WHERE {' AND '.join(conditions)}
            ORDER BY weight_score DESC
            LIMIT ?
        """
        params.append(limit)
        
        rows = self.db.fetch_all(sql, tuple(params))
        return [News.from_db_row(row) for row in rows]
    
    def get_platform_stats(self, crawl_date: str = None) -> List[Dict]:
        """获取各平台新闻统计"""
        if crawl_date is None:
            crawl_date = datetime.now().strftime("%Y-%m-%d")
        
        sql = """
            SELECT 
                platform_id,
                COUNT(*) as total_news,
                AVG(current_rank) as avg_rank,
                SUM(appearance_count) as total_appearances
            FROM news
            WHERE crawl_date = ?
            GROUP BY platform_id
            ORDER BY total_news DESC
        """
        rows = self.db.fetch_all(sql, (crawl_date,))
        return [dict(row) for row in rows]
    
    def get_trending_keywords(
        self, 
        crawl_date: str = None, 
        top_n: int = 20
    ) -> List[Dict]:
        """获取热门关键词（简单分词）"""
        if crawl_date is None:
            crawl_date = datetime.now().strftime("%Y-%m-%d")
        
        # 这里使用关键词匹配表的统计
        sql = """
            SELECT 
                keyword_group,
                COUNT(*) as match_count
            FROM keyword_matches
            WHERE crawl_date = ?
            GROUP BY keyword_group
            ORDER BY match_count DESC
            LIMIT ?
        """
        rows = self.db.fetch_all(sql, (crawl_date, top_n))
        return [dict(row) for row in rows]
    
    def delete_old_news(self, before_date: str) -> int:
        """删除指定日期之前的新闻"""
        sql = "DELETE FROM news WHERE crawl_date < ?"
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, (before_date,))
            return cursor.rowcount


class KeywordMatchRepository:
    """关键词匹配仓库"""
    
    def __init__(self, db: DatabaseManager = None):
        self.db = db or get_db()
    
    def insert(self, match: KeywordMatch) -> int:
        """插入匹配记录"""
        sql = """
            INSERT INTO keyword_matches (
                news_id, keyword_group, keywords_matched, matched_at,
                title, platform_id, crawl_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(sql, match.to_db_tuple())
            return cursor.lastrowid
    
    def insert_batch(self, matches: List[KeywordMatch]) -> int:
        """批量插入匹配记录"""
        sql = """
            INSERT INTO keyword_matches (
                news_id, keyword_group, keywords_matched, matched_at,
                title, platform_id, crawl_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        with self.db.get_connection() as conn:
            conn.executemany(sql, [m.to_db_tuple() for m in matches])
            return len(matches)
    
    def find_by_keyword_group(
        self, 
        keyword_group: str,
        crawl_date: str = None,
        limit: int = 50
    ) -> List[KeywordMatch]:
        """按关键词组查找匹配"""
        conditions = ["keyword_group = ?"]
        params = [keyword_group]
        
        if crawl_date:
            conditions.append("crawl_date = ?")
            params.append(crawl_date)
        
        sql = f"""
            SELECT * FROM keyword_matches 
            WHERE {' AND '.join(conditions)}
            ORDER BY matched_at DESC
            LIMIT ?
        """
        params.append(limit)
        
        rows = self.db.fetch_all(sql, tuple(params))
        return [KeywordMatch.from_db_row(row) for row in rows]
    
    def get_keyword_stats(self, crawl_date: str = None) -> List[Dict]:
        """获取关键词统计"""
        if crawl_date is None:
            crawl_date = datetime.now().strftime("%Y-%m-%d")
        
        sql = """
            SELECT 
                keyword_group,
                COUNT(*) as match_count,
                COUNT(DISTINCT platform_id) as platform_count
            FROM keyword_matches
            WHERE crawl_date = ?
            GROUP BY keyword_group
            ORDER BY match_count DESC
        """
        rows = self.db.fetch_all(sql, (crawl_date,))
        return [dict(row) for row in rows]
