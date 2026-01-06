#!/usr/bin/env python3
"""
TrendRadar 架构小测自动评分脚本 (v1)

题目（供参考）:
  读以下架构节选并回答：
    a) 用户触点层的三个入口分别是什么？
    b) FastAPI 后端默认端口是多少？
    c) 新闻数据 API 的完整路由是什么？
    d) 新闻缓存 TTL 是多少秒？

评分（总分 6）:
  a) 3 分：每命中 1 个入口得 1 分（React 前端 / CLI 命令行 / MCP Server）
  b) 1 分：包含 8000
  c) 1 分：包含 /api/news/{category}
  d) 1 分：包含 3600（或等价 1 小时）

用法:
  # 传文件
  python3 scripts/score_arch_prompt.py --file answer.txt

  # 传字符串
  python3 scripts/score_arch_prompt.py --answer "..."

  # 从 stdin 读取
  cat answer.txt | python3 scripts/score_arch_prompt.py

  # JSON 输出
  python3 scripts/score_arch_prompt.py --file answer.txt --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


QUESTION_ID = "trendradar_arch_v1"


ENTRYPOINTS: Dict[str, Dict[str, List[str]]] = {
    "react_frontend": {
        "label": "React 前端",
        "patterns": [
            r"\breact\b",
            r"react\s*前端",
            r"frontend",
            r"web\s*前端",
            r"前端界面",
            r"前端",
        ],
    },
    "cli": {
        "label": "CLI 命令行",
        "patterns": [
            r"\bcli\b",
            r"命令行",
            r"main\.py",
        ],
    },
    "mcp_server": {
        "label": "MCP Server",
        "patterns": [
            r"\bmcp\b",
            r"mcp\s*server",
            r"mcp_server",
            r"ide\s*工具",
        ],
    },
}


PORT_PATTERN = re.compile(r"(?<!\d)8000(?!\d)")
NEWS_ROUTE_PATTERN = re.compile(
    r"/?api/news/\s*(\{?\s*category\s*\}?|<\s*category\s*>|\{category\})",
    re.IGNORECASE,
)
TTL_PATTERN = re.compile(r"(?<!\d)3600(?!\d)|1\s*小时|一\s*小时", re.IGNORECASE)


@dataclass
class PartScore:
    score: int
    max_score: int
    detail: Dict


def _normalize(text: str) -> str:
    return text.strip().lower()


def score_part_a(text: str) -> PartScore:
    found_keys: List[str] = []
    for key, info in ENTRYPOINTS.items():
        for pat in info["patterns"]:
            if re.search(pat, text, re.IGNORECASE):
                found_keys.append(key)
                break

    found_keys = sorted(set(found_keys))
    missing_keys = [k for k in ENTRYPOINTS.keys() if k not in found_keys]

    return PartScore(
        score=min(len(found_keys), 3),
        max_score=3,
        detail={
            "found": [ENTRYPOINTS[k]["label"] for k in found_keys],
            "missing": [ENTRYPOINTS[k]["label"] for k in missing_keys],
        },
    )


def score_part_b(text: str) -> PartScore:
    ok = bool(PORT_PATTERN.search(text))
    return PartScore(score=1 if ok else 0, max_score=1, detail={"matched": ok})


def score_part_c(text: str) -> PartScore:
    ok = bool(NEWS_ROUTE_PATTERN.search(text))
    return PartScore(score=1 if ok else 0, max_score=1, detail={"matched": ok})


def score_part_d(text: str) -> PartScore:
    ok = bool(TTL_PATTERN.search(text))
    return PartScore(score=1 if ok else 0, max_score=1, detail={"matched": ok})


def score_answer(answer: str) -> Tuple[int, Dict[str, PartScore]]:
    text = _normalize(answer)
    parts = {
        "a": score_part_a(text),
        "b": score_part_b(text),
        "c": score_part_c(text),
        "d": score_part_d(text),
    }
    total = sum(p.score for p in parts.values())
    return total, parts


def read_answer(args: argparse.Namespace) -> str:
    if args.answer:
        return args.answer
    if args.file:
        return Path(args.file).read_text(encoding="utf-8")

    if not sys.stdin.isatty():
        return sys.stdin.read()

    print("未提供 --answer/--file，开始从 stdin 读取答案，结束请输入 Ctrl-D。", file=sys.stderr)
    return sys.stdin.read()


def main() -> int:
    parser = argparse.ArgumentParser(description="TrendRadar 架构小测自动评分脚本")
    parser.add_argument("--file", "-f", help="包含模型答案的文本文件路径")
    parser.add_argument("--answer", "-a", help="直接传入答案字符串")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出评分结果")
    args = parser.parse_args()

    answer = read_answer(args)
    if not answer.strip():
        print("答案为空，无法评分。", file=sys.stderr)
        return 2

    total, parts = score_answer(answer)

    if args.json:
        payload = {
            "question_id": QUESTION_ID,
            "total": total,
            "max_total": 6,
            "parts": {
                k: {
                    "score": v.score,
                    "max_score": v.max_score,
                    "detail": v.detail,
                }
                for k, v in parts.items()
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"Score report ({QUESTION_ID})")
    a = parts["a"]
    print(
        f"a) 入口: {a.score}/{a.max_score} "
        f"(found: {', '.join(a.detail['found']) or '无'}; "
        f"missing: {', '.join(a.detail['missing']) or '无'})"
    )
    for k in ["b", "c", "d"]:
        p = parts[k]
        label = {"b": "后端端口", "c": "新闻路由", "d": "TTL 秒数"}[k]
        print(f"{k}) {label}: {p.score}/{p.max_score}")
    print(f"Total: {total}/6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

