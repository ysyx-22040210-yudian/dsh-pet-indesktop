# Codex 联动修复报告（2026-10-03）

基线：官方 v4.2.1 `f4cb620` + 同日运行程序识别本地增强版；分支 `feat/running-agent-discovery`。关联：[识别增强报告](PR-REPORT-running-agent-discovery-2026-10-03.md)、[操作说明](RUNNING-AGENT-DISCOVERY.md)、[事件协议](AGENT_LINK_PROTOCOL.md)。尚未发布上游或创建 PR。

## 一、核心特性

用户选择 Codex 后无工作反馈：现场配置只有 `process_names: ["codex.exe"]` 和一个不存在的桌宠通用 JSONL 通道。进程发现不生成任务事件，因此现有监听没有输入。增加 `adapter: "codex"`，直接只读本机 Codex sessions；提取生命周期、思考/工具类型，让现有动画和汇报管线获得真实事件。

## 二、修改文件说明

待最终统计追加逐文件行数。

## 三、实现要点

沿用 BaseAgentMonitor 的 daemon worker、Qt 代次信号、暂停和关闭流程。最多 64 个会话尾部有界增量读取，新日期目录每 1.5 秒发现一次，完整日期树每 30 秒扫描。只接受激活后的带时间戳事件，先前历史不回放；中途回复不结束任务。根会话并发聚合，子会话过滤，旧回合晚到完成事件不能结束新回合。工具结果必须属于活跃会话才会继续推动状态。配置保留适配器，识别窗口使用目录选择器，Codex 联动禁用 OpenCode 插件导出。

## 四、性能分析

首轮现场：Windows 11 x64 / CPython 3.13.13，1843 个真实 rollout、64 个跟踪文件、20 样本，完整扫描中位 90.861 ms / 最大 98.727 ms；未变化读取中位 3.241 ms，RSS 相对增加 1,896,448 B。由此将完整扫描降为每 30 秒，近期目录仍每个轮询探测；启动时已有未变化文件直接跳到末尾。最终版本重测结果和命令将在追加章节记录。

新增只读文件元数据与尾部读取、启用绑定时一个后台 worker；没有外网请求或 Codex 配置写入。跟踪文件数、单次读取和未完成行缓存均有上限；未启用时不启动 worker。

## 五、实机运行记录

根因：`Test-Path .../agent-events/agent-codex.jsonl` 返回 False，而日志显示 `Agent 监视器 [agent-codex] 已启动`，说明不是桌宠漏加载开关。真实 Codex Desktop 0.159.2 的会话记录含 `task_started`、`task_complete`、`turn_aborted`，以及 PascalCase `item_completed` 类型，另有 `response_item` 工具调用；中途消息 phase 为 commentary。

首轮 `E:/dsh-pet-dev313/Scripts/python.exe D:/AI_helper/output/verify-codex-link.py`，55 秒读取真实 Codex 文件，收到 working 和 bash/read/tool 活动共 9 条，worker 正常退出。诊断只输出元数据字段与类型，没有输出代码、命令、聊天正文或认证信息。新适配器没有改动 Codex 文件。

最终 EXE 的 Windows 动画、菜单和部署记录将在追加章节登记；macOS/Linux、远程任务和禁用会话落盘场景未做实机验证。

## 六、测试与验证

修复前新增 10 个公开接缝测试全失败，主要为缺少 CodexMonitor、无法找到来源和无法保存适配器。实现后扩展为 12 个 Codex 用例，聚焦相关测试 267 passed / 1 skipped / 220 warnings（11.97 秒）；ruff pet/tests 和 git diff --check 通过。最终全量门及构建验证将在追加章节登记。

## 七、最终交付与复核

### 修改文件说明（最终统计）

统计口径：相对官方 v4.2.1 的累计未提交分支变更。新增文件此前没有 Git 基线，按完整行数记录；先前识别增强的部分见原报告。

| 文件 | 增删/新增 | 本轮意图 |
|---|---|---|
| `pet/codex_monitor.py` | 新增 197 行 | 将 Codex 本地生命周期和工具类型转成现有六态信号；并发根任务聚合、有界增量读取、过滤旧回合与子 Agent |
| `pet/agent_discovery.py` | 新增文件共 227 行 | 在原进程/兼容来源发现基础上查找 CODEX_HOME 和打开的 rollout 所在 sessions 目录 |
| `pet/running_agents_dialog.py` | 新增文件共 368 行 | 添加 Codex 方式、目录选择、正确保存/回读适配器，禁用不适用的插件导出，缺失来源显示等待 |
| `pet/agent_link.py` | +82 / -20 | 注册 CodexMonitor；包含同日已有自定义来源热替换和代次防陈旧事件改动 |
| `pet/config.py` | +12 / -1 | 允许持久化 codex 适配器，继续保留旧 JSONL 条目形状 |
| `tests/test_codex_link.py` | 新增 256 行 | 12 个用例覆盖来源、配置、状态/隐私、并发、历史/新文件、迟到完成、半行/轮转、删除、Qt 表单与外部进程写入 |
| `tests/test_desktop_pet_features.py` | +11 / -2 | 旧品牌禁用检查允许明确请求的 Agent 适配文件，测试/报告不再作为产品文案；其余产品文案仍检查 |
| `docs/AGENT_LINK_PROTOCOL.md` | +10 / -3 | 登记新适配器契约与示例、互链两份报告 |
| `docs/INDEX.md` | +4 / -1 | 更新使用入口并登记本报告 |
| `docs/RUNNING-AGENT-DISCOVERY.md` | 新增文件共 42 行 | 增补 Codex 接入、原空通道修复方式、轮询和本地执行边界 |
| 本报告 | 新增 84 行 | 保留初次测试/性能现场，追加最终交付记录 |
| `docs/PR-REPORT-running-agent-discovery-2026-10-03.md` | 同日既有报告追加 4 行 | 保留原产物证据，指向新的 Codex 修复和最新包哈希 |

