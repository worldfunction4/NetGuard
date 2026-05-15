"""
NetGuard CLI 入口
支持子命令：
  （无参数）    打印设备列表
  backup       执行并发配置备份
"""
import yaml
import argparse
from pathlib import Path
from src.excel_reader import get_device_data
from src.logger import logger
from backup.collector import backup_all_devices


def main():
    parser = argparse.ArgumentParser(description="NetGuard 网络设备自动化运维工具")
    parser.add_argument("-c", "--config", default="configs/config.yaml", help="指定配置文件路径")

    # 新增一下子命令
    subparsers = parser.add_subparsers(dest="action", help="可用操作")
    backup_parser = subparsers.add_parser("backup", help="执行设备配置并发备份")

    args = parser.parse_args()

    # 读取配置文件
    config_path = Path(args.config)
    if not config_path.exists():
        logger.error(f"配置文件不存在: {config_path}，程序已停止")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        yaml_data = yaml.safe_load(f)
        devices_file = yaml_data["devices_file"]
        logger.info(f"读取配置成功，目标文件: {devices_file}")

    # 读取设备列表
    devices = get_device_data(devices_file)
    if not devices:
        logger.error("未能成功读取设备列表，程序已停止")
        return

    logger.info(f"成功读取 {len(devices)} 台设备")

    # 根据子命令分支
    if args.action == "backup":
        # 并发配置备份
        result = backup_all_devices(devices)
        print(f"\n{'='*40}")
        print(f"备份汇总：共 {result['total']} 台，成功 {result['success']} 台，失败 {result['failed']} 台")
        print(f"{'='*40}")
    else:
        # 默认：打印设备列表
        for device in devices:
            logger.info(
                f"设备: {device['name']:<15}"
                f"IP: {device['ip']:<15}"
                f"类型: {device['device_type']:<12}"
                f"状态: {device['status']}"
            )


if __name__ == "__main__":
    main()
