"""config/manager.py 单元测试——增删改查设备和命令"""
import pytest
from pathlib import Path
from config.manager import (
    load_devices, save_devices,
    add_device, update_device, remove_device, list_devices,
    load_commands, save_commands,
    add_command, remove_command, list_commands,
)


# ── 公共 fixture ─────────────────────────────────────────────────────────────

def _make_device(name="SW-01", ip="192.168.1.1", port=23,
                 dtype="huawei_telnet", user="admin", pwd="admin123"):
    return {
        "name": name,
        "location": "测试机房",
        "role": "core",
        "connection": {
            "device_type": dtype,
            "ip": ip,
            "port": port,
            "username": user,
            "password": pwd,
            "timeout": 30,
        },
    }


@pytest.fixture
def dev_file(tmp_path):
    """空设备文件路径（测试隔离）"""
    return tmp_path / "devices.yaml"


@pytest.fixture
def cmd_file(tmp_path):
    """预填一条命令的命令文件"""
    import yaml
    p = tmp_path / "commands.yaml"
    p.write_text(yaml.dump({"config": ["vlan batch 10"], "show": ["dis vlan"]},
                           allow_unicode=True), encoding="utf-8")
    return p


# ── load_devices 错误场景 ─────────────────────────────────────────────────────

class TestLoadDevices:

    def test_file_not_exist_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="设备配置文件不存在"):
            load_devices(tmp_path / "nonexistent.yaml")

    def test_empty_file_raises_value_error(self, dev_file):
        dev_file.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="当前没有可以进行配置的设备"):
            load_devices(dev_file)

    def test_null_yaml_raises_value_error(self, dev_file):
        dev_file.write_text("~\n", encoding="utf-8")   # YAML null
        with pytest.raises(ValueError, match="当前没有可以进行配置的设备"):
            load_devices(dev_file)


# ── add_device ────────────────────────────────────────────────────────────────

class TestAddDevice:

    def test_add_first_device(self, dev_file):
        add_device(_make_device("SW-01"), dev_file)
        devices = load_devices(dev_file)
        assert len(devices) == 1
        assert devices[0]["name"] == "SW-01"

    def test_add_two_devices(self, dev_file):
        add_device(_make_device("SW-01"), dev_file)
        add_device(_make_device("SW-02", ip="192.168.1.2"), dev_file)
        assert len(load_devices(dev_file)) == 2

    def test_duplicate_name_raises(self, dev_file):
        add_device(_make_device("SW-01"), dev_file)
        with pytest.raises(ValueError, match="已存在"):
            add_device(_make_device("SW-01"), dev_file)

    def test_missing_name_raises(self, dev_file):
        bad = _make_device("SW-01")
        del bad["name"]
        with pytest.raises(ValueError, match="'name'"):
            add_device(bad, dev_file)

    def test_missing_ip_raises(self, dev_file):
        bad = _make_device("SW-01")
        del bad["connection"]["ip"]
        with pytest.raises(ValueError, match="ip"):
            add_device(bad, dev_file)

    def test_port_not_int_raises(self, dev_file):
        bad = _make_device("SW-01", port="23")   # 字符串端口
        with pytest.raises(ValueError, match="port"):
            add_device(bad, dev_file)


# ── update_device ─────────────────────────────────────────────────────────────

class TestUpdateDevice:

    def test_update_ip(self, dev_file):
        add_device(_make_device("SW-01"), dev_file)
        update_device("SW-01", {"ip": "10.0.0.1"}, dev_file)
        dev = load_devices(dev_file)[0]
        assert dev["connection"]["ip"] == "10.0.0.1"

    def test_update_location(self, dev_file):
        add_device(_make_device("SW-01"), dev_file)
        update_device("SW-01", {"location": "5楼机房"}, dev_file)
        dev = load_devices(dev_file)[0]
        assert dev["location"] == "5楼机房"

    def test_update_connection_dict(self, dev_file):
        add_device(_make_device("SW-01"), dev_file)
        update_device("SW-01", {"connection": {"port": 22, "device_type": "huawei_ssh"}}, dev_file)
        conn = load_devices(dev_file)[0]["connection"]
        assert conn["port"] == 22
        assert conn["device_type"] == "huawei_ssh"

    def test_update_nonexistent_device_raises(self, dev_file):
        add_device(_make_device("SW-01"), dev_file)
        with pytest.raises(KeyError, match="不存在"):
            update_device("SW-99", {"ip": "1.1.1.1"}, dev_file)


# ── remove_device ─────────────────────────────────────────────────────────────

class TestRemoveDevice:

    def test_remove_existing(self, dev_file):
        add_device(_make_device("SW-01"), dev_file)
        add_device(_make_device("SW-02", ip="192.168.1.2"), dev_file)
        remove_device("SW-01", dev_file)
        names = [d["name"] for d in load_devices(dev_file)]
        assert "SW-01" not in names
        assert "SW-02" in names

    def test_remove_nonexistent_raises(self, dev_file):
        add_device(_make_device("SW-01"), dev_file)
        with pytest.raises(KeyError, match="不存在"):
            remove_device("SW-99", dev_file)


# ── list_devices ──────────────────────────────────────────────────────────────

class TestListDevices:

    def test_list_returns_summary(self, dev_file):
        add_device(_make_device("SW-01"), dev_file)
        rows = list_devices(dev_file)
        assert len(rows) == 1
        assert rows[0]["name"] == "SW-01"
        assert "ip" in rows[0]
        assert "device_type" in rows[0]


# ── load_commands 错误场景 ────────────────────────────────────────────────────

class TestLoadCommands:

    def test_file_not_exist_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_commands(tmp_path / "no.yaml")

    def test_empty_file_raises(self, cmd_file):
        cmd_file.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="当前没有可以进行配置的命令"):
            load_commands(cmd_file)


# ── add_command ───────────────────────────────────────────────────────────────

class TestAddCommand:

    def test_add_config_command(self, cmd_file):
        add_command("config", "interface GE0/0/1", cmd_file)
        cmds = load_commands(cmd_file)
        assert "interface GE0/0/1" in cmds["config"]

    def test_add_show_command(self, cmd_file):
        add_command("show", "display version", cmd_file)
        cmds = load_commands(cmd_file)
        assert "display version" in cmds["show"]

    def test_add_duplicate_is_idempotent(self, cmd_file):
        add_command("config", "vlan batch 10", cmd_file)  # 已存在
        cmds = load_commands(cmd_file)
        assert cmds["config"].count("vlan batch 10") == 1

    def test_invalid_section_raises(self, cmd_file):
        with pytest.raises(ValueError, match="无效"):
            add_command("invalid_section", "some cmd", cmd_file)


# ── remove_command ────────────────────────────────────────────────────────────

class TestRemoveCommand:

    def test_remove_existing(self, cmd_file):
        remove_command("config", "vlan batch 10", cmd_file)
        assert "vlan batch 10" not in load_commands(cmd_file)["config"]

    def test_remove_nonexistent_raises(self, cmd_file):
        with pytest.raises(ValueError, match="不存在"):
            remove_command("show", "display cpu", cmd_file)


# ── 空设备时运行 run/diff/inspect 应报错 ─────────────────────────────────────

class TestEmptyDevicesRuntime:
    """验证 load_devices 抛出的错误消息符合需求中的措辞"""

    def test_error_message_contains_chinese_hint(self, tmp_path):
        empty = tmp_path / "devices.yaml"
        empty.write_text("", encoding="utf-8")
        with pytest.raises(ValueError) as exc:
            load_devices(empty)
        assert "当前没有可以进行配置的设备" in str(exc.value)
