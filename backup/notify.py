"""钉钉 Webhook 告警模块——巡检异常时推送消息

无 Webhook 时自动降级：只记录日志，不抛出异常，不影响主流程。
"""
import logging
import os
from datetime import datetime

logger = logging.getLogger("NetGuard")


def send_dingtalk(webhook_url: str, message: str) -> bool:
    """
    通过钉钉自定义机器人 Webhook 发送告警消息（text 类型）。

    Args:
        webhook_url: 钉钉机器人的 Webhook 地址（从 .env 读取）
        message:     告警正文，纯文本

    Returns:
        发送成功返回 True，失败返回 False
    """
    if not webhook_url:
        logger.warning("DINGTALK_WEBHOOK 未配置，跳过告警推送（消息已记录在日志中）")
        return False

    try:
        import requests
        payload = {"msgtype": "text", "text": {"content": message}}
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if data.get("errcode") == 0:
            logger.info("钉钉告警发送成功")
            return True

        # 钉钉 API 返回非 0 错误码
        logger.error(f"钉钉 API 错误: errcode={data.get('errcode')}, errmsg={data.get('errmsg')}")
        return False

    except Exception as e:
        logger.error(f"钉钉告警发送失败: {e}")
        return False


def format_alert_message(device_name: str, metric: str, value: int, threshold: int) -> str:
    """
    格式化告警消息文本。

    示例输出：
        【NetGuard 告警】SW-Core-01
        指标：cpu_percent = 85%（阈值 80%）
        时间：2026-05-24 10:30:00
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        f"【NetGuard 告警】{device_name}\n"
        f"指标：{metric} = {value}%（阈值 {threshold}%）\n"
        f"时间：{now}"
    )


def send_alert_if_configured(device_name: str, metric: str, value: int, threshold: int) -> bool:
    """
    从环境变量读取 Webhook，格式化并发送告警。
    无 Webhook 配置时仅记录日志。

    Returns:
        True 表示成功推送（或无需推送），False 表示推送失败
    """
    webhook = os.environ.get("DINGTALK_WEBHOOK", "").strip()
    msg = format_alert_message(device_name, metric, value, threshold)

    # 无论是否推送，始终把告警写入日志
    logger.warning(f"告警: {device_name} | {metric}={value}% (阈值 {threshold}%)")

    return send_dingtalk(webhook, msg)
