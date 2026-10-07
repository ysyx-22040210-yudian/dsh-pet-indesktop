# 运行中 Agent 识别：本地增强版交付记录

基线：官方 `v4.2.1` / `f4cb620`。分支：`feat/running-agent-discovery`。日期：2026-10-03。属于本地增强版，未改动官方版本号，未提交上游 PR。

用户希望其他设备上的改名版或二次开发 OpenCode 也能被桌宠选择和联动。本机没有指定分支，因此使用通用程序发现、兼容数据库检查及可导出的零依赖 OpenCode 插件，验证范围不冒充特定分支的真实兼容性。

操作说明见 [运行中 Agent 识别与接入](RUNNING-AGENT-DISCOVERY.md)，外部事件格式见 [Agent 联动协议](AGENT_LINK_PROTOCOL.md)，报告格式来自 [PR 报告模板](PR-REPORT-TEMPLATE.md)。

## 修改文件说明

| 文件 | 修改目的 |
|---|---|
| `pet/agent_discovery.py`（新增） | 按需列出当前用户程序；查询选中进程打开的文件与有限目录；只读校验数据库/事件；生成可迁移的零依赖 JS 插件 |
| `pet/running_agents_dialog.py`（新增） | 复用 SettingsSection/SettingRow/ModernSelect；程序选择、来源绑定、插件导出、编辑移除；后台纯 I/O 工作通过队列回到 GUI 线程 |
| `pet/context_menus/shared.py` | 两种菜单模板共有的 Agent 联动入口；延后到菜单关闭后打开窗口 |
| `pet/config.py` | 保持旧 `key/name/path` 形状；清洗可选 `adapter` 和 `process_names` |
| `pet/agent_link.py` | 自定义数据库监视器、来源即时变更、旧代次隔离；数据库 URI 转义；新来源服从隐藏时的暂停状态；自定义程序的主动识屏避让 |
| `tests/test_running_agents.py`（新增） | 改名进程、共享运行时、旧配置、热变更和来源隔离、数据库格式拒绝、菜单、窗口、真实 Node 插件和外部 Python 数据库写入 |
| `docs/AGENT_LINK_PROTOCOL.md` | 新可选字段、启用示例、来源隔离与增强版生效方式 |
| `docs/RUNNING-AGENT-DISCOVERY.md`（新增） | Windows 便携包使用、迁移与兼容边界 |
| 本报告（新增）及 `docs/INDEX.md` | 交付证据及文档登记互链 |

行数（源码终稿）：`agent_discovery.py` +210；`running_agents_dialog.py` +351；`agent_link.py` +79/−20；`config.py` +12/−1；`context_menus/shared.py` +5；`test_running_agents.py` +276；`AGENT_LINK_PROTOCOL.md` +8/−3；`RUNNING-AGENT-DISCOVERY.md` +33；`INDEX.md` +3/−1。没有删除文件。新增文件按实际行数统计，已跟踪文件按 `git diff --numstat` 统计；本报告属于交付记录，随验收结果追加。

## 性能分析

环境：Windows 11 x64，CPython 3.13.13，PySide6 6.11.2，psutil 7.2.2。基准命令：`E:\dsh-pet-dev313\Scripts\python.exe D:\AI_helper\output\verify-agent-discovery.py`。基准脚本和原始 JSON 保存在本机输出目录，未随便携包引入后台任务。

| 路径 | 样本量 | 实测 |
|---|---|---|
| 当前用户程序扫描（174 个程序） | 20 次 | 中位 78.70 ms，最大 142.51 ms |
| 已选改名程序的有限数据源查询 | 20 次 | 中位 3.05 ms，最大 4.47 ms |
| 已绑定程序 busy 状态匹配 | 10,000 次 | 平均 0.889 μs/次 |

扫描只在窗口打开和手动刷新时触发；查找只在选择程序时触发，不增加持续的进程扫描。窗口打开时有一个 50 ms 的 GUI 队列排空计时器，关闭后停止；每次扫描/查询使用一个可取消的 daemon Python 工作线程，无网络请求。来源候选最多 256 个；JSONL 校验最多读取尾部 64 KiB；数据库使用只读连接。运行时仍采用已有监视器的增量读取与轮询频率。

新增内存包括窗口、当前程序列表、最多 8 个绑定的元数据和已退休监视器的代次记录；程序列表在刷新时替换，不积累历史。未做进程级 RSS 或长期内存趋势测量，因此不声称内存没有增长。

## 实机运行记录

