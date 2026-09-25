# NetGuard —— Network Device Automation Tool

A batch network device management tool for SMBs, addressing three pain points: **manual per-device config backup, untraceable changes, and manual inspection**.

> [中文文档 (Chinese README)](README_CN.md)

## Core Features

| Feature | Description |
|---|---|
| Batch Config Backup | Read device list → SSH/Telnet connect → Save before/after snapshots |
| Config Version Diff | difflib generates HTML diff reports — red for deletions, green for additions, changes fully traceable |
| Device Inspection | Collect CPU / Memory / Interface status, generate HTML + Excel reports |
| Threshold Alerts | Auto-log when thresholds exceeded; optional DingTalk Webhook push |
| Multi-Cloud Integration | Alibaba Cloud OSS backup sync (optional). Uploads only files saved by this `run`; skipped silently without credentials |
| Auto-Retry | Timeouts and `OSError` retry up to 5 times. Auth failures and config errors (such as an invalid device type) are not retried |
| Mock Demo | `NETGUARD_MOCK=1` skips real devices. The device list must still contain at least one entry |
| Web API | FastAPI exposes devices, backup, diff, inspection, and report filenames. Open `/docs` in a browser |

## Quick Start

```bash
# 1. Clone the project
git clone https://github.com/worldfunction4/NetGuard.git
cd NetGuard

# 2. Create virtual environment and install dependencies
python -m venv .venv
.venv\Scripts\Activate.ps1              # Windows PowerShell
pip install -r requirements.txt

# 3. Prepare device list (choose one)
# Option A: Copy the YAML example
Copy-Item devices.example.yaml devices.yaml   # PowerShell
# CMD users: copy devices.example.yaml devices.yaml

# Option B: Use Excel (header row: name | ip | port | device_type | username | password)
# Create devices.xlsx, then add --source excel to all subcommands

# 4. Edit devices.yaml with your device info
# Or use interactive mode:
python main.py device add

# 5. Quick demo in Mock mode (no real devices needed)
$env:NETGUARD_MOCK = "1"
python main.py run          # Simulate backup
python main.py diff         # Generate diff report
python main.py inspect      # Run inspection
```

### Install as CLI Command

```powershell
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install as global command (-e = editable dev mode, code changes take effect immediately)
pip install -e .

# Verify
netguard --help
```

> After installation, `netguard` replaces `python main.py`, e.g.: `netguard run`.

### Uninstall

The uninstall method depends on how you installed. **Choose the steps matching your installation method.**

#### Method A: pip-installed CLI Command

```powershell
# 1. Exit virtual environment (if activated)
deactivate

# 2. Uninstall CLI command
pip uninstall netguard -y

# 3. Remove virtual environment (optional — if .venv is not used for other projects)
Remove-Item -Recurse .venv

# 4. Remove runtime files (optional — backups, reports, logs)
Remove-Item -Recurse backups_config, reports, logs -ErrorAction SilentlyContinue

# 5. Remove entire project directory (optional — full cleanup)
cd ..
Remove-Item -Recurse NetGuard
```

> Step 2 is the core — it removes the `netguard` command. Steps 3~5 are optional: keep the code for later reinstall, or wipe everything clean.

#### Method B: Docker Installation

```powershell
# 1. Stop and remove container (if running)
docker compose down

# 2. Remove Docker image
docker image rm netguard-netguard
# If unsure about the image name, check with: docker images

# 3. Remove runtime files (mounted from local directory)
Remove-Item -Recurse backups_config, reports, logs -ErrorAction SilentlyContinue

# 4. Full cleanup — remove project directory
cd ..
Remove-Item -Recurse NetGuard
```

> Default Docker image name is `netguard-netguard`. Verify with `docker images | findstr netguard`.

#### Method C: Using `python main.py` only (never ran `pip install`)

```powershell
# Simply delete the project directory — no system-level residue
cd ..
Remove-Item -Recurse NetGuard
```

### Docker Method (No Python Environment Required)

