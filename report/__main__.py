"""
独立运行入口：python -m report

流程：读取设备列表 → 执行备份 → 差异对比 → 渲染模板 → 输出 HTML 报告
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path，以便 import NetGuard 模块
sys.path.insert(0, str(Path(__file__).parent.parent))

import yaml

from src.excel_reader import get_device_data
from src.logger import logger
from backup.collector import backup_all_devices
from report.generator import generate_report, save_report


def main():
    # 读取 YAML 配置获取 devices_file 路径
    config_path = Path("configs/config.yaml")
    if not config_path.exists():
        logger.error(f"配置文件不存在: {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    devices_file = config.get("devices_file", "devices.xlsx")

    # 1. 读取设备列表
    devices = get_device_data(devices_file)
    if not devices:
        logger.error("设备列表为空，无法生成报告")
        return

    logger.info(f"读取到 {len(devices)} 台设备")

    # 2. 执行并发备份
    logger.info("开始备份...")
    backup_results = backup_all_devices(devices)

    # 3. 生成 HTML 报告
    logger.info("正在生成报告...")
    html = generate_report(devices, backup_results)

    # 4. 保存报告
    filepath = save_report(html)

    print(f"\n{'='*50}")
    print(f"  报告已生成: {filepath}")
    print(f"  共 {backup_results['total']} 台 | 成功 {backup_results['success']} | 失败 {backup_results['failed']}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
