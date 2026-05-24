import re
from netmiko import ConnectHandler
from devices.base import BaseDriver
from devices.try_connect import connect_with_retry


class HuaweiDriver(BaseDriver):
    """华为 VRP 设备驱动"""

    def connect(self):
        # connect_with_retry 只负责重连逻辑，实际连接动作封装在 lambda 里
        # 设备名从 connection 字典里取，只用于日志
        device_name = self.connection.get("host") or self.connection.get("ip", "")
        self._conn = connect_with_retry(
            lambda: ConnectHandler(**self.connection),
            device_name=device_name,
        )

    def disconnect(self):
        if self._conn:
            self._conn.disconnect()

    def send_command(self, cmd: str) -> str:
        return self._conn.send_command(cmd)

    def send_config_set(self, cmds: list) -> str:
        return self._conn.send_config_set(cmds)

    def get_inspect_commands(self) -> list:
        return ["display cpu-usage", "display memory-usage", "display interface brief"]

    def parse_metrics(self, outputs: dict) -> dict:
        cpu_text = outputs.get("display cpu-usage", "")
        mem_text = outputs.get("display memory-usage", "")
        intf_text = outputs.get("display interface brief", "")

        cpu = _extract_int(cpu_text, r"CPU Usage\s*:\s*(\d+)%")
        mem = _extract_int(mem_text, r"Memory Using Percentage Is:\s*(\d+)%")
        up = len(re.findall(r"\bup\s+up\b", intf_text))
        down = len(re.findall(r"\*?down\s+down\b", intf_text))

        return {"cpu_percent": cpu, "memory_percent": mem, "interfaces_up": up, "interfaces_down": down}


def _extract_int(text: str, pattern: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None
