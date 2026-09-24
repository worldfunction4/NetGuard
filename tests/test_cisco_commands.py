"""Cisco 命令管理：写入 cisco 子字典，不把 cisco.show 当成顶层键。

只用 tmp_path 的 yaml，不改项目里的 commands.yaml。
cmd_command.list 写死了默认路径，所以 list/add 走 CLI 时 mock 路径。
"""

import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

from config.manager import add_command, load_commands, remove_command
from main import COMMAND_SECTIONS, cmd_command


def _write_cmds(path, data):
    path.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    return path


def _huawei_only():
    return {"config": ["vlan batch 10"], "show": ["dis vlan"]}


@pytest.fixture
def cmd_file(tmp_path):
    return _write_cmds(tmp_path / "commands.yaml", _huawei_only())


def _logger():
    logger = logging.getLogger("netguard.tests.cisco_commands")
    logger.setLevel(logging.DEBUG)
    return logger


class TestAddCiscoCommand:
    def test_cisco_show_writes_nested_not_top_level_key(self, cmd_file):
        add_command("cisco.show", "show vlan brief", cmd_file)
        cmds = load_commands(cmd_file)
        raw = yaml.safe_load(cmd_file.read_text(encoding="utf-8"))

        assert "cisco.show" not in cmds
        assert "cisco.show" not in raw
        assert cmds["cisco"]["show"] == ["show vlan brief"]
        assert cmds["show"] == ["dis vlan"]
        assert cmds["config"] == ["vlan batch 10"]

    def test_cisco_config_writes_nested_not_top_level_key(self, cmd_file):
        add_command("cisco.config", "interface GigabitEthernet0/1", cmd_file)
        cmds = load_commands(cmd_file)
        raw = yaml.safe_load(cmd_file.read_text(encoding="utf-8"))

        assert "cisco.config" not in cmds
        assert "cisco.config" not in raw
        assert cmds["cisco"]["config"] == ["interface GigabitEthernet0/1"]
        assert cmds["config"] == ["vlan batch 10"]

    def test_creates_cisco_section_when_missing(self, cmd_file):
        raw = yaml.safe_load(cmd_file.read_text(encoding="utf-8"))
        assert "cisco" not in raw

        add_command("cisco.show", "show version", cmd_file)
        cmds = load_commands(cmd_file)

        assert isinstance(cmds["cisco"], dict)
        assert cmds["cisco"]["show"] == ["show version"]
        assert cmds["cisco"]["config"] == []

    def test_idempotent_when_already_present(self, cmd_file):
        add_command("cisco.show", "show vlan brief", cmd_file)
        add_command("cisco.show", "show vlan brief", cmd_file)
        add_command("cisco.config", "hostname R1", cmd_file)
        add_command("cisco.config", "hostname R1", cmd_file)

        cmds = load_commands(cmd_file)
        assert cmds["cisco"]["show"].count("show vlan brief") == 1
        assert cmds["cisco"]["config"].count("hostname R1") == 1

    def test_top_level_config_does_not_go_into_cisco(self, cmd_file):
        add_command("cisco.show", "show vlan brief", cmd_file)
        add_command("config", "interface GE0/0/1", cmd_file)
        cmds = load_commands(cmd_file)

        assert "interface GE0/0/1" in cmds["config"]
        assert "interface GE0/0/1" not in cmds["cisco"].get("config", [])
        assert "interface GE0/0/1" not in cmds["cisco"].get("show", [])
        assert "cisco.config" not in cmds
        assert "cisco.show" not in cmds

    def test_top_level_show_does_not_go_into_cisco(self, cmd_file):
        add_command("cisco.config", "hostname R1", cmd_file)
        add_command("show", "display version", cmd_file)
        cmds = load_commands(cmd_file)

        assert "display version" in cmds["show"]
        assert "display version" not in cmds["cisco"].get("show", [])
        assert "display version" not in cmds["cisco"].get("config", [])


