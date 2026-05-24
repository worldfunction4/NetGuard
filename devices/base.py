"""设备驱动抽象基类——所有厂商驱动都继承这个"""
import os


class BaseDriver:
    """驱动基类，定义统一的设备操作接口"""

    def __init__(self, connection: dict):
        self.connection = connection
        self._conn = None  # 子类用来存实际的连接对象

    # 上下文管理器：让 collector 可以用 with driver as conn
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def connect(self):
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError

    def send_command(self, cmd: str) -> str:
        raise NotImplementedError

    def send_config_set(self, cmds: list) -> str:
        raise NotImplementedError

    def get_inspect_commands(self) -> list:
        """返回该厂商的巡检命令列表，子类按需覆盖"""
        raise NotImplementedError

    def parse_metrics(self, outputs: dict) -> dict:  # noqa: ARG002
        """将命令输出解析为标准化指标字典，子类按需覆盖"""
        raise NotImplementedError


def is_mock_mode() -> bool:
    """判断是否处于 mock 模式（NETGUARD_MOCK=1 或 device_type 以 mock_ 开头）"""
    return os.environ.get("NETGUARD_MOCK", "").strip() in ("1", "true", "yes")


def get_driver(connection: dict) -> "BaseDriver":
    """工厂函数：根据 device_type（或 NETGUARD_MOCK 环境变量）返回对应驱动实例"""
    # 延迟导入：避免循环依赖
    from devices.huawei import HuaweiDriver
    from devices.cioso import CiscoDriver
    from devices.mock import MockDriver

    device_type = connection.get("device_type", "")

    # NETGUARD_MOCK=1 时全局切换为 mock 模式，无需修改 devices.yaml
    if is_mock_mode():
        return MockDriver(connection)

    if device_type.startswith("mock_") or device_type == "mock":
        return MockDriver(connection)

    if "huawei" in device_type:
        return HuaweiDriver(connection)

    if "cisco" in device_type:
        return CiscoDriver(connection)

    raise ValueError(
        f"不支持的设备类型: {device_type!r}。"
        f"支持: huawei_telnet, huawei_ssh, cisco_ios, cisco_xe, mock_huawei, mock_cisco。"
        f"演示模式请设置环境变量 NETGUARD_MOCK=1。"
    )
