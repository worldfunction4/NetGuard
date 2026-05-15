"""
阿里云 OSS 上传模块
将巡检报告上传到阿里云对象存储，异常不中断主流程
"""
import os
from pathlib import Path
import oss2

from src.logger import logger
from dotenv import load_dotenv

# 加载环境变量
env = Path(".env")
if env.exists():
    load_dotenv()
else:
    logger.warning(".env 文件不存在，OSS 上传功能将无法使用")

def _get_bucket():
    # 使用os.getenv获取环境变量，获取 OSS 凭证和配置信息
    access_key = os.getenv("OSS_ACCESS_KEY_ID")
    secret_key = os.getenv("OSS_ACCESS_KEY_SECRET")
    endpoint = os.getenv("OSS_ENDPOINT")
    bucket_name = os.getenv("OSS_BUCKET_NAME")

    if not all([access_key, secret_key, endpoint, bucket_name]):
        logger.warning("OSS 凭证不完整，跳过云端上传")
        return None

    auth = oss2.Auth(access_key, secret_key)
    return oss2.Bucket(auth, endpoint, bucket_name)


def upload_report(filepath):
    bucket = _get_bucket()
    if bucket is None:
        return None

    filepath = Path(filepath)
    if not filepath.exists():
        logger.warning(f"文件不存在，跳过上传: {filepath}")
        return None

    object_name = f"reports/{filepath.name}"
    try:
        bucket.put_object_from_file(object_name, str(filepath))
        oss_url = f"https://{os.getenv('OSS_BUCKET_NAME')}.{os.getenv('OSS_ENDPOINT')}/{object_name}"
        logger.info(f"成功上传报告到 OSS: {oss_url}")
        return oss_url
    except oss2.exceptions.OssError as e:
        logger.warning(f"OSS 上传失败了哦: {e}")
        return None
    except Exception as e:
        logger.warning(f"上传过程中遇到异常了哦: {e}")
        return None
