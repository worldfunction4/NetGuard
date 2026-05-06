import yaml
import argparse
from pathlib import Path

from src.excel_reader import get_device_data
from src.logger import logger

def main():
    parser = argparse.ArgumentParser(description="NetGuard 巡检脚本")
    parser.add_argument("-c", "--config", default="configs/config.yaml",help="指定配置文件")
    # 获取命令行
    args = parser.parse_args()

    # 读取一下菜单
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
            practice_data = yaml_data["devices_file"]
            logger.info(f"读取配置成功,目标文件:{practice_data}")
    else:
        logger.error("配置文件不存在，程序已停止")
        return
    
    list_file = get_device_data(practice_data)
    if list_file:
        logger.info(f"成功，发现{len(list_file)}个设备")
        for i in list_file:
            logger.info(f"设备:{i["name"]:<10}\nIP:{i["ip"]:<13}\n状态:{i["status"]}\n\n")
    else:
        logger.info("未能成功读取")

if __name__ == "__main__":
    main()
