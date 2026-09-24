"""device add/update 密码回归测试——密码只走 getpass，不进日志，不写项目 devices.yaml"""

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from config.manager import add_device as real_add_device
from config.manager import load_devices
from config.manager import update_device as real_update_device
from main import _prompt_device_entry, cmd_device

# 刻意不用 "password" 这个词，避免和日志里的字段名撞车
CLI_SECRET = "CliOnly-NotStored-8841"
PROMPT_SECRET = "PromptSecret-5521"
OLD_SECRET = "OldPlaceholder-1001"


def _device(name="SW-01"):
    return {
        "name": name,
        "location": "测试机房",
        "role": "core",
        "connection": {
            "device_type": "huawei_telnet",
            "ip": "192.168.1.1",
            "port": 23,
            "username": "admin",
            "password": OLD_SECRET,
            "timeout": 30,
        },
    }


def _seed(tmp_path):
    """设备清单只放在 pytest 临时目录，不碰项目根目录的 devices.yaml"""
    dev_file = tmp_path / "devices.yaml"
    real_add_device(_device(), dev_file)
    return dev_file


def _logger():
    logger = logging.getLogger("netguard.tests.device_password")
    logger.setLevel(logging.DEBUG)
    return logger


def _assert_secrets_absent(text, *secrets):
    for secret in secrets:
        assert secret not in text, f"日志或输出里出现了密码原文: {secret}"


class TestUpdatePassword:
    def test_getpass_ignores_cli_secret_and_log_omits_password(self, tmp_path, caplog, capsys):
        dev_file = _seed(tmp_path)
        logger = _logger()
        args = SimpleNamespace(
            action="update", name="SW-01", field="password", value=CLI_SECRET,
        )

        def _write_temp(name, updates, path=None):
            real_update_device(name, updates, dev_file)

        with caplog.at_level(logging.DEBUG, logger=logger.name), \
                patch("main.getpass.getpass", return_value=PROMPT_SECRET) as mock_getpass, \
                patch("main.update_device", side_effect=_write_temp):
            cmd_device(args, logger)

        mock_getpass.assert_called_once_with("密码（直接回车取消）: ")
        saved = load_devices(dev_file)[0]["connection"]["password"]
        assert saved == PROMPT_SECRET
        assert saved != CLI_SECRET

        assert "设备 'SW-01' 字段 password 已更新" in caplog.text
        assert "已更新为" not in caplog.text
        warnings = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
        assert warnings
        assert any("忽略" in msg for msg in warnings)
        _assert_secrets_absent(caplog.text, CLI_SECRET, PROMPT_SECRET, OLD_SECRET)
        for msg in warnings:
            _assert_secrets_absent(msg, CLI_SECRET, PROMPT_SECRET)
        _assert_secrets_absent(capsys.readouterr().out, CLI_SECRET, PROMPT_SECRET)

    @pytest.mark.parametrize("typed,expected", [("q", "q"), ("Q", "Q"), (" q ", "q")])
    def test_q_is_saved(self, tmp_path, typed, expected, caplog):
        dev_file = _seed(tmp_path)
        logger = _logger()
        args = SimpleNamespace(
            action="update", name="SW-01", field="password", value=CLI_SECRET,
        )

        def _write_temp(name, updates, path=None):
            real_update_device(name, updates, dev_file)

        with caplog.at_level(logging.DEBUG, logger=logger.name), \
                patch("main.getpass.getpass", return_value=typed), \
                patch("main.update_device", side_effect=_write_temp):
            cmd_device(args, logger)

        assert load_devices(dev_file)[0]["connection"]["password"] == expected
        assert "设备 'SW-01' 字段 password 已更新" in caplog.text
        assert "已更新为" not in caplog.text
        _assert_secrets_absent(caplog.text, expected, CLI_SECRET)

    @pytest.mark.parametrize("typed", ["", "   "])
    def test_empty_password_not_written(self, tmp_path, typed, capsys):
        dev_file = _seed(tmp_path)
        args = SimpleNamespace(
            action="update", name="SW-01", field="password", value=None,
        )

        with patch("main.getpass.getpass", return_value=typed), \
                patch("main.update_device") as mock_update:
            cmd_device(args, _logger())

        mock_update.assert_not_called()
        assert load_devices(dev_file)[0]["connection"]["password"] == OLD_SECRET
        assert "密码不能为空" in capsys.readouterr().out

    @pytest.mark.parametrize("field", ["ip", "port", "location"])
    def test_missing_value_errors_without_crash(self, field, caplog):
        logger = _logger()
        args = SimpleNamespace(action="update", name="SW-01", field=field, value=None)

        with caplog.at_level(logging.DEBUG, logger=logger.name), \
                patch("main.update_device") as mock_update, \
                patch("main.getpass.getpass") as mock_getpass:
            cmd_device(args, logger)

        mock_update.assert_not_called()
        mock_getpass.assert_not_called()
        assert f"字段 '{field}' 缺少新值" in caplog.text


class TestAddPassword:
    def _inputs(self):
        # 密码不在这份列表里；密码只应交给 getpass
        return ["SW-Add-01", "10.0.0.8", "23", "huawei_telnet", "admin", "机房A", "core"]

    def test_getpass_no_echo_and_log_omits_password(self, tmp_path, caplog, capsys):
        dev_file = tmp_path / "devices.yaml"
        logger = _logger()

        def _write_temp(entry, path=None):
            real_add_device(entry, dev_file)

        with caplog.at_level(logging.DEBUG, logger=logger.name), \
                patch("builtins.input", side_effect=self._inputs()) as mock_input, \
                patch("main.getpass.getpass", return_value=f"  {PROMPT_SECRET}  ") as mock_getpass, \
                patch("main.add_device", side_effect=_write_temp):
            cmd_device(SimpleNamespace(action="add"), logger)

        mock_getpass.assert_called_once_with("  密码（直接回车取消）: ")
        for call in mock_input.call_args_list:
            assert PROMPT_SECRET not in str(call)
        saved = load_devices(dev_file)[0]["connection"]["password"]
        assert saved == PROMPT_SECRET
        assert "设备 'SW-Add-01' 添加成功" in caplog.text
        _assert_secrets_absent(caplog.text, PROMPT_SECRET)
        _assert_secrets_absent(capsys.readouterr().out, PROMPT_SECRET)

    @pytest.mark.parametrize("typed,expected", [("q", "q"), (" Q ", "Q")])
    def test_q_is_saved_as_password(self, typed, expected):
        with patch("builtins.input", side_effect=self._inputs()) as mock_input, \
                patch("main.getpass.getpass", return_value=typed):
            result = _prompt_device_entry()

        assert result is not None
        assert result["connection"]["password"] == expected
        # 密码保存后继续询问位置和角色
        assert mock_input.call_count == 7

    @pytest.mark.parametrize("typed", ["", "   "])
    def test_empty_password_returns_none(self, typed, capsys):
        with patch("builtins.input", side_effect=self._inputs()) as mock_input, \
                patch("main.getpass.getpass", return_value=typed), \
                patch("main.add_device") as mock_add:
            result = _prompt_device_entry()

        assert result is None
        mock_add.assert_not_called()
        assert mock_input.call_count == 5
        assert "密码不能为空" in capsys.readouterr().out
