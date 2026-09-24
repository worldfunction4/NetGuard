"""Web API 回归：TestClient 调用 api.app:app。

会读文件或连设备的函数全部 mock，报告目录只指向 tmp_path。
不读取、不写入项目里的 devices.yaml、commands.yaml、devices.xlsx。
"""

import asyncio
import copy
import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from api.app import app, key_error_handler

client = TestClient(app)

# 各用例用不同明文，断言响应里不会出现调用方传入的密码。
LIST_SECRET = "list-DoNotLeak-91ff"
CREATE_SECRET = "create-DoNotLeak-7c1e9a"
INSPECT_SECRET = "inspect-DoNotLeak-44ab"


def _assert_no_password(value):
    """响应 JSON 的任何一层都不能有 password 字段。"""
    if isinstance(value, dict):
        assert "password" not in value
        for item in value.values():
            _assert_no_password(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_password(item)


def _assert_error(response, status, code):
    """统一错误体是 {"error": {"code", "message"}}，不能是 {"detail": ...}。"""
    assert response.status_code == status
    body = response.json()
    assert "detail" not in body
    assert set(body) == {"error"}
    error = body["error"]
    assert set(error) == {"code", "message"}
    assert error["code"] == code
    assert isinstance(error["message"], str) and error["message"]
    return body


def _device_body(**overrides):
    body = {
        "name": "Core-SW",
        "ip": "192.0.2.10",
        "port": 22,
        "device_type": "huawei",
        "username": "admin",
        "password": CREATE_SECRET,
        "location": "机房A",
        "role": "core",
    }
    body.update(overrides)
    return body


class TestGetDevices:
    def test_response_has_no_password_field(self, monkeypatch):
        """list_devices 即使带了 password，GET /devices 的结果里也不能有。"""
        monkeypatch.setattr(
            "api.devices.list_devices",
            lambda: [
                {
                    "name": "Core-SW",
                    "ip": "192.0.2.10",
                    "port": 22,
                    "device_type": "huawei",
                    "location": "机房A",
                    "role": "core",
                    "password": LIST_SECRET,
                    "username": "admin",
                    "connection": {
                        "ip": "192.0.2.10",
                        "password": LIST_SECRET,
                    },
                }
            ],
        )

        response = client.get("/devices")

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list) and body
        assert body[0]["name"] == "Core-SW"
        assert LIST_SECRET not in response.text
        _assert_no_password(body)


class TestPostDevices:
    def test_missing_name_is_validation_error(self):
        payload = _device_body()
        payload.pop("name")

        response = client.post("/devices", json=payload)

        body = _assert_error(response, 400, "VALIDATION_ERROR")
        assert CREATE_SECRET not in response.text
        assert CREATE_SECRET not in body["error"]["message"]

    def test_missing_password_is_validation_error(self):
        payload = _device_body()
        payload.pop("password")

        response = client.post("/devices", json=payload)

        _assert_error(response, 400, "VALIDATION_ERROR")
        assert "detail" not in response.json()

    def test_valid_request_calls_add_device_with_timeout(self, monkeypatch):
        """合法请求调用 add_device，connection.timeout 为 30，响应不含密码。"""
        captured = {}

        def fake_add_device(entry):
            # 调用当下就拷贝。接口返回前会从同一字典里清掉密码。
            captured["entry"] = copy.deepcopy(entry)

        monkeypatch.setattr("api.devices.add_device", fake_add_device)
        payload = _device_body()

        response = client.post("/devices", json=payload)

        assert response.status_code == 200
        assert "entry" in captured
        connection = captured["entry"]["connection"]
        assert connection["timeout"] == 30
        # 只和请求里的密码比较，不另写日志。
        assert connection["password"] == payload["password"]
        body = response.json()
        assert payload["password"] not in response.text
        _assert_no_password(body)
        assert body["name"] == "Core-SW"
        assert body["ip"] == "192.0.2.10"


