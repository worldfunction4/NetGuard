"""python -m report 入口——直接运行报告生成

使用方法：
    python -m report <template_name> <data_json_path> <output_path>

示例：
    python -m report inspect.html data.json report.html
"""
import sys
from report.generator import generate_report
from report.excel import generate_excel_report


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        print("参数不足。用法: python -m report <模板名> <数据JSON路径> <输出路径>")
        sys.exit(1)

    template = sys.argv[1]
    data_path = sys.argv[2]
    output_path = sys.argv[3]

    import json
    data = json.loads(open(data_path, encoding="utf-8").read())
    if output_path.endswith(".xlsx"):
        generate_excel_report(data, output_path)
    else:
        generate_report(data, template, output_path)
    print(f"报告已生成 → {output_path}")
