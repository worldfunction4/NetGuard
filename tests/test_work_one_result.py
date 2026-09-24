"""work_one 结果回归：配置错误和不可达都是 ok=False，快照只写临时目录"""

from pathlib import Path
from unittest.mock import patch

from devices.mock import MockDriver
from backup.collector import work_one

_PROJECT_BACKUP = Path(__file__).resolve().parents[1] / "backups_config"


def _snapshot(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {str(item.relative_to(path)) for item in path.rglob("*")}


def _device(name="SW-Mock-01", device_type="mock_huawei"):
    return {
        "name": name,
        "connection": {
            "device_type": device_type,
            "ip": "192.0.2.30",
            "port": 23,
            "username": "admin",
            "password": "admin",
        },
    }


class TestWorkOneResult:
    def test_config_error_is_not_success_but_keeps_saved_paths(self, tmp_path):
        """修复前错误标记只打日志，返回值仍是「完成」字符串"""
        before = _snapshot(_PROJECT_BACKUP)
        device = _device()
        driver = MockDriver(device["connection"])
        driver.send_config_set = lambda cmds: "Error: Unrecognized command"

        with patch("backup.collector.get_driver", return_value=driver), \
                patch("backup.storage.BACKUP_DIR", tmp_path):
            result = work_one(device, ["vlan batch 10"], ["display vlan"])

        assert isinstance(result, dict)
        assert result["ok"] is False
        assert not str(result["message"]).endswith("完成")
        assert result["saved"]
        for raw in result["saved"]:
            saved = Path(raw).resolve()
            assert saved.is_file()
            assert saved.is_relative_to(tmp_path.resolve())
        assert _snapshot(_PROJECT_BACKUP) == before

    def test_unreachable_is_not_ok(self):
        """修复前不可达返回一段文本，没有 ok=False"""
        before = _snapshot(_PROJECT_BACKUP)
        device = _device(device_type="huawei_telnet")

        with patch("backup.collector.is_mock_mode", return_value=False), \
                patch("backup.collector.check_reachable", return_value=False), \
                patch("backup.collector.get_driver") as get_driver:
            result = work_one(device, ["vlan batch 10"], ["display vlan"])

        get_driver.assert_not_called()
        assert isinstance(result, dict)
        assert result["ok"] is False
        assert result["saved"] == []
        assert _snapshot(_PROJECT_BACKUP) == before
