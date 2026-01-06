import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_database_cfg() -> dict:
    cfg_path = PROJECT_ROOT / "config" / "database.yaml"
    if not cfg_path.exists():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}


def _get_sqlite_path(cfg: dict, override: str = "") -> str:
    if override:
        return override
    return str((cfg.get("sqlite") or {}).get("path") or "data/trendradar.db")


def _get_mongo_cfg(cfg: dict) -> dict:
    return dict(cfg.get("mongodb") or {})


def _open_sqlite(db_path: str):
    from database.connection import get_db

    return get_db(db_path)


def _iter_sqlite_rows(conn, sql: str, params: tuple, batch_size: int):
    cursor = conn.execute(sql, params)
    while True:
        batch = cursor.fetchmany(batch_size)
        if not batch:
            return
        yield batch


def _count_sqlite(conn, table: str) -> int:
    row = conn.execute(f"SELECT COUNT(*) AS c FROM {table}").fetchone()
    if not row:
        return 0
    return int(row[0] or 0)


def init_mongo_indexes(mongo_db, dry_run: bool):
    specs = {
        "platforms": [
            {
                "keys": [("category", 1), ("enabled", 1)],
                "kwargs": {"name": "idx_platforms_category_enabled"},
            }
        ],
        "news": [
            {
                "keys": [("platform_id", 1), ("title_hash", 1), ("crawl_date", 1)],
                "kwargs": {
                    "name": "uniq_news_platform_titlehash_date",
                    "unique": True,
                },
            },
            {
                "keys": [("platform_id", 1), ("crawl_date", 1)],
                "kwargs": {"name": "idx_news_platform_date"},
            },
            {
                "keys": [("platform_id", 1), ("category", 1), ("crawl_date", -1)],
                "kwargs": {"name": "idx_news_platform_category_date"},
            },
            {"keys": [("crawl_date", -1)], "kwargs": {"name": "idx_news_crawl_date"}},
            {"keys": [("category", 1)], "kwargs": {"name": "idx_news_category"}},
            {"keys": [("title_hash", 1)], "kwargs": {"name": "idx_news_title_hash"}},
            {"keys": [("weight_score", -1)], "kwargs": {"name": "idx_news_weight"}},
        ],
        "keyword_matches": [
            {"keys": [("news_id", 1)], "kwargs": {"name": "idx_keyword_matches_news_id"}},
            {
                "keys": [("keyword_group", 1)],
                "kwargs": {"name": "idx_keyword_matches_keyword"},
            },
            {
                "keys": [("crawl_date", -1)],
                "kwargs": {"name": "idx_keyword_matches_date"},
            },
            {
                "keys": [("crawl_date", 1), ("keyword_group", 1)],
                "kwargs": {"name": "idx_keyword_matches_date_group"},
            },
        ],
        "crawl_logs": [
            {
                "keys": [("task_id", 1)],
                "kwargs": {"name": "uniq_crawl_logs_task_id", "unique": True},
            },
            {
                "keys": [("started_at", -1)],
                "kwargs": {"name": "idx_crawl_logs_started_at"},
            },
            {
                "keys": [("status", 1), ("started_at", -1)],
                "kwargs": {"name": "idx_crawl_logs_status"},
            },
        ],
        "push_records": [
            {
                "keys": [("channel", 1), ("push_date", 1)],
                "kwargs": {"name": "idx_push_records_channel_date"},
            },
            {
                "keys": [("push_date", 1), ("channel", 1), ("status", 1)],
                "kwargs": {"name": "idx_push_records_date_channel_status"},
            },
            {
                "keys": [("pushed_at", -1)],
                "kwargs": {"name": "idx_push_records_pushed_at"},
            },
        ],
        "analytics_cache": [
            {
                "keys": [("expires_at", 1)],
                "kwargs": {
                    "name": "ttl_analytics_cache_expires",
                    "expireAfterSeconds": 0,
                },
            }
        ],
    }

    if dry_run:
        return {"dry_run": True, "collections": {k: len(v) for k, v in specs.items()}}

    if mongo_db is None:
        raise ValueError("mongo_db 不能为空")

    created = 0
    for col_name, idx_specs in specs.items():
        col = mongo_db[col_name]
        for spec in idx_specs:
            keys = spec["keys"]
            kwargs = dict(spec.get("kwargs") or {})
            col.create_index(keys, **kwargs)
            created += 1
    return {"dry_run": False, "created": created}


