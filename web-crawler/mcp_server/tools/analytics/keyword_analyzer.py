# coding=utf-8
"""
关键词分析模块
提供关键词共现分析功能
"""

import re
from collections import Counter, defaultdict
from typing import Dict

from ...services.data_service import DataService
from ...utils.validators import validate_limit, validate_top_n
from ...utils.errors import MCPError


class KeywordAnalyzer:
    """关键词分析器"""

    def __init__(self, data_service: DataService):
        self.data_service = data_service

    def analyze_keyword_cooccurrence(
        self,
        min_frequency: int = 3,
        top_n: int = 20
    ) -> Dict:
        """
        关键词共现分析 - 分析哪些关键词经常同时出现

        Args:
            min_frequency: 最小共现频次
            top_n: 返回TOP N关键词对

        Returns:
            关键词共现分析结果
        """
        try:
            min_frequency = validate_limit(min_frequency, default=3, max_limit=100)
            top_n = validate_top_n(top_n, default=20)

            all_titles, _, _ = self.data_service.parser.read_all_titles_for_date()

            cooccurrence = Counter()
            keyword_titles = defaultdict(list)

            for platform_id, titles in all_titles.items():
                for title in titles.keys():
                    keywords = self._extract_keywords(title)

                    for kw in keywords:
                        keyword_titles[kw].append(title)

                    if len(keywords) >= 2:
                        for i, kw1 in enumerate(keywords):
                            for kw2 in keywords[i+1:]:
                                pair = tuple(sorted([kw1, kw2]))
                                cooccurrence[pair] += 1

            filtered_pairs = [
                (pair, count) for pair, count in cooccurrence.items()
                if count >= min_frequency
            ]

            top_pairs = sorted(filtered_pairs, key=lambda x: x[1], reverse=True)[:top_n]

            result_pairs = []
            for (kw1, kw2), count in top_pairs:
                titles_with_both = [
                    title for title in keyword_titles[kw1]
                    if kw2 in self._extract_keywords(title)
                ][:3]

                result_pairs.append({
                    "keyword1": kw1,
                    "keyword2": kw2,
                    "cooccurrence_count": count,
                    "sample_titles": titles_with_both
                })

            return {
                "success": True,
                "min_frequency": min_frequency,
                "top_n": top_n,
                "cooccurrence_pairs": result_pairs,
                "total_pairs_found": len(filtered_pairs)
            }

        except MCPError as e:
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            return {"success": False, "error": {"code": "INTERNAL_ERROR", "message": str(e)}}

    def _extract_keywords(self, title: str) -> list:
        """从标题中提取关键词"""
        words = re.split(r'[\s,，。！？、：；""''【】（）\[\]《》]+', title)
        keywords = [w.strip() for w in words if len(w.strip()) >= 2]
        return keywords[:5]
