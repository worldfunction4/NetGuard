# NetGuard —— 网络设备自动化运维工具

面向中小企业的网络设备批量管理工具，解决**人工逐台备份配置、变更无法追溯、巡检靠人肉**三大痛点。

> [English README](README.md)

## 核心功能

| 功能 | 说明 |
|---|---|
| 批量配置备份 | 读取设备列表 → SSH/Telnet 连接 → 保存 before/after 快照 |
| 配置版本对比 | difflib 生成 HTML 差异报告，红删绿增，变更可追溯 |
| 设备巡检 | 采集 CPU / 内存 / 接口状态，生成 HTML + Excel 报告 |
| 阈值告警 | 超阈值自动记录日志，可选钉钉 Webhook 推送 |
| 多云集成 | 阿里云 OSS 备份同步（可选）。只上传本次 `run` 新保存的文件，无凭据时静默跳过 |
| 自动重连 | 超时和 `OSError` 最多重试 5 次。认证失败、非法设备类型等配置错误不重试 |
| Mock 演示 | `NETGUARD_MOCK=1` 不连接真实设备。设备清单里仍要有至少一台设备 |
| Web 接口 | FastAPI 提供设备列表、备份、对比、巡检和报告文件名。浏览器打开 `/docs` |

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/worldfunction4/NetGuard.git
cd NetGuard

# 2. 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
pip install -r requirements.txt

# 3. 准备设备列表（二选一）
# 方式 A：复制 YAML 示例
Copy-Item devices.example.yaml devices.yaml   # PowerShell
# CMD 用户请用: copy devices.example.yaml devices.yaml

# 方式 B：使用 Excel（首行: name | ip | port | device_type | username | password）
# 创建 devices.xlsx 后，所有子命令加上 --source excel

# 4. 编辑 devices.yaml 填入你的设备信息
# 或直接使用交互式添加：
python main.py device add

# 5. Mock 模式快速体验（无需真实设备）
$env:NETGUARD_MOCK = "1"
python main.py run          # 模拟备份
python main.py diff         # 生成差异报告
python main.py inspect      # 执行巡检
```
### 安装为 CLI 命令

```powershell
# 激活虚拟环境
.venv\Scripts\Activate.ps1

# 安装为全局命令（-e = editable 开发模式，改代码立即生效）
pip install -e .

# 验证
netguard --help
```

> 安装完成后，`netguard` 可以替代 `python main.py`，示例：`netguard run`。

### 卸载

卸载方式取决于你的安装方式。**请按你实际使用的安装方式选择对应的清理步骤。**

#### 方式 A：pip 安装的 CLI 命令

```powershell
# 1. 退出虚拟环境（如果已激活）
deactivate

# 2. 卸载 CLI 命令
pip uninstall netguard -y

# 3. 删除虚拟环境（可选——如果 .venv 不再用于其他项目）
Remove-Item -Recurse .venv

# 4. 删除运行时产生的文件（可选——备份、报告、日志）
Remove-Item -Recurse backups_config, reports, logs -ErrorAction SilentlyContinue

# 5. 删除整个项目目录（可选——彻底清除）
cd ..
Remove-Item -Recurse NetGuard
```

> 第 2 步是核心，做完就移除了 `netguard` 命令。第 3~5 步按需执行：留代码日后重装，还是彻底删干净。

#### 方式 B：Docker 安装

```powershell
# 1. 停止并删除容器（如果正在运行）
docker compose down

# 2. 删除 Docker 镜像
docker image rm netguard-netguard
# 如果镜像名不确定，用 docker images 查看

# 3. 删除运行时产生的文件（已在本地目录挂载）
Remove-Item -Recurse backups_config, reports, logs -ErrorAction SilentlyContinue

# 4. 彻底清除——删除项目目录
cd ..
Remove-Item -Recurse NetGuard
```

> Docker 镜像名默认为 `netguard-netguard`。可用 `docker images | findstr netguard` 确认。

#### 方式 C：仅用 `python main.py`（未执行过 `pip install`）

```powershell
# 直接删除项目目录即可，没有系统级残留
cd ..
Remove-Item -Recurse NetGuard
```


### Docker 方式（无需安装 Python 环境）

```bash
# 构建镜像
docker compose build

# 复制示例配置
Copy-Item devices.example.yaml devices.yaml

