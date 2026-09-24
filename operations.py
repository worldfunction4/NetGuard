"""备份、差异、巡检的编排。只返回结果，不退出进程，不读命令行。"""
from concurrent.futures import ThreadPoolExecutor, as_completed

from backup.collector import work_one
from backup.storage import _safe_name
from config import BACKUP_DIR, REPORT_DIR
from config.manager import validate_devices
from diff.comparator import generate_html_diff


def commands_for_device(device: dict, commands: dict) -> tuple[list, list]:
    """按 device_type 选命令。含 cisco 的设备只用 cisco 节，不用顶层华为命令。"""
    device_type = str(device.get("connection", {}).get("device_type", ""))
    if "cisco" in device_type.lower():
        cisco = commands.get("cisco")
        if not isinstance(cisco, dict):
            return [], []
        return list(cisco.get("config") or []), list(cisco.get("show") or [])
    return list(commands.get("config") or []), list(commands.get("show") or [])


def run_backup(devices, commands, logger) -> dict:
    """并发执行每台设备的配置与快照，并同步本次新保存的文件。

    返回 {"failed": int, "results": [{"name", "ok", "message"}], "saved": [str]}。
    不退出进程。返回值和日志里不放密码。
    """
    validate_devices(devices)
    failed = 0
    saved: list[str] = []
    results: list[dict] = []
    warned_missing_cisco = False

    with ThreadPoolExecutor(max_workers=2) as exe:
        future_names = {}
        for dev in devices:
            device_type = str(dev.get("connection", {}).get("device_type", ""))
            if "cisco" in device_type.lower() and not isinstance(commands.get("cisco"), dict):
                if not warned_missing_cisco:
                    logger.warning(
                        "commands.yaml 没有 cisco 节，Cisco 设备使用空命令列表，不会下发华为命令"
                    )
                    warned_missing_cisco = True
            config_commands, show_commands = commands_for_device(dev, commands)
            future = exe.submit(work_one, dev, config_commands, show_commands)
            future_names[future] = dev.get("name", "")

        for future in as_completed(future_names):
            result = future.result()
            for path in result.get("saved") or []:
                saved.append(str(path))
            ok = bool(result.get("ok"))
            if ok:
                message = result.get("message", "")
            else:
                failed += 1
                message = result.get("message", "设备执行失败")
            results.append({
                "name": future_names[future],
                "ok": ok,
                "message": message,
            })

    # 只上传本次新保存的文件；无 OSS 凭据时返回 False，不抛异常。
    # 在函数内部导入，方便测试替换 backup.cloud.sync_backup_to_cloud。
    from backup.cloud import sync_backup_to_cloud
    sync_backup_to_cloud(files=saved)

    return {"failed": failed, "results": results, "saved": saved}


def find_latest_complete_pair(device_dir):
    """在设备备份目录中找到最新的 before/after 完整配对。

    策略：从最新的 before 文件往前找，直到找到配对的 after 文件为止。
    这样即使最近一次 run 只保存了 before（run 中途失败），
    也能自动回退到上一次成功的完整配对，而不是直接跳过。

    返回 (before_path, after_path)，找不到则返回 (None, None)。
    """
    before_files = sorted(device_dir.glob("*_before.txt"), reverse=True)
    for before_file in before_files:
        timestamp_prefix = before_file.name.replace("_before.txt", "")
        after_file = device_dir / f"{timestamp_prefix}_after.txt"
        if after_file.exists():
            return before_file, after_file
    return None, None


def run_diff(devices, logger) -> list[dict]:
    """为每台设备找最新完整配对并生成 HTML 差异报告。

    每台返回 {"name", "ok", "report"}。没有备份目录或没有完整配对时
    ok 为 False，report 为 None。成功时 report 是 HTML 路径字符串。
    """
    validate_devices(devices)
    reports: list[dict] = []
    for dev in devices:
        name = dev["name"]
        # 使用 _safe_name 与 storage.py 保持一致的目录命名
        safe = _safe_name(name)
        device_dir = BACKUP_DIR / safe

        if not device_dir.exists():
            logger.warning(f"{name} 没有备份目录，跳过")
            reports.append({"name": name, "ok": False, "report": None})
            continue

        before_file, after_file = find_latest_complete_pair(device_dir)

        if before_file is None or after_file is None:
            logger.warning(f"{name} 找不到任何完整的 before/after 配对，跳过")
            reports.append({"name": name, "ok": False, "report": None})
            continue

        before_text = before_file.read_text(encoding="utf-8")
        after_text = after_file.read_text(encoding="utf-8")

        report_path = generate_html_diff(name, before_text, after_text)
        reports.append({"name": name, "ok": True, "report": str(report_path)})
    return reports


def run_inspect(devices, logger, workers: int = 4) -> dict:
    """并发巡检所有设备，生成 HTML 与 Excel 报告。

    返回 {"metrics": list, "html_path": str, "excel_path": str}。
    """
    validate_devices(devices)
    from datetime import datetime
    from report.inspector import inspect_all
    from report.generator import generate_report
    from report.excel import generate_excel_report
    from backup.cloud import notify_alert

    logger.info(f"开始巡检 {len(devices)} 台设备...")
    metrics = inspect_all(devices, max_workers=workers)

    # 触发告警推送（使用 inspector.py 已计算好的结构化告警）
    for dev in metrics:
        for alert in dev.get("alerts", []):
            if isinstance(alert, dict):
                notify_alert(dev["name"], alert["metric"], alert["value"], alert["threshold"])

    # 生成报告
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    html_path = str(REPORT_DIR / f"inspect_{timestamp}.html")
    generate_report(
        {"devices": metrics, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        "inspect.html",
        html_path,
    )
    logger.info(f"HTML 巡检报告 → {html_path}")

    excel_path = str(REPORT_DIR / f"inspect_{timestamp}.xlsx")
    generate_excel_report(metrics, excel_path)
    logger.info(f"Excel 巡检报告 → {excel_path}")

    return {"metrics": metrics, "html_path": html_path, "excel_path": excel_path}
