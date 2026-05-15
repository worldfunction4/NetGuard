"""
Jinja2 报告生成器
组装设备列表、备份状态、差异摘要，渲染 HTML 报告
"""
import time
from pathlib import Path
import difflib
from jinja2 import Environment, FileSystemLoader

from src.logger import logger

# 路径常量
TEMPLATE_DIR = Path(__file__).parent / "templates"
BACKUP_DIR = Path("backup_configs")
OUTPUT_DIR = Path("reports")


def find_latest_backups(device_name, backup_dir=None):
    """
    扫描备份目录，找到指定设备最近两份备份文件

    Args:
        device_name: 设备名，用于匹配文件名前缀
        backup_dir: 备份目录路径，默认 backup_configs/

    Returns:
        list[Path]: 按时间倒序排列的备份文件路径（最新的在前），最多2个
    """
    if backup_dir is None:
        backup_dir = BACKUP_DIR

    backup_path = Path(backup_dir)
    if not backup_path.exists():
        return []

    # glob 匹配 {设备名}_*.cfg，按文件名（含时间戳）排序
    pattern = f"{device_name}_*.cfg"
    files = sorted(backup_path.glob(pattern), reverse=True)
    return files[:2]


def diff_configs(file1, file2):
    """
    对比两个配置文件，生成差异统计和内嵌 HTML 表格

    Args:
        file1: 旧配置文件 Path（作为 difflib 的 fromfile）
        file2: 新配置文件 Path（作为 difflib 的 tofile）

    Returns:
        dict: {"has_previous": bool, "added": int, "deleted": int,
               "diff_table_html": str, "old_file": str, "new_file": str}
    """
    if file1 is None or file2 is None:
        return {
            "has_previous": False,
            "added": 0, "deleted": 0,
            "diff_table_html": "",
            "old_file": "", "new_file": "",
        }

    try:
        lines1 = file1.read_text(encoding="utf-8").splitlines(keepends=True)
        lines2 = file2.read_text(encoding="utf-8").splitlines(keepends=True)
    except Exception as e:
        logger.error(f"读取备份文件失败: {e}")
        return {
            "has_previous": False,
            "added": 0, "deleted": 0,
            "diff_table_html": "",
            "old_file": "", "new_file": "",
        }

    # 用 difflib 生成内嵌的差异表格（HTML 片段，不是完整页面）
    differ = difflib.HtmlDiff(tabsize=4, wrapcolumn=80)
    table_html = differ.make_table(
        lines1, lines2,
        fromdesc=f"旧: {file1.name}",
        todesc=f"新: {file2.name}",
    )

    # 用 SequenceMatcher 统计增/删行数
    # 去掉行尾空白再比，避免无意义的 whitespace 差异
    text1 = [l.strip() for l in file1.read_text(encoding="utf-8").splitlines()]
    text2 = [l.strip() for l in file2.read_text(encoding="utf-8").splitlines()]
    matcher = difflib.SequenceMatcher(None, text1, text2)

    added = 0
    deleted = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            added += (j2 - j1)
        elif tag == "delete":
            deleted += (i2 - i1)
        elif tag == "replace":
            deleted += (i2 - i1)
            added += (j2 - j1)

    return {
        "has_previous": True,
        "added": added,
        "deleted": deleted,
        "diff_table_html": table_html,
        "old_file": file1.name,
        "new_file": file2.name,
    }


def generate_report(devices, backup_results, backup_dir=None):
    """
    组装所有数据，渲染 Jinja2 模板，返回完整 HTML 报告字符串

    Args:
        devices: 设备字典列表（来自 excel_reader.get_device_data）
        backup_results: 备份结果字典（来自 backup_all_devices 返回值）
        backup_dir: 备份目录路径

    Returns:
        str: 完整的 HTML 报告
    """
    if backup_dir is None:
        backup_dir = BACKUP_DIR

    # 构建备份结果索引：{设备名: 结果字典}
    result_map = {}
    for r in backup_results.get("results", []):
        result_map[r["device"]] = r

    # 为每台设备构建报告数据
    device_reports = []
    for device in devices:
        name = device["name"]
        result = result_map.get(name, {})
        backup_status = result.get("status", "")

        # 查找最近两份备份，生成差异数据
        latest_backups = find_latest_backups(name, backup_dir)
        if len(latest_backups) >= 2:
            # files 按时间倒序：latest_backups[0] 最新，latest_backups[1] 次新
            diff_data = diff_configs(latest_backups[1], latest_backups[0])
        else:
            diff_data = {
                "has_previous": False,
                "added": 0, "deleted": 0,
                "diff_table_html": "",
                "old_file": "", "new_file": "",
            }

        device_reports.append({
            "name": name,
            "ip": device.get("ip", ""),
            "device_type": device.get("device_type", ""),
            "status": device.get("status", ""),
            "backup_status": backup_status,
            "backup_file": result.get("file", ""),
            "backup_reason": result.get("reason", ""),
            "diff": diff_data,
        })

    # Jinja2 模板渲染
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("report.html")

    context = {
        "report_time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "device_count": len(devices),
        "backup_summary": {
            "total": backup_results.get("total", 0),
            "success": backup_results.get("success", 0),
            "failed": backup_results.get("failed", 0),
        },
        "devices": device_reports,
    }

    logger.info(f"报告数据组装完成，共 {len(device_reports)} 台设备")
    return template.render(context)


def save_report(html_content, output_dir=None):
    """
    将 HTML 报告保存到文件

    Args:
        html_content: 完整 HTML 字符串
        output_dir: 输出目录，默认 reports/

    Returns:
        Path: 保存的文件路径
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"NetGuard_报告_{timestamp}.html"
    filepath = output_path / filename

    filepath.write_text(html_content, encoding="utf-8")
    logger.info(f"报告已保存 → {filepath}")
    return filepath