```bash
# Build the image
docker compose build

# Copy sample config
Copy-Item devices.example.yaml devices.yaml

# One-click demo (mock mode enabled by default)
docker compose run --rm netguard run
docker compose run --rm netguard diff
docker compose run --rm netguard inspect

# Interactive device addition
docker compose run --rm netguard device add

# Output files are in the local directory — open directly in browser
start reports\*.html
```

> For real device connections, remove `NETGUARD_MOCK=1` from `docker-compose.yml` and ensure the container can reach device IPs (default bridge network usually works).

## Command Reference

```
Subcommand                           Description
────────────────────────────────────────────────────
run [--source yaml|excel]            Connect to devices, push config, save snapshots
diff [--source yaml|excel]           Generate HTML config diff report
inspect [--workers N] [--source ...] Inspect all devices, generate HTML + Excel
device list                          List all devices
device add                           Add device interactively
device update <name> <field> [val]   Modify a field (password: press Enter to cancel; q is a valid password)
device remove <name>                 Remove a device
command list                         List all commands
command add <section> <cmd>          config/show = Huawei; cisco.config / cisco.show = Cisco
command remove <section> <cmd>       Remove a command from those same sections
```

> `--source excel --source-file devices.xlsx` loads devices from Excel (header: name | ip | port | device_type | username | password). Default loads from `devices.yaml`. `devices.xlsx` contains passwords and is listed in `.gitignore`.
>
> Top-level `config` / `show` in `commands.yaml` are sent only to Huawei devices. Cisco devices use the `cisco` section in the same file. `diff` and `inspect` do not read the command file. If any device fails, `run` exits with code 1. An invalid device list is logged and the CLI returns; the Web API responds with 400 before connecting.

## Web API

Backup, diff, and inspection are orchestrated in `operations.py`. The CLI and the API call the same functions.

```powershell
$env:NETGUARD_MOCK = "1"
.\.venv\Scripts\python.exe -m uvicorn api.app:app --port 8000
```

Open http://127.0.0.1:8000/docs and call the endpoints from that page.

| Method | Path | Description |
|---|---|---|
| GET | `/devices` | List devices. The response has no passwords |
| POST | `/devices` | Add one device |
| POST | `/jobs/backup` | Run backup |
| POST | `/jobs/diff` | Generate diff reports |
| POST | `/jobs/inspect` | Run inspection |
| GET | `/reports` | List generated HTML filenames |

Errors use `{"error": {"code": "...", "message": "..."}}`. Press `Ctrl+C` in the server window when finished.

## Mock Mode

Set `NETGUARD_MOCK=1` to run backup, diff, and inspection without connecting to real devices. `devices.yaml` must still list at least one device; copy `devices.example.yaml` first. MockDriver returns simulated Huawei/Cisco output, and CPU/memory values vary slightly.

```powershell
# PowerShell
$env:NETGUARD_MOCK = "1"
python main.py run
python main.py diff
python main.py inspect
start reports\           # Open reports directory in Explorer
```

```cmd
REM CMD
set NETGUARD_MOCK=1
python main.py run
python main.py diff
python main.py inspect
start reports\
```

> You can also copy `.env.example` to `.env` and add `NETGUARD_MOCK=1` to avoid setting the env var manually each time.

For real environments, simply remove the env var and fill in real IPs in `devices.yaml`. — **Config and mock are completely separated; zero code changes to switch.**

## Multi-Vendor Support

```
                ┌──────────────────┐
                │    BaseDriver    │  ← Abstract base class
                │  connect()       │     Defines unified interface
                │  send_command()  │
                │  send_config()   │
                └────────┬─────────┘
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │HuaweiDriver│ │CiscoDriver│ │MockDriver │
    │ (Netmiko) │  │ (Netmiko) │  │ (built-in)│
    └──────────┘  └──────────┘  └──────────┘
```

To add a new vendor, just inherit `BaseDriver` and register a `device_type` branch in the `get_driver()` factory function. The upper-level collector/inspector **needs zero code changes**.

## Project Structure

