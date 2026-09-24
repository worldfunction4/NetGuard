"""cmd_run 回归：失败退出码、Cisco 命令隔离、不真上传 OSS"""

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from main import cmd_run


def _logger():
    logger = logging.getLogger("netguard.tests.cmd_run")
    logger.setLevel(logging.DEBUG)
    return logger


def _device(name, device_type):
    return {
        "name": name,
        "connection": {
            "device_type": device_type,
            "ip": "192.0.2.40",
            "port": 23,
            "username": "admin",
            "password": "admin",
        },
    }


HUAWEI_COMMANDS = {
    "config": ["vlan batch 10"],
    "show": ["dis vlan"],
}


class TestCmdRun:
    def test_failure_exits_with_code_1(self):
        """修复前失败只打日志，进程不退出"""
        device = _device("SW-HW", "huawei_telnet")

        def failed(dev, config_commands, show_commands):
            return {"ok": False, "message": "配置失败", "saved": []}

        with patch("main.work_one", side_effect=failed), \
                patch("backup.cloud.sync_backup_to_cloud") as cloud, \
                pytest.raises(SystemExit) as exc_info:
            cmd_run(SimpleNamespace(), _logger(), [device], HUAWEI_COMMANDS)

        assert exc_info.value.code == 1
        cloud.assert_called_once_with(files=[])

    def test_all_success_does_not_exit_with_error(self):
        device = _device("SW-HW", "huawei_telnet")

        def ok(dev, config_commands, show_commands):
            return {"ok": True, "message": "完成", "saved": []}

        with patch("main.work_one", side_effect=ok), \
                patch("backup.cloud.sync_backup_to_cloud", return_value=False):
            try:
                cmd_run(SimpleNamespace(), _logger(), [device], HUAWEI_COMMANDS)
            except SystemExit as exc:
                assert exc.code in (0, None)

    def test_cisco_gets_only_cisco_section(self):
        """修复前 Cisco 会收到顶层 vlan batch / dis vlan"""
        calls = {}

        def record(dev, config_commands, show_commands):
            calls[dev["name"]] = (list(config_commands), list(show_commands))
            return {"ok": True, "message": "完成", "saved": []}

        commands = {
            "config": ["vlan batch 10"],
            "show": ["dis vlan"],
            "cisco": {"config": ["interface Gi0/1"], "show": ["show vlan brief"]},
        }
        devices = [
            _device("SW-HW", "huawei_telnet"),
            _device("SW-CS", "cisco_ios"),
        ]

        with patch("main.work_one", side_effect=record), \
                patch("backup.cloud.sync_backup_to_cloud", return_value=False) as cloud:
            cmd_run(SimpleNamespace(), _logger(), devices, commands)

        assert calls["SW-HW"] == (["vlan batch 10"], ["dis vlan"])
        cisco_config, cisco_show = calls["SW-CS"]
        assert cisco_config == ["interface Gi0/1"]
        assert cisco_show == ["show vlan brief"]
        assert "vlan batch 10" not in cisco_config
        assert "dis vlan" not in cisco_show
        assert cloud.call_args.kwargs.get("files") is not None
        assert cloud.call_args.args == ()

    def test_missing_cisco_section_sends_empty_lists(self):
        """修复前没有 cisco 节时，Cisco 会退回使用华为顶层命令"""
        calls = {}

        def record(dev, config_commands, show_commands):
            calls[dev["name"]] = (list(config_commands), list(show_commands))
            return {"ok": True, "message": "完成", "saved": []}

        with patch("main.work_one", side_effect=record), \
                patch("backup.cloud.sync_backup_to_cloud", return_value=False):
            cmd_run(
                SimpleNamespace(),
                _logger(),
                [_device("SW-CS", "cisco_ios")],
                HUAWEI_COMMANDS,
            )

        assert calls["SW-CS"] == ([], [])
