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
    """连接设备，执行配置和查看命令，保存 before/after 快照"""
    from datetime import datetime
    name = device["name"]
    conn_info = device["connection"]
    # 同一次 run 的 before/after 共用同一个 run_id，保证 diff 配对正确
    _now = datetime.now()
    run_id = _now.strftime("%Y-%m-%d_%H-%M-%S_") + f"{_now.microsecond:06d}"

    # mock 模式下跳过真实网络探测；真实设备才做 TCP 可达性检查
    is_mock = is_mock_mode() or conn_info.get("device_type", "").startswith("mock")
    if not is_mock and not check_reachable(conn_info["ip"], conn_info["port"]):
        return f"===== {name} =====\n设备不可达: {conn_info['ip']}:{conn_info['port']},请检查IP是否正确"

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
            save_result(name, before_content, suffix="before", run_id=run_id)
            logger.info(f"{name} before 快照已保存")

            # 推配置，记录输出并检查华为常见错误标记
            if config_commands:
                config_output = conn.send_config_set(config_commands)
                logger.debug(f"{name} 配置下发输出:\n{config_output}")
                error_markers = ("Error:", "Unrecognized command", "Invalid input")
                if any(marker in config_output for marker in error_markers):
                    logger.warning(f"{name} 配置下发输出包含错误标记，请检查:\n{config_output}")

            # 配置下发后 → after 快照
            after_parts = []
            for cmd in show_commands:
                after_parts.append(conn.send_command(cmd))
            after_content = "\n".join(after_parts)
            save_path = save_result(name, after_content, suffix="after", run_id=run_id)
            logger.info(f"{name} after 快照已保存 → {save_path}")

            return f"===== {name} ===== 完成"

    except NetmikoTimeoutException:
        logger.error(f"===== {name} =====\n连接超时，设备不可达")
        return None
    except NetMikoAuthenticationException:
        logger.error(f"===== {name} =====\n认证失败，用户名或密码错误")
        return None
    except NetmikoBaseException as e:
        logger.error(f"===== {name} =====\nNetmiko 异常: {e}")
        return None
    except Exception as e:
        logger.error(f"===== {name} =====\n未知错误: {e}")
        return None
