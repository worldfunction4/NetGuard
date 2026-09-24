"""Excel 设备清单：read_devices 与 main._load_devices_from_source 的 excel 分支。

xlsx 只写在 tmp_path，不在项目根目录生成 devices.xlsx。
"""

from pathlib import Path

import pytest
from openpyxl import Workbook

from main import _load_devices_from_source
from src.excel_reader import read_devices

HEADERS = ["name", "ip", "port", "device_type", "username", "password"]
OPTIONAL_HEADERS = HEADERS + ["location", "role"]


def _write_xlsx(path: Path, headers, rows):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(list(row))
    wb.save(path)
    wb.close()
    return path


def _sample_row(
    name="SW-Core-01",
    ip="192.168.1.1",
    port=23,
    device_type="huawei_telnet",
    username="admin",
    password="admin123",
    location=None,
    role=None,
):
    row = [name, ip, port, device_type, username, password]
    if location is not None or role is not None:
        row.append("" if location is None else location)
        row.append("" if role is None else role)
    return row


class TestReadDevices:
    def test_reads_yaml_shaped_devices_with_int_port(self, tmp_path):
        xlsx = _write_xlsx(
            tmp_path / "devices.xlsx",
            OPTIONAL_HEADERS,
            [_sample_row(location="3楼机房", role="core")],
        )

        devices = read_devices(str(xlsx))
        assert len(devices) == 1
        dev = devices[0]
        assert dev["name"] == "SW-Core-01"
        assert dev["location"] == "3楼机房"
        assert dev["role"] == "core"
        conn = dev["connection"]
        assert conn["ip"] == "192.168.1.1"
        assert conn["port"] == 23
        assert isinstance(conn["port"], int)
        assert conn["device_type"] == "huawei_telnet"
        assert conn["username"] == "admin"
        assert conn["password"] == "admin123"

    def test_optional_location_role_default_empty(self, tmp_path):
        xlsx = _write_xlsx(tmp_path / "devices.xlsx", HEADERS, [_sample_row()])
        dev = read_devices(str(xlsx))[0]
        assert dev["location"] == ""
        assert dev["role"] == ""

    def test_missing_required_column_raises(self, tmp_path):
        headers = ["name", "ip", "port", "device_type", "username"]  # 缺 password
        xlsx = _write_xlsx(tmp_path / "bad.xlsx", headers, [["SW-01", "10.0.0.1", 23, "huawei_telnet", "admin"]])
        with pytest.raises(ValueError, match="缺少必要列"):
            read_devices(str(xlsx))

    def test_empty_workbook_raises(self, tmp_path):
        path = tmp_path / "empty.xlsx"
        wb = Workbook()
        wb.save(path)
        wb.close()
        with pytest.raises(ValueError, match="为空"):
            read_devices(str(path))

    def test_non_integer_port_raises(self, tmp_path):
        xlsx = _write_xlsx(tmp_path / "devices.xlsx", HEADERS, [_sample_row(port="abc")])
        with pytest.raises(ValueError, match="port"):
            read_devices(str(xlsx))

    def test_missing_name_raises(self, tmp_path):
        xlsx = _write_xlsx(tmp_path / "devices.xlsx", HEADERS, [_sample_row(name="")])
        with pytest.raises(ValueError, match="name 或 ip"):
            read_devices(str(xlsx))

    def test_missing_ip_raises(self, tmp_path):
        xlsx = _write_xlsx(tmp_path / "devices.xlsx", HEADERS, [_sample_row(ip="")])
        with pytest.raises(ValueError, match="name 或 ip"):
            read_devices(str(xlsx))

    def test_file_not_found_raises(self, tmp_path):
        missing = tmp_path / "no-such-devices.xlsx"
        with pytest.raises(FileNotFoundError):
            read_devices(str(missing))


class TestLoadDevicesFromExcelSource:
    def test_load_devices_from_source_excel(self, tmp_path):
        xlsx = _write_xlsx(
            tmp_path / "inventory.xlsx",
            OPTIONAL_HEADERS,
            [
                _sample_row(name="SW-01", ip="10.0.0.1", port=23, location="机房A", role="core"),
                _sample_row(
                    name="R-01",
                    ip="10.0.0.2",
                    port=22,
                    device_type="cisco_ios",
                    location="机房B",
                    role="edge",
                ),
            ],
        )

        devices = _load_devices_from_source("excel", str(xlsx))
        assert [d["name"] for d in devices] == ["SW-01", "R-01"]
        assert devices[0]["connection"]["port"] == 23
        assert isinstance(devices[0]["connection"]["port"], int)
        assert devices[1]["connection"]["device_type"] == "cisco_ios"
        assert devices[1]["connection"]["port"] == 22
        assert isinstance(devices[1]["connection"]["port"], int)

    def test_load_devices_from_source_missing_file(self, tmp_path):
        missing = tmp_path / "missing.xlsx"
        with pytest.raises(FileNotFoundError, match="设备列表文件不存在"):
            _load_devices_from_source("excel", str(missing))

    def test_does_not_write_project_root_xlsx(self, tmp_path):
        """回归：测试过程不得在仓库根目录落 devices.xlsx"""
        root_xlsx = Path(__file__).resolve().parents[1] / "devices.xlsx"
        existed = root_xlsx.exists()
        xlsx = _write_xlsx(tmp_path / "devices.xlsx", HEADERS, [_sample_row()])
        _load_devices_from_source("excel", str(xlsx))
        if existed:
            assert root_xlsx.exists()
        else:
            assert not root_xlsx.exists()
