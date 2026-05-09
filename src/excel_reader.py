"""
读取 Excel 文件，获取设备信息，返回设备列表
Excel 文件的格式需要满足以下要求：
1. 第一行是表头，列名为：name, ip, username, password, device_type, status
2. 第二行开始是设备信息，每行对应一个设备，列顺序为：name, ip, username, password, device_type, status

"""

import openpyxl
from openpyxl.utils.exceptions import InvalidFileException
from .logger import logger

def get_device_data(file_path):
    devices = [] # 用队列来存储读取到的数据
    # 异常处理
    try:
        # 尝试通过路径打开文件。data_only=True 表示只读结果，不要公式
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet = wb.active
        # min_row=2：从第 2 行开始扫描，避开第一行的表头
        # values_only=True：直接拿格里的值，而不要格子对象本身
        for row in sheet.iter_rows(min_row=2, values_only=True):
            # 考虑到整行都是空的情况
            if not any(row):
                continue

            # 利用解包技术，把这一行的六列数据分别赋值给六个变量
            # Excel 列顺序：name, ip, username, password, device_type, status
            name, ip, username, password, device_type, status = row[:6]

            # 将设备信息打包成字典
            device_info = {
                "name": name,
                "ip": ip,
                "username": username,
                "password": password,
                "device_type": device_type,
                "status": status,
            }

            # 将字典内容装入devices
            devices.append(device_info)
        return devices
    
    # 路径不对
    except FileNotFoundError:
        logger.error(f"抱歉，未能成功找到:{file_path},请重新检查一下文件路径是否正确？")
        return None # 调用函数失败
    # 格式不对
    except InvalidFileException:
        logger.error(f"{file_path}似乎不是正确的xlsx格式?还请重新检查一下")
        return None # 失败
    # 其他错误
    except Exception as e:
        logger.error(f"抱歉，似乎遇到的突发情况:{e}")
        return None # 失败
