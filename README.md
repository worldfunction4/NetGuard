# NetGuard —— 网络设备自动化运维工具

面向中小企业的网络设备批量管理工具，解决**人工逐台备份配置、变更无法追溯、巡检靠人肉**三大痛点。

## 核心功能

| 功能 | 说明 |
|---|---|
| 批量配置备份 | 读取设备列表 → SSH/Telnet 连接 → 保存 before/after 快照 |
| 配置版本对比 | difflib 生成 HTML 差异报告，红删绿增，变更可追溯 |
| 设备巡检 | 采集 CPU / 内存 / 接口状态，生成 HTML + Excel 报告 |
| 阈值告警 | 超阈值自动记录日志，可选钉钉 Webhook 推送 |
| 多云集成 | 阿里云 OSS 备份同步（可选），无凭据时静默跳过 |
| 自动重连 | 网络抖动时自动重试，最大 5 次，认证失败不重连 |
| Mock 演示 | `NETGUARD_MOCK=1` 无设备也能完整演示 |

## 快速开始

```bash
# 1. 克隆项目
git clone https://github.com/worldfunction4/NetGuard.git
cd NetGuard

# 2. 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
pip install -r requirements.txt

# 3. 复制示例配置
copy devices.example.yaml devices.yaml

# 4. 编辑 devices.yaml 填入你的设备信息
# 或直接使用交互式添加：
python main.py device add

# 5. Mock 模式快速体验（无需真实设备）
$env:NETGUARD_MOCK = "1"
python main.py run          # 模拟备份
python main.py diff         # 生成差异报告
python main.py inspect      # 执行巡检
```

## 命令参考

```
子命令                       说明
───────────────────────────────────────────
run                          连接设备，推配置，保存快照
diff                         生成 HTML 配置差异报告
inspect [--workers N]        巡检所有设备，生成 HTML + Excel
device list                  列出所有设备
device add                   交互式添加设备
device update <名> <字段> <值> 修改设备字段
device remove <名>            删除设备
command list                 列出所有命令
command add config/show <命令> 添加配置 / 查看命令
command remove config/show <命令> 删除命令
```

## Mock 模式

设置环境变量 `NETGUARD_MOCK=1` 即可在**无任何网络设备**的情况下跑通全流程。MockDriver 返回模拟的华为 / Cisco 设备输出,CPU / 内存数据有随机波动，巡检报告、差异报告都能正常生成。

```powershell
# PowerShell
$env:NETGUARD_MOCK = "1"
python main.py run && python main.py diff && python main.py inspect
start reports\           # 在资源管理器打开报告目录
```

真实环境只需去掉环境变量，`devices.yaml` 填写真实 IP。——**配置和 mock 彻底分离，切换零代码改动。**

## 多厂商支持

```
                ┌──────────────────┐
                │    BaseDriver    │  ← 抽象基类
                │  connect()      │     定义统一接口
                │  send_command() │
                │  send_config()  │
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
├── config.py              # 路径常量 + 告警阈值
├── logger.py              # 日志模块（控制台 + 文件双输出）
├── devices/
│   ├── base.py            # BaseDriver 抽象基类 + get_driver 工厂
│   ├── huawei.py          # 华为 VRP 驱动
│   ├── cisco.py           # Cisco IOS 驱动
│   ├── mock.py            # Mock 驱动（无设备演示）
│   └── try_connect.py     # 重连机制（最大 5 次，7 秒上限）
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
│   └── manager.py         # 设备和命令的 YAML 配置管理
├── src/
│   └── excel_reader.py    # Excel 设备列表读取
├── tests/                 # 73 项 pytest 单元测试
├── commands.yaml          # 配置 / 查看命令示例
├── devices.example.yaml   # 设备列表示例
└── requirements.txt       # 项目依赖
```

## 技术栈

```
Python · Netmiko · difflib · Jinja2 · openpyxl · oss2 · requests
argparse · ThreadPoolExecutor · pytest · PyYAML
```

## 异常处理层次

```
TCP 可达性探测（socket.create_connection）
  → 不可达直接跳过，不浪费后续资源

连接层异常（NetmikoTimeoutException / NetMikoAuthenticationException）
  → 超时自动重连（最多 5 次）
  → 认证失败立即上抛（不重连，避免锁定账号）

业务层异常（NetmikoBaseException / Exception）
  → 分类捕获，单台设备失败不影响其他设备继续执行
```

## 许可证

MIT License
