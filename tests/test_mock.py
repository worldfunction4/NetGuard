"""Mock 驱动单元测试——无需真实设备即可运行"""
import pytest
from unittest.mock import patch
import os


# ── MockDriver 基础行为 ───────────────────────────────────────────────────────

class TestMockDriver:

    def _make(self, device_type="mock_huawei"):
        from devices.mock import MockDriver
        return MockDriver({"device_type": device_type, "ip": "192.168.1.1", "port": 23})

    def test_connect_disconnect_no_exception(self):
        d = self._make()
        d.connect()
        d.disconnect()

    def test_context_manager(self):
        d = self._make()
        with d:
            pass  # 不抛即为通过

    def test_send_command_known_cmd(self):
        d = self._make("mock_huawei")
        out = d.send_command("display cpu-usage")
        assert "CPU Usage" in out

    def test_send_command_unknown_cmd(self):
        d = self._make()
        out = d.send_command("non_existent_cmd_xyz")
        assert "Unknown command" in out

    def test_send_config_set_returns_echo(self):
        d = self._make()
        out = d.send_config_set(["vlan batch 10 20"])
        assert "vlan batch 10 20" in out

    def test_cisco_mock_variant(self):
        d = self._make("mock_cisco")
        out = d.send_command("show processes cpu")
        assert "CPU utilization" in out

    def test_huawei_inspect_commands(self):
        d = self._make("mock_huawei")
        cmds = d.get_inspect_commands()
        assert "display cpu-usage" in cmds
        assert "display memory-usage" in cmds

    def test_cisco_inspect_commands(self):
        d = self._make("mock_cisco")
        cmds = d.get_inspect_commands()
        assert "show processes cpu" in cmds

    def test_parse_metrics_returns_dict(self):
        d = self._make("mock_huawei")
        cmds = d.get_inspect_commands()
        outputs = {cmd: d.send_command(cmd) for cmd in cmds}
        metrics = d.parse_metrics(outputs)
        assert "cpu_percent" in metrics
        assert "memory_percent" in metrics
        assert isinstance(metrics.get("cpu_percent"), int)

    def test_metrics_values_in_range(self):
        d = self._make("mock_huawei")
        cmds = d.get_inspect_commands()
        outputs = {cmd: d.send_command(cmd) for cmd in cmds}
        metrics = d.parse_metrics(outputs)
        cpu = metrics.get("cpu_percent")
        mem = metrics.get("memory_percent")
        assert 1 <= cpu <= 99
        assert 1 <= mem <= 99


# ── get_driver 的 mock 分支 ───────────────────────────────────────────────────

class TestGetDriverMockBranch:

    def test_mock_prefix_returns_mock_driver(self):
        from devices.base import get_driver
        from devices.mock import MockDriver
        conn = {"device_type": "mock_huawei", "ip": "1.1.1.1", "port": 23}
        driver = get_driver(conn)
        assert isinstance(driver, MockDriver)

    def test_env_var_mock_overrides_real_type(self):
        from devices.base import get_driver
        from devices.mock import MockDriver
        conn = {"device_type": "huawei_telnet", "ip": "1.1.1.1", "port": 23}
        with patch.dict(os.environ, {"NETGUARD_MOCK": "1"}):
            driver = get_driver(conn)
        assert isinstance(driver, MockDriver)

    def test_env_var_not_set_returns_real_driver(self):
        """NETGUARD_MOCK 未设置时应返回真实驱动（不实际连接）"""
        from devices.base import get_driver
        from devices.huawei import HuaweiDriver
        conn = {"device_type": "huawei_telnet", "ip": "1.1.1.1", "port": 23}
        env = {k: v for k, v in os.environ.items() if k != "NETGUARD_MOCK"}
        with patch.dict(os.environ, env, clear=True):
            driver = get_driver(conn)
        assert isinstance(driver, HuaweiDriver)


# ── inspect_device 端到端（全 mock）─────────────────────────────────────────

