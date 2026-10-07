# 麒麟少女形象与程序品牌图标交付报告

基线：官方 v4.2.1 `f4cb620` 加同日 Agent 识别、会话联动增强；分支 `feat/running-agent-discovery`。日期：2026-10-03。本报告是当日 Windows 11 x64 实测快照，尚未创建上游 PR。

关联：[文档索引](INDEX.md)、[上次会话联动报告](PR-REPORT-codex-link-2026-10-03.md)、[打包规范](ONEDIR_PACKAGING.md)、[交付模板](PR-REPORT-TEMPLATE.md)。

## 一、核心特性

将用户自定角色安装为外部 `qilin` 角色包：橙黄国风、直立人形女性、绒感猫耳、金色麟角、小黄翼、右嘴角单颗虎牙；去掉动物鬃毛。龙尾保留橙色鳞片、黄色腹纹和黄色尾尖，按最后反馈将长尾稿缩短约一半。黄色服装腹部原云纹、打字笔记本和程序图标使用同一红色品牌标志。

角色原画及编辑均使用内置 imagegen；动画为 Qt/FFmpeg 功能姿态关键帧循环。没有启动其他视频项目、付费视频任务或编写叙事剧本。最终母版、动作图、步态图分别为 1254×1254、1086×1448、1024×1536 RGBA；原始生成文件与每轮实际提示词保留在仓库外。

## 二、修改文件说明

本轮相对上次交付的新增范围为 5 个源码/测试/报告文件；既有未提交的运行程序识别及会话适配改动均保留。

| 文件 | 本轮行数 | 修改意图 |
|---|---:|---|
| `pet/branding.py` | 新增 23 行 | 在 GUI 线程从部署根目录加载可选 `branding/logo.png`；冻结程序依据 EXE 位置，与启动工作目录无关 |
| `pet/app.py` | +10 / -1 | AppShell 初始化时缓存品牌 QIcon，设置应用窗口图标，并在新建和刷新托盘时复用 |
| `tests/test_branding.py` | 新增 56 行 | 验证冻结程序路径、源码工作目录、缺失/损坏文件回退 |
| `docs/INDEX.md` | 本轮新增 1 行 | 登记本报告；同日之前的 +4/-1 改动保留，累计 +5/-1 |
| 本报告 | 新增 90 行 | 汇总制作、品牌、性能、实机、测试和回滚证据 |

15 个角色 WebM、manifest、移动曲线、preview、Logo PNG/ICO、EXE/ZIP、生成提示词及验收脚本均在 `D:/AI_helper/output/` 或安装目录，不作为源码文件加入 Git。未删除源码文件。

## 三、实现要点

`load_application_logo()` 返回空 QIcon 时，托盘继续采用既有角色头像路径；有效图标只在 AppShell 构造时加载一次，刷新菜单复用缓存。没有新增设置键、配置迁移、定时读文件、线程或网络请求。字符头像、聊天头像和动画仍采用角色资源。

EXE 使用红色多尺寸 ICO 构建，ICO 含 16/24/32/48/64/128/256 尺寸；同一图片用于窗口/托盘。桌面快捷方式只更新 IconLocation，保持启动器路径和参数。

外部角色包整体保留 `characters/qilin/videos/` 布局，15 个 VP9-alpha WebM 均为 640×360、24fps、透明背景、脚底 y=330。独立解码 alpha≥128 待机边界为 [234,42,407,330]，manifest body_box 为镜像对称的 [233,42,407,330]。保留现有联动需要的“写代码”“吃Token”“轻快记录”“漂浮踏步”名称。

## 四、性能分析

命令：`E:/dsh-pet-dev313/Scripts/python.exe D:/AI_helper/output/qilin-pet/verify_live_branding.py`，以及同目录 `render_qilin.py`、`verify_qilin.py`、`verify_live_qilin.py`。环境：Windows 11 x64、CPython 3.13.13、PySide6 6.11.2、FFmpeg VP9-alpha。

| 指标 | 实测 | 触发/归属 |
|---|---:|---|
| 部署 Logo 首次加载 | 4.533 ms | 进程初始化一次；本机冷调用 |
| 已缓存磁盘 Logo 加载 | 均值 0.0621 ms / p95 0.1193 ms | 100 个独立验收调用；运行程序不定时重读 |
| 15 段动画编排及编码 | 24.234 秒 | 离线制作一次，共 1236 帧 |
| 15 段完整解码 + 实际 Qt 播放 | 7.955 秒 | 独立验收一次 |
| 全部动画体积 | 5,703,870 B | 外部磁盘角色资源 |
| 实机主进程 CPU | 单核口径 20.961% | 12 个样本，观察 6.262 秒 |
| 实机主进程 RSS | 129,789,952–141,889,536 B | 同一短时观察，期间有真实联动解码 |

新增稳态路径仅复用一个 QIcon，未在动画帧循环或 Agent 轮询中增加 Logo 文件读操作。新增初始化文件 stat/PNG 读取；无新增网络、线程或周期 I/O。256×256 RGBA 原始像素为 262,144 B，Qt/native icon 缓存另计，未做受控的前后 RSS 差值实验。CPU/RSS 数字属于整个已有桌宠主进程，不是品牌函数成本，也不能证明长期内存稳定或相对旧版的性能变化。

## 五、实机运行记录

