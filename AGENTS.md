# Repository Guidelines

## Project Structure & Module Organization

NetGuard is a small Python CLI for network device configuration collection and diff reporting. The entry point is `main.py`, which dispatches the `run` and `diff` subcommands. Device connection logic lives in `devices/`, with shared driver behavior in `devices/base.py`, Huawei Netmiko support in `devices/huawei.py`, and Cisco support in `devices/cioso.py` (implemented, untested on real devices). Backup collection and file persistence live in `backup/`; HTML diff generation lives in `diff/`. Runtime inputs are `devices.yaml` (gitignored, copy from `devices.example.yaml`) and `commands.yaml`. Runtime outputs go to `backups_config/`, `reports/`, and `logs/`; treat these as generated data, not source. Tests live in `tests/`.

## Build, Test, and Development Commands

Create and activate a virtual environment before installing dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Useful local commands:

```powershell
python main.py --help
python main.py run
python main.py diff
python -m compileall -q .
```

`run` connects to configured devices, captures before/after command output, and applies commands from `commands.yaml`. `diff` generates HTML reports from the latest backup pair. `compileall` is the current lightweight syntax check.

## Coding Style & Naming Conventions

Use Python 3 style with 4-space indentation, descriptive snake_case names for functions and variables, and PascalCase for classes such as `HuaweiDriver`. Keep modules focused: drivers in `devices/`, backup workflow in `backup/`, reporting in `diff/`. Prefer `pathlib.Path` for filesystem paths and UTF-8 for text files. Keep comments short and useful, especially around network-device behavior or file pairing logic.

## Testing Guidelines

There is no formal test suite yet. Add tests under `tests/` using `pytest` when introducing behavior that can be verified without real devices, such as YAML validation, backup filename pairing, and diff file generation. Name tests `test_<module>.py` and functions `test_<behavior>()`. Mock Netmiko connections rather than requiring live network devices in automated tests.

## Commit & Pull Request Guidelines

This repository currently has no commit history, so no existing convention can be inferred. Use short imperative commit messages, for example `Add backup pairing validation` or `Ignore generated reports`. Pull requests should describe the operational impact, list commands run, and call out any changes to `devices.yaml`, `commands.yaml`, or network-device behavior.

## Security & Configuration Tips

Do not commit real device passwords, logs, reports, or backups. `devices.yaml` is gitignored — copy `devices.example.yaml` to `devices.yaml` and fill in real credentials locally. Sanitize device IPs and outputs before sharing reports outside the team.
