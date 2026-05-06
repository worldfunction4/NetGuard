import logging
from pathlib import Path

def setup_logging():
    # 使用pathlib准备日志文件夹
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(exist_ok=True) #不存在则创建一个
    log_file = log_dir / "automation.log"

    # 获取logger
    logger = logging.getLogger("myscript")
    logger.setLevel(logging.DEBUG)

    # 创建FileHandler,记录所有细节
    file_handler = logging.FileHandler(log_file,encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # 创建StreamHandler,只看重要INFO
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # 定义统一标签格式
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

logger = setup_logging() # 进行初始化