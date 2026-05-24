import logging
from pathlib import Path

"""日志模块，同时输出到控制台和文件"""
def setup_logger(name="NetGuard", level=logging.INFO):
    logger = logging.getLogger(name)  # 获取日志器
    logger.setLevel(level)  # 设置INFO以下的会被忽略

    # 防止重复添加 handler（多次调用 setup_logger 时会出现重复日志）
    if logger.handlers:
        return logger

    # 设置格式：时间|级别|消息
    fmt = logging.Formatter("%(asctime)s|%(levelname)s|%(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # 输出到控制台的日志
    console = logging.StreamHandler()
    console.setFormatter(fmt)

    # 输出到文件内
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)
    file_handle = logging.FileHandler(log_dir / "netguard.log", encoding="utf-8")
    file_handle.setFormatter(fmt)

    # 把两个 handler 绑定在同一个 logger 上
    logger.addHandler(console)
    logger.addHandler(file_handle)
    return logger