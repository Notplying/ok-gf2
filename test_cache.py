import json
from pathlib import Path
import re

# 读取缓存
cache_file = Path('configs/schedule_tasks_cache.json')
cache = json.loads(cache_file.read_text(encoding='utf-8'))

print("=== 缓存中的任务信息 ===\n")

for task_name, task_data in cache.items():
    print(f"任务: {task_name}")
    print(f"  trigger_type: {task_data.get('trigger_type', 'N/A')}")
    print(f"  interval_days: {task_data.get('interval_days', 0)}")
    print(f"  interval_hours: {task_data.get('interval_hours', 0)}")
    
    # 从 XML 解析
    xml = task_data.get('xml_config', '')
    days_match = re.search(r'<DaysInterval>(\d+)</DaysInterval>', xml)
    hours_match = re.search(r'<Interval>PT(\d+)H</Interval>', xml)
    
    if days_match:
        print(f"  XML 中的 DaysInterval: {days_match.group(1)}")
    if hours_match:
        print(f"  XML 中的 Hours: {hours_match.group(1)}")
    print()

print("\n=== 测试修复逻辑 ===\n")

# 测试修复逻辑
from src.scheduler.windows_schedule import WindowsScheduleCache

cache_mgr = WindowsScheduleCache()
cache_mgr.load_cache()

for task_name, task_info in cache_mgr.cache.items():
    if task_info.interval_days > 0 or task_info.interval_hours > 0:
        print(f"任务: {task_name}")
        print(f"  trigger_type: {task_info.trigger_type}")
        print(f"  interval_days: {task_info.interval_days}")
        print(f"  interval_hours: {task_info.interval_hours}")
        print()
