"""设备列表和命令配置的读写管理模块

职责：
  - 读取 devices.yaml / commands.yaml
  - 增加 / 修改 / 删除 设备条目
  - 增加 / 修改 / 删除 命令条目（config 区 / show 区）
  - 校验结构，空列表或空文件时给出明确错误

所有改动直接写回 YAML 文件，原有注释因 PyYAML 限制无法保留。
"""
from pathlib import Path
from typing import Optional
import yaml

# 默认文件位置（项目根目录）
_ROOT = Path(__file__).parent.parent
DEVICES_FILE  = _ROOT / "devices.yaml"
COMMANDS_FILE = _ROOT / "commands.yaml"

# commands.yaml 必须包含的两个顶层键
_CMD_SECTIONS = ("config", "show")

# ── 设备管理 ─────────────────────────────────────────────────────────────────

def load_devices(path: Path = DEVICES_FILE) -> list:
    """读取设备列表，文件不存在或内容为空时抛出友好错误。"""
    if not path.exists():
        raise FileNotFoundError(
            f"设备配置文件不存在: {path}\n"
            f"请复制 devices.example.yaml 为 devices.yaml 并填写真实信息。"
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not raw:
        raise ValueError(
            "当前没有可以进行配置的设备。\n"
            f"请在 {path} 中添加至少一台设备信息后重试。"
        )
    if not isinstance(raw, list):
        raise ValueError(f"{path} 格式有误：顶层应为列表（- name: ...），当前是 {type(raw).__name__}")
    return raw


def save_devices(devices: list, path: Path = DEVICES_FILE) -> None:
    """将设备列表写回文件。"""
    path.write_text(
        yaml.dump(devices, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def add_device(entry: dict, path: Path = DEVICES_FILE) -> None:
    """新增一台设备。如果同名设备已存在则抛出 ValueError。

    Args:
        entry: 设备字典，需包含 name 和 connection（含 ip/port/device_type/username/password）
    """
    _validate_device_entry(entry)
    try:
        devices = load_devices(path)
    except (FileNotFoundError, ValueError):
        # 文件不存在或为空时，从空列表开始（首次添加设备的场景）
        devices = []

    name = entry["name"]
    if any(d["name"] == name for d in devices):
        raise ValueError(f"设备 '{name}' 已存在，如需修改请使用 update_device()")

    devices.append(entry)
    save_devices(devices, path)


def update_device(name: str, updates: dict, path: Path = DEVICES_FILE) -> None:
    """修改指定设备的字段（支持顶层字段和 connection 子字段）。

    Args:
        name:    要修改的设备名
        updates: 要覆盖的字段，例如 {"connection": {"ip": "10.0.0.1"}}
                 或扁平写法 {"ip": "10.0.0.1"}（自动写入 connection 层）
    """
    devices = load_devices(path)
    target = _find_device(devices, name)

    # 扁平字段（非 connection 层的顶层字段）直接更新
    for k, v in updates.items():
        if k == "connection" and isinstance(v, dict):
            target.setdefault("connection", {}).update(v)
        elif k in ("name", "location", "role"):
            target[k] = v
        else:
            # 其他字段默认写入 connection 层（如直接写 ip / port）
            target.setdefault("connection", {})[k] = v

    save_devices(devices, path)


def remove_device(name: str, path: Path = DEVICES_FILE) -> None:
    """删除指定名称的设备。"""
    devices = load_devices(path)
    _find_device(devices, name)  # 不存在会抛出 KeyError
    new_devices = [d for d in devices if d["name"] != name]
    save_devices(new_devices, path)


def list_devices(path: Path = DEVICES_FILE) -> list:
    """返回当前所有设备的摘要（name / ip / device_type）。"""
    devices = load_devices(path)
    return [
        {
            "name": d.get("name", ""),
            "ip": d.get("connection", {}).get("ip", ""),
            "port": d.get("connection", {}).get("port", ""),
            "device_type": d.get("connection", {}).get("device_type", ""),
            "location": d.get("location", ""),
            "role": d.get("role", ""),
        }
        for d in devices
    ]


# ── 命令管理 ─────────────────────────────────────────────────────────────────

def load_commands(path: Path = COMMANDS_FILE) -> dict:
    """读取命令配置，文件不存在或内容为空时抛出友好错误。"""
    if not path.exists():
        raise FileNotFoundError(f"命令配置文件不存在: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not raw:
        raise ValueError(
            "当前没有可以进行配置的命令。\n"
            f"请在 {path} 中添加 config 和 show 命令后重试。"
        )
    if not isinstance(raw, dict):
        raise ValueError(f"{path} 格式有误：顶层应为字典（config:/show:），当前是 {type(raw).__name__}")
    for section in _CMD_SECTIONS:
        if section not in raw:
            raw[section] = []
    return raw


def save_commands(commands: dict, path: Path = COMMANDS_FILE) -> None:
    """将命令配置写回文件。"""
    path.write_text(
        yaml.dump(commands, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def add_command(section: str, cmd: str, path: Path = COMMANDS_FILE) -> None:
    """向指定区块（config 或 show）添加命令。已存在则跳过（幂等）。

    Args:
        section: "config" 或 "show"
        cmd:     要添加的命令字符串
    """
    _validate_section(section)
    try:
        commands = load_commands(path)
    except ValueError:
        commands = {s: [] for s in _CMD_SECTIONS}

    cmds: list = commands.setdefault(section, [])
    if cmd in cmds:
        return  # 已存在，幂等
    cmds.append(cmd)
    save_commands(commands, path)


def remove_command(section: str, cmd: str, path: Path = COMMANDS_FILE) -> None:
    """从指定区块删除命令。命令不存在时抛出 ValueError。"""
    _validate_section(section)
    commands = load_commands(path)
    cmds: list = commands.get(section, [])
    if cmd not in cmds:
        raise ValueError(f"命令 '{cmd}' 在 {section} 区块中不存在")
    cmds.remove(cmd)
    save_commands(commands, path)


def list_commands(path: Path = COMMANDS_FILE) -> dict:
    """返回当前所有命令的分区字典。"""
    return load_commands(path)


# ── 校验辅助 ─────────────────────────────────────────────────────────────────

_REQUIRED_CONN_FIELDS = ("device_type", "ip", "username", "password", "port")


def _validate_device_entry(entry: dict) -> None:
    """校验设备字典结构，不合法时抛出 ValueError。"""
    if not isinstance(entry, dict):
        raise ValueError(f"设备信息应为字典，当前是 {type(entry).__name__}")
    if "name" not in entry:
        raise ValueError("设备信息缺少 'name' 字段")
    if "connection" not in entry or not isinstance(entry["connection"], dict):
        raise ValueError(f"设备 '{entry.get('name')}' 缺少 connection 字段（应为字典）")
    conn = entry["connection"]
    missing = [f for f in _REQUIRED_CONN_FIELDS if f not in conn]
    if missing:
        raise ValueError(f"设备 '{entry['name']}' 的 connection 缺少字段: {missing}")
    if not isinstance(conn["port"], int):
        raise ValueError(f"设备 '{entry['name']}' 的 port 应为整数，当前: {conn['port']!r}")


def _find_device(devices: list, name: str) -> dict:
    """按名称查找设备，找不到抛出 KeyError。"""
    for d in devices:
        if d.get("name") == name:
            return d
    raise KeyError(f"设备 '{name}' 不存在，请先用 'device list' 查看当前设备列表")


def _validate_section(section: str) -> None:
    if section not in _CMD_SECTIONS:
        raise ValueError(f"区块 '{section}' 无效，只支持: {_CMD_SECTIONS}")
