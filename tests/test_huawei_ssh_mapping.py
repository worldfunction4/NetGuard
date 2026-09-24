"""华为 SSH 类型名映射回归：传给 Netmiko 的是 huawei，调用方字典保持原样"""

from unittest.mock import patch

from devices.huawei import HuaweiDriver


class TestHuaweiSshMapping:
    @patch("devices.huawei.ConnectHandler")
    def test_huawei_ssh_maps_to_huawei_without_mutating_caller_dict(self, mock_ch):
        """修复前会把 huawei_ssh 原样交给 ConnectHandler，或直接改掉原字典"""
        original = {
            "device_type": "huawei_ssh",
            "host": "192.0.2.10",
            "ip": "192.0.2.10",
            "username": "admin",
            "password": "secret-not-for-log",
        }
        snapshot = dict(original)
        driver = HuaweiDriver(original)

        driver.connect()

        assert original == snapshot
        assert original["device_type"] == "huawei_ssh"
        kwargs = mock_ch.call_args.kwargs
        assert kwargs["device_type"] == "huawei"
        assert kwargs["host"] == "192.0.2.10"
        assert kwargs["password"] == "secret-not-for-log"
        mock_ch.assert_called_once()

    @patch("devices.huawei.ConnectHandler")
    def test_huawei_telnet_is_not_remapped(self, mock_ch):
        original = {"device_type": "huawei_telnet", "host": "192.0.2.11"}
        driver = HuaweiDriver(original)

        driver.connect()

        assert original["device_type"] == "huawei_telnet"
        assert mock_ch.call_args.kwargs["device_type"] == "huawei_telnet"