class TestBackupJob:
    def test_failure_result_is_http_200(self, monkeypatch):
        """run_backup 返回失败台数时，HTTP 仍是 200，进程不退出。"""
        devices = [{"name": "Core-SW", "connection": {"password": "unused"}}]
        commands = {"config": [], "show": ["display version"]}

        def fake_backup(devs, cmds, logger):
            assert devs == devices
            assert cmds == commands
            return {
                "failed": 1,
                "results": [
                    {"name": "Core-SW", "ok": False, "message": "连接超时"},
                ],
                "saved": [],
            }

        monkeypatch.setattr("api.jobs.load_devices", lambda: devices)
        monkeypatch.setattr("api.jobs.load_commands", lambda: commands)
        monkeypatch.setattr("api.jobs.run_backup", fake_backup)

        response = client.post("/jobs/backup")

        assert response.status_code == 200
        body = response.json()
        assert "failed" in body
        assert "results" in body
        assert "saved" in body
        assert body["failed"] == 1
        assert body["results"][0]["ok"] is False
        assert body["saved"] == []

    def test_missing_device_file_is_not_found(self, monkeypatch):
        """load_devices 抛 FileNotFoundError 时，备份接口返回 404 统一错误体。"""

        def missing_devices():
            raise FileNotFoundError("设备配置文件不存在")

        monkeypatch.setattr("api.jobs.load_devices", missing_devices)
        monkeypatch.setattr("api.jobs.load_commands", lambda: {"config": [], "show": []})
        monkeypatch.setattr(
            "api.jobs.run_backup",
            lambda *args, **kwargs: {"failed": 0, "results": [], "saved": []},
        )

        response = client.post("/jobs/backup")

        _assert_error(response, 404, "NOT_FOUND")


class TestInspectJob:
    def test_response_drops_password_from_metrics(self, monkeypatch):
        monkeypatch.setattr("api.jobs.load_devices", lambda: [{"name": "Core-SW"}])

        def fake_inspect(devices, logger):
            return {
                "metrics": [
                    {
                        "name": "Core-SW",
                        "cpu_percent": 12,
                        "password": INSPECT_SECRET,
                        "connection": {"password": INSPECT_SECRET, "ip": "192.0.2.10"},
                    }
                ],
                "html_path": "reports/inspect.html",
                "excel_path": "reports/inspect.xlsx",
            }

        monkeypatch.setattr("api.jobs.run_inspect", fake_inspect)

        response = client.post("/jobs/inspect")

        assert response.status_code == 200
        body = response.json()
        assert "metrics" in body
        assert "html_path" in body
        assert "excel_path" in body
        assert body["html_path"] == "reports/inspect.html"
        assert body["excel_path"] == "reports/inspect.xlsx"
        assert body["metrics"][0]["name"] == "Core-SW"
        assert INSPECT_SECRET not in response.text
        _assert_no_password(body)


class TestDiffJob:
    def test_response_has_name_ok_report(self, monkeypatch):
        monkeypatch.setattr(
            "api.jobs.load_devices",
            lambda: [{"name": "Core-SW"}, {"name": "Edge-SW"}],
        )

        def fake_diff(devices, logger):
            return [
                {"name": "Core-SW", "ok": True, "report": "reports/core.html"},
                {"name": "Edge-SW", "ok": False, "report": None},
            ]

        monkeypatch.setattr("api.jobs.run_diff", fake_diff)

        response = client.post("/jobs/diff")

        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list) and len(body) == 2
        for item in body:
            assert "name" in item
            assert "ok" in item
            assert "report" in item
        assert body[0]["name"] == "Core-SW"
        assert body[0]["ok"] is True
        assert body[0]["report"] == "reports/core.html"
        assert body[1]["ok"] is False
        assert body[1]["report"] is None


