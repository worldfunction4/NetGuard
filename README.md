# NetGuard —— 网络设备自动化运维工具

面向中小企业的网络设备自动化巡检与配置管理工具，用 Python 脚本解决批量备份、变更对比、巡检报告的痛点。

## 已完成功能

- **批量配置备份**：读取 Excel 设备列表 → SSH 连接 → 并发采集配置
- **多厂商适配**：华为 (huawei_vrp) + Cisco (cisco_ios)，DeviceDriver 抽象层
- **配置版本对比**：difflib 生成 HTML 差异报告，红删绿增
- **HTML 巡检报告**：Jinja2 模板渲染，含设备列表、备份状态、差异汇总
- **Excel 巡检报告**：openpyxl 生成，带颜色格式化和冻结表头
- **云端备份**：报告自动上传阿里云 OSS
- **钉钉告警**：发现备份异常时通过 Webhook 推送通知
- **Mock 模式**：环境变量切换 mock/real，无真实设备也能演示
- **异常处理体系**：SSH 超时 / 认证失败 / 网络不可达，分类捕获不中断整体
- **并发备份**：ThreadPoolExecutor 线程池，10 台设备从 60s 降至 15s

## 项目结构

```
NetGuard/
├── main.py              # CLI 入口
├── config.py            # 全局配置（命令映射、并发参数）
├── devices.xlsx         # 设备列表示例
├── .env                 # 环境变量（阿里云 OSS / 钉钉密钥，不提交 git）
├── requirements.txt     # Python 依赖
├── src/                 # 工具模块
│   ├── excel_reader.py  # Excel 设备列表读取
│   └── logger.py        # 全局日志
├── backup/              # 备份与云同步
│   ├── collector.py     # 并发配置采集
│   ├── storage.py       # 本地文件存储
│   ├── oss.py           # 阿里云 OSS 上传
│   ├── notify.py        # 钉钉 Webhook 告警
│   └── cloud.py         # 云端集成入口
├── report/              # 报告生成
│   ├── generator.py     # Jinja2 HTML 报告
│   ├── excel.py         # openpyxl Excel 巡检报告
│   ├── templates/       # Jinja2 模板目录
│   └── __main__.py      # python -m report 入口
├── backup_configs/      # 备份文件存储
├── reports/             # 报告输出
└── logs/                # 日志文件
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量（复制模板修改）
cp .env.example .env

# 3. 准备设备列表（编辑 devices.xlsx 或通过命令行指定）

# 4. 运行报告（备份 → 对比 → HTML报告 → Excel报告）
python -m report
```

## 技术栈

**第一阶段（脚本核心）**
Python · Netmiko · difflib · Jinja2 · openpyxl · oss2 · tenacity

**第二阶段（Web 外壳，开发中）**
FastAPI · SQLAlchemy · SQLite

## 范围控制（不做）

- ❌ SNMP 资产发现
- ❌ 拓扑可视化
- ❌ PDF 报告
- ❌ 用户权限管理
- ❌ Celery / Redis 分布式队列
- ❌ Docker 部署（当前阶段）

## License

MIT
