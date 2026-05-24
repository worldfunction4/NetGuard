# config 包入口——从根目录 config.py 重新导出所有公共符号，
# 保持 "from config import BACKUP_DIR / REPORT_DIR / THRESHOLDS" 等用法不变。
import sys
from pathlib import Path

# 把项目根目录加入搜索路径（如果还没有的话），
# 以便能 import 到根目录的 config.py（名为 _root_config）
_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# 直接从根目录 config.py 导入并重新暴露
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location("_root_config", _root / "config.py")
_mod  = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ROOT       = _mod.ROOT
BACKUP_DIR = _mod.BACKUP_DIR
REPORT_DIR = _mod.REPORT_DIR
LOG_DIR    = _mod.LOG_DIR
THRESHOLDS = _mod.THRESHOLDS

__all__ = ["ROOT", "BACKUP_DIR", "REPORT_DIR", "LOG_DIR", "THRESHOLDS"]
