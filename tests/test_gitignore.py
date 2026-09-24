"""gitignore 回归：设备表 devices.xlsx 不应被入库"""

from pathlib import Path


def test_gitignore_contains_devices_xlsx():
    gitignore = Path(__file__).resolve().parents[1] / ".gitignore"
    active_lines = []
    for line in gitignore.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        active_lines.append(stripped)
    assert "devices.xlsx" in active_lines
