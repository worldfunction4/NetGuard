"""
巡检解析模块
用正则表达式从网络设备 CLI 输出中提取 CPU、内存等结构化指标
"""
import re
from src.logger import logger


def parse_cpu(output: str, device_type: str) -> dict:
    """
    从 CPU 相关命令输出中提取使用率
    """
    try:
        if "huawei" in device_type:
            # 从华为 output 中提取 "CPU Usage : 23.5%" 里的数字
            # 用 re.search(r'...', output) 匹配 "CPU Usage" 后面的小数
            result = r"CPU Usage\s*:\s*(\d+(?:\.\d+)?)%"
            match = re.search(result, output)
            if match:
                return {"cpu_usage": float(match.group(1)), "raw": match.group(0).strip()}
            else:
                return {"cpu_usage": None, "error": "未匹配到华为 CPU 使用率"}

        elif "cisco" in device_type:
            # 从 Cisco output 提取 "five seconds: 15%" 里的第一个数字
            # 用 re.search(r'...', output) 匹配 "five seconds:" 后面的数字
            pattern = r"five seconds:\s*(\d+(?:\.\d+)?)%"
            match = re.search(pattern, output)
            if match:
                return {"cpu_usage": float(match.group(1)), "raw": match.group(0).strip()}
            else:
                return {"cpu_usage": None, "error": "未匹配到 Cisco CPU 使用率"}

        else:
            return {"cpu_usage": None, "error": f"不支持的设备类型: {device_type}"}

    except Exception as e:
        logger.error(f"解析 CPU 输出失败: {e}")
        return {"cpu_usage": None, "error": str(e)}


def parse_memory(output: str, device_type: str) -> dict:
    """
    从内存相关命令输出中提取使用率
    """
    try:
        if "huawei" in device_type:
            # 从华为 output 提取 "Memory Using Percentage Is: 50%" 里的数字
            # 用 re.search() 匹配 "Percentage Is:" 后面的整数或小数
            match = re.search(r"Percentage Is:\s*(\d+(?:\.\d+)?)%", output)
            if match:
                return {"memory_usage": float(match.group(1)), "raw": match.group(0).strip()}
            else:
                return {"memory_usage": None, "error": "未匹配到华为内存使用率"}

        elif "cisco" in device_type:
            # Cisco 通常没有单条内存命令，用 show memory 或 show processes memory
            # 简化处理：尝试匹配 "Used:" 或 "Free:" 行
            match = None  # ← 替换这行（可选）
            if match:
                return {"memory_usage": float(match.group(1)), "raw": match.group(0).strip()}
            else:
                return {"memory_usage": None, "error": "Cisco 内存解析暂未实现"}

        else:
            return {"memory_usage": None, "error": f"不支持的设备类型: {device_type}"}

    except Exception as e:
        logger.error(f"解析内存输出失败: {e}")
        return {"memory_usage": None, "error": str(e)}


def parse_inspection(output: str, command: str, device_type: str) -> dict:
    """
    解析单条巡检命令的输出，根据命令类型路由到对应解析器
    """
    command_lower = command.lower()

    if "cpu" in command_lower:
        result = parse_cpu(output, device_type)
        result["metric"] = "CPU 使用率"
        result["unit"] = "%"
        return result

    elif "memory" in command_lower or "mem" in command_lower:
        result = parse_memory(output, device_type)
        result["metric"] = "内存使用率"
        result["unit"] = "%"
        return result

    else:
        return {
            "metric": "未知",
            "value": None,
            "unit": "",
            "raw": output[:200],
            "error": f"暂不支持解析命令: {command}",
        }


if __name__ == "__main__":
    # 模拟华为输出
    huawei_cpu_output = """
CPU Usage Stat. Cycle: 60 (Second)
CPU Usage         : 23.5% Max: 45%
CPU Usage Stat. Time: 2023-06-15 10:30:00
"""
    huawei_mem_output = """
System Total Memory Is: 2048 Mbytes
Total Memory Used Is: 1024 Mbytes
Memory Using Percentage Is: 50%
"""

    print("测试华为 CPU 解析:", parse_inspection(huawei_cpu_output, "display cpu-usage", "huawei"))
    print("测试华为内存解析:", parse_inspection(huawei_mem_output, "display memory-usage", "huawei"))
