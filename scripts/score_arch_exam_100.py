#!/usr/bin/env python3
"""
TrendRadar 架构 100 分小测自动评分脚本 (v2)

要求模型按 JSON 格式回答，字段见题目说明。

用法:
  python3 scripts/score_arch_exam_100.py --file answer.json
  python3 scripts/score_arch_exam_100.py --answer '{"q1_touchpoints":[...], ... }'
  cat answer.json | python3 scripts/score_arch_exam_100.py
  python3 scripts/score_arch_exam_100.py --file answer.json --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


QUESTION_ID = "trendradar_arch_v2_100"


def _normalize(s: str) -> str:
    return re.sub(r"\s+", "", s or "").lower()


def _coerce_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if str(v).strip()]
    if isinstance(value, (str, int, float)):
        text = str(value)
        # split by common separators
        parts = re.split(r"[,\n;；、/|]+", text)
        return [p.strip() for p in parts if p.strip()]
    return [str(value)]


def _extract_numbers(value: Any) -> List[int]:
    if value is None:
        return []
    if isinstance(value, (int, float)):
        return [int(value)]
    if isinstance(value, list):
        nums: List[int] = []
        for v in value:
            nums.extend(_extract_numbers(v))
        return nums
    text = str(value)
    return [int(n) for n in re.findall(r"\d+", text)]


def _match_patterns(texts: Iterable[str], patterns: List[str]) -> bool:
    joined = "\n".join(texts)
    for pat in patterns:
        if re.search(pat, joined, re.IGNORECASE):
            return True
    return False


def _score_list_question(
    answer_value: Any,
    expected: Dict[str, List[str]],
    weight: float,
) -> Tuple[float, Dict[str, Any]]:
    answers = _coerce_list(answer_value)
    per_item = weight / max(len(expected), 1)
    found: Dict[str, bool] = {}
    for key, patterns in expected.items():
        found[key] = _match_patterns(answers, patterns)
    score = per_item * sum(1 for v in found.values() if v)
    detail = {
        "per_item": round(per_item, 4),
        "found": [k for k, v in found.items() if v],
        "missing": [k for k, v in found.items() if not v],
    }
    return score, detail


def _score_mapping_question(
    answer_value: Any,
    expected: Dict[str, str],
    weight: float,
    key_normalizer=None,
    value_matcher=None,
) -> Tuple[float, Dict[str, Any]]:
    if not isinstance(answer_value, dict):
        answer_map: Dict[str, Any] = {}
    else:
        answer_map = answer_value

    per_item = weight / max(len(expected), 1)
    found: Dict[str, bool] = {}

    def norm_key(k: str) -> str:
        return key_normalizer(k) if key_normalizer else _normalize(k)

    def match_val(exp: str, act: Any) -> bool:
        if value_matcher:
            return value_matcher(exp, act)
        return _normalize(exp) in _normalize(str(act))

    normalized_answer = {norm_key(k): v for k, v in answer_map.items()}

    for exp_key, exp_val in expected.items():
        act_val = normalized_answer.get(norm_key(exp_key))
        found[exp_key] = act_val is not None and match_val(exp_val, act_val)

    score = per_item * sum(1 for v in found.values() if v)
    detail = {
        "per_item": round(per_item, 4),
        "found": [k for k, v in found.items() if v],
        "missing": [k for k, v in found.items() if not v],
    }
    return score, detail


def normalize_endpoint(s: str) -> str:
    s = _normalize(s)
    if not s.startswith("/"):
        s = "/" + s
    s = s.replace("<category>", "{category}")
    s = s.replace("{category}", "{category}")
    return s


def match_path(expected_path: str, actual_value: Any) -> bool:
    exp = _normalize(expected_path)
    act = _normalize(str(actual_value))
    return exp in act or act.endswith(exp.split("/")[-1])


def extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        # try to extract first {...}
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            snippet = text[start : end + 1]
            return json.loads(snippet)
        raise


@dataclass
class QuestionResult:
    score: float
    weight: float
    detail: Dict[str, Any]


def grade(answer: Dict[str, Any]) -> Tuple[float, Dict[str, QuestionResult]]:
    results: Dict[str, QuestionResult] = {}

    # Q1 touchpoints (10)
    q1_expected = {
        "React 前端": [r"\breact\b", r"react前端", r"frontend", r"前端"],
        "CLI 命令行": [r"\bcli\b", r"命令行", r"main\.py"],
        "MCP Server": [r"\bmcp\b", r"mcpserver", r"mcp_server", r"ide"],
    }
    q1_score, q1_detail = _score_list_question(answer.get("q1_touchpoints"), q1_expected, 10)
    results["q1_touchpoints"] = QuestionResult(q1_score, 10, q1_detail)

    # Q2 ports (8): frontend=5173, backend=[8000,5173], redis=49907
    q2_weight = 8
    q2_expected_ports = {
        "frontend_port_5173": 5173,
        "backend_port_8000": 8000,
        "backend_port_5173": 5173,
        "redis_port_49907": 49907,
    }
    q2_answers = answer.get("q2_ports", {})
    if not isinstance(q2_answers, dict):
        q2_answers = {}
    nums_frontend = _extract_numbers(q2_answers.get("frontend"))
    nums_backend = _extract_numbers(q2_answers.get("backend"))
    nums_redis = _extract_numbers(q2_answers.get("redis"))
    q2_found = {
        "frontend_port_5173": 5173 in nums_frontend,
        "backend_port_8000": 8000 in nums_backend,
        "backend_port_5173": 5173 in nums_backend,
        "redis_port_49907": 49907 in nums_redis,
    }
    q2_per_item = q2_weight / 4
    q2_score = q2_per_item * sum(1 for v in q2_found.values() if v)
    results["q2_ports"] = QuestionResult(
        q2_score,
        q2_weight,
        {
            "per_item": round(q2_per_item, 4),
            "found": [k for k, v in q2_found.items() if v],
            "missing": [k for k, v in q2_found.items() if not v],
        },
    )

    # Q3 main API endpoints (10)
    q3_expected = {
        "/api/news/{category}": [r"/api/news/\s*(\{?\s*category\s*\}?|<\s*category\s*>|\{category\})"],
        "/api/data": [r"/api/data\b"],
        "/api/generate-analysis": [r"/api/generate-analysis\b"],
        "/api/market-analysis": [r"/api/market-analysis\b"],
        "/api/price-history": [r"/api/price-history\b"],
        "/api/reports": [r"/api/reports\b"],
        "/api/cache/status": [r"/api/cache/status\b"],
    }
    q3_score, q3_detail = _score_list_question(answer.get("q3_api_endpoints"), q3_expected, 10)
    results["q3_api_endpoints"] = QuestionResult(q3_score, 10, q3_detail)

    # Q4 endpoint -> route file mapping (10)
    q4_expected = {
        "/api/news/{category}": "api/routes/news.py",
        "/api/data": "api/routes/data.py",
        "/api/generate-analysis": "api/routes/analysis.py",
        "/api/market-analysis": "api/routes/analysis.py",
        "/api/price-history": "api/routes/data.py",
        "/api/reports": "api/routes/reports.py",
        "/api/cache/status": "api/routes/cache.py",
    }
    q4_score, q4_detail = _score_mapping_question(
        answer.get("q4_route_files"),
        q4_expected,
        10,
        key_normalizer=normalize_endpoint,
        value_matcher=match_path,
    )
    results["q4_route_files"] = QuestionResult(q4_score, 10, q4_detail)

    # Q5 scrapers/ core files (8)
    q5_expected = {
        "unified.py": [r"unified\.py", r"\bunified\b"],
        "finance.py": [r"finance\.py", r"\bfinance\b"],
        "commodity.py": [r"commodity\.py", r"\bcommodity\b"],
        "smm.py": [r"smm\.py", r"\bsmm\b", r"上海有色"],
        "plastic21cp.py": [r"plastic21cp\.py", r"21cp", r"中塑在线"],
        "plasway.py": [r"plasway\.py", r"plasway"],
    }
    q5_score, q5_detail = _score_list_question(answer.get("q5_scrapers_files"), q5_expected, 8)
    results["q5_scrapers_files"] = QuestionResult(q5_score, 8, q5_detail)

    # Q6 pacong components (8)
    q6_expected = {
        "applescript.py": [r"applescript\.py", r"applescript"],
        "selenium_driver": [r"selenium", r"selenium_driver"],
        "cdp_driver": [r"cdp", r"cdp_driver"],
        "business_insider": [r"business\s*insider", r"business_insider"],
        "world_bank": [r"world\s*bank", r"world_bank"],
    }
    q6_value = answer.get("q6_pacong_components")
    # allow object {"browser":[...], "scrapers":[...]} or list
    if isinstance(q6_value, dict):
        merged: List[str] = []
        merged.extend(_coerce_list(q6_value.get("browser")))
        merged.extend(_coerce_list(q6_value.get("scrapers")))
        q6_value = merged
    q6_score, q6_detail = _score_list_question(q6_value, q6_expected, 8)
    results["q6_pacong_components"] = QuestionResult(q6_score, 8, q6_detail)

    # Q7 core/ modules (8)
    q7_expected = {
        "config.py": [r"config\.py", r"\bconfig\b"],
        "analyzer.py": [r"analyzer\.py", r"\banalyzer\b"],
        "statistics.py": [r"statistics\.py", r"\bstatistics\b", r"词频"],
        "price_history.py": [r"price_history\.py", r"pricehistory"],
        "notifiers/": [r"notifiers", r"推送", r"通知"],
        "reporters/": [r"reporters", r"报告生成", r"report"],
    }
    q7_score, q7_detail = _score_list_question(answer.get("q7_core_modules"), q7_expected, 8)
    results["q7_core_modules"] = QuestionResult(q7_score, 8, q7_detail)

    # Q8 commodity sources (10)
    q8_expected = {
        "新浪期货": [r"新浪期货", r"\bsina\b"],
        "上海有色网": [r"上海有色", r"\bsmm\b"],
        "Business Insider": [r"business\s*insider", r"\bbi\b"],
        "中塑在线 21CP": [r"21cp", r"中塑在线"],
        "中国原油网 intercrude": [r"intercrude", r"中国原油网"],
        "WTI 原油": [r"\bwti\b", r"wti原油"],
    }
    q8_score, q8_detail = _score_list_question(answer.get("q8_commodity_sources"), q8_expected, 10)
    results["q8_commodity_sources"] = QuestionResult(q8_score, 10, q8_detail)

    # Q9 persistence targets (6)
    q9_expected = {
        "Redis 缓存": [r"redis", r"缓存"],
        "MySQL 持久化": [r"mysql", r"commodity_latest", r"commodity_history"],
        "PriceHistory 历史存档": [r"pricehistory", r"价格历史"],
        "文件系统输出": [r"reports/\\*\\.md", r"report_.*\\.md", r"output/\\*\\.json", r"文件系统"],
    }
    q9_score, q9_detail = _score_list_question(answer.get("q9_persistence_targets"), q9_expected, 6)
    results["q9_persistence_targets"] = QuestionResult(q9_score, 6, q9_detail)

    # Q10 AI config (8)
    q10_weight = 8
    q10_value = answer.get("q10_ai_config", {})
    if not isinstance(q10_value, dict):
        q10_value = {}
    q10_expected = {
        "internal_api_base": r"10\.180\.116\.2:6400/v1",
        "internal_model": r"openai[_-]?gpt-oss-120b",
        "external_api_base": r"generativelanguage\.googleapis\.com/v1beta",
        "external_model": r"gemini-3-pro-preview",
        "thinking_level": r"\bhigh\b",
    }
    q10_found: Dict[str, bool] = {}
    for k, pat in q10_expected.items():
        q10_found[k] = re.search(pat, str(q10_value.get(k, "")), re.IGNORECASE) is not None
    q10_per_item = q10_weight / len(q10_expected)
    q10_score = q10_per_item * sum(1 for v in q10_found.values() if v)
    results["q10_ai_config"] = QuestionResult(
        q10_score,
        q10_weight,
        {
            "per_item": round(q10_per_item, 4),
            "found": [k for k, v in q10_found.items() if v],
            "missing": [k for k, v in q10_found.items() if not v],
        },
    )

    # Q11 weight values (6)
    q11_weight = 6
    q11_value = answer.get("q11_weight_values", {})
    if not isinstance(q11_value, dict):
        q11_value = {}
    q11_expected = {
        "rank_weight": 0.6,
        "frequency_weight": 0.3,
        "hotness_weight": 0.1,
    }
    q11_found: Dict[str, bool] = {}
    for k, exp in q11_expected.items():
        nums = _extract_numbers(q11_value.get(k))
        ok = any(abs(n - int(exp * 10)) <= 0 for n in nums)  # allow 0.6 -> 6 or 0.6
        if not ok:
            try:
                ok = abs(float(q11_value.get(k)) - exp) <= 0.01
            except Exception:
                ok = False
        q11_found[k] = ok
    q11_per_item = q11_weight / len(q11_expected)
    q11_score = q11_per_item * sum(1 for v in q11_found.values() if v)
    results["q11_weight_values"] = QuestionResult(
        q11_score,
        q11_weight,
        {
            "per_item": round(q11_per_item, 4),
            "found": [k for k, v in q11_found.items() if v],
            "missing": [k for k, v in q11_found.items() if not v],
        },
    )

    # Q12 region colors (8)
    q12_expected = {
        "华东": "#3b82f6",
        "华南": "#10b981",
        "华北": "#f59e0b",
    }
    q12_score, q12_detail = _score_mapping_question(
        answer.get("q12_region_colors"),
        q12_expected,
        8,
        key_normalizer=lambda k: k.strip(),
        value_matcher=lambda exp, act: _normalize(exp) == _normalize(str(act)),
    )
    results["q12_region_colors"] = QuestionResult(q12_score, 8, q12_detail)

    total = sum(r.score for r in results.values())
    return total, results


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
    parser = argparse.ArgumentParser(description="TrendRadar 架构 100 分小测自动评分脚本")
    parser.add_argument("--file", "-f", help="JSON 答案文件路径")
    parser.add_argument("--answer", "-a", help="直接传入 JSON 答案字符串")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出评分结果")
    args = parser.parse_args()

    raw = read_answer(args)
    if not raw.strip():
        print("答案为空，无法评分。", file=sys.stderr)
        return 2

    try:
        answer_obj = extract_json(raw)
    except Exception as e:
        print(f"无法解析 JSON: {e}", file=sys.stderr)
        return 2

    total, results = grade(answer_obj)

    if args.json:
        payload = {
            "question_id": QUESTION_ID,
            "total": round(total, 2),
            "max_total": 100,
            "parts": {
                k: {
                    "score": round(v.score, 2),
                    "weight": v.weight,
                    "detail": v.detail,
                }
                for k, v in results.items()
            },
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"Score report ({QUESTION_ID})")
    for k, v in results.items():
        print(f"- {k}: {v.score:.2f}/{v.weight} (found {len(v.detail.get('found', []))})")
    print(f"Total: {total:.2f}/100")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

