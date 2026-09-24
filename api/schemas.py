"""请求和响应模型。响应里只放公开字段，不放密码。"""
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


# 设备列表和新增成功时对外暴露的字段，与 list_devices 的摘要一致。
PUBLIC_DEVICE_KEYS = ("name", "ip", "port", "device_type", "location", "role")


class DeviceCreate(BaseModel):
    """新增设备的请求体。password 只用于调用 add_device，不会出现在响应里。"""

    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)

    name: str = Field(min_length=1)
    ip: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    device_type: str = Field(min_length=1)
    username: str = Field(min_length=1)
    password: SecretStr = Field(min_length=1)
    location: str | None = None
    role: str | None = None

    @field_validator("name", "ip", "device_type", "username", mode="before")
    @classmethod
    def require_text(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            raise ValueError("不能为空")
        return text

    @field_validator("password", mode="before")
    @classmethod
    def require_password(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        text = value.strip()
        if not text:
            raise ValueError("不能为空")
        return text

    @field_validator("location", "role", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        text = value.strip()
        return text or None

    def to_entry(self) -> dict:
        """组装 add_device 需要的字典。connection 里固定带 timeout=30。"""
        entry: dict = {
            "name": self.name,
            "connection": {
                "device_type": self.device_type,
                "ip": self.ip,
                "port": self.port,
                "username": self.username,
                "password": self.password.get_secret_value(),
                "timeout": 30,
            },
        }
        if self.location:
            entry["location"] = self.location
        if self.role:
            entry["role"] = self.role
        return entry


class DevicePublic(BaseModel):
    """设备公开信息。没有 password，也没有 username。"""

    model_config = ConfigDict(extra="ignore")

    name: str = ""
    ip: str = ""
    port: int | str = ""
    device_type: str = ""
    location: str = ""
    role: str = ""


class BackupDeviceResult(BaseModel):
    name: str = ""
    ok: bool = False
    message: str = ""


class BackupResponse(BaseModel):
    failed: int
    results: list[BackupDeviceResult]
    saved: list[str]


class InspectResponse(BaseModel):
    metrics: list[Any]
    html_path: str
    excel_path: str


class DiffItem(BaseModel):
    name: str = ""
    ok: bool = False
    report: str | None = None


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def to_public_device(data: dict) -> dict:
    """从设备字典里取出公开字段。connection 里的密码不会被复制出来。"""
    flat = dict(data)
    connection = flat.get("connection")
    if isinstance(connection, dict):
        for key in ("ip", "port", "device_type"):
            flat.setdefault(key, connection.get(key, ""))
    public: dict = {}
    for key in PUBLIC_DEVICE_KEYS:
        value = flat.get(key, "")
        if value is None:
            value = ""
        public[key] = value
    return public


def strip_password(value: Any) -> Any:
    """递归删掉 password 字段，避免巡检等结果意外带出密码。"""
    if isinstance(value, dict):
        return {
            key: strip_password(item)
            for key, item in value.items()
            if key != "password"
        }
    if isinstance(value, list):
        return [strip_password(item) for item in value]
    return value