```
NetGuard/
├── main.py                # CLI entry point, argparse command dispatch
├── operations.py          # Backup, diff, and inspection orchestration shared by CLI and API
├── logger.py              # Logging module (console + file dual output)
├── api/
│   ├── app.py             # FastAPI app and the shared error shape
│   ├── devices.py         # Device list endpoints
│   ├── jobs.py            # Backup, inspection, diff, and report list
│   └── schemas.py         # Request and response fields
├── devices/
│   ├── base.py            # BaseDriver abstract class + get_driver factory
│   ├── huawei.py          # Huawei VRP driver
│   ├── cisco.py           # Cisco IOS driver
│   ├── mock.py            # Mock driver (demo without devices)
│   └── try_connect.py     # Retry (network errors, max 5; config errors are not retried)
├── backup/
│   ├── collector.py       # Config collection (connect → before → push → after)
│   ├── storage.py         # File storage (organized by device/timestamp)
│   ├── oss.py             # Alibaba Cloud OSS upload (optional)
│   ├── notify.py          # DingTalk Webhook alerts (optional)
│   └── cloud.py           # Cloud integration entry point
├── diff/
│   └── comparator.py      # difflib HTML diff report
├── report/
│   ├── inspector.py       # Inspection collection (concurrent, metric parsing)
│   ├── generator.py       # Jinja2 HTML report rendering
│   ├── excel.py           # openpyxl Excel report (dual sheets, styled)
│   └── templates/
│       └── inspect.html   # Inspection report Jinja2 template
├── config/
│   ├── __init__.py          # Path constants + thresholds + .env loading
│   └── manager.py           # YAML config management for devices and commands
├── src/
│   └── excel_reader.py      # Excel device list reader (for --source excel)
├── tests/                 # 150 pytest unit tests
├── commands.yaml          # Huawei commands at top level; Cisco commands under cisco
├── devices.example.yaml   # Device list example
├── .env.example           # Env var configuration example (DingTalk/OSS/Mock)
└── requirements.txt       # Project dependencies
```

## Tech Stack

```
Python · Netmiko · difflib · Jinja2 · openpyxl · oss2 · requests
FastAPI · Uvicorn · argparse · ThreadPoolExecutor · pytest · PyYAML
```

## Exception Handling Layers

```
TCP reachability probe (socket.create_connection)
  → Unreachable devices are marked failed and are not connected

Connection layer
  → Timeouts and OSError retry automatically, up to 5 times
  → Sleep between retries totals at most 4 seconds, not counting each connection timeout
  → Auth failures and config errors such as ValueError are raised immediately, with no retry

Business layer
  → A device is failed when config output contains Error:, Unrecognized command, or Invalid input
  → One device failure does not stop the others; `run` exits with code 1 if any device failed
  → OSS uploads only snapshots saved in this run
```

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-09-25 | — | Added the FastAPI surface; moved backup, diff, and inspection into `operations.py`; invalid device lists fail before any connection |
| 2026-09-24 | — | `command` can manage Cisco commands; the password `q` is stored as a real password |
| 2026-09-24 | — | Fixed missing `re` in Huawei inspection and passwords written to logs; `run` exits 1 when config push fails; Cisco devices no longer receive Huawei commands; OSS uploads only new files from this run |
| 2026-06-01 | v1.3 | New CLI commands; fixed code redundancy issues |
| 2026-05-27 | v1.2 | Added `.env.example` env var docs; unified README shell syntax to PowerShell |
| 2026-05-27 | v1.1 | Merged config module; integrated `--source excel` device list loading; removed duplicate code; fixed missing Excel hint in error messages |
| 2026-05-26 | v1.0 | Docker support; `.env` auto-loading; project restructure; improved driver abstraction layer |
| 2026-05-25 | v0.9 | Enhanced alerting; code optimizations |
| 2026-05-24 | v0.8 | DingTalk Webhook alerts; Alibaba Cloud OSS backup sync |
| 2026-05-23 | v0.7 | difflib HTML config diff reports; concurrent backup; backup comparison |
| 2026-05-22 | v0.5 | Basic backup module; device driver abstraction (Huawei + Cisco + Mock); project init |

> Run `git pull` to get the latest version. `devices.yaml`, `devices.xlsx`, and `.env` are in `.gitignore` and won't be overwritten by pull.
