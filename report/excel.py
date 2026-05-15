"""
Excel 巡检报告生成器
将设备信息和备份状态写入格式化的 Excel 文件，适合存档、打印和分析
"""
import time
from pathlib import Path

import openpyxl
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, NamedStyle
)
from openpyxl.utils import get_column_letter

from src.logger import logger

OUTPUT_DIR = Path("reports")

# ── 配色（与 HTML 报告统一） ──────────────────────────
HEADER_FILL = PatternFill(start_color="1A1A2E", end_color="1A1A2E", fill_type="solid")
HEADER_FONT = Font(name="微软雅黑", bold=True, color="FFFFFF", size=11)

SUCCESS_FILL = PatternFill(start_color="D1FAE5", end_color="D1FAE5", fill_type="solid")
SUCCESS_FONT = Font(name="微软雅黑", bold=True, color="065F46", size=10)

FAILED_FILL = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
FAILED_FONT = Font(name="微软雅黑", bold=True, color="991B1B", size=10)

NORMAL_FONT = Font(name="微软雅黑", size=10)
TITLE_FONT = Font(name="微软雅黑", bold=True, size=16, color="1A1A2E")
SUBTITLE_FONT = Font(name="微软雅黑", size=10, color="64748B")

THIN_BORDER = Border(
    left=Side(style="thin", color="E5E7EB"),
    right=Side(style="thin", color="E5E7EB"),
    top=Side(style="thin", color="E5E7EB"),
    bottom=Side(style="thin", color="E5E7EB"),
)
CENTER_ALIGN = Alignment(horizontal="center", vertical="center")
LEFT_ALIGN = Alignment(horizontal="left", vertical="center")


def _apply_border_and_align(ws, row, col_count, alignment=LEFT_ALIGN):
    """给一行所有单元格加边框和对齐"""
    for c in range(1, col_count + 1):
        cell = ws.cell(row, c)
        cell.border = THIN_BORDER
        cell.alignment = alignment


def generate_excel_report(devices, backup_results, output_dir=None):
    """
    生成格式化的 Excel 巡检报告

    Args:
        devices: 设备字典列表（来自 excel_reader.get_device_data）
        backup_results: 备份结果字典（来自 backup_all_devices 返回值）
        output_dir: 输出目录，默认 reports/

    Returns:
        Path: 保存的文件路径
    """
    if output_dir is None:
        output_dir = OUTPUT_DIR

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "巡检报告"

    # ── 列宽预设 ──────────────────────────────────
    col_widths = [18, 18, 16, 12, 14, 50]
    # cols: A=设备名称, B=IP, C=设备类型, D=状态, E=备份结果, F=文件/原因
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    # ── 第1行：标题 ────────────────────────────────
    ws.merge_cells("A1:F1")
    title_cell = ws.cell(row=1, column=1, value="NetGuard 设备巡检报告")
    title_cell.font = TITLE_FONT
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 36

    # ── 第2行：生成时间 ────────────────────────────
    report_time = time.strftime("%Y-%m-%d %H:%M:%S")
    ws.merge_cells("A2:F2")
    time_cell = ws.cell(row=2, column=1, value=f"生成时间：{report_time}")
    time_cell.font = SUBTITLE_FONT
    time_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 22

    # ── 第4行：汇总卡片 ────────────────────────────
    summary_row = 4
    total = backup_results.get("total", 0)
    success = backup_results.get("success", 0)
    failed = backup_results.get("failed", 0)

    ws.merge_cells(f"A{summary_row}:B{summary_row}")
    total_cell = ws.cell(row=summary_row, column=1,
                         value=f"设备总数：{total} 台")
    total_cell.font = Font(name="微软雅黑", bold=True, size=11, color="1A1A2E")

    success_cell = ws.cell(row=summary_row, column=3,
                           value=f"成功：{success} 台")
    success_cell.font = Font(name="微软雅黑", bold=True, size=11, color="10B981")

    failed_cell = ws.cell(row=summary_row, column=5,
                          value=f"失败：{failed} 台")
    failed_cell.font = Font(name="微软雅黑", bold=True, size=11, color="EF4444")

    # ── 第6行：表头 ────────────────────────────────
    header_row = 6
    headers = ["设备名称", "IP 地址", "设备类型", "状态", "备份结果", "备份文件 / 失败原因"]
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=header_row, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = CENTER_ALIGN
        cell.border = THIN_BORDER
    ws.row_dimensions[header_row].height = 28

    # ── 数据行 ──────────────────────────────────────
    # 构建结果索引
    result_map = {}
    for r in backup_results.get("results", []):
        result_map[r["device"]] = r

    data_start_row = header_row + 1
    for i, device in enumerate(devices):
        row = data_start_row + i
        name = device["name"]
        result = result_map.get(name, {})
        backup_status = result.get("status", "")

        # 基本信息
        ws.cell(row, 1, name)
        ws.cell(row, 2, device.get("ip", ""))
        ws.cell(row, 3, device.get("device_type", ""))
        ws.cell(row, 4, device.get("status", ""))

        # 根据备份状态填入不同内容和样式
        if backup_status == "success":
            ws.cell(row, 5, "成功")
            ws.cell(row, 6, result.get("file", ""))
            # 应用成功行样式
            for c in range(1, 7):
                cell = ws.cell(row, c)
                cell.fill = SUCCESS_FILL
                cell.font = Font(name="微软雅黑", size=10)
                cell.border = THIN_BORDER
                cell.alignment = LEFT_ALIGN if c > 1 else LEFT_ALIGN
            # 第5列"成功"用绿色粗体突出
            ws.cell(row, 5).font = SUCCESS_FONT

        elif backup_status == "failed":
            ws.cell(row, 5, "失败")
            ws.cell(row, 6, result.get("reason", ""))
            # 应用失败行样式
            for c in range(1, 7):
                cell = ws.cell(row, c)
                cell.fill = FAILED_FILL
                cell.font = Font(name="微软雅黑", size=10)
                cell.border = THIN_BORDER
                cell.alignment = LEFT_ALIGN if c > 1 else LEFT_ALIGN
            ws.cell(row, 5).font = FAILED_FONT

        else:
            ws.cell(row, 5, "未备份")
            ws.cell(row, 6, "")
            for c in range(1, 7):
                cell = ws.cell(row, c)
                cell.font = NORMAL_FONT
                cell.border = THIN_BORDER
                cell.alignment = LEFT_ALIGN if c > 1 else LEFT_ALIGN

        ws.row_dimensions[row].height = 22

    # ── 冻结表头 ────────────────────────────────────
    ws.freeze_panes = f"A{header_row + 1}"

    # ── 打印设置 ────────────────────────────────────
    ws.sheet_properties.pageSetUpPr = openpyxl.worksheet.properties.PageSetupProperties(fitToPage=True)
    ws.page_setup.orientation = "landscape"

    # ── 保存 ────────────────────────────────────────
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"NetGuard_巡检报告_{timestamp}.xlsx"
    filepath = output_path / filename

    wb.save(str(filepath))
    logger.info(f"Excel 巡检报告已保存 → {filepath}")
    return filepath
