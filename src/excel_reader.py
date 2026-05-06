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
        # values_only=True：直接拿格心里的值，不要格子对象本身
        for row in sheet.iter_rows(min_row=2, values_only=True):
            # 考虑到整行都是空的情况
            if not any(row):
                continue

            # 利用“解包”技术，把这一行的三列数据分别赋值给三个变量
            name, ip, status = row

            # 将设备信息打包成字典
            device_info = {
            "name":name,
            "ip":ip,
            "status":status,
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
