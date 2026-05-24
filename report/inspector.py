"""设备巡检模块——采集 CPU / 内存 / 接口等状态指标"""
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from backup.collector import check_reachable
from devices.base import get_driver, is_mock_mode
from config import THRESHOLDS

logger = logging.getLogger("NetGuard")


def inspect_device(device: dict) -> dict:
    """连接单台设备，采集巡检指标，返回标准化指标字典"""
    name = device["name"]
    conn_info = device["connection"]
    collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    base = {
        "name": name,
        "ip": conn_info.get("ip", ""),
        "device_type": conn_info.get("device_type", ""),
        "location": device.get("location", ""),
        "role": device.get("role", ""),
        "collected_at": collected_at,
        "cpu_percent": None,
        "memory_percent": None,
        "interfaces_up": None,
        "interfaces_down": None,
        "alerts": [],
    }

    # mock 模式下跳过真实网络探测；真实设备才做 TCP 可达性检查
    is_mock = is_mock_mode() or conn_info.get("device_type", "").startswith("mock")
    if not is_mock and not check_reachable(conn_info["ip"], conn_info["port"]):
        logger.warning(f"{name} 不可达，跳过巡检")
        return {**base, "status": "unreachable"}

    try:
        driver = get_driver(conn_info)
        with driver as conn:
            commands = conn.get_inspect_commands()
            outputs = {cmd: conn.send_command(cmd) for cmd in commands}
            metrics = conn.parse_metrics(outputs)

        alerts = _check_thresholds(metrics)
        if alerts:
            logger.warning(f"{name} 巡检告警: {'; '.join(alerts)}")

        return {**base, "status": "ok", **metrics, "alerts": alerts}

    except Exception as e:
        logger.error(f"{name} 巡检失败: {e}")
        return {**base, "status": "error", "error": str(e)}


def inspect_all(devices: list, max_workers: int = 4) -> list:
    """并发巡检所有设备，返回指标列表"""
    results = [None] * len(devices)
    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        future_to_idx = {exe.submit(inspect_device, dev): i for i, dev in enumerate(devices)}
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            results[idx] = future.result()
    return results


def _check_thresholds(metrics: dict) -> list:
    """对照 config.THRESHOLDS 检查指标，返回告警文本列表"""
    alerts = []
    for key, threshold in THRESHOLDS.items():
        val = metrics.get(key)
        if val is not None and val >= threshold:
            alerts.append(f"{key} = {val}%（阈值 {threshold}%）")
    return alerts
