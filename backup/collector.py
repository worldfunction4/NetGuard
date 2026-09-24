"""配置采集模块——连接设备、执行命令、保存快照"""
import socket
import logging
from netmiko import NetMikoAuthenticationException, NetmikoBaseException, NetmikoTimeoutException
from backup.storage import save_result
from devices.base import get_driver, is_mock_mode

logger = logging.getLogger("NetGuard")


def check_reachable(host, port, timeout=5):
    """TCP 端口探测，快速判断设备是否可达"""
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return True
    except (socket.timeout, socket.error, OSError):
        return False


def work_one(device, config_commands, show_commands):
    """连接设备，执行配置和查看命令，保存 before/after 快照。

    返回 {"ok": bool, "message": str, "saved": list[str]}。
    saved 只放本次新保存的文件路径。配置回显含错误标记时 ok 为 False，
    但 before 以及失败后的 after 仍放进 saved，方便留证。
    """
    from datetime import datetime
    name = device["name"]
    conn_info = device["connection"]
    saved: list[str] = []
    # 同一次 run 的 before/after 共用同一个 run_id，保证 diff 配对正确
    _now = datetime.now()
    run_id = _now.strftime("%Y-%m-%d_%H-%M-%S_") + f"{_now.microsecond:06d}"

    def _fail(message: str) -> dict:
        logger.error(message)
        return {"ok": False, "message": message, "saved": saved}

    # mock 模式下跳过真实网络探测；真实设备才做 TCP 可达性检查
    is_mock = is_mock_mode() or conn_info.get("device_type", "").startswith("mock")
    if not is_mock and not check_reachable(conn_info["ip"], conn_info["port"]):
        return _fail(
            f"===== {name} =====\n设备不可达: {conn_info['ip']}:{conn_info['port']},请检查IP是否正确"
        )

    try:
        logger.info(f"开始连接 {name}（{conn_info['ip']}）")

        # 通过工厂拿到对应厂商的驱动，用 with 自动管理连接
        driver = get_driver(conn_info)
        with driver as conn:
            # 配置下发前 → before 快照
            before_parts = []
            for cmd in show_commands:
                before_parts.append(conn.send_command(cmd))
            before_content = "\n".join(before_parts)
            before_path = save_result(name, before_content, suffix="before", run_id=run_id)
            saved.append(str(before_path))
            logger.info(f"{name} before 快照已保存")

            # 推配置，记录输出并检查常见错误标记
            config_failed = False
            if config_commands:
                config_output = conn.send_config_set(config_commands)
                logger.debug(f"{name} 配置下发输出:\n{config_output}")
                error_markers = ("Error:", "Unrecognized command", "Invalid input")
                if any(marker in config_output for marker in error_markers):
                    config_failed = True
                    logger.error(f"{name} 配置下发输出包含错误标记，请检查:\n{config_output}")

            # 配置失败也继续保存 after，便于留证；ok 仍为 False
            after_parts = []
            for cmd in show_commands:
                after_parts.append(conn.send_command(cmd))
            after_content = "\n".join(after_parts)
            save_path = save_result(name, after_content, suffix="after", run_id=run_id)
            saved.append(str(save_path))
            logger.info(f"{name} after 快照已保存 → {save_path}")

            if config_failed:
                return _fail(f"===== {name} ===== 配置下发包含错误标记")

            return {"ok": True, "message": f"===== {name} ===== 完成", "saved": saved}

    except NetmikoTimeoutException:
        return _fail(f"===== {name} =====\n连接超时，设备不可达")
    except NetMikoAuthenticationException:
        return _fail(f"===== {name} =====\n认证失败，用户名或密码错误")
    except NetmikoBaseException as e:
        return _fail(f"===== {name} =====\nNetmiko 异常: {e}")
    except Exception as e:
        return _fail(f"===== {name} =====\n未知错误: {e}")