# 一键演示（mock 模式默认开启）
docker compose run --rm netguard run
docker compose run --rm netguard diff
docker compose run --rm netguard inspect

# 交互式添加设备
docker compose run --rm netguard device add

# 产出文件在本地目录，直接用浏览器打开
start reports\*.html
```

> 真实设备连接时，在 `docker-compose.yml` 中去掉 `NETGUARD_MOCK=1` 环境变量，并确保容器能访问设备 IP（默认 bridge 网络通常可以）。

## 命令参考

```
子命令                               说明
────────────────────────────────────────────────────
run [--source yaml|excel]            连接设备，推配置，保存快照
diff [--source yaml|excel]           生成 HTML 配置差异报告
inspect [--workers N] [--source ...] 巡检所有设备，生成 HTML + Excel
device list                          列出所有设备
device add                           交互式添加设备
device update <名> <字段> [值]       修改设备字段（密码直接回车取消，q 可以作为密码）
device remove <名>                    删除设备
command list                         列出所有命令
command add <区块> <命令>            config/show 为华为，cisco.config / cisco.show 为 Cisco
command remove <区块> <命令>         从上述区块删除命令
```

> `--source excel --source-file devices.xlsx` 可从 Excel 加载设备列表（首行：name | ip | port | device_type | username | password），默认从 `devices.yaml` 加载。`devices.xlsx` 含密码，已加入 `.gitignore`。
>
> `commands.yaml` 顶层 `config` / `show` 只下发给华为设备。Cisco 使用同文件中的 `cisco` 节。`diff` 和 `inspect` 不读取命令表。任一设备失败时，`run` 的退出码为 1。设备清单不合法时，命令行只记日志并返回；Web 接口在连接前返回 400。

## Web 接口

备份、对比、巡检的编排在 `operations.py`。命令行和接口调用同一批函数。

```powershell
$env:NETGUARD_MOCK = "1"
.\.venv\Scripts\python.exe -m uvicorn api.app:app --port 8000
```

浏览器打开 http://127.0.0.1:8000/docs ，在页面上直接调用接口。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/devices` | 列出设备，响应不含密码 |
| POST | `/devices` | 添加一台设备 |
| POST | `/jobs/backup` | 执行备份 |
| POST | `/jobs/diff` | 生成差异报告 |
| POST | `/jobs/inspect` | 执行巡检 |
| GET | `/reports` | 列出已生成的 HTML 文件名 |

错误正文统一为 `{"error": {"code": "...", "message": "..."}}`。看完后在运行服务的窗口按 `Ctrl+C` 停止。

## Mock 模式

设置环境变量 `NETGUARD_MOCK=1` 后，不连接真实设备也能跑通备份、对比和巡检。`devices.yaml` 不能是空文件，至少要有一台设备；可以先复制 `devices.example.yaml`。MockDriver 返回模拟的华为 / Cisco 输出，CPU / 内存数据有随机波动。

```powershell
# PowerShell
$env:NETGUARD_MOCK = "1"
python main.py run
python main.py diff
python main.py inspect
start reports\           # 在资源管理器打开报告目录
```

```cmd
REM CMD
set NETGUARD_MOCK=1
python main.py run
python main.py diff
python main.py inspect
start reports\
```

> 也可以复制 `.env.example` 为 `.env`，将 `NETGUARD_MOCK=1` 写入其中，省去每次手动设置环境变量。

真实环境只需去掉环境变量，`devices.yaml` 填写真实 IP。——**配置和 mock 彻底分离，切换零代码改动。**

## 多厂商支持

```
                ┌──────────────────┐
                │    BaseDriver    │  ← 抽象基类
                │  connect()       │     定义统一接口
                │  send_command()  │
                │  send_config()   │
                └────────┬─────────┘
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │HuaweiDriver│ │CiscoDriver│ │MockDriver │
    │ (Netmiko) │  │ (Netmiko) │  │ (内置数据) │
    └──────────┘  └──────────┘  └──────────┘
```

新增厂商只需继承 `BaseDriver`，在 `get_driver()` 工厂函数注册一个 `device_type` 分支，上层 collector / inspector **一行不用改**。

## 项目结构

