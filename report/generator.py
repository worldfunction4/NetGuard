"""Jinja2 HTML 巡检报告生成模块"""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

# 模板目录：与本文件同级的 templates/
_TEMPLATE_DIR = Path(__file__).parent / "templates"


def generate_report(data: dict, template_name: str, output_path: str) -> str:
    """
    用 Jinja2 模板渲染 HTML 报告。

    Args:
        data:          传入模板的数据字典（设备列表、生成时间等）
        template_name: templates/ 目录下的模板文件名，如 "inspect.html"
        output_path:   输出 HTML 文件的完整路径（自动创建父目录）

    Returns:
        输出文件的路径字符串
    """
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),  # 防止 XSS，HTML 模板自动转义
    )
    template = env.get_template(template_name)
    html = template.render(**data)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return str(out)
