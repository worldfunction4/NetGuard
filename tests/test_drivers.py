"""驱动层单元测试——使用 mock 替代真实网络连接"""

import pytest
from unittest.mock import MagicMock, patch


# ── get_driver 工厂函数测试 ──────────────────────────────────────────────────

class TestGetDriver:
    """测试 get_driver 能否根据 device_type 返回正确的驱动实例"""

    def test_huawei_vrp_returns_huawei_driver(self):
        from devices.base import get_driver
        from devices.huawei import HuaweiDriver

        conn = {"device_type": "huawei_vrp", "host": "1.1.1.1"}
        driver = get_driver(conn)
        assert isinstance(driver, HuaweiDriver)

    def test_cisco_ios_returns_cisco_driver(self):
        from devices.base import get_driver
        from devices.cioso import CiscoDriver

        conn = {"device_type": "cisco_ios", "host": "1.1.1.1"}
        driver = get_driver(conn)
        assert isinstance(driver, CiscoDriver)

    def test_cisco_xe_returns_cisco_driver(self):
        from devices.base import get_driver
        from devices.cioso import CiscoDriver

        conn = {"device_type": "cisco_xe", "host": "1.1.1.1"}
        driver = get_driver(conn)
        assert isinstance(driver, CiscoDriver)

    def test_unknown_device_type_raises_value_error(self):
        from devices.base import get_driver

        conn = {"device_type": "juniper_junos", "host": "1.1.1.1"}
        with pytest.raises(ValueError, match="不支持的设备类型"):
            get_driver(conn)

    def test_empty_device_type_raises_value_error(self):
        from devices.base import get_driver

        with pytest.raises(ValueError):
            get_driver({"host": "1.1.1.1"})


# ── CiscoDriver 接口测试 ─────────────────────────────────────────────────────

class TestCiscoDriver:
    """测试 CiscoDriver 的四个接口，用 mock 替代 Netmiko ConnectHandler"""

    def _make_driver(self):
        from devices.cioso import CiscoDriver
        return CiscoDriver({"device_type": "cisco_ios", "host": "1.1.1.1"})

    @patch("devices.cioso.ConnectHandler")
    def test_connect_calls_connect_handler(self, mock_ch):
        driver = self._make_driver()
        driver.connect()
        mock_ch.assert_called_once_with(device_type="cisco_ios", host="1.1.1.1")

    @patch("devices.cioso.ConnectHandler")
    def test_disconnect_calls_underlying_disconnect(self, mock_ch):
        driver = self._make_driver()
        driver.connect()
        driver.disconnect()
        mock_ch.return_value.disconnect.assert_called_once()

    @patch("devices.cioso.ConnectHandler")
    def test_send_command_returns_output(self, mock_ch):
        mock_ch.return_value.send_command.return_value = "Cisco IOS Version 15.2"
        driver = self._make_driver()
        driver.connect()
        result = driver.send_command("show version")
        assert result == "Cisco IOS Version 15.2"
        mock_ch.return_value.send_command.assert_called_once_with("show version")

    @patch("devices.cioso.ConnectHandler")
    def test_send_config_set_returns_output(self, mock_ch):
        mock_ch.return_value.send_config_set.return_value = "config applied"
        driver = self._make_driver()
        driver.connect()
        result = driver.send_config_set(["interface lo0", "description test"])
        assert result == "config applied"
        mock_ch.return_value.send_config_set.assert_called_once_with(
            ["interface lo0", "description test"]
        )

    @patch("devices.cioso.ConnectHandler")
    def test_context_manager_connects_and_disconnects(self, mock_ch):
        """with 语句应自动 connect / disconnect"""
        driver = self._make_driver()
        with driver:
            pass
        mock_ch.assert_called_once()
        mock_ch.return_value.disconnect.assert_called_once()