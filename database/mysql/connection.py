"""
MySQL 数据库连接管理
"""
import os
from typing import Optional
from contextlib import contextmanager
from pathlib import Path

import yaml
import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB


def _load_mysql_config() -> dict:
    """
    载入 MySQL 配置，优先级：
    1) config/database.yaml 的 mysql 节点
    2) 环境变量 MYSQL_HOST/PORT/USER/PASSWORD/DATABASE
    3) 默认值
    """
    # 默认值
    cfg = {
        'host': 'localhost',
        'port': 3306,
        'user': 'root',
        'password': 'trendradar123',
        'database': 'trendradar',
        'charset': 'utf8mb4',
        'cursorclass': DictCursor,
        'autocommit': False,
    }

    # config/database.yaml
    try:
        config_path = Path(__file__).resolve().parent.parent.parent / "config" / "database.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            mysql_cfg = data.get("mysql", {}) or {}
            cfg.update({
                'host': mysql_cfg.get('host', cfg['host']),
                'port': mysql_cfg.get('port', cfg['port']),
                'user': mysql_cfg.get('user', cfg['user']),
                'password': mysql_cfg.get('password', cfg['password']),
                'database': mysql_cfg.get('database', cfg['database']),
            })
    except Exception as e:
        print(f"⚠️ 加载 database.yaml 失败: {e}")

    # 环境变量覆盖
    env_host = os.getenv('MYSQL_HOST')
    env_port = os.getenv('MYSQL_PORT')
    env_user = os.getenv('MYSQL_USER')
    env_pwd = os.getenv('MYSQL_PASSWORD')
    env_db = os.getenv('MYSQL_DATABASE')

    if env_host:
        cfg['host'] = env_host
    if env_port:
        cfg['port'] = int(env_port)
    if env_user:
        cfg['user'] = env_user
    if env_pwd:
        cfg['password'] = env_pwd
    if env_db:
        cfg['database'] = env_db

    return cfg


# 数据库配置
MYSQL_CONFIG = _load_mysql_config()

# 连接池配置
POOL_CONFIG = {
    'creator': pymysql,
    'maxconnections': 10,
    'mincached': 2,
    'maxcached': 5,
    'blocking': True,
    'maxusage': None,
    'setsession': ['SET AUTOCOMMIT = 0'],
}

# 全局连接池
_pool: Optional[PooledDB] = None


def get_pool() -> PooledDB:
    """获取数据库连接池"""
    global _pool
    if _pool is None:
        _pool = PooledDB(**{**POOL_CONFIG, **MYSQL_CONFIG})
    return _pool


def get_connection():
    """获取数据库连接"""
    return get_pool().connection()


@contextmanager
def get_cursor(commit: bool = False):
    """
    获取游标的上下文管理器
    
    Args:
        commit: 是否在退出时自动提交
    
    Usage:
        with get_cursor(commit=True) as cursor:
            cursor.execute("SELECT * FROM commodity_latest")
            results = cursor.fetchall()
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield cursor
        if commit:
            conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


@contextmanager
def transaction():
    """
    事务上下文管理器
    
    Usage:
        with transaction() as (conn, cursor):
            cursor.execute("UPDATE ...")
            cursor.execute("INSERT ...")
            # 自动提交或回滚
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        yield conn, cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def init_database():
    """初始化数据库 (执行 schema.sql)"""
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    
    if not os.path.exists(schema_path):
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()
    
    # 分割 SQL 语句
    statements = [s.strip() for s in schema_sql.split(';') if s.strip()]
    
    conn = pymysql.connect(
        host=MYSQL_CONFIG['host'],
        port=MYSQL_CONFIG['port'],
        user=MYSQL_CONFIG['user'],
        password=MYSQL_CONFIG['password'],
        charset='utf8mb4',
        autocommit=True
    )
    
    try:
        cursor = conn.cursor()
        for stmt in statements:
            if stmt and not stmt.startswith('--'):
                try:
                    cursor.execute(stmt)
                except Exception as e:
                    print(f"Warning: {e}")
        print("✅ MySQL 数据库初始化完成")
    finally:
        conn.close()


def test_connection() -> bool:
    """测试数据库连接"""
    try:
        with get_cursor() as cursor:
            cursor.execute("SELECT 1")
            return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False


if __name__ == '__main__':
    # 测试连接
    if test_connection():
        print("✅ MySQL 连接成功")
    else:
        print("尝试初始化数据库...")
        init_database()