```
NetGuard/
├── main.py                # CLI 入口，argparse 命令分发
├── operations.py          # 备份、对比、巡检编排，CLI 与 API 共用
├── logger.py              # 日志模块（控制台 + 文件双输出）
├── api/
│   ├── app.py             # FastAPI 应用与统一错误格式
│   ├── devices.py         # 设备列表接口
│   ├── jobs.py            # 备份、巡检、对比、报告列表
│   └── schemas.py         # 请求和响应字段
├── devices/
│   ├── base.py            # BaseDriver 抽象基类 + get_driver 工厂
│   ├── huawei.py          # 华为 VRP 驱动
│   ├── cisco.py           # Cisco IOS 驱动
│   ├── mock.py            # Mock 驱动（无设备演示）
│   └── try_connect.py     # 重连（网络错误最多 5 次；配置错误不重试）
├── backup/
│   ├── collector.py       # 配置采集（连接 → before → 推命令 → after）
│   ├── storage.py         # 文件存储（按设备/时间戳组织目录）
│   ├── oss.py             # 阿里云 OSS 上传（可选）
│   ├── notify.py          # 钉钉 Webhook 告警（可选）
│   └── cloud.py           # 云端集成入口
├── diff/
│   └── comparator.py      # difflib HTML 差异报告
├── report/
│   ├── inspector.py       # 巡检采集（并发，指标解析）
│   ├── generator.py       # Jinja2 HTML 报告渲染
│   ├── excel.py           # openpyxl Excel 报告（双 Sheet，带样式）
│   └── templates/
│       └── inspect.html   # 巡检报告 Jinja2 模板
├── config/
│   ├── __init__.py          # 路径常量 + 阈值 + .env 加载
│   └── manager.py           # 设备和命令的 YAML 配置管理
├── src/
│   └── excel_reader.py      # Excel 设备列表读取（--source excel 时使用）
├── tests/                 # 150 项 pytest 单元测试
├── commands.yaml          # 华为命令在顶层，Cisco 命令在 cisco 节
├── devices.example.yaml   # 设备列表示例
├── .env.example           # 环境变量配置示例（钉钉/OSS/Mock）
└── requirements.txt       # 项目依赖
```

## 技术栈

```
Python · Netmiko · difflib · Jinja2 · openpyxl · oss2 · requests
FastAPI · Uvicorn · argparse · ThreadPoolExecutor · pytest · PyYAML
```

## 异常处理层次

```
TCP 可达性探测（socket.create_connection）
  → 不可达记为失败，不再连接该设备

连接层异常
  → 超时和 OSError 自动重试，最多 5 次
  → 重试之间的等待合计不超过 4 秒，不含单次连接的 timeout
  → 认证失败、ValueError 等配置错误立即上抛，不重试

业务层
  → 配置回显含 Error:、Unrecognized command、Invalid input 时，该设备记为失败
  → 单台失败不影响其他设备；只要有失败，run 退出码为 1
  → OSS 只上传本次新保存的快照
```

## 更新日志

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-09-25 | — | 新增 FastAPI 接口；备份、对比、巡检抽到 `operations.py`；设备清单不合法时，任务在连接前失败 |
| 2026-09-24 | — | `command` 可管理 Cisco 命令；密码 `q` 可以作为真实密码保存 |
| 2026-09-24 | — | 修复华为巡检缺少 `re`、密码写入日志；配置失败时 `run` 退出码为 1；Cisco 不再接收华为命令；OSS 只上传本次新文件 |
| 2026-06-01 | v1.3 | 新增CLI命令，修复代码冗余问题 |
| 2026-05-27 | v1.2 | 新增 `.env.example` 环境变量文档；统一 README Shell 语法为 PowerShell |
| 2026-05-27 | v1.1 | 合并 config 模块；集成 `--source excel` 设备列表加载；消除重复代码；修复错误消息缺失 Excel 提示 |
| 2026-05-26 | v1.0 | Docker 支持；`.env` 自动加载；项目结构重构；驱动抽象层完善 |
| 2026-05-25 | v0.9 | 告警功能完善；代码优化 |
| 2026-05-24 | v0.8 | 钉钉 Webhook 告警；阿里云 OSS 备份同步 |
| 2026-05-23 | v0.7 | difflib HTML 配置差异报告；并发备份；备份对比功能 |
| 2026-05-22 | v0.5 | 基础备份模块；设备驱动抽象层（华为 + Cisco + Mock）；项目初始化 |

> 运行 `git pull` 获取最新版本。`devices.yaml`、`devices.xlsx` 和 `.env` 已在 `.gitignore` 中，pull 不会被覆盖。

