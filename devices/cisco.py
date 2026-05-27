import re
from netmiko import ConnectHandler
from devices.base import BaseDriver
from devices.try_connect import connect_with_retry


class CiscoDriver(BaseDriver):
    """Cisco IOS / IOS-XE 设备驱动"""

    def connect(self):
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
        return ["show processes cpu", "show processes memory", "show ip interface brief"]

    def parse_metrics(self, outputs: dict) -> dict:
        cpu_text = outputs.get("show processes cpu", "")
        mem_text = outputs.get("show processes memory", "")
        intf_text = outputs.get("show ip interface brief", "")

        cpu = _extract_int(cpu_text, r"five seconds:\s*(\d+)%")
        mem = _calc_mem_percent(mem_text)
        up = len(re.findall(r"\bup\s+up\b", intf_text))
        down = len(re.findall(r"administratively down\s+down\b", intf_text))

        return {"cpu_percent": cpu, "memory_percent": mem, "interfaces_up": up, "interfaces_down": down}


def _extract_int(text: str, pattern: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


def _calc_mem_percent(text: str) -> int | None:
    m = re.search(r"Total:\s*(\d+),\s*Used:\s*(\d+)", text)
    if m:
        total, used = int(m.group(1)), int(m.group(2))
        return round(used / total * 100) if total else None
    return None
