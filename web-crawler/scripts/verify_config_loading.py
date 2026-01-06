import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

print(f"Project root: {project_root}")

try:
    from api.cache import REDIS_HOST, REDIS_PORT, REDIS_DB
    print(f"api.cache config: host={REDIS_HOST}, port={REDIS_PORT}, db={REDIS_DB}")
except Exception as e:
    print(f"Failed to import api.cache: {e}")

try:
    from database.cache import _load_redis_config_from_yaml
    config = _load_redis_config_from_yaml()
    if isinstance(config, dict) and config.get("password") not in (None, ""):
        config = dict(config)
        config["password"] = "******"
    print(f"database.cache loaded config: {config}")
except Exception as e:
    print(f"Failed to check database.cache config loading: {e}")

try:
    from core.price_history import PriceHistory
    # We can't easily check internal vars without instantiation, and instantiation connects to Redis.
    # But we can check if the file is importable and if it has the logic we added.
    print("core.price_history imported successfully")
except Exception as e:
    print(f"Failed to import core.price_history: {e}")
