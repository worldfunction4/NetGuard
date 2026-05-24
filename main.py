from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
from backup.collector import work_one
from diff.comparator import generate_html_diff
from logger import setup_logger
from config import BACKUP_DIR, REPORT_DIR
from config.manager import (
    load_devices, load_commands,
    add_device, update_device, remove_device, list_devices,
    add_command, remove_command, list_commands,
)


def cmd_run(args, logger, devices, commands):
    """子命令 run：连接设备，推配置，保存 before/after 快照"""
    config_commands = commands["config"]
    show_commands = commands["show"]

    with ThreadPoolExecutor(max_workers=2) as exe:
        futures = [exe.submit(work_one, dev, config_commands, show_commands) for dev in devices]
        for future in as_completed(futures):
            result = future.result()
            if result:
                logger.info(result)


def _find_latest_complete_pair(device_dir):
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


def cmd_diff(_args, logger, devices):
    """子命令 diff：为每台设备找最新完整配对，生成 HTML 差异报告"""
    import re

    for dev in devices:
        name = dev["name"]
        # 目录名与 storage.py 保持一致：使用净化后的设备名
        safe = re.sub(r'[/\\<>:"|?*\x00-\x1f]', "_", name).replace("..", "__").strip(". ") or "unknown_device"
        device_dir = BACKUP_DIR / safe

        if not device_dir.exists():
            logger.warning(f"{name} 没有备份目录，跳过")
            continue

        before_file, after_file = _find_latest_complete_pair(device_dir)

        if before_file is None or after_file is None:
            logger.warning(f"{name} 找不到任何完整的 before/after 配对，跳过")
            continue

        before_text = before_file.read_text(encoding="utf-8")
        after_text = after_file.read_text(encoding="utf-8")

        report_path = generate_html_diff(name, before_text, after_text)
        logger.info(f"{name} 差异报告 → {report_path}")


def cmd_device(args, logger):
    """子命令 device：管理设备列表（增删改查）"""
    action = args.action

    if action == "list":
        try:
            rows = list_devices()
        except (FileNotFoundError, ValueError) as e:
            logger.error(str(e))
            return
        if not rows:
            print("当前没有可以进行配置的设备。")
            return
        print(f"\n{'设备名':<14} {'IP':<17} {'端口':<6} {'类型':<18} {'位置':<12} {'角色'}")
        print("-" * 80)
        for r in rows:
            print(f"{r['name']:<14} {r['ip']:<17} {str(r['port']):<6} {r['device_type']:<18} {r['location']:<12} {r['role']}")

    elif action == "add":
        # 交互式收集字段
        entry = _prompt_device_entry()
        if entry is None:
            return
        try:
            add_device(entry)
            logger.info(f"设备 '{entry['name']}' 添加成功")
        except (ValueError, Exception) as e:
            logger.error(str(e))

    elif action == "update":
        name = args.name
        field = args.field
        value = args.value
        # port 字段强制转 int
        if field == "port":
            try:
                value = int(value)
            except ValueError:
                logger.error(f"port 必须是整数，当前值: {value!r}")
                return
        # connection 层字段和顶层字段
        conn_fields = {"ip", "port", "device_type", "username", "password", "timeout"}
        updates = {"connection": {field: value}} if field in conn_fields else {field: value}
        try:
            update_device(name, updates)
            logger.info(f"设备 '{name}' 字段 '{field}' 已更新为 {value!r}")
        except (KeyError, ValueError) as e:
            logger.error(str(e))

    elif action == "remove":
        name = args.name
        confirm = input(f"确认删除设备 '{name}'？(y/N) ").strip().lower()
        if confirm != "y":
            print("取消操作")
            return
        try:
            remove_device(name)
            logger.info(f"设备 '{name}' 已删除")
        except (KeyError, ValueError) as e:
            logger.error(str(e))


def cmd_command(args, logger):
    """子命令 command：管理 commands.yaml 中的命令列表（增删查）"""
    action = args.action

    if action == "list":
        try:
            cmds = list_commands()
        except (FileNotFoundError, ValueError) as e:
            logger.error(str(e))
            return
        for section in ("config", "show"):
            print(f"\n[{section}]")
            items = cmds.get(section, [])
            if items:
                for i, c in enumerate(items, 1):
                    print(f"  {i}. {c}")
            else:
                print("  （空）")

    elif action == "add":
        section = args.section
        cmd = args.cmd
        try:
            add_command(section, cmd)
            logger.info(f"命令 '{cmd}' 已添加到 [{section}] 区块")
        except (ValueError, Exception) as e:
            logger.error(str(e))

    elif action == "remove":
        section = args.section
        cmd = args.cmd
        try:
            remove_command(section, cmd)
            logger.info(f"命令 '{cmd}' 已从 [{section}] 区块移除")
        except (ValueError, Exception) as e:
            logger.error(str(e))


