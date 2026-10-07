# 麒麟本机长期助手交付报告

基线：`4cd311ebc56f5be8947c5b61ccbe7ceaf59599ad`；分支 `feat/running-agent-discovery`；2026-10-08。角色包保持3.0.2-keyboard-contact、105动作、68图层。功能使用说明见 [QILIN-COMPANION.md](QILIN-COMPANION.md)，工程约定见 [CONTEXT.md](../CONTEXT.md)，前次交付见 [键盘接触报告](PR-REPORT-qilin-keyboard-contact-2026-10-08.md)。

## 一、核心特性

用户可把有明确范围的工作交给麒麟，关闭面板后由桌宠继续执行。新增后台任务、指定时间与重复任务、自主跟进、等待回答/追加指示、暂停/继续/停止、可编辑长期记忆、结果文件、活动记录和主动提醒。右键与托盘的稳定动作ID为 `companion`；快速对话可预填任务。新功能沿用现有AI配置和通知设置，不增加设置一级域，不改变角色与动作。

参考已读取的官方 [Your dot](https://learn.chatgpt.com/docs/dots)、[任务与记忆](https://learn.chatgpt.com/docs/dots/tasks-and-memory)、[电脑与应用](https://learn.chatgpt.com/docs/dots/computers-and-apps) 与 [非交互模式](https://learn.chatgpt.com/docs/non-interactive-mode)。本轮实现本机能力；关机运行、云端常驻、跨设备同步和Slack/Teams服务不在本轮产物中。

## 二、修改文件说明

<!-- FILES_BEGIN -->
| 文件 | 增删 | 改动与原因 |
|---|---|---|
| `CONTEXT.md` | +9 / −0 | 定义长期助手任务/设置/生命周期归属，保持单一能力域契约。 |
| `docs/INDEX.md` | +2 / −0 | 登记功能指南和本轮交付报告，使文档可定位。 |
| `docs/QILIN-COMPANION.md` | +47 / −0（新增） | 用户入口、任务/记忆/调度、数据恢复、执行引擎与云端边界。 |
| `docs/PR-REPORT-qilin-companion-2026-10-08.md` | +121 / −0（新增） | 逐文件、性能、实机与交付门禁证据。 |
| `pet/app.py` | +70 / −0 | 懒创建/恢复服务、菜单与托盘入口、快速对话回调、结果提醒和退出清理。 |
| `pet/companion_store.py` | +394 / −0（新增） | 原子状态库、调度/暂停/继续/结果/记忆和完整持久化验证。 |
| `pet/companion_runner.py` | +312 / −0（新增） | 本机Codex与现有文字模型边界、结果协议、UTF-8与独立子进程回收。 |
| `pet/companion_service.py` | +249 / −0（新增） | GUI线程协调、QLockFile、后台工作线程、QueuedConnection、取消和存储失败停机。 |
| `pet/companion_panel.py` | +418 / −0（新增） | 四标签非模态任务/结果面板、固定主动作、响应式明暗控件和错误反馈。 |
| `pet/chat/prompt.py` | +9 / −3 | 可选长期记忆上下文，在每次发送前读取，当前请求优先。 |
| `pet/chat/widgets.py` | +3 / −1 | 现代聊天传入实例记忆路径。 |
| `pet/chat/legacy_widgets.py` | +3 / −1 | 经典聊天使用相同记忆语义。 |
| `pet/quick_chat.py` | +15 / −1 | 快速聊天记忆接入、显式任务预填按钮和不可用入口隐藏。 |
| `pet/context_menus/registry.py` | +7 / −1 | 稳定companion动作、标签、语义图标和可用性。 |
| `pet/context_menus/legacy.py` | +3 / −0 | 经典菜单接入同一长期助手回调。 |
| `pet/menu_templates/modern-default-v1.json` | +6 / −0 | 默认AI对话后新增入口，旧布局沿用既有补齐规则。 |
| `tests/test_companion.py` | +543 / −0（新增） | 28项公开状态/Qt/独立进程/取消/记忆/存储失败/短窗口回归。 |
| `tests/test_desktop_pet_features.py` | +4 / −0 | 精确新增菜单标签和具名模块/文档扫描，保留品牌红线。 |
| `tests/test_menu_layout.py` | +6 / −2 | 加入入口后的默认/注册/真实菜单/相邻移动精确预期。 |
<!-- FILES_END -->

四个新模块分别拥有状态、执行边界、GUI调度与非模态面板。`app.py` 只负责懒加载、恢复、入口、提醒和退出；聊天组件只增加记忆读取与任务入口，菜单继续使用现有注册表和布局迁移。菜单测试精确加入新的相邻入口，并保留排序与隐藏覆盖断言。没有增加依赖。

## 三、实现要点

- GUI线程拥有状态库、QTimer、QLockFile和面板，Python后台线程返回结果，QObject bridge明确使用QueuedConnection。run token拒绝暂停/停止后的迟到结果。
- 原子JSON写入先fsync再replace；状态容量16 MiB、100任务、80记忆、300活动。读取损坏/缺字段记录时保留原文件并解释原因。任务/聊天记忆使用完整条目的8000字符预算。
- 最多并行2项任务；重叠Codex目录串行。重复任务推进到未来时点，休眠后不连续补跑；自主跟进需该任务允许，最短60秒，最长30天，连续最多6次。相同跟进结果静默。
- Codex使用UTF-8 stdin、JSONL事件与结果schema；仅在有效结果且收到turn.completed后完成。继续时指定保存的精确UUID。执行器保留用户模型/认证/rules，只按任务选择read-only或workspace-write。
- Windows使用独立kill-on-close Job Object，复用ctypes结构，不使用ffmpeg全局Job；取消只回收本执行器拥有的进程树。进度落盘限每2秒一次，首次会话ID立即保存。
- 保存失败的暂停不取消仍在运行的工作；后台调度保存失败会暂停服务并禁用修改入口；删除记忆失败可见且可重试。退出后中断任务保持暂停，避免自动重复副作用。

## 四、性能分析

环境：Windows 11 build26200、16逻辑核、Python3.13.13、PySide6 6.11.2。命令：`E:/dsh-pet-dev313/Scripts/python.exe E:/qilin-codex-fix-20261007/dot-companion-20261008/benchmark_companion.py`；原始数据 `performance.json`。状态100个未来任务、20条记忆，134206 bytes。

| 路径 | 样本量 | 中位数 | P95 |
|---|---:|---:|---:|
| 检查100个未来任务 | 1000 | 1.038 ms | 1.333 ms |
| 构建受限记忆prompt | 500 | 0.295 ms | 0.377 ms |
| 从磁盘读取聊天记忆 | 500 | 1.016 ms | 1.363 ms |
| 原子保存记忆（含fsync与replace） | 30 | 3.534 ms | 4.426 ms |

空服务真实Qt事件循环15秒：自身调度timer未启动、0工作线程，进程线程7→7、Python线程1→1；I/O全部增量0；RSS变化−73728 bytes；进程CPU为单核的0.104%。该数字包含验收采样timer，不能解释成应用全进程稳态数字。

没有状态文件时应用只检查文件存在性，不创建服务/timer/worker。存在待执行/定时任务时每5秒调度；上述100任务样本推算此新增检查约0.021%单核，仅为按实测成本/触发频率计算，不冒称长时间全进程实测。保存、结果落盘和普通聊天读取记忆会新增磁盘调用；文本任务只在执行时使用已有模型接口，本机任务启动Codex进程；最多2个工作线程，CLI还各有stdout/stderr读取线程。状态有容量上限，历史结果文件需用户自行整理。

<!-- EXE_PERF_BEGIN -->
`benchmark_exe.py`交替运行原安装与本轮候选EXE各2次，每次20秒，后10秒为稳态；隔离且相同配置、同一105动作/68图层角色资源、未创建任何长期助手任务。原始每秒CPU/RSS/线程/子进程/I/O数据在exe-performance/records.json。

| 实际产物 | 启动中位数 | 稳态CPU（单核%） | 稳态RSS |
|---|---:|---:|---:|
| 原安装 | 1.087s | 26.890% | 118.204MiB |
| 本轮候选 | 2.288s | 29.795% | 120.107MiB |

本轮候选稳态CPU差+2.905个百分点、RSS差+1.903MiB。样本有限，不宣称改进性能；两组最后均没有INET连接。稳定服务与新增路径的测量分列，不能将此短时角色渲染对比归因于执行模型或云端任务。
<!-- EXE_PERF_END -->

## 五、实机运行记录

证据根目录 `E:/qilin-codex-fix-20261007/dot-companion-20261008`，验收使用独立状态，不混入用户真实记忆和任务。

原安装没有长期助手入口。真实配置公共字段核验：当前模型 `qwen3.5:9b`、接口 `http://127.0.0.1:11436`；未输出密钥、未修改真实配置。`real_text_task.py` 使用该实际模型经CompanionService完成一项中文清单，**12.573秒、completed、1次通知、Markdown成功保存**。结果与时间见 `real-local-text-result.json`。

原生Windows平台UI已在720/1100宽、明暗、150% DPI（720×500逻辑像素）检查四个标签、长中文/英文、等待回答、错误禁用态和底部按钮可达性。每场景7张截图，实际像素已查看，记录在 `native-ui/*/records.json`。发现并修正创建动作在短窗口需滚动的问题（主动作移到固定底栏），以及原生选择框深色对比不足（改用ModernSelect和共享编辑器tokens）。未使用Cocoa/Linux能力fake冒充实机结果。

本机当前PATH实际解析到Codex原生CLI **0.160.1**，`exec resume --help`确认支持schema/JSON/精确UUID；最初检查npm CLI为0.154.0。真实独立子进程验证UTF-8输入、JSONL完成协议、取消后回收子进程树；没有用真实模型修改工程或借CLI代理完成实现。本轮没有以真实Codex模型推理验证所有文件/工具任务，其执行效果仍取决于用户Codex配置、连接与授权。实际本机模型只验证了文字任务。

<!-- DELIVERY_BEGIN -->
真实候选EXE通过原生右键菜单打开麒麟长期助手，UIAutomation输入文字、选择当前聊天模型、提交任务，再收起面板；模型实际执行后状态completed且输出文件存在。记录在exe-ui-candidate/native-result.json，正常退出码0。

安装后在用户原配置下通过真实Windows右键菜单再次打开“麒麟长期助手”，进程40480、窗口标题与UI可访问性确认通过；截图installed-companion.png已实际查看，installed-ui.json记录窗口与进程。验收测试任务保持在独立配置中。

本轮安装已替换到`D:\AI_helper\dsh-pet-enhanced\qilin-pet-webm-chat.exe`，旧主进程8024用核验完整EXE路径后的WM_QUIT正常退出（0）；原launcher SHA保持不变，2份私有配置在替换时逐文件SHA一致。1102个安装文件与候选/staging/便携目录一致，角色包两份完整SHA清单核验、105动作、68PNG、无旧WebM。

备份：`E:\qilin-codex-fix-20261007\dot-companion-20261008\installed-before-companion`；完整旧安装移位保留：`D:\AI_helper\dsh-pet-enhanced-before-companion-20261008`；私有配置备份：`E:\qilin-codex-fix-20261007\dot-companion-20261008\private-config-before-companion`。此前备份均保留。

EXE SHA256：`3ed4bb15735c4aee19a9645fc2db4cbb1d0b240f1b10313579630e1c201873b3`。
便携包：`E:\qilin-codex-fix-20261007\qilin-pet-portable-20261008-companion.zip`，1102个成员，115148840 bytes；每个解压成员的大小/SHA都与安装文件一致。
ZIP SHA256：`6e8dfea751be1b11807de7efbaad69c4f431191e46c7cfbd14a5a19228e83435`。
<!-- DELIVERY_END -->

## 六、测试与验证

最初16项领域/协议/菜单测试失败；随后21项通过。新增保存失败/记忆预算三项红灯后修复；短窗口主按钮可达性红灯后修复。首次全量发现两项快速对话回归：独立PetInstance没有shell时直接取callback导致无法显示，已改为可选入口。

<!-- GATES_BEGIN -->
| 门 | 实际结果 |
|---|---|
| ruff / diff --check | `python -m ruff check .`与`git diff --check`通过 |
| 聚焦与相关 | companion共28项；`pytest-related-final.log`为109 passed、1 skipped |
| 全量 | `python -m pytest -q`，3056 passed、13 skipped、252 warnings、207.73秒 |
| 时序族CPU满载三轮 | 每轮319 passed、2 skipped；总耗时36.02s, 37.05s, 36.81s |
| 满载质量 | 110个1秒样本，平均99.872%、最大100.0%，负载子进程全部回收 |
| 构建 | UTF-8检查、Qt/Shiboken DLL链、真实桌宠/设置窗口启动与正常退出通过；13个嵌入模块与测试源码完全相同 |

命令与原始日志均在证据目录。首次压力脚本每次计算批次太短，同步检查Event造成负载不足（81.66%）；三轮测试均绿，但未当作满载证据。将负载计算批次提高到500000后重新完整三轮，结果见上表；旧记录保留在stress-initial。未改变产品或放松测试断言。
<!-- GATES_END -->

## 七、已知限制与后续

云端、离线关机运行、跨设备与第三方消息服务需要外部后台；本版不声称实现。当前聊天引擎没有工具；文本任务要把资料直接提供给模型。Windows实机已验收，macOS/Linux未实机运行。记忆以显式保存为准，不自动授权操作；超过每轮记忆预算的后续条目不带入。任务周期暂不能直接编辑，可停止并创建新任务。历史输出保留，不自动清理用户结果。

## 八、风险与回滚

只增加独立companion数据，不迁移既有聊天认证或角色配置。使用Codex任务可按用户勾选修改所选目录；暂停/停止不会撤销已经执行的修改。原安装、私有配置和此前备份全部保留；回滚时先正常退出麒麟，再恢复本轮安装备份，保留companion目录供后续恢复。旧版本不启动该调度器。
