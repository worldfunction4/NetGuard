"""巡检 HTML 回归：告警渲染 text，ok 且有告警的设备不算正常"""

import re
from datetime import datetime

from report.generator import generate_report


def _card_num(html: str, label: str) -> int:
    match = re.search(
        rf'<div class="num">(\d+)</div>\s*<div class="label">{label}</div>',
        html,
    )
    assert match, f"找不到汇总卡片：{label}"
    return int(match.group(1))


def _device(name, ip, alerts):
    return {
        "name": name,
        "ip": ip,
        "location": "测试机房",
        "role": "core",
        "device_type": "mock_huawei",
        "cpu_percent": 90 if alerts else 10,
        "memory_percent": 40,
        "interfaces_up": 2,
        "interfaces_down": 0,
        "status": "ok",
        "alerts": alerts,
        "collected_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


class TestInspectTemplate:
    def test_alert_dict_text_and_warn_count(self, tmp_path):
        """修复前会把告警字典原文打进页面，并把有告警的 ok 设备算进正常"""
        alert_text = "CPU使用率 90% 超过阈值 80%"
        devices = [
            _device("SW-Alert", "192.0.2.51", [{
                "metric": "cpu_percent",
                "value": 90,
                "threshold": 80,
                "text": alert_text,
            }]),
            _device("SW-Ok", "192.0.2.52", []),
        ]
        out = tmp_path / "inspect.html"
        generate_report(
            {"devices": devices, "generated_at": "2026-09-24 22:00:00"},
            "inspect.html",
            str(out),
        )
        html = out.read_text(encoding="utf-8")

        assert alert_text in html
        assert "{'metric'" not in html
        assert '{"metric"' not in html
        assert "&#39;metric&#39;" not in html
        assert _card_num(html, "正常") == 1
        assert _card_num(html, "告警") == 1
