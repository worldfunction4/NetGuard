"""Excel 设备列表读取模块——从 .xlsx 文件解析设备信息"""
from pathlib import Path
import openpyxl


# 期望的列顺序（大小写不敏感）
_EXPECTED_COLS = ["name", "ip", "port", "device_type", "username", "password"]


def read_devices(path: str) -> list:
    """
    从 Excel 文件读取设备列表。

    期望的列顺序：name | ip | port | device_type | username | password
    （首行为表头，不区分大小写；额外列 location / role 可选）

    返回格式与 devices.yaml 一致，供 collector.py 直接使用：
    [
        {
            "name": "SW-Core-01",
            "location": "",
            "role": "",
            "connection": {
                "ip": "192.168.1.1",
                "port": 22,
                "device_type": "huawei_ssh",
                "username": "admin",
                "password": "admin123"
            }
        },
        ...
    ]

    Raises:
        FileNotFoundError: 文件不存在
        ValueError:        表头缺少必要列
    """
    file = Path(path)
    if not file.exists():
        raise FileNotFoundError(f"设备列表文件不存在: {path}")

    wb = openpyxl.load_workbook(str(file), read_only=True, data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("Excel 文件为空")

    # 解析表头（首行），支持大小写不敏感
    header = [str(h).strip().lower() if h else "" for h in rows[0]]
    _validate_header(header, path)

    col_idx = {col: header.index(col) for col in _EXPECTED_COLS if col in header}
    loc_idx = header.index("location") if "location" in header else None
    role_idx = header.index("role") if "role" in header else None

    devices = []
    for row_num, row in enumerate(rows[1:], start=2):
        # 跳过全空行
        if all(cell is None or str(cell).strip() == "" for cell in row):
            continue

        def _get(col: str, default=""):
            idx = col_idx.get(col)
            if idx is None or idx >= len(row):
                return default
            v = row[idx]
            return str(v).strip() if v is not None else default

        name     = _get("name")
        ip       = _get("ip")
        username = _get("username")
        password = _get("password")
        dtype    = _get("device_type")

        # port 必须是整数
        port_raw = _get("port", "22")
        try:
            port = int(float(port_raw))
        except (ValueError, TypeError):
            raise ValueError(f"第 {row_num} 行 port 列值 {port_raw!r} 不是有效整数")

        if not name or not ip:
            raise ValueError(f"第 {row_num} 行缺少 name 或 ip 字段")

        location = str(row[loc_idx]).strip() if loc_idx is not None and row[loc_idx] else ""
        role     = str(row[role_idx]).strip() if role_idx is not None and row[role_idx] else ""

        devices.append({
            "name": name,
            "location": location,
            "role": role,
            "connection": {
                "ip": ip,
                "port": port,
                "device_type": dtype,
                "username": username,
                "password": password,
            },
        })

    wb.close()
    return devices


def _validate_header(header: list, path: str):
    missing = [col for col in _EXPECTED_COLS if col not in header]
    if missing:
        raise ValueError(
            f"Excel 文件 {path} 表头缺少必要列: {missing}。"
            f"请确保首行包含: {_EXPECTED_COLS}"
        )