class TestListReports:
    def test_missing_report_dir_returns_empty_list(self, monkeypatch, tmp_path):
        """api/jobs.py 读取的是 config.REPORT_DIR，目录不存在时返回 []。"""
        missing = tmp_path / "reports-missing"
        monkeypatch.setattr("config.REPORT_DIR", missing)

        response = client.get("/reports")

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_only_html_filenames(self, monkeypatch, tmp_path):
        """目录里混有其他文件时，只返回 html 文件名。"""
        report_dir = tmp_path / "reports"
        report_dir.mkdir()
        (report_dir / "b.html").write_text("<html></html>", encoding="utf-8")
        (report_dir / "a.html").write_text("<html></html>", encoding="utf-8")
        (report_dir / "notes.txt").write_text("not a report", encoding="utf-8")
        (report_dir / "inspect.xlsx").write_bytes(b"not-a-real-xlsx")
        (report_dir / "nested.html").mkdir()
        # jobs.py 使用 import config 后的 config.REPORT_DIR，请求时才读取。
        monkeypatch.setattr("config.REPORT_DIR", report_dir)

        response = client.get("/reports")

        assert response.status_code == 200
        assert response.json() == ["a.html", "b.html"]


def _assert_chinese_sentence(message: str) -> None:
    """错误说明必须是完整中文句子，不能只剩字段名。"""
    assert isinstance(message, str) and message
    assert message not in {"name", "connection"}
    assert message.strip("'\"") not in {"name", "connection"}
    assert any("\u4e00" <= char <= "\u9fff" for char in message)


def _block_device_work(monkeypatch, devices):
    """挡住真正连设备和上传。load_commands 也不读项目里的 yaml。"""
    work = MagicMock()
    sync = MagicMock()
    monkeypatch.setattr("api.jobs.load_devices", lambda: devices)
    monkeypatch.setattr("api.jobs.load_commands", lambda: {"config": [], "show": []})
    monkeypatch.setattr("operations.work_one", work)
    monkeypatch.setattr("backup.cloud.sync_backup_to_cloud", sync)
    return work, sync


class TestDeviceShapeRejectedBeforeWork:
    """结构不合法时，三个任务接口应在 work_one / sync 之前失败。"""

    @pytest.mark.parametrize("path", ["/jobs/backup", "/jobs/inspect", "/jobs/diff"])
    def test_missing_connection_is_validation_error(self, monkeypatch, path):
        work, sync = _block_device_work(monkeypatch, [{"name": "SW-01"}])

        response = client.post(path)

        body = _assert_error(response, 400, "VALIDATION_ERROR")
        _assert_chinese_sentence(body["error"]["message"])
        work.assert_not_called()
        if path == "/jobs/backup":
            sync.assert_not_called()

    def test_blank_device_name_is_validation_error(self, monkeypatch):
        """名称只有空格。connection 补齐后才会走到名称校验，而不是缺字段。"""
        devices = [
            {
                "name": "   ",
                "connection": {
                    "device_type": "huawei",
                    "ip": "192.0.2.10",
                    "username": "admin",
                    "password": "blank-name-unused",
                    "port": 22,
                },
            }
        ]
        work, sync = _block_device_work(monkeypatch, devices)

        response = client.post("/jobs/backup")

        body = _assert_error(response, 400, "VALIDATION_ERROR")
        message = body["error"]["message"]
        _assert_chinese_sentence(message)
        assert "名称" in message
        assert "不能为空" in message
        work.assert_not_called()
        sync.assert_not_called()


def _call_key_error(exc: KeyError) -> tuple[int, dict]:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/jobs/backup",
        "raw_path": b"/jobs/backup",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 0),
        "server": ("testserver", 80),
    }
    response = asyncio.run(key_error_handler(Request(scope), exc))
    return response.status_code, json.loads(response.body)


class TestKeyErrorHandler:
    def test_missing_device_is_not_found(self):
        status, body = _call_key_error(
            KeyError("设备 'SW-01' 不存在，请先用 'device list' 查看当前设备列表")
        )

        assert status == 404
        assert "detail" not in body
        assert body["error"]["code"] == "NOT_FOUND"
        assert "不存在" in body["error"]["message"]

    def test_missing_field_is_validation_error(self):
        status, body = _call_key_error(KeyError("name"))

        assert status == 400
        assert "detail" not in body
        assert body["error"]["code"] == "VALIDATION_ERROR"
        message = body["error"]["message"]
        _assert_chinese_sentence(message)
        assert "name" in message
        assert message != "name"
