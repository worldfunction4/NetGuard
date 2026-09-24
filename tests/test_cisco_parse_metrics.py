"""Cisco 指标解析回归：无逗号内存行、以及多种 down 接口都要计对"""

from devices.cisco import CiscoDriver


def _driver():
    return CiscoDriver({"device_type": "cisco_ios", "host": "192.0.2.12"})


class TestCiscoParseMetrics:
    def test_memory_without_comma(self):
        """修复前正则强制逗号，Total/Used 之间没有逗号时内存百分比是 None"""
        metrics = _driver().parse_metrics({
            "show processes memory": "Processor Pool Total: 123 Used: 456 Free: 0",
        })
        assert metrics["memory_percent"] == round(456 / 123 * 100)

    def test_memory_with_comma_still_works(self):
        metrics = _driver().parse_metrics({
            "show processes memory": "Processor Pool Total: 100, Used: 50 Free: 50",
        })
        assert metrics["memory_percent"] == 50

    def test_interface_down_variants_exclude_up_up(self):
        """修复前只匹配 administratively down down，普通 down down 和 up down 会漏计"""
        brief = "\n".join([
            "Gi0/0  up up",
            "Gi0/1  down down",
            "Gi0/2  administratively down down",
            "Gi0/3  up down",
        ])
        metrics = _driver().parse_metrics({
            "show ip interface brief": brief,
        })
        assert metrics["interfaces_up"] == 1
        assert metrics["interfaces_down"] == 3
