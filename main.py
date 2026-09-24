import argparse
import getpass
import sys
from logger import setup_logger
from config import load_dotenv
from operations import run_backup, run_diff, run_inspect
from config.manager import (
    load_devices, load_commands,
    add_device, update_device, remove_device, list_devices,
    add_command, remove_command, list_commands,
    COMMAND_SECTIONS, validate_devices,
)


def cmd_run(args, logger, devices, commands):
    """子命令 run：连接设备，推配置，保存 before/after 快照"""
    summary = run_backup(devices, commands, logger)
    for item in summary["results"]:
        if item["ok"]:
            logger.info(item.get("message", ""))
        else:
            logger.error(item.get("message", "设备执行失败"))
    if summary["failed"] > 0:
        sys.exit(1)


def cmd_diff(_args, logger, devices):
    """子命令 diff：为每台设备找最新完整配对，生成 HTML 差异报告"""
    for item in run_diff(devices, logger):
        if item["ok"]:
            logger.info(f"{item['name']} 差异报告 → {item['report']}")


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
            print("当前没有可以进行配置的设备（请检查 devices.yaml 或 devices.xlsx）。")
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
        except Exception as e:
            logger.error(str(e))

    elif action == "update":
        name = args.name
        field = args.field
        value = args.value
        # 密码不从命令行取值，避免进入 shell 历史和进程列表
        if field == "password":
            if value is not None:
                logger.warning("命令行密码已忽略，请在提示中输入")
            value = getpass.getpass("密码（直接回车取消）: ").strip()
            # 空输入取消。q 去掉首尾空格后是合法密码，会写入。
            if not value:
                print("取消操作")
                print("密码不能为空")
                return
        else:
            if value is None:
                logger.error(f"字段 '{field}' 缺少新值，请在命令行提供")
                return
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
            if field == "password":
                logger.info(f"设备 '{name}' 字段 password 已更新")
            else:
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
        for section in COMMAND_SECTIONS:
            print(f"\n[{section}]")
            items = _items_for_command_section(cmds, section)
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
        except Exception as e:
            logger.error(str(e))

    elif action == "remove":
        section = args.section
        cmd = args.cmd
        try:
            remove_command(section, cmd)
            logger.info(f"命令 '{cmd}' 已从 [{section}] 区块移除")
        except Exception as e:
            logger.error(str(e))


def _items_for_command_section(cmds: dict, section: str) -> list:
    """command list 用：顶层区块直接取，Cisco 区块从 cisco 子字典取。"""
    if section in ("config", "show"):
        items = cmds.get(section) or []
        return items if isinstance(items, list) else []
    cisco = cmds.get("cisco")
    if not isinstance(cisco, dict):
        return []
    kind = "config" if section == "cisco.config" else "show"
    items = cisco.get(kind) or []
    return items if isinstance(items, list) else []


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
    # 密码不回显。直接回车是空密码，拒绝。q 去掉首尾空格后原样保存。
    password = getpass.getpass("  密码（直接回车取消）: ")
    if not password.strip():
        print("  密码不能为空")
        return None
    password = password.strip()
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
    run_inspect(devices, logger, workers=getattr(args, "workers", 4))


def _load_devices_from_source(source: str, source_file: str | None = None):
    """根据 --source 参数加载设备列表（yaml 或 excel），统一转为标准格式。"""
    if source == "excel":
        excel_path = source_file or "devices.xlsx"
        try:
            from src.excel_reader import read_devices
            return read_devices(excel_path)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"设备列表文件不存在: {excel_path}\n"
                f"请创建 {excel_path}（首行: name | ip | port | device_type | username | password）\n"
                f"或使用 --source yaml 从 devices.yaml 加载。"
            )
        except ValueError as e:
            raise ValueError(str(e))

    # 默认 yaml
    try:
        return load_devices()
    except FileNotFoundError:
        raise FileNotFoundError(
            "设备配置文件不存在: devices.yaml\n"
            "请复制 devices.example.yaml 为 devices.yaml 并填写真实信息，\n"
            "或使用 --source excel --source-file devices.xlsx 从 Excel 加载。"
        )
    except ValueError:
        raise  # load_devices() 的消息已包含 Excel 提示，直接上抛