- 前提：原增强版 EXE 和快捷方式仍使用旧品牌，角色曾为制作中的动物稿。用户最后要求直立少女、猫耳、短龙尾，以及服装腹部、笔记本、程序图标的统一品牌。
- 隔离构建：`powershell -NoProfile -ExecutionPolicy Bypass -File D:/AI_helper/output/build-qilin-pet.ps1`；PyInstaller 6.22.3 / Python 3.13.13，构建约 99.4 秒成功。输出独立存放于 `E:/dsh-pet-qilin-brand-build/dist/`，未覆盖受保护稳定版。
- 安装前保留完整旧客户端 `D:/AI_helper/dsh-pet-enhanced-before-qilin-20261003-151000`。通过本进程右键菜单“退出”正常结束 PID 14468；旧角色另外保留于 `D:/AI_helper/dsh-pet-local/qilin-role-before-final-20261003-153242`，避免旧动作混入新版。
- 安装位置继续为 `D:/AI_helper/dsh-pet-enhanced`。当前 EXE PID **51044**，Responding=True。实机截图可见少女坐着打字、笔记本红色标志、猫耳、小黄翼和短鳞片尾；461×281 的本进程 PetWindow 可视矩形截图保存在 `D:/AI_helper/output/qilin-pet/小瑞麟-少女桌面实机.png`。
- 对该 EXE 自有 ffmpeg 子进程采样，观察到新版 `写代码.webm`、`吃Token.webm`、`轻快记录.webm` 解码。完整资源解码及 Qt 播放验证另见下节；没有修改真实会话文件来制造状态。
- 配置相对制作前备份仅 `character/rx/ry` 变化，分别为角色及正常窗口位置。chat 与 agent_link 两块逐字段完全相同。仍为本机 `qwen3.5:9b`，11436 桥接 health 正常，Ollama 11434 tags 确认模型存在。
- 从运行程序的 3 个可见 Qt 窗口读取原生 HICON，32×32 非透明部分均为红色品牌（red fraction=1.0）；EXE 原生资源图标也为 1.0。桌面快捷方式 IconLocation 已指向部署目录的 `branding/logo.ico`，原启动路径和参数保持。
- 边界：缺失/损坏 Logo 返回空图标的公开接缝验证通过；原“深深”角色仍可切换。没有改动设置页面布局和键盘导航。
- 验收工具修正：首次图标探针错误假定资源提取返回 1，现场返回大/小两个有效句柄，改为检查有效句柄和真实红色像素。直接抓取透明 Qt 窗口得到黑图，改为只截 UIA 所属 PetWindow 的屏幕矩形后做像素/视觉确认；黑图未作为视觉通过依据。
- 清洁包内容与隔离构建对照：1214 个构建文件，加 24 个角色/品牌/授权/说明文件，没有旧二进制混入。包内不含用户配置、日志、对话或密钥。

EXE 大小 **11,132,868 B**，SHA-256 `9d0db08514cb720414e170fa75794b5860fde838e1af04a7d3eca30afd7ebab7`。

角色包：`D:/AI_helper/output/小瑞麟-麒麟少女桌宠形象包-v1.0.zip`，22 文件，5,878,497 B；SHA-256 `9f099faddb70bc7d1270b1c9e2d6bc9e23a8c98d2e164cec4257ed9d46a195d6`。

完整便携包：`D:/AI_helper/output/dsh-pet-v4.2.1-qilin-brand-windows-x64.zip`，1238 文件，185,532,170 B，解压 338,859,256 B；SHA-256 `eb739c12bdf19afb14298d58cd4c7c7661d984bdd305addce8dc172e846d5525`。两包 CRC 全部通过，旧便携包保留。

## 六、测试与验证

| 门 | 命令与结果 |
|---|---|
| 测试先行 | 3 个新品牌接缝用例先因缺失 pet.branding 失败；实现后 3 passed，1.99 秒 |
| 全量 | `python -m pytest -q`：**2954 passed / 11 skipped / 261 warnings，268.25 秒** |
| 全量日志 | `D:/AI_helper/output/qilin-branding-full-tests.log` |
| 静态 | `python -m ruff check pet tests scripts`、`git diff --check` 通过；Git 仅提示 CRLF 转换 |
| 角色数据 | `verify_qilin.py` 全量 15 个 WebM / 1236 帧，四类真实 Qt 播放每类至少 6 frameChanged，无错误，透明四角、边界、步幅和曲线通过 |
| 冻结程序 | 原生红色图标、已部署形象、真实工作动作、配置保留和本机模型桥接通过 |
| 包校验 | 两个 ZIP `testzip()` 通过；私有配置和日志文件断言通过 |

全量完成后源码没有继续变更，后续是角色像素更新、验收脚本修正及本文/索引补充；文档门单独执行并追加结果。不推送上游，因此未执行推送前的 CPU 满载三轮时序门。

## 七、已知限制与后续

仅本机 Windows 11 x64 实测。动画采用姿态关键帧、眨眼、轻微呼吸/浮动和插值；不是三维骨骼动画或生成视频。角色包可用于支持外部角色的 v4.2.1；原版程序没有本次可选品牌加载功能，托盘/窗口品牌需使用更新的完整客户端。新电脑需独立设置其本机模型和 Agent 数据来源。

## 八、风险与回滚

可通过“切换角色”恢复旧角色。要恢复完整旧程序，正常退出当前 EXE 后使用保留的客户端备份；个人配置另存于用户 Roaming，未打包或迁移。没有新增配置键、数据库迁移和对外写入。制作期间的原始图像和旧角色均保存为仓库外版本档案。
