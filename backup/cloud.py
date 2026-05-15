"""
云端集成模块
将报告上传 OSS + 异常时钉钉告警，完整的云网融合流程
"""
from pathlib import Path

from src.logger import logger
from backup.oss import upload_report
from backup.notify import DingTalkNotifier


def cloud_sync(html_path, excel_path, backup_results):
    """
    云端同步：上传报告到 OSS，发现异常时推送钉钉告警

    Args:
        html_path: HTML 报告路径
        excel_path: Excel 报告路径
        backup_results: backup_all_devices() 的返回值 {total, success, failed, results}

    Returns:
        dict: {oss_html, oss_excel, alert_sent}
    """
    oss_urls = {"oss_html": None, "oss_excel": None, "alert_sent": False}

    # 1. 上传 HTML 报告
    html_url = upload_report(html_path)
    if html_url:
        logger.info(f"HTML 报告已上传: {html_url}")
        oss_urls["oss_html"] = html_url
    else:
        logger.warning("HTML 报告 OSS 上传跳过（无凭证或上传失败）")

    # 2. 上传 Excel 报告
    excel_url = upload_report(excel_path)
    if excel_url:
        logger.info(f"Excel 报告已上传: {excel_url}")
        oss_urls["oss_excel"] = excel_url
    else:
        logger.warning("Excel 报告 OSS 上传跳过（无凭证或上传失败）")

    # 3. 检查是否有失败设备，有则发送钉钉告警
    failed_count = backup_results.get("failed", 0)
    if failed_count > 0:
        notifier = DingTalkNotifier()
        if notifier._enabled:
            # 构建告警内容
            lines = [
                f"## NetGuard 备份异常告警",
                f"",
                f"- 备份总数：**{backup_results['total']}** 台",
                f"- 成功：**{backup_results['success']}** 台",
                f"- 失败：**{failed_count}** 台",
                f"",
                f"### 失败设备详情",
            ]
            for r in backup_results.get("results", []):
                if r.get("status") == "failed":
                    lines.append(f"- {r['device']}: {r.get('reason', '未知')}")

            # 如有 OSS 链接，附在告警里
            if oss_urls["oss_html"]:
                lines.append(f"")
                lines.append(f"[查看完整报告]({oss_urls['oss_html']})")

            text = "\n".join(lines)
            ok = notifier.send_markdown("NetGuard 备份异常告警", text)
            if ok:
                oss_urls["alert_sent"] = True

    return oss_urls


if __name__ == "__main__":
    # 独立运行：python -m backup.cloud
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))

    logger.info("进入 Mock 模式测试云端同步...")
    result = cloud_sync(
        html_path="reports/nonexistent.html",
        excel_path="reports/nonexistent.xlsx",
        backup_results={
            "total": 5,
            "success": 4,
            "failed": 1,
            "results": [
                {"device": "SW-Core", "status": "success"},
                {"device": "R1-Edge", "status": "failed", "reason": "连接超时"},
            ],
        },
    )
    print(f"结果: {result}")