def _add_source_args(parser):
    """为子命令添加 --source / --source-file 参数"""
    parser.add_argument(
        "--source", choices=["yaml", "excel"], default="yaml",
        help="设备列表来源：yaml（默认 devices.yaml）或 excel（devices.xlsx）",
    )
    parser.add_argument(
        "--source-file", default=None,
        help="当 --source excel 时的 .xlsx 路径（默认 devices.xlsx）",
    )


def main():
    # 加载 .env（必须在日志之前）
    load_dotenv()

    # 初始化日志
    logger = setup_logger()

    # 解析命令行参数
    parser = argparse.ArgumentParser(
        prog="netguard",
        description="NetGuard 网络设备自动化运维工具"
    )
    subparsers = parser.add_subparsers(dest="command", help="可用子命令")

    # 子命令 run：连设备推配置
    run_parser = subparsers.add_parser("run", help="连接设备，推配置，保存快照")
    _add_source_args(run_parser)

    # 子命令 diff：生成差异报告
    diff_parser = subparsers.add_parser("diff", help="对最新 before/after 快照生成 HTML 差异报告")
    _add_source_args(diff_parser)

    # 子命令 inspect：设备巡检
    inspect_parser = subparsers.add_parser("inspect", help="巡检所有设备，生成 HTML + Excel 报告")
    inspect_parser.add_argument("--workers", type=int, default=4, help="并发线程数（默认 4）")
    _add_source_args(inspect_parser)

    # 子命令 device：管理设备列表
    dev_parser = subparsers.add_parser("device", help="管理 devices.yaml 设备列表")
    dev_sub = dev_parser.add_subparsers(dest="action", help="操作")
    dev_sub.add_parser("list", help="列出所有设备")
    dev_sub.add_parser("add",  help="交互式添加一台设备")
    dev_update = dev_sub.add_parser("update", help="修改设备某个字段")
    dev_update.add_argument("name",  help="要修改的设备名")
    dev_update.add_argument("field", help="字段名（如 ip / port / username / password / location）")
    dev_update.add_argument("value", nargs="?", help="新值（修改 password 时请在提示中输入）")
    dev_remove = dev_sub.add_parser("remove", help="删除一台设备")
    dev_remove.add_argument("name", help="要删除的设备名")

    # 子命令 command：管理命令列表
    cmd_parser = subparsers.add_parser("command", help="管理 commands.yaml 命令列表")
    cmd_sub = cmd_parser.add_subparsers(dest="action", help="操作")
    cmd_sub.add_parser("list", help="列出所有命令")
    cmd_add = cmd_sub.add_parser("add", help="添加一条命令")
    cmd_add.add_argument("section", choices=list(COMMAND_SECTIONS), help="目标区块")
    cmd_add.add_argument("cmd", help="命令字符串，如 'dis cpu-usage'")
    cmd_rm = cmd_sub.add_parser("remove", help="删除一条命令")
    cmd_rm.add_argument("section", choices=list(COMMAND_SECTIONS), help="目标区块")
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

    # ── 其余子命令需要加载设备列表（yaml 或 excel）────────────────────
    # diff / inspect 不读命令表；只有 run 才 load_commands()
    source = getattr(args, "source", "yaml")
    source_file = getattr(args, "source_file", None)
    try:
        devices = _load_devices_from_source(source, source_file)
    except (FileNotFoundError, ValueError) as e:
        logger.error(str(e))
        return

    commands = None
    if args.command == "run":
        try:
            commands = load_commands()
        except (FileNotFoundError, ValueError) as e:
            logger.error(str(e))
            return

    # 校验设备列表。失败只记日志并返回，不把异常抛到进程外，也不改退出码。
    try:
        validate_devices(devices)
    except ValueError as e:
        logger.error(str(e))
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
