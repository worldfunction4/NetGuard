"""Mock 驱动——无真实设备时用于演示和测试

使用方式：
  1. 环境变量：NETGUARD_MOCK=1 python main.py run
  2. devices.yaml 中 device_type 设为 mock_huawei 或 mock_cisco
"""
import random
import re
from devices.base import BaseDriver


def _rand(base: int, spread: int = 8) -> int:
    """生成以 base 为中心、±spread 范围内的随机整数，模拟真实波动"""
    return max(1, min(99, base + random.randint(-spread, spread)))


# ── 华为 VRP 预置响应 ────────────────────────────────────────────────────────

def _huawei_responses() -> dict:
    cpu = _rand(23)
    mem = _rand(42)
    return {
        "dis vlan": (
            "VID  Status    Property      MAC-LRN Statistics Description\n"
            "--------------------------------------------------------------------------------\n"
            "1    enable    default       enable  disable    VLAN 0001\n"
            "10   enable    default       enable  disable    VLAN 0010\n"
            "20   enable    default       enable  disable    VLAN 0020\n"
        ),
        "display vlan": (
            "VID  Status    Property      MAC-LRN Statistics Description\n"
            "--------------------------------------------------------------------------------\n"
            "1    enable    default       enable  disable    VLAN 0001\n"
            "10   enable    default       enable  disable    VLAN 0010\n"
            "20   enable    default       enable  disable    VLAN 0020\n"
        ),
        "display cpu-usage": (
            "CPU Usage Stat. Cycle: 60 (Second)\n"
            f"CPU Usage          : {cpu}%\n"
            f"CPU Usage Min      : {max(1, cpu - 15)}%\n"
            f"CPU Usage Max      : {min(99, cpu + 20)}%\n"
            f"CPU Usage Avg      : {max(1, cpu - 5)}%\n"
        ),
        "display memory-usage": (
            f"Memory Using Percentage Is: {mem}%\n"
        ),
        "display interface brief": (
            "PHY: Physical\n"
            "*down: administratively down\n\n"
            "Interface            PHY   Protocol InUti OutUti   inErrors  outErrors\n"
            "GigabitEthernet0/0/0 up    up          0%     0%          0          0\n"
            "GigabitEthernet0/0/1 up    up          0%     0%          0          0\n"
            "GigabitEthernet0/0/2 up    up          0%     0%          0          0\n"
            "GigabitEthernet0/0/3 *down down        0%     0%          0          0\n"
            "NULL0                up    up(s)       0%     0%          0          0\n"
        ),
        "display version": (
            "Huawei Versatile Routing Platform Software\n"
            "VRP (R) software, Version 5.170 (S5700 V200R019C10SPC500)\n"
            "Copyright (C) 2000-2022 HUAWEI TECH CO., LTD\n"
            "HUAWEI S5700-28C-EI-24S Routing Switch uptime is 30 days, 4 hours, 12 minutes\n"
        ),
    }


# ── Cisco IOS 预置响应 ───────────────────────────────────────────────────────

def _cisco_responses() -> dict:
    cpu = _rand(15)
    mem_total = 1073741824
    mem_used = int(mem_total * (_rand(40) / 100))
    return {
        "show vlan brief": (
            "VLAN Name                             Status    Ports\n"
            "---- -------------------------------- --------- -------------------------------\n"
            "1    default                          active    Gi0/0, Gi0/1\n"
            "10   VLAN0010                         active\n"
            "20   VLAN0020                         active\n"
        ),
        "show processes cpu": (
            f"CPU utilization for five seconds: {cpu}%/3%; "
            f"one minute: {max(1, cpu - 3)}%; "
            f"five minutes: {max(1, cpu - 5)}%\n"
        ),
        "show processes memory": (
            f"Total: {mem_total}, Used: {mem_used}, Free: {mem_total - mem_used}\n"
        ),
        "show ip interface brief": (
            "Interface              IP-Address      OK? Method Status                Protocol\n"
            "GigabitEthernet0/0     192.168.1.1     YES NVRAM  up                    up\n"
            "GigabitEthernet0/1     unassigned      YES unset  up                    up\n"
            "GigabitEthernet0/2     unassigned      YES unset  up                    up\n"
            "GigabitEthernet0/3     unassigned      YES unset  administratively down down\n"
        ),
        "show version": (
            "Cisco IOS Software, Version 15.2(4)M7\n"
            "ROM: System Bootstrap, Version 15.1(4)M4\n"
            "cisco 2901 (revision 1.0) with 483328K/40960K bytes of memory.\n"
            "Processor board ID FTX152400KS\n"
            "1 Gigabit Ethernet interface\n"
            "System image file is \"flash0:c2900-universalk9-mz.SPA.152-4.M7.bin\"\n"
        ),
    }