def migrate_platforms(sqlite_db, mongo_db, batch_size: int, dry_run: bool, limit: int):
    from database.models import Platform
    from database.repositories.platform_repo import MongoPlatformRepository

    repo = MongoPlatformRepository(mongo_db) if not dry_run else None
    inserted = 0
    with sqlite_db.get_connection() as conn:
        sql = "SELECT * FROM platforms ORDER BY id"
        params = ()
        if limit > 0:
            sql = f"{sql} LIMIT ?"
            params = (int(limit),)

        for batch in _iter_sqlite_rows(conn, sql, params, batch_size):
            models = [Platform.from_db_row(r) for r in batch]
            if dry_run:
                inserted += len(models)
            else:
                inserted += int(repo.insert_batch(models))
    return {"inserted": inserted}


def migrate_news(sqlite_db, mongo_db, batch_size: int, dry_run: bool, limit: int):
    from database.models import News
    from database.repositories.news_repo import MongoNewsRepository

    repo = MongoNewsRepository(mongo_db) if not dry_run else None
    inserted = 0
    updated = 0
    with sqlite_db.get_connection() as conn:
        sql = "SELECT * FROM news ORDER BY id"
        params = ()
        if limit > 0:
            sql = f"{sql} LIMIT ?"
            params = (int(limit),)

        for batch in _iter_sqlite_rows(conn, sql, params, batch_size):
            models = [News.from_db_row(r) for r in batch]
            if dry_run:
                inserted += len(models)
            else:
                if callable(getattr(repo, "upsert_exact_batch", None)):
                    ins, upd = repo.upsert_exact_batch(models)
                else:
                    ins, upd = repo.insert_batch(models)
                inserted += int(ins)
                updated += int(upd)
    return {"inserted": inserted, "updated": updated}


def migrate_crawl_logs(sqlite_db, mongo_db, batch_size: int, dry_run: bool, limit: int):
    from database.models import CrawlLog

    inserted = 0
    updated = 0
    with sqlite_db.get_connection() as conn:
        sql = "SELECT * FROM crawl_logs ORDER BY id"
        params = ()
        if limit > 0:
            sql = f"{sql} LIMIT ?"
            params = (int(limit),)

        col = mongo_db["crawl_logs"] if not dry_run else None
        for batch in _iter_sqlite_rows(conn, sql, params, batch_size):
            models = [CrawlLog.from_db_row(r) for r in batch]
            if dry_run:
                inserted += len(models)
                continue

            for log in models:
                update = {
                    "$set": {
                        "task_id": log.task_id,
                        "started_at": log.started_at,
                        "finished_at": log.finished_at,
                        "duration_ms": int(log.duration_ms),
                        "platforms_crawled": list(log.platforms_crawled or []),
                        "total_news": int(log.total_news),
                        "new_news": int(log.new_news),
                        "failed_platforms": list(log.failed_platforms or []),
                        "status": log.status,
                        "error_message": log.error_message,
                        "platform_results": list(log.platform_results or []),
                    }
                }
                res = col.update_one({"task_id": log.task_id}, update, upsert=True)
                if res.upserted_id is not None:
                    inserted += 1
                else:
                    updated += 1
    return {"inserted": inserted, "updated": updated}


def _build_news_sqlite_id_map(mongo_db, sqlite_news_ids: list[int]) -> dict[int, object]:
    if not sqlite_news_ids:
        return {}
    ids = sorted({int(x) for x in sqlite_news_ids if x is not None})
    if not ids:
        return {}
    cursor = mongo_db["news"].find(
        {"sqlite_id": {"$in": ids}},
        {"_id": 1, "sqlite_id": 1},
    )
    mapping: dict[int, object] = {}
    for doc in cursor:
        sqlite_id = doc.get("sqlite_id")
        if sqlite_id is None:
            continue
        try:
            mapping[int(sqlite_id)] = doc.get("_id")
        except Exception:
            continue
    return mapping


