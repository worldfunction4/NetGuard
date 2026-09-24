"""设备接口：只校验请求，再调用 config.manager 里已有的函数。"""
from fastapi import APIRouter

from api.schemas import DeviceCreate, DevicePublic, to_public_device
from config.manager import add_device, list_devices
from logger import setup_logger

router = APIRouter(tags=["devices"])
logger = setup_logger()


@router.get("/devices", response_model=list[DevicePublic])
def get_devices() -> list[dict]:
    """返回设备摘要。list_devices 本身不含密码，这里再按公开字段收一遍。"""
    return [to_public_device(row) for row in list_devices()]


@router.post("/devices", response_model=DevicePublic)
def create_device(body: DeviceCreate) -> dict:
    """新增设备。成功时只回公开字段，不回传密码。"""
    entry = body.to_entry()
    try:
        add_device(entry)
    finally:
        # 调用结束后清掉内存里的密码，避免异常日志带出原文。
        connection = entry.get("connection")
        if isinstance(connection, dict):
            connection.pop("password", None)
    logger.info("设备 '%s' 添加成功", body.name)
    return to_public_device(entry)