class TestInspectDeviceMock:

    def _make_device(self, device_type="mock_huawei"):
        return {
            "name": "SW-Mock-01",
            "location": "测试机房",
            "role": "core",
            "connection": {
                "device_type": device_type,
                "ip": "127.0.0.1",
                "port": 23,
                "username": "admin",
                "password": "admin",
            },
        }

    def test_inspect_device_ok(self):
        from report.inspector import inspect_device
        # mock 驱动自身不需要真实网络，is_mock_mode() 在 NETGUARD_MOCK 未设置时为 False
        # 但 device_type 以 mock_ 开头，同样会绕过 check_reachable
        result = inspect_device(self._make_device())
        assert result["status"] == "ok"
        assert result["name"] == "SW-Mock-01"
        assert result["cpu_percent"] is not None

    def test_inspect_device_unreachable(self):
        from report.inspector import inspect_device
        # 只有真实设备类型（非 mock）才会触发不可达逻辑
        device = self._make_device("huawei_telnet")  # 真实类型 + 假 IP
        with patch("report.inspector.check_reachable", return_value=False):
            result = inspect_device(device)
        assert result["status"] == "unreachable"

    def test_inspect_all_returns_list(self):
        from report.inspector import inspect_all
        devices = [self._make_device("mock_huawei"), self._make_device("mock_cisco")]
        # mock_ 前缀设备无需 patch check_reachable
        results = inspect_all(devices, max_workers=2)
        assert len(results) == 2
        assert all(r["status"] == "ok" for r in results)


# ── generate_report（HTML）────────────────────────────────────────────────────

class TestGenerateReport:

    def test_render_creates_html_file(self, tmp_path):
        from report.generator import generate_report
        from datetime import datetime

        devices = [
            {
                "name": "SW-01", "ip": "1.1.1.1", "location": "", "role": "",
                "device_type": "mock_huawei", "cpu_percent": 25, "memory_percent": 40,
                "interfaces_up": 3, "interfaces_down": 1,
                "status": "ok", "alerts": [],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        ]
        out = tmp_path / "test.html"
        generate_report(
            {"devices": devices, "generated_at": "2026-05-24 10:00:00"},
            "inspect.html",
            str(out),
        )
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "SW-01" in content
        assert "NetGuard" in content


# ── generate_excel_report ─────────────────────────────────────────────────────

class TestGenerateExcelReport:

    def test_excel_file_created(self, tmp_path):
        from report.excel import generate_excel_report
        from datetime import datetime

        metrics = [
            {
                "name": "SW-01", "ip": "192.168.1.1", "location": "3楼机房",
                "role": "core", "device_type": "mock_huawei",
                "cpu_percent": 45, "memory_percent": 60,
                "interfaces_up": 4, "interfaces_down": 0,
                "status": "ok", "alerts": [],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
            {
                "name": "SW-02", "ip": "192.168.1.2", "location": "2楼机房",
                "role": "access", "device_type": "mock_huawei",
                "cpu_percent": 90, "memory_percent": 88,
                "interfaces_up": 2, "interfaces_down": 2,
                "status": "ok", "alerts": ["cpu_percent = 90%（阈值 80%）"],
                "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            },
        ]
        out = tmp_path / "test_report.xlsx"
        generate_excel_report(metrics, str(out))
        assert out.exists()
        assert out.stat().st_size > 0


# ── notify（无 Webhook 时不崩溃）────────────────────────────────────────────

class TestNotify:

    def test_send_dingtalk_no_webhook(self):
        from backup.notify import send_dingtalk
        result = send_dingtalk("", "测试消息")
        assert result is False  # 无 Webhook，返回 False，不抛出

    def test_format_alert_message(self):
        from backup.notify import format_alert_message
        msg = format_alert_message("SW-01", "cpu_percent", 85, 80)
        assert "SW-01" in msg
        assert "cpu_percent" in msg
        assert "85%" in msg
        assert "80%" in msg
