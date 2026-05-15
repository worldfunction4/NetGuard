"""
目标是把backup_configs文件夹里面最后两个备份进行对比（改用HTML格式），目前有两个测试txt
1 获取backup_configs文件夹位置并读取路径
1.1 添加命令行一次性读取两个文件？表现为 
2.将Path对象进行转化成文件
3.用difflib对两个文本进行对比
4.打印出来

目前功能做出，计划比较时间戳，如果file1早于file2会报错？或者加上自动识别新旧文件功能

"""
from src.logger import logger
import difflib as df
from pathlib import Path
# 一次性传入两个参数？用来读取两个文件内容

def read_to_compare(file1, file2):
    path1 = Path(__file__).parent.parent / "backup_configs" / file1
    path2 = Path(__file__).parent.parent / "backup_configs" / file2
    # 读取文件并且转换类型
    try:  
        with open(path1, "r",encoding="utf-8") as file1, open(path2, "r", encoding="utf-8") as file2:
            lines1= file1.readlines()
            lines2= file2.readlines()
    except FileNotFoundError as e:
        logger.error(f"{path1}\n{path2}\n文件未找到: {e}")
        lines1 = []
        lines2 = []
    except Exception as e:
        logger.error(f"读取文件时发生错误: {e}")

        lines1 = []
        lines2 = []

    # 进行初始化
    diff = df.HtmlDiff()
    diff_conext = diff.make_file(
        lines1, lines2, fromdesc=str(path1), todesc=str(path2)
    )
    
        # 选择将html文件保存在logs内
    try:
        path = Path(__file__).parent.parent / "logs" / "compare_config.html"
        with open(path, "w", encoding="utf-8") as f:
            f.write(diff_conext)
    # 文件不存在
    except FileNotFoundError as no:
        logger.error(f"文件不存在：{no}")
    except Exception as e:
        logger.error(f"未知错误{e}")

if __name__ == "__main__":
    file1= input("请输入最新的文件名：")
    file2= input("请输入最后备份的文件名：")
    read_to_compare(file1, file2)