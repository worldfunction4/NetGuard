"""华为驱动 parse_metrics 回归测试——接口回显必须能走 re.findall，不能 NameError"""

from devices.huawei import HuaweiDriver


class TestHuaweiParseMetrics:
    def test_interface_brief_findall_counts_up_and_down(self):
        """补上 import re 之后，接口 up/down 计数不应再因 NameError 中断"""
        driver = HuaweiDriver({"device_type": "huawei_vrp", "host": "1.1.1.1"})
        outputs = {
            "display cpu-usage": "CPU Usage          : 23%\n",
            "display memory-usage": "Memory Using Percentage Is: 42%\n",
            "display interface brief": (
                "Interface            PHY   Protocol\n"
                "GigabitEthernet0/0/0 up    up\n"
                "GigabitEthernet0/0/1 up    up\n"
                "GigabitEthernet0/0/3 *down down\n"
                "GigabitEthernet0/0/4 down  down\n"
            ),
        }

        metrics = driver.parse_metrics(outputs)

        assert metrics["cpu_percent"] == 23
        assert metrics["memory_percent"] == 42
        assert metrics["interfaces_up"] == 2
        assert metrics["interfaces_down"] == 2
