"""配置备份存储模块——把设备输出存到本地文件，按设备名和日期组织目录，
结果保存到 backups/{device_name}/{时间戳}.txt"""
from pathlib import Path
from datetime import datetime
import re
from typing import Optional, Union
from config import BACKUP_DIR


def _safe_name(name: str) -> str:
    """将设备名净化为安全的文件系统路径分量。

    只保留字母、数字、连字符、下划线、点号；
    路径分隔符 / \\ 以及 .. 会被替换，防止路径穿越攻击。
    """
    # 替换路径分隔符和控制字符
    safe = re.sub(r'[/\\<>:"|?*\x00-\x1f]', "_", name)
    # 防止 .. 跳目录
    safe = safe.replace("..", "__")
    # 去掉首尾空白/点（Windows 不允许以点结尾的目录名）
    safe = safe.strip(". ")
    return safe or "unknown_device"


def save_result(device_name: str, content: str, suffix: str = "", base_dir: Optional[Union[str, Path]] = None, run_id: Optional[str] = None):

      _now = datetime.now()
      timestamp = run_id if run_id else _now.strftime("%Y-%m-%d_%H-%M-%S_") + f"{_now.microsecond:06d}"

      # 净化设备名，防止路径穿越（如 "../../etc/passwd"）
      safe_device_name = _safe_name(device_name)

      # 自动创建设备目录,其中exist_ok=True 表示目录已存在也不报错
      if base_dir is None:
          base_dir = BACKUP_DIR
      device_dir = Path(base_dir) / safe_device_name
      device_dir.mkdir(parents=True, exist_ok=True)  # 自动创建目录，不存在时不报错
      # 文件名带 suffix（before/after），方便配对查看
      filename = f"{timestamp}_{suffix}.txt" if suffix else f"{timestamp}.txt"
      file_path = device_dir / filename
      file_path.write_text(content, encoding="utf-8")

      return file_path