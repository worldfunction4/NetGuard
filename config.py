# 取消硬编码传入对应文件
from pathlib import Path

ROOT = Path(__file__).parent
BACKUP_DIR = ROOT / "backups_config"
REPORT_DIR = ROOT / "reports"
LOG_DIR = ROOT / "logs"

# 巡检告警阈值（百分比）
THRESHOLDS: dict = {
    "cpu_percent": 80,
    "memory_percent": 85,
}
