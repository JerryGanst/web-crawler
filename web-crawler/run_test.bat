@echo off
python scripts/test_mongodb_connection.py > test_result.txt 2>&1
if %errorlevel% neq 0 (
    echo Python failed with error level %errorlevel% >> test_result.txt
    echo Checking python location: >> test_result.txt
    where python >> test_result.txt
    echo Checking pip location: >> test_result.txt
    where pip >> test_result.txt
)