def migrate_keyword_matches(sqlite_db, mongo_db, batch_size: int, dry_run: bool, limit: int):
    from database.models import KeywordMatch

    inserted = 0
    missing_news_ref = 0

    with sqlite_db.get_connection() as conn:
        sql = "SELECT * FROM keyword_matches ORDER BY id"
        params = ()
        if limit > 0:
            sql = f"{sql} LIMIT ?"
            params = (int(limit),)

        col = mongo_db["keyword_matches"] if not dry_run else None

        for batch in _iter_sqlite_rows(conn, sql, params, batch_size):
            models = [KeywordMatch.from_db_row(r) for r in batch]
            if dry_run:
                inserted += len(models)
                continue

            news_id_map = _build_news_sqlite_id_map(mongo_db, [m.news_id for m in models])
            docs = []
            for m in models:
                news_oid = news_id_map.get(int(m.news_id)) if m.news_id is not None else None
                if news_oid is None:
                    missing_news_ref += 1
                docs.append(
                    {
                        "news_id": news_oid,
                        "keyword_group": m.keyword_group,
                        "keywords_matched": list(m.keywords_matched or []),
                        "matched_at": m.matched_at,
                        "title": m.title,
                        "platform_id": m.platform_id,
                        "crawl_date": m.crawl_date,
                        "sqlite_id": int(m.id) if m.id is not None else None,
                    }
                )

            if docs:
                col.insert_many(docs, ordered=False)
                inserted += len(docs)

    return {"inserted": inserted, "missing_news_ref": missing_news_ref}


def migrate_push_records(sqlite_db, mongo_db, batch_size: int, dry_run: bool, limit: int):
    from database.models import PushRecord

    inserted = 0
    updated = 0

    with sqlite_db.get_connection() as conn:
        sql = "SELECT * FROM push_records ORDER BY id"
        params = ()
        if limit > 0:
            sql = f"{sql} LIMIT ?"
            params = (int(limit),)

        col = mongo_db["push_records"] if not dry_run else None

        for batch in _iter_sqlite_rows(conn, sql, params, batch_size):
            models = [PushRecord.from_db_row(r) for r in batch]
            if dry_run:
                inserted += len(models)
                continue

            from pymongo import UpdateOne

            ops = []
            for r in models:
                sqlite_id = int(r.id) if r.id is not None else None
                if sqlite_id is None:
                    continue
                update = {
                    "$set": {
                        "sqlite_id": sqlite_id,
                        "channel": r.channel,
                        "report_type": r.report_type,
                        "status": r.status,
                        "error_message": r.error_message,
                        "news_count": int(r.news_count),
                        "keyword_groups": list(r.keyword_groups or []),
                        "message_batches": int(r.message_batches),
                        "message_hash": r.message_hash,
                        "pushed_at": r.pushed_at,
                        "push_date": r.push_date,
                    },
                    "$setOnInsert": {"created_at": r.pushed_at},
                }
                ops.append(UpdateOne({"sqlite_id": sqlite_id}, update, upsert=True))

            if ops:
                result = col.bulk_write(ops, ordered=False)
                inserted += int(result.upserted_count or 0)
                updated += int(result.matched_count or 0)

    return {"inserted": inserted, "updated": updated}


def _try_parse_json(value: str):
    import json

    if value is None:
        return None
    if not isinstance(value, str):
        return value


def _parse_dt(value):
    from datetime import datetime

    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            if "T" not in text and " " in text:
                text = text.replace(" ", "T", 1)
            return datetime.fromisoformat(text)
        except Exception:
            return value
    return value
    text = value.strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except Exception:
        return value


def migrate_analytics_cache(sqlite_db, mongo_db, batch_size: int, dry_run: bool, limit: int):
    inserted = 0
    updated = 0

    with sqlite_db.get_connection() as conn:
        sql = "SELECT * FROM analytics_cache ORDER BY cache_key"
        params = ()
        if limit > 0:
            sql = f"{sql} LIMIT ?"
            params = (int(limit),)

        col = mongo_db["analytics_cache"] if not dry_run else None

        for batch in _iter_sqlite_rows(conn, sql, params, batch_size):
            if dry_run:
                inserted += len(batch)
                continue

            from pymongo import UpdateOne

            ops = []
            for r in batch:
                cache_key = r["cache_key"]
                cache_type = r["cache_type"]
                result_raw = r["result"]
                expires_at = _parse_dt(r["expires_at"])
                created_at = _parse_dt(r["created_at"]) if "created_at" in r.keys() else None

                if not cache_key:
                    continue

                update = {
                    "$set": {
                        "cache_type": cache_type,
                        "result": _try_parse_json(result_raw),
                        "expires_at": expires_at,
                        "updated_at": created_at,
                    },
                    "$setOnInsert": {"created_at": created_at},
                }
                ops.append(UpdateOne({"_id": cache_key}, update, upsert=True))

            if ops:
                result = col.bulk_write(ops, ordered=False)
                inserted += int(result.upserted_count or 0)
                updated += int(result.matched_count or 0)

    return {"inserted": inserted, "updated": updated}


