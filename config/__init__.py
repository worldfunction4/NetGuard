# config 包入口——从根目录 config.py 重新导出所有公共符号，
# 保持 "from config import BACKUP_DIR / REPORT_DIR / THRESHOLDS" 等用法不变。
import os
import sys
from pathlib import Path

# 把项目根目录加入搜索路径，以便能 import 根目录的 config.py
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("_root_config", _root / "config.py")
_mod  = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ROOT       = _mod.ROOT
BACKUP_DIR = _mod.BACKUP_DIR
REPORT_DIR = _mod.REPORT_DIR
LOG_DIR    = _mod.LOG_DIR
THRESHOLDS = _mod.THRESHOLDS

__all__ = ["ROOT", "BACKUP_DIR", "REPORT_DIR", "LOG_DIR", "THRESHOLDS", "load_dotenv"]


def load_dotenv(path: str | Path | None = None) -> None:
    """读取 .env 文件，将键值对注入 os.environ（已存在的键不覆盖）。

    生产环境中同名环境变量优先于 .env 文件。
    在 main() 启动时自动调用，用户只需编辑 .env 填入凭据即可。
    """
    if path is None:
        path = _root / ".env"
    env_file = Path(path)
    if not env_file.is_file():
        return
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
