"""
并发配置采集模块
使用 ThreadPoolExecutor 实现多设备并发备份，单设备失败不影响整体
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

from config import COMMAND_MAP, MAX_WORKERS, TIMEOUT
from backup.storage import save_config
from src.logger import logger


def _backup_one(device: dict) -> dict:
    """
    备份单台设备配置（线程安全，永不抛异常）

    这是异常隔离的核心：任何失败都以字典形式返回，不向上传播异常，
    确保单个设备的问题不会中断其他设备的备份任务。
    参数:
        Args:
            device: 设备字典，包含 name, ip, username, password, device_type, status

        Returns:
            {"device": 设备名, "status": "success"/"failed", "file": 文件路径或 None, "reason": 失败原因或 None}
        """


    device_name = device["name"]
    logger.info(f"[{time.strftime('%H:%M:%S')}] 正在连接到设备{device_name}")
    try:
        command = COMMAND_MAP.get(device["device_type"])
        if command == None:  # [new] is None vs == None：功能上没区别，但 is None 更快（直接比较内存地址，不走 __eq__ 魔术方法）且不会被重载 __eq__ 的类坑到。PEP 8 推荐 is None 检查
            return {"device": device["name"], 
                    "status": "failed", 
                    "reason": f"不支持的设备类型: {device['device_type']}"}
        with ConnectHandler(device_type=device["device_type"], 
                            ip=device["ip"],
                            username=device["username"],
                            password=device["password"]) as conn:
            
            logger.info(f"[{time.strftime('%H:%M:%S')}] 连接成功^_^")
            output = conn.send_command(command) # 获取配置的输出
            filepath = save_config(device_name, output) # 备份文件（包括了时间戳）
            return {"device": device_name, "status": "success", "file": str(filepath)}
    except NetmikoAuthenticationException as ne:
        logger.error(f"认证失败了:( \n {ne}")
        return {"device": device_name, "status": "failed", "reason": "认证失败"}
    except NetmikoTimeoutException as nt:
        logger.error(f"似乎超时了:( \n {nt}")
        return {"device": device_name, "status": "failed", "reason": "连接超时"}
    except Exception as e:
        logger.error(f"出现未知错误!\n {e}")
        return {"device": device_name, "status": "failed", "reason": str(e)}


def backup_all_devices(devices: list[dict], max_workers: int = MAX_WORKERS) -> dict:
    """
    并发备份多台设备配置

    用 ThreadPoolExecutor 线程池并发执行，as_completed 按完成顺序(不是先进先出原则)收集结果。
    线程池用 with 语句确保无论成功失败都正确释放资源。
    参数：
        Args:
            devices: 设备字典列表
            max_workers: 最大并发线程数，默认取 config.py 中的 MAX_WORKERS

        Returns:
            {"total": 总数, "success": 成功数, "failed": 失败数, "results": [各设备结果...]}
        """


    if not devices:
        logger.warning("设备列表为空，跳过备份")
        return {"total": 0, "success": 0, "failed": 0, "results": []}

    logger.info(f"开始并发备份 {len(devices)} 台设备，最大并发 {max_workers}")
    results = []

    # executor.submit() 将每个设备提交到线程池，立即返回 future 对象（非阻塞）
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 构建 future→设备名 映射，方便结果关联
        future_to_device = {
            executor.submit(_backup_one, device): device["name"]
            for device in devices
        }

        # as_completed: 哪台先完成先处理哪台（不按提交顺序）
        for future in as_completed(future_to_device):
            device_name = future_to_device[future]
            try:
                result = future.result()  # 获取 _backup_one 的返回值
                results.append(result)
                if result["status"] == "success":
                    logger.info(f"[{device_name}] 备份成功:) → {result.get('file', '')}")
                else:
                    logger.error(f"[{device_name}] 备份失败:( → {result.get('reason', '未知')}")
            except Exception as e:
                # 即使 _backup_one 意外抛异常也不会中断整体
                logger.error(f"[{device_name}] 未预期的错误：{e}")
                results.append({"device": device_name, "status": "failed", "reason": str(e)})

    # 汇总统计
    success_count = sum(1 for r in results if r["status"] == "success")
    failed_count = sum(1 for r in results if r["status"] == "failed")
    logger.info(f"备份完成：成功 {success_count} 台，失败 {failed_count} 台")

    return {
        "total": len(devices),
        "success": success_count,
        "failed": failed_count,
        "results": results,
    }
