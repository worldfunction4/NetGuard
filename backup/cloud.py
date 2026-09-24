"""云端集成入口——OSS 备份同步 + 钉钉告警"""
import logging
import os

from backup.oss import make_oss_client_from_env
from backup.notify import send_alert_if_configured

logger = logging.getLogger("NetGuard")


def sync_backup_to_cloud(local_path: str | None = None, files: list | None = None) -> bool:
    """
    将本地备份文件或目录上传到阿里云 OSS。
    OSS 凭据从环境变量读取（见 .env）。

    files 不为 None 时只上传这些文件，不再扫描整个备份目录。
    无 OSS 配置时静默跳过，返回 False，不抛异常。

    Args:
        local_path: 要上传的本地文件或目录路径（未传 files 时使用）
        files:      本次新保存的文件路径列表

    Returns:
        同步成功返回 True，未配置或失败返回 False
    """
    from pathlib import Path

    client = make_oss_client_from_env()
    if client is None:
        return False

    remote_prefix = "netguard/backups"

    # 只上传调用方给出的文件，避免 rglob 重传历史备份
    if files is not None:
        uploaded = 0
        for raw in files:
            local = Path(raw)
            if not local.is_file():
                logger.error(f"sync_backup_to_cloud: 路径不存在 {raw}")
                continue
            remote = f"{remote_prefix}/{local.parent.name}/{local.name}"
            if client.upload(str(local), remote):
                uploaded += 1
        return uploaded > 0

    if not local_path:
        logger.error("sync_backup_to_cloud: 未指定上传路径")
        return False

    local = Path(local_path)

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