未删除源码文件。生成 EXE/ZIP、构建环境、性能脚本和私有配置备份在仓库外，不进入 Git。

### 性能分析（最终版本）

命令：`E:/dsh-pet-dev313/Scripts/python.exe D:/AI_helper/output/verify-codex-link.py`；Windows 11 x64，Python 3.13.13 / PySide6 6.11.2。真实 sessions 共 1843 文件，跟踪 64；20 个完整扫描/读取样本，和 55 秒真实事件观察。期间全量测试与打包并行运行。

| 路径 | 中位 | 最大 | 触发频率 |
|---|---:|---:|---|
| 完整日期树发现 | 113.366 ms | 146.908 ms | 首次及每 30 秒 |
| 近期目录发现 + 无新增行轮询 | 7.507 ms | 17.217 ms | 每 1.5 秒 |

本轮 RSS 相对创建适配器前增长 282,624 B（约 0.270 MiB），是短期实测，不作为长期泄露结论。最多 64 个 tailer 和状态条目，半行缓冲单文件 64 KiB 上限，首次新内容最多取 256 KiB 尾部；源码中没有保存完整消息或代码。相对原先启用的空 JSONL 绑定，后台 worker 数仍为 1；相对关闭联动时会新增 1 个 worker。新增文件 stat、glob、只读头部/尾部读取；聚合状态变化时本应用日志增加一行。未增加网络请求、外部写入器或 Codex 文件写入。

### 实机运行记录（最终版本）

- 构建：`powershell -NoProfile -ExecutionPolicy Bypass -File D:/AI_helper/output/build-enhanced-pet.ps1`；PyInstaller 6.22.3 / CPython 3.13.13，103.6 秒成功。桥接零依赖、精简和编码检查均通过。验证 144 个 PE 文件、43841 个导入符号，无缺失。
- 保留旧增强版于 `D:/AI_helper/dsh-pet-enhanced-before-codex-20261003-134007`，配置备份于 `D:/AI_helper/dsh-pet-local/config.before-codex-link-20261003-134007.json`。安装路径继续为 `D:/AI_helper/dsh-pet-enhanced`，原桌面/开始菜单启动器仍可使用。
- 当前配置 `agent-codex` 启用、`adapter=codex`、`path=~/.codex/sessions`。备份与交付后的 JSON 比对，唯一变化的顶层键为 `agent_link`；chat 块完全相同，仍为 `ollama-qwen35 / qwen3.5:9b / http://127.0.0.1:11436`。桥接 health 正常。
- 已运行 EXE 的 PID 37892，Responding=True。实际日志：13:40:26 `working`，13:40:28 `thinking`，随后持续收到新事件。仅检查该桌宠的 ffmpeg 子进程，发现正在解码 `吃Token.webm`；日志中也有 `写代码.webm` 和 `轻快记录.webm` 的播放生命周期，证明信号进入动画路径。
- Windows UIA 实际通过右键菜单打开新窗口，选择已绑定 codex，读取来源 `~/.codex/sessions`，OpenCode 导出按钮 disabled；Esc 关闭。Windows 原生 Qt light/dark 720/1100 截图分别保存在 `D:/AI_helper/output/codex-link-ui-verification/`，控件可见、文本换行正常；截图列表的 MyWorkbench/OpenCode 名称是布局样本，不作为实际分支验证。
- 本机真实 Codex 55 秒观察共 10 条安全状态/工具事件，包含 working、thinking、bash/edit/read；worker 退出完成。结束/中止与并发不误完成通过独立 rollout 文件、实际 Qt worker/外部 writer 回归验证；本 turn 仍在运行，未伪造或修改真实 Codex 历史来触发完成。

便携包：`D:/AI_helper/output/dsh-pet-v4.2.1-agent-discovery-windows-x64.zip`，1093 文件，157,185,430 B，解压 277,746,803 B；CRC 全部通过，不含用户配置、日志、对话或密钥。SHA-256 `13b4414204a2aebfb12d5c4abac3e211aea769d10b962973092731ccbfa419de`；EXE SHA-256 `9872344d8f79e85b534689d7fa62d9c795e969023a768b5042f8ea381b45d653`。便携说明已经包含 Codex 接入步骤。

### 测试与验证（最终门）

初次全量：2950 passed / 11 skipped / 1 failed，唯一失败为旧文案测试禁止整个仓库出现 Codex 名称。这与明确请求的具名服务联动冲突；调整为允许适配文件和工程证据，保留其余产品文案的检查。修复后相关 34 项全通过。

最终 `python -m pytest -q`：**2951 passed / 11 skipped / 261 warnings，242.95 秒**；日志 `D:/AI_helper/output/codex-link-full-tests-final.log`。`ruff check pet tests` 和 `git diff --check` 均通过（Git 仅提示 CRLF 转换）。没有推送/创建 PR，故未执行推送前 CPU 满载三轮门。全量重跑只改变测试范围，之后的追加报告不改变程序或 EXE。
