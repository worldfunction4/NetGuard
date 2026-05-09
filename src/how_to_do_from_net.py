from pathlib import Path # 获取文件路径,同时读取文件
import openpyxl # 打开xlsx文件
from netmiko import ConnectHandler # 用来进行远程登录（SSH或Telnet）
import time # 用来生成时间戳
from config import * # 需要一个命令映射

# 读取xlsx文件函数
def get_excel():
    # 1. 拼接路径
    path = Path(__file__).parent / "devices.xlsx"
    
    # 2. 加载工作簿 (data_only=True 确保读取的是值)
    workbook = openpyxl.load_workbook(path, data_only=True)
    
    # 3. 获取工作表
    sheet = workbook["设备清单"]
    
    devices = []
    
    # 4. 遍历所有行
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not any(row):continue
        # 使用切片 [:6] 确保只取前四列，防止 Excel 里有多余空格列导致解包失败
        name, ip, username, password, device_type, status = row[:6] 
        devices.append({"name": name, "ip": ip, "username": username, "password": password, "device_type": device_type, "status": status})

    return devices
# 备份函数
def back_device_config(devices, command):

    device_name =devices["name"]

    # 用time打印
    print(f"[{time.strftime('%H:%M:%S')}]正在连接到设备{device_name}")
    try:
        with ConnectHandler(device_type=devices["device_type"],ip=devices["ip"],username=devices["username"],password=devices["password"],) as connect_net:
            print(f"[{time.strftime('%H:%M:%S')}]连接成功")
            output = connect_net.send_command(command)
            # 利用time生成时间戳
            # time.localtime()获取本地时间元组，strftime进行格式化
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
            backup_dir = Path(__file__).parent.parent / "backup_configs"
            backup_dir.mkdir(parents=True, exist_ok=True)
            filepath = backup_dir / f"{device_name}_{timestamp}.cfg"
            # 使用write_text写入文件
            filepath.write_text(output, encoding="utf-8")
            print(f"[{time.strftime('%H:%M:%S')}] 备份ok，文件保存至:{filepath.absolute()}")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}]备份出现问题：{e}")

def main():
    
    devices = get_excel()
    if devices == None:
        print("抱歉，未取得设备参数")
    else:
        for device in devices:
            cmd = COMMAND_MAP.get(device["device_type"])
            back_device_config(device, cmd)
if __name__ == "__main__":
    main()