- Windows 原生 `windows` Qt 平台运行识别窗口，取得浅色/深色、720/1100 宽度的窗口抓图，并逐张检查表单、底部按钮及深色页签文字。截图采用明确的示例程序名，真实程序扫描另行测量。
- 真实 Node.js 24.19.0 子进程载入生成的 `.mjs` 插件，发送主会话 busy、工具事件、子会话及主会话 idle。事件文件得到 `working, working, idle`，子会话结束未冒充主会话完成，工具参数 `PRIVATE-CODE` 未写入文件。包含 `AGENT DESTINATION` 的文件名也正确处理。
- 外部 Python 进程写入含空格和 `#` 的改名数据库；真实 OpenCodeMonitor 工作线程通过 Qt 事件循环收到改名 Agent 的 `working/idle`。该数据库仅是兼容事件表的验证来源，不代表某个用户分支。
- 手动/自动校验拒绝无 `event(type,data)` 的数据库、聊天历史 JSONL、结构错误的状态字段；没有兼容来源时保留插件导出路径。
- 真实 Python 线程排入旧来源的 Qt 状态信号后更换绑定，新来源未收到旧 `working`；从 JSONL 切换到数据库后不再混读旧事件文件。
- Windows 打包 EXE 中使用 UI Automation 打开「Agent 联动 → 识别运行中的 Agent…」，保存并移除独立测试绑定，导出 2,002 字节的 JS 插件，关闭后再次打开。最终 EXE 接收目标窗口的 Esc 消息后隐藏识别窗口；源码 Qt 键盘测试同时确认计时器和取消状态已收口。
- 打包时排除 Anaconda/MiKTeX 的 DLL 搜索路径，修复混入的有版本后缀 ICU 与 Qt 的 Windows ICU 接口冲突；Python 3.13 的 OpenSSL 改为其运行时自带的 3.5.5，修复 PySide6 附带 3.0.15 导致的 `_ssl` 导入失败。最终 144 个二进制、43,841 项静态导入校验无缺失导出；Common Controls 使用实际进程按清单加载的 Windows WinSxS 版本核对。
- 本机增强版位于 `D:\AI_helper\dsh-pet-enhanced`。原安装 `D:\AI_helper\dsh-pet` 保留。桌面/开始菜单使用的 `dsh-pet-local/Start-dsh-pet.ps1` 已指向增强版，原启动路径和配置留有本地备份。旧进程关闭后启动增强版，进程 `44328` 报告 `Responding=True`。此前 Chat 配置块的 SHA-256 比较完全一致，仍使用 `ollama-qwen35` / `qwen3.5:9b` / `127.0.0.1:11436`，本地桥接健康检查通过。
- 本机没有用户指定的 OpenCode 二次开发程序；macOS/Linux 无运行环境。未验证这些分支的专用目录、改造的插件加载器或其他平台原生菜单。

## 测试与验证

- 初始新功能测试在实现前因缺少 discovery 模块失败，再实现。后来针对不可信 JSON 字段、插件路径模板、迟到事件与数据库混读的用例均先复现失败，再修正。
- 最终新增功能测试 22 项；与 `test_agent_link.py`、`test_agent_link_threads.py`、`test_config_schema.py` 合跑：255 passed / 1 skipped，10.38 s。
- 全量：`QT_QPA_PLATFORM=offscreen E:\dsh-pet-dev313\Scripts\python.exe -m pytest -q --tb=short`，2937 passed / 11 skipped / 262 warnings，231.49 s。跳过项未改动，警告包括既有 PySide6 镜像 API 与 persona 短语参数弃用警告；新迟到事件用例调用既有短语路径产生一条相同警告。
- 静态检查：`ruff check pet/ tests/` 通过；`git diff --check` 通过。
- `fix_bridge_bundle.py` 的无 node_modules 导入冒烟通过；`slim_bundle.py` 的依赖闭包和必需清单检查通过，移除 124 个文件、53.03 MiB；`check_bundle_encoding.py` 的中文字面量、资源、文件名检查通过。
- ZIP 的逐文件 CRC 校验通过，内含 1,093 个文件，无用户配置或运行日志。

## 分发范围

Windows x64 onedir 程序基于隔离的 CPython 环境构建，包含既有 Chat 功能。便携包不包含本机用户配置、API Key、测试数据库、截图或私有对话。生成插件使用 Node/Bun 自带模块，没有 NPM 运行时依赖。

- 便携包：`D:\AI_helper\output\dsh-pet-v4.2.1-agent-discovery-windows-x64.zip`。
- 压缩大小：157,176,451 字节（149.90 MiB）；解压文件：277,736,906 字节（264.87 MiB）。
- ZIP SHA-256：`f2c405ce677a7172175b322bab60ba770fdc71f716856bde46d092e6b57235fa`。
- EXE SHA-256：`58c78dc42b77478e65574947f07868f6d15adefe44cd230687da7f64d69fee40`。
- 包含中文使用说明、原 MIT LICENSE 与第三方授权声明。
- 构建复现脚本：`D:\AI_helper\output\build-enhanced-pet.ps1`；打包脚本：`D:\AI_helper\output\package-enhanced-pet.py`；截图与测量目录：`D:\AI_helper\output\agent-discovery-verification`。这些本地路径描述本次验收现场，迁移源码后需要调整脚本中的路径。

## 后续：Codex 真实事件接入

同日发现 Codex 仅绑定进程与空 JSONL，缺少事件写入器。已增加只读 sessions 适配、更新本机程序和同路径便携包。上述哈希保留为初次交付历史；最新配置、产物哈希、性能和 2951 项通过的回归证据见 [Codex 联动修复报告](PR-REPORT-codex-link-2026-10-03.md)。
