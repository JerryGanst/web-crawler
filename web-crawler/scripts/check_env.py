import sys
try:
    import pymongo
    print("pymongo installed")
except ImportError:
    print("pymongo NOT installed")

try:
    import yaml
    print("yaml installed")
except ImportError:
    print("yaml NOT installed")

print(f"Python executable: {sys.executable}")
