"""
巡检阈值检查模块
接收 parser 的解析结果，对照阈值判断是否需要告警
"""
from config import THRESHOLDS
from src.logger import logger


def _check_single_metric(value: float, threshold: int) -> bool:
    """
    判断单个指标值是否超标
    """
    # 实现判断逻辑
    # 如果 value 是 None（解析失败），不应该告警，返回 False
    # 如果 value > threshold，返回 True
    if value is None:
        return False
    elif value > threshold:
        return True
    return False

def check_threshold(parsed_result: dict, device_name: str) -> list[dict]:
    """
    检查解析结果中的所有指标是否超过阈值

    Args:
        parsed_result: parser.parse_inspection() 的返回值
                       例如 {"cpu_usage": 92.5, "metric": "CPU 使用率", "unit": "%"}
        device_name: 设备名，用于告警信息

    Returns:
        超标告警列表，为空表示一切正常
        例如 [{"device": "Core-SW", "metric": "CPU 使用率", "value": 92.5, "threshold": 80}]
    """
    alerts = []

    # 遍历 parsed_result 中的所有键值对
    for key, value in parsed_result.items():
        # 跳过非指标字段（metric, unit, raw, error 等不是数值的字段）
        if key in ("metric", "unit", "raw", "error"):
            continue

        # 找到对应的阈值
        # 从键名中提取指标类型，如 "cpu_usage" → "cpu"
        metric_type = key.replace("_usage", "")

        if metric_type not in THRESHOLDS:
            continue  # 没有配置阈值的指标，跳过

        threshold = THRESHOLDS[metric_type]

        # 判断是否超标
        if _check_single_metric(value, threshold):
            # 超过阈值 20% 以上是 P0（紧急），刚超标是 P1（关注）
            level = "P0" if value > threshold * 1.2 else "P1"

            alert = {
                "device": device_name,
                "metric": parsed_result.get("metric", metric_type),
                "value": value,
                "threshold": threshold,
                "level": level,
            }
            alerts.append(alert)
    return alerts


def check_all_devices(inspection_results: list[dict]) -> list[dict]:
    """
    对所有设备的巡检结果做阈值检查

    Args:
        inspection_results: 列表，每项为 {"device": 设备名, "results": [parser返回的dict, ...]}

    Returns:
        所有设备的告警清单
    """
    all_alerts = []

    for item in inspection_results:
        device_name = item["device"]
        for parsed in item["results"]:
            alerts = check_threshold(parsed, device_name)
            all_alerts.extend(alerts)

    # 统计
    if all_alerts:
        logger.warning(f"发现 {len(all_alerts)} 条告警:")
        for a in all_alerts:
            logger.warning(f"  [{a['device']}] {a['metric']}: {a['value']}% (阈值 {a['threshold']}%)")
    else:
        logger.info("所有指标正常，无告警")

    return all_alerts


if __name__ == "__main__":
    # 模拟 parser 返回的结果
    normal_cpu = {"cpu_usage": 23.5, "metric": "CPU 使用率", "unit": "%", "raw": "CPU Usage: 23.5%"}
    high_cpu = {"cpu_usage": 92.5, "metric": "CPU 使用率", "unit": "%", "raw": "CPU Usage: 92.5%"}
    normal_mem = {"memory_usage": 50.0, "metric": "内存使用率", "unit": "%", "raw": "Memory Using Percentage Is: 50%"}
    parse_failed = {"cpu_usage": None, "metric": "CPU 使用率", "unit": "%", "error": "解析失败"}

    print("正常 CPU (23.5%):", check_threshold(normal_cpu, "Test-Device"))
    print("高 CPU (92.5%):", check_threshold(high_cpu, "Test-Device"))
    print("正常内存 (50%):", check_threshold(normal_mem, "Test-Device"))
    print("解析失败的情况:", check_threshold(parse_failed, "Test-Device"))

    # 测试 check_all_devices
    print("\n综合测试:")
    test_data = [
        {"device": "Core-SW-01", "results": [normal_cpu, normal_mem]},
        {"device": "Access-SW-02", "results": [high_cpu, normal_mem]},
    ]
    all = check_all_devices(test_data)
    print(f"共发现 {len(all)} 条告警")
