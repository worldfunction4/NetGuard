"""
配置备份文件存储模块
负责将设备配置写入本地文件，按日期和设备名组织
"""
import time
from pathlib import Path

from src.logger import logger


def save_config(device_name: str, content: str, backup_dir: str = "backup_configs") -> Path:
    """
    将设备配置保存到本地文件

    Args:
        device_name: 设备名称
        content: 配置文本内容
        backup_dir: 备份存储目录（相对于项目根目录）

    Returns:
        保存的文件路径
    """
    # 确保备份目录存在
    backup_path = Path(backup_dir)
    backup_path.mkdir(parents=True, exist_ok=True)

    # 生成带时间戳的文件名
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
    filename = f"{device_name}_{timestamp}.cfg"
    filepath = backup_path / filename

    # 写入文件
    filepath.write_text(content, encoding="utf-8")

    logger.info(f"[{device_name}] 配置已保存 → {filepath}")
    return filepath
