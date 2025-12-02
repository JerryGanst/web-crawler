# coding=utf-8
"""
推送记录管理模块
管理推送记录，支持每天只推送一次功能
"""

import json
from datetime import datetime
from pathlib import Path

import pytz

from .config import CONFIG
from .utils import get_beijing_time


class PushRecordManager:
    """推送记录管理器"""

    def __init__(self):
        self.record_dir = Path("output") / ".push_records"
        self.ensure_record_dir()
        self.cleanup_old_records()

    def ensure_record_dir(self):
        """确保记录目录存在"""
        self.record_dir.mkdir(parents=True, exist_ok=True)

    def get_today_record_file(self) -> Path:
        """获取今天的记录文件路径"""
        today = get_beijing_time().strftime("%Y%m%d")
        return self.record_dir / f"push_record_{today}.json"

    def cleanup_old_records(self):
        """清理过期的推送记录"""
        retention_days = CONFIG["PUSH_WINDOW"]["RECORD_RETENTION_DAYS"]
        current_time = get_beijing_time()

        for record_file in self.record_dir.glob("push_record_*.json"):
            try:
                date_str = record_file.stem.replace("push_record_", "")
                file_date = datetime.strptime(date_str, "%Y%m%d")
                file_date = pytz.timezone("Asia/Shanghai").localize(file_date)

                if (current_time - file_date).days > retention_days:
                    record_file.unlink()
                    print(f"清理过期推送记录: {record_file.name}")
            except Exception as e:
                print(f"清理记录文件失败 {record_file}: {e}")

    def has_pushed_today(self) -> bool:
        """检查今天是否已经推送过"""
        record_file = self.get_today_record_file()

        if not record_file.exists():
            return False

        try:
            with open(record_file, "r", encoding="utf-8") as f:
                record = json.load(f)
            return record.get("pushed", False)
        except Exception as e:
            print(f"读取推送记录失败: {e}")
            return False

    def record_push(self, report_type: str):
        """记录推送"""
        record_file = self.get_today_record_file()
        now = get_beijing_time()

        record = {
            "pushed": True,
            "push_time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "report_type": report_type,
        }

        try:
            with open(record_file, "w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)
            print(f"推送记录已保存: {report_type} at {now.strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"保存推送记录失败: {e}")

    def is_in_time_range(self, start_time: str, end_time: str) -> bool:
        """检查当前时间是否在指定时间范围内"""
        now = get_beijing_time()
        current_time = now.strftime("%H:%M")

        def normalize_time(time_str: str) -> str:
            """将时间字符串标准化为 HH:MM 格式"""
            try:
                parts = time_str.strip().split(":")
                if len(parts) != 2:
                    raise ValueError(f"时间格式错误: {time_str}")

                hour = int(parts[0])
                minute = int(parts[1])

                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError(f"时间范围错误: {time_str}")

                return f"{hour:02d}:{minute:02d}"
            except Exception as e:
                print(f"时间格式化错误 '{time_str}': {e}")
                return time_str

        normalized_start = normalize_time(start_time)
        normalized_end = normalize_time(end_time)
        normalized_current = normalize_time(current_time)

        result = normalized_start <= normalized_current <= normalized_end

        if not result:
            print(f"时间窗口判断：当前 {normalized_current}，窗口 {normalized_start}-{normalized_end}")

        return result
