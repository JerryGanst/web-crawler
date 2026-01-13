#!/usr/bin/env python3
# coding=utf-8
"""
Text-to-SQL 混合查询端到端测试

使用方法:
    cd /Users/jerryganst/Desktop/Commodities/web-master/web/web-crawler
    python -m tests.test_hybrid_query

测试内容:
    1. MySQL 连接测试
    2. IntentClassifier 分类测试
    3. TextToSQLEngine SQL 生成测试
    4. SQL 执行测试
    5. 端到端查询测试
"""

import sys
import os
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_mysql_connection():
    """测试 1: MySQL 连接"""
    print("\n" + "=" * 60)
    print("测试 1: MySQL 连接测试")
    print("=" * 60)

    try:
        from database.mysql.connection import get_cursor, test_connection, MYSQL_CONFIG

        print(f"配置: {MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{MYSQL_CONFIG['database']}")

        if test_connection():
            print("[PASS] MySQL 连接成功")

            # 检查表是否存在
            with get_cursor() as cursor:
                cursor.execute("SHOW TABLES LIKE 'commodity_latest'")
                if cursor.fetchone():
                    print("[PASS] commodity_latest 表存在")

                    # 检查数据
                    cursor.execute("SELECT COUNT(*) as cnt FROM commodity_latest")
                    count = cursor.fetchone()['cnt']
                    print(f"[INFO] commodity_latest 表记录数: {count}")

                    if count > 0:
                        cursor.execute("SELECT id, chinese_name, price, category FROM commodity_latest LIMIT 5")
                        rows = cursor.fetchall()
                        print("[INFO] 示例数据:")
                        for row in rows:
                            print(f"       - {row['id']}: {row['chinese_name']} = {row['price']} ({row['category']})")
                        return True
                    else:
                        print("[WARN] commodity_latest 表为空!")
                        return False
                else:
                    print("[FAIL] commodity_latest 表不存在")
                    return False
        else:
            print("[FAIL] MySQL 连接失败")
            return False
    except Exception as e:
        print(f"[FAIL] 异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_intent_classifier():
    """测试 2: 意图分类"""
    print("\n" + "=" * 60)
    print("测试 2: IntentClassifier 分类测试")
    print("=" * 60)

    try:
        from chat_engine.hybrid_query import IntentClassifier, QueryType

        classifier = IntentClassifier(use_llm=False)

        # 测试用例: (问题, 期望结果)
        test_cases = [
            # 商品查询 - 应该返回 COMMODITY
            ("黄金现在多少钱？", QueryType.COMMODITY),
            ("原油价格是多少？", QueryType.COMMODITY),
            ("白银行情怎么样？", QueryType.COMMODITY),
            ("铜价格查询", QueryType.COMMODITY),
            ("贵金属价格", QueryType.COMMODITY),
            ("查看黄金价格", QueryType.COMMODITY),

            # 新闻查询 - 应该返回 NEWS
            ("最近有什么热搜？", QueryType.NEWS),
            ("知乎热门话题", QueryType.NEWS),
            ("今天有什么新闻", QueryType.NEWS),

            # 可能被误分类的边界情况
            ("黄金走势分析", QueryType.COMMODITY),  # 注意: 当前可能被误分类为 NEWS
            ("原油趋势怎么样", QueryType.COMMODITY),  # 注意: 当前可能被误分类为 NEWS

            # 混合查询
            ("铜价和相关新闻", QueryType.MIXED),
        ]

        all_passed = True
        failed_cases = []

        for question, expected in test_cases:
            result = classifier.classify(question)
            passed = result == expected
            status = "[PASS]" if passed else "[FAIL]"

            if not passed:
                all_passed = False
                failed_cases.append((question, expected, result))

            print(f"{status} '{question}' -> {result.value} (期望: {expected.value})")

        if failed_cases:
            print("\n[WARN] 以下测试用例分类错误,需要修复 IntentClassifier:")
            for q, exp, got in failed_cases:
                print(f"       - '{q}': 期望 {exp.value}, 实际 {got.value}")

        return all_passed
    except Exception as e:
        print(f"[FAIL] 异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_text_to_sql_engine():
    """测试 3: TextToSQLEngine"""
    print("\n" + "=" * 60)
    print("测试 3: TextToSQLEngine 测试")
    print("=" * 60)

    try:
        from chat_engine.hybrid_query import TextToSQLEngine

        engine = TextToSQLEngine()

        print(f"[INFO] Engine available: {engine.available}")

        if not engine.available:
            print("[FAIL] TextToSQLEngine 不可用 (MySQL 连接失败)")
            if hasattr(engine, 'last_error'):
                print(f"[INFO] 错误信息: {engine.last_error}")
            return False

        # 测试 SQL 生成
        test_questions = [
            "黄金现在多少钱？",
            "查看原油价格",
            "贵金属类商品有哪些？",
        ]

        all_passed = True

        for question in test_questions:
            print(f"\n[测试] 问题: '{question}'")
            try:
                sql = engine.generate_sql(question)
                print(f"[INFO] 生成 SQL: {sql}")

                # 验证 SQL 语法
                if not sql.upper().strip().startswith('SELECT'):
                    print(f"[WARN] SQL 不是 SELECT 语句")
                    all_passed = False
                else:
                    print(f"[PASS] SQL 生成成功")

                    # 尝试执行
                    try:
                        results = engine.execute_sql(sql)
                        print(f"[PASS] SQL 执行成功, 返回 {len(results)} 条记录")
                        if results:
                            first = results[0]
                            print(f"[INFO] 第一条结果: id={first.get('id')}, chinese_name={first.get('chinese_name')}, price={first.get('price')}")
                    except Exception as e:
                        print(f"[FAIL] SQL 执行失败: {e}")
                        all_passed = False

            except Exception as e:
                print(f"[FAIL] SQL 生成失败: {e}")
                all_passed = False

        return all_passed
    except Exception as e:
        print(f"[FAIL] 异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_full_query():
    """测试 4: 完整查询流程"""
    print("\n" + "=" * 60)
    print("测试 4: 完整查询流程测试")
    print("=" * 60)

    try:
        from chat_engine.hybrid_query import get_hybrid_router

        router = get_hybrid_router()

        print(f"[INFO] Classifier LLM 模式: {router.classifier.use_llm}")
        print(f"[INFO] SQL Engine 可用: {router.sql_engine.available}")
        print(f"[INFO] RAG Engine 可用: {router.rag_engine.available}")

        if not router.sql_engine.available:
            print("[FAIL] SQL Engine 不可用,无法进行完整测试")
            return False

        test_questions = [
            "黄金现在多少钱？",
            "原油价格是多少？",
            "查看贵金属行情",
        ]

        all_passed = True

        for question in test_questions:
            print(f"\n[测试] 问题: '{question}'")
            result = router.route_and_query(question)

            print(f"[INFO] 查询类型: {result.get('query_type')}")
            print(f"[INFO] 成功: {result.get('success')}")
            print(f"[INFO] 耗时: {result.get('total_time_ms', 0):.0f}ms")

            if result.get('sql'):
                print(f"[INFO] SQL: {result.get('sql')}")

            if result.get('success'):
                answer = result.get('answer', '')
                print(f"[PASS] 查询成功")
                print(f"[INFO] 回答预览: {answer[:200]}..." if len(answer) > 200 else f"[INFO] 回答: {answer}")
            else:
                print(f"[FAIL] 查询失败: {result.get('answer')}")
                all_passed = False

        return all_passed
    except Exception as e:
        print(f"[FAIL] 异常: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    print("\n" + "#" * 60)
    print("# Text-to-SQL 混合查询诊断测试")
    print("#" * 60)

    results = {}

    # 测试 1: MySQL 连接
    results["MySQL 连接"] = test_mysql_connection()

    # 测试 2: 意图分类 (即使 MySQL 失败也可以测试)
    results["意图分类"] = test_intent_classifier()

    # 测试 3: SQL 引擎 (依赖 MySQL)
    if results["MySQL 连接"]:
        results["SQL 引擎"] = test_text_to_sql_engine()
    else:
        print("\n[SKIP] SQL 引擎测试 (MySQL 连接失败)")
        results["SQL 引擎"] = False

    # 测试 4: 完整查询 (依赖前面的测试)
    if results["MySQL 连接"]:
        results["完整查询"] = test_full_query()
    else:
        print("\n[SKIP] 完整查询测试 (MySQL 连接失败)")
        results["完整查询"] = False

    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {name}")

    all_passed = all(results.values())

    if all_passed:
        print("\n[成功] 所有测试通过!")
    else:
        print("\n[失败] 存在测试未通过,请检查上述日志")

        # 提供修复建议
        print("\n" + "-" * 60)
        print("修复建议:")
        print("-" * 60)

        if not results["MySQL 连接"]:
            print("1. 检查 MySQL 服务是否运行: brew services list | grep mysql")
            print("2. 检查 config/database.yaml 中的 MySQL 配置")
            print("3. 确保 trendradar 数据库已创建")
            print("4. 运行 database/mysql/schema.sql 创建表结构")

        if not results["意图分类"]:
            print("1. IntentClassifier 分类逻辑需要优化")
            print("2. '走势'、'趋势' 等词不应该导致商品问题被分类为 NEWS")

        if not results["SQL 引擎"]:
            print("1. 检查 LLM API Key 是否有效")
            print("2. 检查生成的 SQL 语法是否正确")

        if not results["完整查询"]:
            print("1. 检查 HybridQueryRouter 路由逻辑")
            print("2. 查看详细日志定位失败原因")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
