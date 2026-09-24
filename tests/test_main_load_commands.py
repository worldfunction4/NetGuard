"""main 入口回归：diff/inspect 不因缺少 commands.yaml 而失败，只有 run 才加载命令"""

import logging
import sys
from unittest.mock import patch

from main import main


def _logger():
    logger = logging.getLogger("netguard.tests.main_entry")
    logger.setLevel(logging.DEBUG)
    return logger


def _device():
    return {
        "name": "SW-01",
        "connection": {
            "device_type": "huawei_telnet",
            "ip": "192.0.2.60",
            "username": "admin",
            "password": "admin",
            "port": 23,
        },
    }


def _run_main(argv):
    """隔离日志和设备清单。load_commands 一旦被调用就假装文件不存在。"""
    logger = _logger()
    missing = FileNotFoundError("commands.yaml 不存在")
    with patch.object(sys, "argv", argv), \
            patch("main.load_dotenv"), \
            patch("main.setup_logger", return_value=logger), \
            patch("main._load_devices_from_source", return_value=[_device()]), \
            patch("main.load_commands", side_effect=missing) as load_commands, \
            patch("main.cmd_run") as cmd_run, \
            patch("main.cmd_diff") as cmd_diff, \
            patch("main.cmd_inspect") as cmd_inspect:
        main()
    return load_commands, cmd_run, cmd_diff, cmd_inspect


class TestMainLoadCommands:
    def test_diff_does_not_load_commands(self):
        """修复前 diff 也会 load_commands，文件不存在时直接 return，到不了 cmd_diff"""
        load_commands, cmd_run, cmd_diff, cmd_inspect = _run_main(["netguard", "diff"])
        load_commands.assert_not_called()
        cmd_diff.assert_called_once()
        cmd_run.assert_not_called()
        cmd_inspect.assert_not_called()

    def test_inspect_does_not_load_commands(self):
        load_commands, cmd_run, cmd_diff, cmd_inspect = _run_main(["netguard", "inspect"])
        load_commands.assert_not_called()
        cmd_inspect.assert_called_once()
        cmd_run.assert_not_called()
        cmd_diff.assert_not_called()

    def test_run_still_loads_commands(self):
        load_commands, cmd_run, cmd_diff, cmd_inspect = _run_main(["netguard", "run"])
        load_commands.assert_called_once()
        cmd_run.assert_not_called()
        cmd_diff.assert_not_called()
        cmd_inspect.assert_not_called()
