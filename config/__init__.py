# config 包入口——项目级路径常量和环境变量加载
import os
from pathlib import Path

# 项目根目录（config/ 的上层）
ROOT = Path(__file__).parent.parent
BACKUP_DIR = ROOT / "backups_config"
REPORT_DIR = ROOT / "reports"
LOG_DIR = ROOT / "logs"

# 巡检告警阈值（百分比）
THRESHOLDS: dict = {
    "cpu_percent": 80,
    "memory_percent": 85,
}

__all__ = ["ROOT", "BACKUP_DIR", "REPORT_DIR", "LOG_DIR", "THRESHOLDS", "load_dotenv"]


def load_dotenv(path: str | Path | None = None) -> None:
    """读取 .env 文件，将键值对注入 os.environ（已存在的键不覆盖）。

    优先使用 python-dotenv 库（功能完整）；未安装时回退到简易内置解析。
    """
    if path is None:
        path = ROOT / ".env"
    env_file = Path(path)
    if not env_file.is_file():
        return

    try:
        from dotenv import load_dotenv as _load
        _load(dotenv_path=str(env_file), override=False)
    except ImportError:
        # 简易回退解析：跳过空行和注释行，按第一个 = 分割
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
