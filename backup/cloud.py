"""云端集成入口——OSS 备份同步 + 钉钉告警"""
import logging
import os

from backup.oss import make_oss_client_from_env
from backup.notify import send_alert_if_configured

logger = logging.getLogger("NetGuard")


def sync_backup_to_cloud(local_path: str) -> bool:
    """
    将本地备份文件或目录上传到阿里云 OSS。
    OSS 凭据从环境变量读取（见 .env）。

    无 OSS 配置时静默跳过，返回 False。

    Args:
        local_path: 要上传的本地文件或目录路径

    Returns:
        同步成功返回 True，未配置或失败返回 False
    """
    from pathlib import Path

    client = make_oss_client_from_env()
    if client is None:
        return False

    local = Path(local_path)
    remote_prefix = "netguard/backups"

    if local.is_dir():
        count = client.upload_dir(str(local), remote_prefix)
        return count > 0
    elif local.is_file():
        remote = f"{remote_prefix}/{local.name}"
        return client.upload(str(local), remote)
    else:
        logger.error(f"sync_backup_to_cloud: 路径不存在 {local_path}")
        return False


def notify_alert(device_name: str, metric: str, value: int, threshold: int):
    """
    触发钉钉告警推送。
    Webhook 地址从环境变量 DINGTALK_WEBHOOK 读取。
    无配置时仅记录日志，不影响主流程。
    """
    send_alert_if_configured(device_name, metric, value, threshold)
