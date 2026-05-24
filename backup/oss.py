"""阿里云 OSS 上传模块——将本地备份文件同步到对象存储

无 OSS 凭据时自动降级：跳过上传，返回 0 / False，不抛出异常。
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger("NetGuard")


class OSSClient:
    """阿里云 OSS 客户端封装（使用 oss2 SDK）"""

    def __init__(self, access_key: str, secret_key: str, bucket: str, endpoint: str):
        """
        Args:
            access_key: 阿里云 AccessKey ID
            secret_key: 阿里云 AccessKey Secret
            bucket:     OSS Bucket 名称
            endpoint:   OSS 地域节点，如 oss-cn-hangzhou.aliyuncs.com
        """
        import oss2
        auth = oss2.Auth(access_key, secret_key)
        self._bucket = oss2.Bucket(auth, f"https://{endpoint}", bucket)
        self._bucket_name = bucket
        logger.info(f"OSSClient 初始化完成，Bucket: {bucket} / {endpoint}")

    def upload(self, local_path: str, remote_path: str) -> bool:
        """
        上传单个文件到 OSS。

        Args:
            local_path:  本地文件路径
            remote_path: OSS 上的目标路径，如 netguard/backups/SW-01/2026-05-24.txt

        Returns:
            上传成功返回 True，失败返回 False
        """
        try:
            result = self._bucket.put_object_from_file(remote_path, local_path)
            if result.status == 200:
                logger.info(f"OSS 上传成功: {local_path} → oss://{self._bucket_name}/{remote_path}")
                return True
            logger.error(f"OSS 上传失败，HTTP {result.status}: {local_path}")
            return False
        except Exception as e:
            logger.error(f"OSS 上传异常: {e}")
            return False

    def upload_dir(self, local_dir: str, remote_prefix: str) -> int:
        """
        批量上传目录下所有文件。

        Returns:
            成功上传的文件数量
        """
        local = Path(local_dir)
        if not local.is_dir():
            logger.error(f"OSS 批量上传：目录不存在 {local_dir}")
            return 0

        count = 0
        for file in local.rglob("*"):
            if file.is_file():
                relative = file.relative_to(local)
                remote = f"{remote_prefix.rstrip('/')}/{relative.as_posix()}"
                if self.upload(str(file), remote):
                    count += 1
        logger.info(f"OSS 批量上传完成：{count} 个文件 → {remote_prefix}")
        return count


def make_oss_client_from_env() -> "OSSClient | None":
    """
    从环境变量读取凭据并创建 OSSClient。
    凭据不完整时返回 None（降级模式）。
    """
    ak = os.environ.get("OSS_ACCESS_KEY", "").strip()
    sk = os.environ.get("OSS_SECRET_KEY", "").strip()
    bk = os.environ.get("OSS_BUCKET", "").strip()
    ep = os.environ.get("OSS_ENDPOINT", "oss-cn-hangzhou.aliyuncs.com").strip()

    if not all([ak, sk, bk]):
        logger.warning("OSS 凭据未配置（OSS_ACCESS_KEY / OSS_SECRET_KEY / OSS_BUCKET），跳过 OSS 同步")
        return None

    try:
        return OSSClient(ak, sk, bk, ep)
    except Exception as e:
        logger.error(f"OSSClient 初始化失败: {e}")
        return None
