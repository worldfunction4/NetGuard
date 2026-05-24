# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## 常用命令

```bash
# 激活虚拟环境（Windows）
.\.venv\Scripts\Activate.ps1

# 安装依赖
pip install -r requirements.txt

# 运行主程序
python main.py run                          # 连接设备，推配置，保存 before/after 快照
python main.py diff                         # 对最新快照对生成 HTML 差异报告
python main.py inspect                      # 巡检所有设备，生成 HTML + Excel 报告
python main.py inspect --workers 8          # 指定并发数（默认 4）
python main.py device list                  # 查看设备列表
python main.py device add                   # 交互式添加设备
python main.py device update SW-01 ip 10.0.0.1   # 修改设备字段
python main.py device remove SW-01          # 删除设备
python main.py command list                 # 查看命令列表
python main.py command add config "vlan batch 100"  # 添加配置命令
python main.py command remove show "dis vlan"       # 删除命令
python main.py --help

# Mock 模式（无需真实设备）
NETGUARD_MOCK=1 python main.py run
NETGUARD_MOCK=1 python main.py inspect

# 语法检查（无测试框架时用）
python -m compileall -q .
```

---

## 架构概览

### 数据流

```
devices.yaml + commands.yaml
        ↓
main.py (argparse 分发)
        ├── cmd_run     → backup/collector.py::work_one()
        ├── cmd_diff    → diff/comparator.py::generate_html_diff()
        ├── cmd_inspect → report/inspector.py::inspect_all()
        ├── cmd_device  → config/manager.py（设备 CRUD）
        └── cmd_command → config/manager.py（命令 CRUD）

┌─ run 子命令数据流 ─────────────────────────────────────────────┐
│                                                                  │
│  backup/collector.py::work_one()                                 │
│        ↓ 调用工厂                                                │
│  devices/base.py::get_driver()                                   │
│    → devices/huawei.py::HuaweiDriver                             │
│    → devices/cioso.py::CiscoDriver                               │
│    → devices/mock.py::MockDriver（NETGUARD_MOCK=1 时自动切换）     │
│        ↓ 执行命令                                                │
│  backup/storage.py::save_result()                                │
│    → backups_config/{设备名}/{run_id}_before.txt                 │
│    → backups_config/{设备名}/{run_id}_after.txt                  │
│        ↓（diff 子命令）                                           │
│  diff/comparator.py::generate_html_diff()                        │
│    → reports/{设备名}_{时间戳}_diff.html                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘

┌─ inspect 子命令数据流 ──────────────────────────────────────────┐
│                                                                  │
│  report/inspector.py::inspect_all()                              │
│    → 并发调用 inspect_device()，使用 get_driver() 采集指标         │
│    → 与 THRESHOLDS (config.py) 比对，触发 alerts                 │
│    → 遍历 alerts 推送钉钉通知（backup/cloud.py::notify_alert）     │
│                                                                  │
│  生成两份报告：                                                   │
│    ① report/generator.py → Jinja2 → reports/inspect_{ts}.html   │
│    ② report/excel.py     → openpyxl → reports/inspect_{ts}.xlsx │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 目录结构

```
NetGuard/
├── main.py               # CLI 入口，argparse 分发 5 个子命令
├── config.py             # 基础路径常量（BACKUP_DIR / REPORT_DIR / LOG_DIR）+ 阈值
├── logger.py             # 全局日志配置（控制台 + 文件）
│
├── config/
│   ├── __init__.py
│   └── manager.py        # devices.yaml / commands.yaml 的 CRUD 操作
│
├── devices/
│   ├── base.py           # BaseDriver 抽象基类 + get_driver() 工厂函数 + is_mock_mode()
│   ├── huawei.py         # HuaweiDriver → Netmiko ConnectHandler
│   ├── cioso.py          # CiscoDriver → Netmiko ConnectHandler
│   └── mock.py           # MockDriver → 预置响应，无需网络连接
│
├── backup/
│   ├── collector.py      # work_one()：连接设备、保存 before/after
│   ├── storage.py        # save_result()：写入 backups_config/{设备名}/
│   ├── cloud.py          # 云端集成入口：OSS 同步 + 钉钉告警
│   ├── oss.py            # 阿里云 OSS 客户端封装（oss2 SDK）
│   └── notify.py         # 钉钉 Webhook 告警推送
│
├── diff/
│   └── comparator.py     # difflib.HtmlDiff → 红删绿增 HTML 报告
│
├── report/
│   ├── inspector.py      # inspect_device() + inspect_all() 巡检逻辑
│   ├── generator.py      # Jinja2 HTML 报告渲染
│   ├── excel.py          # openpyxl Excel 巡检报告（含汇总 Sheet + 告警高亮）
│   ├── __main__.py       # 占位：直接运行会报 NotImplementedError
│   └── templates/
│       └── inspect.html  # 巡检报告的 Jinja2 模板
│
├── devices.yaml          # 设备列表（含凭据，已 gitignore）
├── devices.example.yaml  # 示例文件，复制为 devices.yaml 后使用
├── commands.yaml          # config 命令 + show 命令列表
└── requirements.txt       # netmiko, pyyaml, openpyxl, jinja2, requests, oss2
```

---

## 驱动层（devices/）

- **BaseDriver**（`base.py`）：抽象基类，定义 `connect / disconnect / send_command / send_config_set / get_inspect_commands / parse_metrics` 接口；实现了 `__enter__` / `__exit__` 上下文管理器（collector 中用 `with driver as conn` 自动管理连接生命周期）
- **get_driver() 工厂函数**：根据 `device_type` 字段分发到对应驱动。支持双层切换机制：
  - 环境变量 `NETGUARD_MOCK=1` 全局生效
  - 单设备 `device_type: mock_huawei` 或 `mock_cisco` 也走 MockDriver
- **添加新厂商**时：① 在 `devices/` 新建驱动文件继承 `BaseDriver`；② 在 `base.py::get_driver` 中注册对应 `device_type` 分支

### 厂商差异封装策略

各厂商驱动只封装两个层面的差异：
| 层面 | 华为 | Cisco |
|------|------|-------|
| 巡检命令 | `display cpu-usage` / `display memory-usage` / `display interface brief` | `show processes cpu` / `show processes memory` / `show ip interface brief` |
| 指标解析 | 从上述输出中正则提取 CPU%、内存%、接口数 | 同上，格式不同 |

`send_command` / `send_config_set` 由 Netmiko 统一处理，驱动层只需做基本的 CRC。

---

## Before/After 配对逻辑

`run_id` 格式为 `%Y-%m-%d_%H-%M-%S_microsecond`（精确到微秒级），在 `work_one()` 入口处生成，同时传给 before 和 after 的 `save_result`，保证同一次 run 的两个文件前缀完全一致。

`cmd_diff` 中的 `_find_latest_complete_pair()` 实现了**容错配对策略**：从最新的 `*_before.txt` 往前找，直到在设备目录下找到同前缀的 `*_after.txt`。这样即使某次 run 中途失败（只有 before 没有 after），也能自动回退到上一次成功的完整配对，而不是跳过该设备。

---

## 配置管理（config/manager.py）

`devices.yaml` 和 `commands.yaml` 均通过 `config/manager.py` 读写：
- **设备管理**：`load_devices / add_device / update_device / remove_device / list_devices`
- **命令管理**：`load_commands / add_command / remove_command / list_commands`
- 所有 CRUD 操作直接写回 YAML 文件，原有注释因 PyYAML 限制无法保留
- 设备列表校验必填字段：`name + connection(device_type, ip, username, password, port)`
- `port` 必须是整数（命令行输入时自动转换）

---

## 可观测性设计

- **日志**：`logger.py` 同时输出到控制台和 `logs/netguard.log`，格式 `时间|级别|消息`
- **OSS 同步**：`backup/oss.py` 从环境变量 `OSS_ACCESS_KEY / OSS_SECRET_KEY / OSS_BUCKET / OSS_ENDPOINT` 读取凭据，凭据不完整时自动降级（不抛异常）
- **钉钉告警**：`backup/notify.py` 从环境变量 `DINGTALK_WEBHOOK` 读取 Webhook 地址，无配置时仅记录日志
- **Mock 模式**：设置 `NETGUARD_MOCK=1` 跳过所有真实网络操作，返回预置的设备响应

---

## 当前实现状态

| 功能 | 状态 |
|------|------|
| 华为驱动（Telnet/SSH） | ✅ 已实现 |
| Cisco 驱动 | ⚠️ 已实现，未经真实 Cisco 设备测试 |
| Mock 驱动（无设备演示） | ✅ 已实现 |
| 并发备份（ThreadPoolExecutor） | ✅ 已实现 |
| HTML 差异报告 | ✅ 已实现 |
| 巡检报告（HTML + Excel） | ✅ 已实现 |
| 钉钉告警推送 | ✅ 已实现 |
| OSS 云端同步 | ✅ 已实现 |
| 设备/命令管理的 CLI | ✅ 已实现 |
| 测试套件 | ❌ 未建立 |

---

## 注意事项

- `devices.yaml` 含真实凭据，已加入 `.gitignore` 不入库；新环境复制 `devices.example.yaml` 为 `devices.yaml` 并填入真实信息
- `backups_config/`、`reports/`、`logs/` 均为运行时生成目录，视为数据而非源码
- `main.py` 对 `device` / `command` 子命令做了特殊处理：这两个子命令不需要加载 devices.yaml，可直接运行
- `config.py` 用 `Path(__file__).parent` 定义路径常量，保证从任意工作目录运行都正确
- Excel 报告中的 `_safe_cell()` 函数防止公式注入（`= + - @ TAB` 开头的字符串前面加英文单引号）