# ── MockDriver ───────────────────────────────────────────────────────────────

class MockDriver(BaseDriver):
    """无需真实网络连接的演示驱动，返回预置的设备输出

    支持重连失败模拟：通过 connection 字典传入 _mock_fail_times（int），
    可以让 connect() 先连续失败指定次数，用于测试重连机制。
    """

    def __init__(self, connection: dict):
        super().__init__(connection)
        dt = connection.get("device_type", "")
        if "cisco" in dt:
            self._vendor = "cisco"
            self._responses = _cisco_responses()
        else:
            self._vendor = "huawei"
            self._responses = _huawei_responses()

        # 模拟连接失败：前 N 次 connect() 抛出 NetmikoTimeoutException
        self._fail_times_left: int = int(connection.get("_mock_fail_times", 0))

    def connect(self):
        if self._fail_times_left > 0:
            self._fail_times_left -= 1
            from netmiko import NetmikoTimeoutException
            raise NetmikoTimeoutException(
                f"MockDriver 模拟连接超时（还会失败 {self._fail_times_left} 次）"
            )

    def disconnect(self):
        pass

    def send_command(self, cmd: str) -> str:
        cmd_s = cmd.strip()
        # 精确匹配
        if cmd_s in self._responses:
            return self._responses[cmd_s]
        # 前缀匹配（处理带参数的命令，如 "dis vlan 10"）
        for key, val in self._responses.items():
            if cmd_s.startswith(key):
                return val
        return f"% Unknown command: {cmd_s}\n"

    def send_config_set(self, cmds: list) -> str:
        name = self.connection.get("ip", "MockDevice")
        lines = [f"[{name}]"]
        for cmd in cmds:
            lines.append(f"[{name}]{cmd}")
        lines.append(f"[{name}]return")
        return "\n".join(lines)

    # ── 巡检接口 ────────────────────────────────────────────────────────────

    def get_inspect_commands(self) -> list:
        if self._vendor == "cisco":
            return ["show processes cpu", "show processes memory", "show ip interface brief"]
        return ["display cpu-usage", "display memory-usage", "display interface brief"]

    def parse_metrics(self, outputs: dict) -> dict:
        if self._vendor == "cisco":
            return _parse_cisco_metrics(outputs)
        return _parse_huawei_metrics(outputs)


# ── 指标解析函数 ─────────────────────────────────────────────────────────────

def _parse_huawei_metrics(outputs: dict) -> dict:
    cpu = _extract_int(outputs.get("display cpu-usage", ""), r"CPU Usage\s*:\s*(\d+)%")
    mem = _extract_int(outputs.get("display memory-usage", ""), r"Memory Using Percentage Is:\s*(\d+)%")
    up, down = _count_huawei_interfaces(outputs.get("display interface brief", ""))
    return {"cpu_percent": cpu, "memory_percent": mem, "interfaces_up": up, "interfaces_down": down}


def _parse_cisco_metrics(outputs: dict) -> dict:
    cpu = _extract_int(outputs.get("show processes cpu", ""), r"five seconds:\s*(\d+)%")
    mem_text = outputs.get("show processes memory", "")
    mem = _calc_cisco_mem_percent(mem_text)
    up, down = _count_cisco_interfaces(outputs.get("show ip interface brief", ""))
    return {"cpu_percent": cpu, "memory_percent": mem, "interfaces_up": up, "interfaces_down": down}


def _extract_int(text: str, pattern: str) -> int | None:
    m = re.search(pattern, text)
    return int(m.group(1)) if m else None


def _calc_cisco_mem_percent(text: str) -> int | None:
    m = re.search(r"Total:\s*(\d+),\s*Used:\s*(\d+)", text)
    if m:
        total, used = int(m.group(1)), int(m.group(2))
        return round(used / total * 100) if total else None
    return None


def _count_huawei_interfaces(text: str) -> tuple[int, int]:
    up = len(re.findall(r"\bup\s+up\b", text))
    down = len(re.findall(r"\*?down\s+down\b", text))
    return up, down


def _count_cisco_interfaces(text: str) -> tuple[int, int]:
    up = len(re.findall(r"\bup\s+up\b", text))
    down = len(re.findall(r"administratively down\s+down\b", text))
    return up, down