def _prompt_device_entry() -> dict | None:
    """交互式收集新设备信息，返回设备字典；用户中途取消则返回 None。"""
    print("\n─── 添加新设备 ────────────────────────────")
    print("（直接回车接受括号内的默认值；输入 q 取消）\n")

    def ask(prompt, default=""):
        val = input(f"  {prompt}" + (f" [{default}]" if default else "") + ": ").strip()
        if val.lower() == "q":
            return None
        return val if val else default

    name = ask("设备名称（如 SW-Core-01）")
    if name is None:
        return None
    ip = ask("IP 地址")
    if ip is None:
        return None
    port_raw = ask("端口", "23")
    if port_raw is None:
        return None
    try:
        port = int(port_raw)
    except ValueError:
        print(f"  端口必须是整数，输入值: {port_raw!r}")
        return None
    dtype = ask("设备类型（huawei_telnet / huawei_ssh / cisco_ios / mock_huawei）", "huawei_telnet")
    if dtype is None:
        return None
    username = ask("用户名", "admin")
    if username is None:
        return None
    password = ask("密码")
    if password is None:
        return None
    location = ask("位置（可选）", "") or ""
    role = ask("角色（可选，如 core / access）", "") or ""

    entry = {
        "name": name,
        "connection": {
            "device_type": dtype,
            "ip": ip,
            "port": port,
            "username": username,
            "password": password,
            "timeout": 30,
        },
    }
    if location:
        entry["location"] = location
    if role:
        entry["role"] = role
    return entry


def cmd_inspect(args, logger, devices):
    """子命令 inspect：并发巡检所有设备，生成 HTML + Excel 报告"""
    from datetime import datetime
    from report.inspector import inspect_all
    from report.generator import generate_report
    from report.excel import generate_excel_report
    from backup.cloud import notify_alert
    from config import THRESHOLDS

    logger.info(f"开始巡检 {len(devices)} 台设备...")
    metrics = inspect_all(devices, max_workers=getattr(args, "workers", 4))

    # 触发告警推送（钉钉）
    for dev in metrics:
        for key, threshold in THRESHOLDS.items():
            val = dev.get(key)
            if val is not None and val >= threshold:
                notify_alert(dev["name"], key, val, threshold)

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


def main():
    # 初始化日志
    logger = setup_logger()

    # 解析命令行参数
    parser = argparse.ArgumentParser(
        prog="netguard",
        description="NetGuard 网络设备自动化运维工具"
    )
    subparsers = parser.add_subparsers(dest="command", help="可用子命令")

    # 子命令 run：连设备推配置
    subparsers.add_parser("run", help="连接设备，推配置，保存快照")

    # 子命令 diff：生成差异报告
    subparsers.add_parser("diff", help="对最新 before/after 快照生成 HTML 差异报告")

    # 子命令 inspect：设备巡检
    inspect_parser = subparsers.add_parser("inspect", help="巡检所有设备，生成 HTML + Excel 报告")
    inspect_parser.add_argument("--workers", type=int, default=4, help="并发线程数（默认 4）")

    # 子命令 device：管理设备列表
    dev_parser = subparsers.add_parser("device", help="管理 devices.yaml 设备列表")
    dev_sub = dev_parser.add_subparsers(dest="action", help="操作")
    dev_sub.add_parser("list", help="列出所有设备")
    dev_sub.add_parser("add",  help="交互式添加一台设备")
    dev_update = dev_sub.add_parser("update", help="修改设备某个字段")
    dev_update.add_argument("name",  help="要修改的设备名")
    dev_update.add_argument("field", help="字段名（如 ip / port / username / password / location）")
    dev_update.add_argument("value", help="新值")
    dev_remove = dev_sub.add_parser("remove", help="删除一台设备")
    dev_remove.add_argument("name", help="要删除的设备名")

    # 子命令 command：管理命令列表
    cmd_parser = subparsers.add_parser("command", help="管理 commands.yaml 命令列表")
    cmd_sub = cmd_parser.add_subparsers(dest="action", help="操作")
    cmd_sub.add_parser("list", help="列出所有命令")
    cmd_add = cmd_sub.add_parser("add", help="添加一条命令")
    cmd_add.add_argument("section", choices=["config", "show"], help="目标区块")
    cmd_add.add_argument("cmd", help="命令字符串，如 'dis cpu-usage'")
    cmd_rm = cmd_sub.add_parser("remove", help="删除一条命令")
    cmd_rm.add_argument("section", choices=["config", "show"], help="目标区块")
    cmd_rm.add_argument("cmd", help="命令字符串")

    args = parser.parse_args()

    # ── device / command 子命令不需要加载设备列表，直接分发 ──────────────────
    if args.command == "device":
        if not args.action:
            dev_parser.print_help()
            return
        cmd_device(args, logger)
        return

    if args.command == "command":
        if not args.action:
            cmd_parser.print_help()
            return
        cmd_command(args, logger)
        return

    # ── 其余子命令需要加载 devices.yaml + commands.yaml ────────────────────
    try:
        devices  = load_devices()
        commands = load_commands()
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        return

    # 校验 devices 结构（manager 已做基础校验，这里补充字段完整性）
    for dev in devices:
        if not isinstance(dev, dict) or "name" not in dev or "connection" not in dev:
            logger.error(f"devices.yaml 中某设备缺少 name 或 connection 字段: {dev}")
            return
        if not dev.get("name", "").strip():
            logger.error(f"devices.yaml 中存在设备名为空的条目: {dev}")
            return
        conn = dev["connection"]
        for field in ("device_type", "ip", "username", "password", "port"):
            if field not in conn:
                logger.error(f"设备 {dev['name']} 的 connection 缺少必填字段: {field}")
                return
        if not isinstance(conn["port"], int):
            logger.error(f"设备 {dev['name']} 的 port 应为整数，当前值: {conn['port']!r}")
            return

    # 根据子命令分发
    if args.command == "run":
        cmd_run(args, logger, devices, commands)
    elif args.command == "diff":
        cmd_diff(args, logger, devices)
    elif args.command == "inspect":
        cmd_inspect(args, logger, devices)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()