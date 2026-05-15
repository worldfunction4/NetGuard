"""
NetGuard 全局配置常量
- 多厂商命令映射
- 并发参数
- 重试参数

"""
COMMAND_MAP = {
    "huawei": "display current-configuration",
    "hp_comware": "display current-configuration",
    "cisco_ios": "show running-config",
    "cisco_nxos": "show running-config",
    "juniper_junos": "show configuration", 
    "huawei_telnet": "display current-configuration",
}


MAX_WORKERS = 5       # 最大并发线程数（此数字由业界测出，保守起步，I/O 密集型可按需上调）
TIMEOUT = 30           # 单设备 SSH 连接超时秒数

# 重试参数（供 try_reconnect.py 使用）
MAX_RECONNECT = 3      # 最大重试次数
RETRY_TIME = 5         # 重试间隔秒数
