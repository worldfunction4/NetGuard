"""备份、巡检、对比和报告列表。只调用 operations 与 config，不自己连设备、不解析 YAML。"""
from fastapi import APIRouter

import config
from api.schemas import (
    BackupResponse,
    DiffItem,
    InspectResponse,
    strip_password,
)
from config.manager import load_commands, load_devices
from logger import setup_logger
from operations import run_backup, run_diff, run_inspect

router = APIRouter(tags=["jobs"])
logger = setup_logger()


@router.post("/jobs/backup", response_model=BackupResponse)
def backup_job() -> dict:
    """加载设备和命令后执行备份。失败台数放在结果里，不退出进程。"""
    summary = run_backup(load_devices(), load_commands(), logger)
    cleaned = strip_password(summary)
    results = []
    for item in cleaned.get("results") or []:
        if not isinstance(item, dict):
            continue
        message = item.get("message", "")
        if not isinstance(message, str):
            message = str(strip_password(message))
        results.append({
            "name": _as_text(item.get("name")),
            "ok": bool(item.get("ok")),
            "message": message,
        })
    saved = [str(path) for path in (cleaned.get("saved") or [])]
    return {
        "failed": int(cleaned.get("failed") or 0),
        "results": results,
        "saved": saved,
    }


@router.post("/jobs/inspect", response_model=InspectResponse)
def inspect_job() -> dict:
    """巡检全部设备。metrics 里如果带了 password 字段，删掉再返回。"""
    result = strip_password(run_inspect(load_devices(), logger))
    return {
        "metrics": result.get("metrics") or [],
        "html_path": _as_path(result.get("html_path")),
        "excel_path": _as_path(result.get("excel_path")),
    }


@router.post("/jobs/diff", response_model=list[DiffItem])
def diff_job() -> list[dict]:
    """为每台设备生成差异结果，只返回 name、ok、report。"""
    rows = []
    for item in run_diff(load_devices(), logger):
        report = item.get("report")
        rows.append({
            "name": _as_text(item.get("name")),
            "ok": bool(item.get("ok")),
            "report": None if report is None else str(report),
        })
    return rows


@router.get("/reports", response_model=list[str])
def list_reports() -> list[str]:
    """列出报告目录里的 .html 文件名。目录不存在时返回空列表。"""
    report_dir = config.REPORT_DIR
    if not report_dir.is_dir():
        return []
    names = [
        item.name
        for item in report_dir.iterdir()
        if item.is_file() and item.suffix.lower() == ".html"
    ]
    return sorted(names)


def _as_text(value) -> str:
    if value is None:
        return ""
    return str(value)


def _as_path(value) -> str:
    return _as_text(value)
