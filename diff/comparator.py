# diff/comparator.py -- 用 difflib 生成 HTML 差异报告

from pathlib import Path
from datetime import datetime
import difflib
import html
import re

from config import REPORT_DIR


def _safe_name(name: str) -> str:
    """净化设备名，用于文件名和 HTML 属性，防止路径穿越和注入"""
    safe = re.sub(r'[/\\<>:"|?*\x00-\x1f]', "_", name)
    safe = safe.replace("..", "__").strip(". ")
    return safe or "unknown_device"

"""
对比 before 和 after 文本，生成带颜色高亮的 HTML 差异报告。

参数：
    device_name: 设备名，比如核心交换机
    before:      配置下发前的输出文本
    after:       配置下发后的输出文本
    base_dir:    报告保存目录，默认用 config.py 里定义的 REPORT_DIR
                 （绝对路径，不管从哪个目录运行脚本都能找到正确的位置）

返回：
    报告文件的 Path 对象
"""

def generate_html_diff(device_name: str, before: str, after: str, base_dir: Path | None = None) -> Path:
    # 净化设备名：用于文件名（路径穿越防护）和 HTML 描述（XSS 防护）
    safe = _safe_name(device_name)
    safe_html = html.escape(device_name)   # 只用于 fromdesc/todesc 文本显示

    # 把文本按行拆开，difflib 需要列表格式
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)

    # 生成 HTML 差异表格（左列 before，右列 after，红删绿增）
    differ = difflib.HtmlDiff(wrapcolumn=80)
    html_content = differ.make_file(
        before_lines,
        after_lines,
        fromdesc=f"{safe_html} - 变更前",
        todesc=f"{safe_html} - 变更后",
        context=True,   # 只显示有差异的行及其上下文，不显示全文
        numlines=3,     # 差异行上下各显示 3 行上下文
    )

    # 保存到 reports/ 目录
    # base_dir 默认用 config.py 里的 REPORT_DIR（基于 __file__ 的绝对路径）
    # 而不是相对路径 "reports"，这样无论从哪个目录运行脚本结果都一样
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    report_dir = Path(base_dir) if base_dir is not None else REPORT_DIR
    report_dir.mkdir(parents=True, exist_ok=True)

    # 文件名用净化后的 safe，不用原始 device_name
    file_path = report_dir / f"{safe}_{timestamp}_diff.html"
    file_path.write_text(html_content, encoding="utf-8")

    return file_path