class TestRemoveCiscoCommand:
    def test_remove_missing_cisco_command_raises(self, cmd_file):
        add_command("cisco.show", "show vlan brief", cmd_file)
        with pytest.raises(ValueError, match="不存在"):
            remove_command("cisco.show", "show ip interface brief", cmd_file)

    def test_remove_missing_when_cisco_section_absent_raises(self, cmd_file):
        with pytest.raises(ValueError, match="不存在"):
            remove_command("cisco.config", "hostname R1", cmd_file)
        with pytest.raises(ValueError, match="不存在"):
            remove_command("cisco.show", "show version", cmd_file)

    def test_remove_existing_cisco_command(self, cmd_file):
        add_command("cisco.show", "show vlan brief", cmd_file)
        remove_command("cisco.show", "show vlan brief", cmd_file)
        assert "show vlan brief" not in load_commands(cmd_file)["cisco"]["show"]


class TestCmdCommandCli:
    """list 默认读项目 commands.yaml，必须 mock 到 tmp_path。"""

    def _patch_cmd_file(self, cmd_file):
        def _add(section, cmd, path=None):
            return add_command(section, cmd, cmd_file)

        def _remove(section, cmd, path=None):
            return remove_command(section, cmd, cmd_file)

        def _list(path=None):
            return load_commands(cmd_file)

        return (
            patch("main.add_command", side_effect=_add),
            patch("main.remove_command", side_effect=_remove),
            patch("main.list_commands", side_effect=_list),
        )

    def test_list_prints_huawei_and_cisco_section_headers(self, cmd_file, capsys):
        add_command("cisco.config", "interface Gi0/1", cmd_file)
        add_command("cisco.show", "show vlan brief", cmd_file)
        p_add, p_remove, p_list = self._patch_cmd_file(cmd_file)

        with p_add, p_remove, p_list:
            cmd_command(SimpleNamespace(action="list"), _logger())

        out = capsys.readouterr().out
        for section in ("config", "show", "cisco.config", "cisco.show"):
            assert f"[{section}]" in out
        assert COMMAND_SECTIONS == ("config", "show", "cisco.config", "cisco.show")
        assert "vlan batch 10" in out
        assert "dis vlan" in out
        assert "interface Gi0/1" in out
        assert "show vlan brief" in out

    def test_list_prints_empty_cisco_sections_when_missing(self, cmd_file, capsys):
        p_add, p_remove, p_list = self._patch_cmd_file(cmd_file)

        with p_add, p_remove, p_list:
            cmd_command(SimpleNamespace(action="list"), _logger())

        out = capsys.readouterr().out
        assert "[cisco.config]" in out
        assert "[cisco.show]" in out
        assert "[config]" in out
        assert "[show]" in out

    def test_add_cisco_show_via_cli_writes_nested_yaml(self, cmd_file):
        p_add, p_remove, p_list = self._patch_cmd_file(cmd_file)
        args = SimpleNamespace(action="add", section="cisco.show", cmd="show version")

        with p_add, p_remove, p_list:
            cmd_command(args, _logger())

        raw = yaml.safe_load(cmd_file.read_text(encoding="utf-8"))
        assert "cisco.show" not in raw
        assert raw["cisco"]["show"] == ["show version"]

    def test_add_cisco_config_via_cli_writes_nested_yaml(self, cmd_file):
        p_add, p_remove, p_list = self._patch_cmd_file(cmd_file)
        args = SimpleNamespace(action="add", section="cisco.config", cmd="hostname R1")

        with p_add, p_remove, p_list:
            cmd_command(args, _logger())

        raw = yaml.safe_load(cmd_file.read_text(encoding="utf-8"))
        assert "cisco.config" not in raw
        assert raw["cisco"]["config"] == ["hostname R1"]

    def test_remove_missing_via_cli_logs_value_error(self, cmd_file, caplog):
        p_add, p_remove, p_list = self._patch_cmd_file(cmd_file)
        args = SimpleNamespace(
            action="remove", section="cisco.show", cmd="show ip interface brief",
        )

        with caplog.at_level(logging.ERROR, logger=_logger().name), \
                p_add, p_remove, p_list:
            cmd_command(args, _logger())

        assert "不存在" in caplog.text
        raw = yaml.safe_load(cmd_file.read_text(encoding="utf-8"))
        assert "cisco.show" not in raw