def verify_migration(sqlite_db, mongo_db):
    sqlite_counts = {}
    with sqlite_db.get_connection() as conn:
        for table in (
            "platforms",
            "news",
            "keyword_matches",
            "crawl_logs",
            "push_records",
            "analytics_cache",
        ):
            sqlite_counts[table] = _count_sqlite(conn, table)

    mongo_counts = {}
    for col_name in (
        "platforms",
        "news",
        "keyword_matches",
        "crawl_logs",
        "push_records",
        "analytics_cache",
    ):
        mongo_counts[col_name] = int(mongo_db[col_name].count_documents({}))

    diff = {k: int(mongo_counts.get(k, 0)) - int(sqlite_counts.get(k, 0)) for k in sqlite_counts}
    ok = all(int(v) == 0 for v in diff.values())
    return {"ok": ok, "sqlite": sqlite_counts, "mongo": mongo_counts, "diff": diff}


def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--sqlite-path", default="")
    common.add_argument("--batch-size", type=int, default=500)
    common.add_argument("--limit", type=int, default=0)
    common.add_argument("--dry-run", action="store_true")

    parser = argparse.ArgumentParser(parents=[common])

    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("platforms", parents=[common])
    sub.add_parser("news", parents=[common])
    sub.add_parser("keyword_matches", parents=[common])
    sub.add_parser("crawl_logs", parents=[common])
    sub.add_parser("push_records", parents=[common])
    sub.add_parser("analytics_cache", parents=[common])
    sub.add_parser("init_indexes", parents=[common])
    sub.add_parser("verify", parents=[common])
    sub.add_parser("all", parents=[common])
    sub.add_parser("counts", parents=[common])
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    cfg = _load_database_cfg()
    if args.cmd == "counts":
        sqlite_path = _get_sqlite_path(cfg, args.sqlite_path)
        sqlite_db = _open_sqlite(sqlite_path)
        with sqlite_db.get_connection() as conn:
            counts = {
                "platforms": _count_sqlite(conn, "platforms"),
                "news": _count_sqlite(conn, "news"),
                "keyword_matches": _count_sqlite(conn, "keyword_matches"),
                "crawl_logs": _count_sqlite(conn, "crawl_logs"),
                "push_records": _count_sqlite(conn, "push_records"),
                "analytics_cache": _count_sqlite(conn, "analytics_cache"),
            }
            print({"sqlite_path": sqlite_path, "counts": counts})
            return 0

    if args.cmd == "init_indexes":
        mongo_db = None
        if not args.dry_run:
            from database.connection import get_mongo_database

            mongo_db = get_mongo_database(_get_mongo_cfg(cfg))
        print({"init_indexes": init_mongo_indexes(mongo_db, args.dry_run)})
        return 0

    sqlite_path = _get_sqlite_path(cfg, args.sqlite_path)
    sqlite_db = _open_sqlite(sqlite_path)

    mongo_db = None
    if args.cmd == "verify":
        from database.connection import get_mongo_database

        mongo_db = get_mongo_database(_get_mongo_cfg(cfg))
        print({"verify": verify_migration(sqlite_db, mongo_db)})
        return 0

    if not args.dry_run:
        from database.connection import get_mongo_database

        mongo_db = get_mongo_database(_get_mongo_cfg(cfg))

    batch_size = max(1, int(args.batch_size))
    limit = int(args.limit)

    if args.cmd in ("platforms", "all"):
        print({"platforms": migrate_platforms(sqlite_db, mongo_db, batch_size, args.dry_run, limit)})
    if args.cmd in ("news", "all"):
        print({"news": migrate_news(sqlite_db, mongo_db, batch_size, args.dry_run, limit)})
    if args.cmd in ("keyword_matches", "all"):
        print({"keyword_matches": migrate_keyword_matches(sqlite_db, mongo_db, batch_size, args.dry_run, limit)})
    if args.cmd in ("crawl_logs", "all"):
        print({"crawl_logs": migrate_crawl_logs(sqlite_db, mongo_db, batch_size, args.dry_run, limit)})
    if args.cmd in ("push_records", "all"):
        print({"push_records": migrate_push_records(sqlite_db, mongo_db, batch_size, args.dry_run, limit)})
    if args.cmd in ("analytics_cache", "all"):
        print({"analytics_cache": migrate_analytics_cache(sqlite_db, mongo_db, batch_size, args.dry_run, limit)})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
