# 麒麟旋转展示尾根与裙摆遮挡修复

基线：`4259e10b5b1d89c92bfe37005557e126570c929a`，分支 `feat/running-agent-discovery`，Windows 本机 2026-10-08。角色资源版本 `2.0.22-tail-root`。本报告是本轮历史快照，延续[轮廓与摆放](PR-REPORT-qilin-alpha-geometry-2026-10-07.md)和[本子接触修复](PR-REPORT-qilin-notebook-contact-2026-10-07.md)；安装入口见[打包指南](ONEDIR_PACKAGING.md)。

## 一、核心特性

用户指出“小幅度原地360度旋转展示”的尾巴位置不对。旧片尾巴从头发/上腰附近伸出，过长的尾身与背部、裙摆和腿部混合。本轮移除旧尾及其残片，将一条短尾绑定到后臀，尾根藏在后侧裙摆下面，按角色转向连续缩短侧向投影。

同一条短尾贯穿全部241帧，避免新旧尾淡入淡出形成双尾。旧尾遮挡的裙布及两次背面转侧身时的上腿像素局部修复；原角色动作、640×360画布、24fps与既有摆放保持。尾巴与对应遮挡在全部解码帧上验收，验收范围不延伸为整个动画库完成。

## 二、修改文件说明

本轮六个源码文件。视频、制作脚本/缓存、测试日志、便携包和配置在E盘；源码保存生成参考与制作配方。已有文本增删来自 `git diff --numstat`，新增文本使用 `git diff --no-index --numstat -- /dev/null <file>`；二进制用实际字节数。

| 文件 | 增删 | 改动与原因 |
|---|---|---|
| `packaging/character_postprocess/assets/qilin-short-tail-reference-20261008.png` | 新增二进制，508,528字节 | 提供后臀位置的短尾参考，局部裁取尾巴用于原动作合成。 |
| `packaging/character_postprocess/assets/qilin-rear-cloth-reference-20261008.png` | 新增二进制，518,005字节 | 提供移除高位旧尾后的背面裙布，补全被旧尾遮挡的局部。 |
| `packaging/character_postprocess/qilin-tail-root-20261008.json` | 新增，+290 / −0 | 保存两次精确生图提示词、实际尺寸/SHA、离线脚本与输入SHA、18个尾根关键帧及验收范围。 |
| `docs/PR-REPORT-qilin-tail-root-2026-10-08.md` | 新增，+89 / −0 | 保存视觉、性能、满载失败及复测、实机安装、包与回滚证据。 |
| `docs/INDEX.md` | +2 / −1 | 登记本报告，并补充几何基线后的局部接触与尾根覆盖指针。 |
| `docs/ONEDIR_PACKAGING.md` | +2 / −0 | 明确2.0.22三文件覆盖、配方与回滚入口，避免重复几何变换。 |

播放器、应用依赖和EXE字节保持。视觉修复依实际像素验收，没有新增只复述离线合成实现的单元测试。

## 三、实现要点

[制作配方](../packaging/character_postprocess/qilin-tail-root-20261008.json)绑定最终 `render_tail.py`、`segment_head.py` 与原帧/遮罩SHA。SAM2.1 Hiera small仅用于离线保护前景头发；遮罩分数不能代替视觉检查，也不进入应用依赖。

原输入已包含scale 1、dx −48.5、dy −1和sigma 0.65，不能再套一次。短尾工作图55×53，按18个尾根关键帧插值并作连续方向投影，置于裙摆和角色前景之后。预乘alpha Lanczos与0.55源像素过滤用于局部图层；编码前原图上方158行逐字节保留，编码后的颜色允许有编码误差。

两张参考由内置imagegen生成，实际均为1672×941 RGBA；工具未报告后端模型，配方保留未知。生成的整个人物没有替换原动作，只取尾巴、布料及被旧尾污染的局部腿部。早期保留首尾原尾的方案会产生双尾，已弃用；最终版本全片采用同一条短尾。

## 四、性能分析

环境：Windows、16逻辑核；应用测试解释器 `E:/dsh-pet-dev313/Scripts/python.exe`，制作解释器 `D:/anaconda3/python.exe`，NumPy/OpenCV/Pillow和FFmpeg 8.1.1。实际命令：

```powershell
D:/anaconda3/python.exe E:/qilin-codex-fix-20261007/tail-root-20261007/render_tail.py --encode
E:/dsh-pet-dev313/Scripts/python.exe E:/qilin-codex-fix-20261007/tail-root-20261007/benchmark_tail.py
```

同一实际EXE，独立配置，旧/新旋转片交替各3×24秒；每轮后12个一秒样本统计CPU/RSS，计入EXE和解码子进程，CPU为psutil单逻辑核口径。记录在 `runtime-performance/summary.json`。基准在安装前完成；复测旧片必须使用 `before/external`，不能原样重跑已指向新片的基准脚本。

| 指标 | 修改前 | 修改后 |
|---|---:|---:|
| 合计CPU均值 | 28.475% | 26.650% |
| 合计RSS均值 | 147.264MiB | 147.527MiB |
| 后半段RSS增量均值 | +8.280MiB | +7.695MiB |
| 主机CPU均值 | 22.228% | 21.167% |
| 线程数均值 | 81 | 81 |
| GUI启动中位数 | 0.763657s | 0.760938s |

样本CPU减少1.825百分点，RSS增加0.263MiB；短样本和主机负载有波动，不能据此推断普遍提速或长期内存无增长。运行时仍播放预合成的同尺寸/同帧率WebM，按原动作调度触发，没有新增模型、图层计算、线程、系统调用、网络请求或新的磁盘访问路径。离线最终编码一次60.588s；复制三文件及核验两份角色SHA 1.815s；便携包制作及1069成员核验74.761s，均不在播放热路径。

## 五、实机运行记录

证据根目录：`E:/qilin-codex-fix-20261007/tail-root-20261007`。旧片SHA `476f9a7fbea3aced6f41c09338b56ab5bff0eba9793024ae057c431dc81786a5`；新片SHA `1a5240a181de23d9cdf0381fc079bfa0edcf5880cf543503a531a610191dcbbc`。

1. 用户截图与旧帧确认高位尾根和长尾问题。11页覆盖全部241个实际解码帧，全身/腰臀白暗底已查看；尾根、裙摆遮挡、转身及首尾循环通过。`decoded-review-summary.json`标记 `ACCEPTED_FOR_TAIL_REPAIR`；动态对照 `before-after.gif`。
2. 原生Qt完整播放241帧，错误0，中位间隔42.029ms，超过84ms为0，回执 `native-candidate.json`绑定新片SHA。完整播放覆盖末帧，帧文件完整不单独作为视觉通过。
3. 候选和安装目录分别运行真实Windows `PetWindow`；17个旋转抓取标签与前后待机共19组实际绘制像素完全一致，位置固定、二值mask为空，DPR1/scale0.85。`turn-f240`标签在循环回调时实际帧号为0，不能计为独立末帧抓取；末帧覆盖来自全帧解码审查和完整播放。其他DPR未实测。
4. 旧PID40744经完整路径核实后对其拥有窗口的线程发送WM_QUIT，正常退出。三文件在 `before/external`、`before/internal`备份；仅本段WebM和两份manifest替换。外部 `characters/qilin`、内部 `_internal/assets/characters/qilin`各109文件SHA全部与候选一致，其他104段（含本子接触修复）字节不变。
5. 原启动链 `D:/AI_helper/dsh-pet-local/Start-dsh-pet.ps1`重启成功，记录PID54688、窗口3871534。EXE `D:/AI_helper/dsh-pet-enhanced/qilin-pet-webm-chat.exe`，SHA仍为 `caeae34968902f2e1ef58fe4cc3152883e68ec0e187d125765d110fe17c3cde3`。实机图 `installed-window.png`是待机画面，用于确认安装运行；尾巴画面见动态对照和实际绘制记录。
6. 新便携包 `E:/qilin-codex-fix-20261007/qilin-pet-portable-20261008-tail-root.zip`，1,340,589,400字节，SHA `e1a13c1607a93b16cb958394a01881a12507a73c205ccf981de6db0baa93834a`。1069成员全部核验，仅3成员替换，其余与2.0.21旧包SHA一致。旧包保留。

真实绘制复验命令（使用新的输出目录保存复验）：

```powershell
E:/dsh-pet-dev313/Scripts/python.exe E:/qilin-codex-fix-20261007/tail-root-20261007/preview_tail_pet.py D:/AI_helper/dsh-pet-enhanced/characters/qilin installed-pet-recheck
```

## 六、测试与验证

- 全量命令：`QT_QPA_PLATFORM=offscreen E:/dsh-pet-dev313/Scripts/python.exe -m pytest -q`，**2981 passed / 13 skipped / 252 warnings，194.60s**，`full-tests.log`。此后仅补充文档与本地台账，没有产品代码改动。
- 制作解释器媒体回归：`D:/anaconda3/python.exe -m pytest --noconftest -q tests/test_alpha_fringe_tool.py tests/test_alpha_geometry_tool.py`，**7 passed，0.33s**；应用解释器未安装NumPy/OpenCV，相关跳过由此实际补跑。
- 初组时序三轮各90 passed，但主机CPU均值仅61.418%，保留记录，不能算严格满载门禁。
- 满载r2使用16个NORMAL优先级施压进程，每200万次运算检查停止事件，与打包同时运行；CPU均值98.923%，第一轮 **2 failed / 88 passed，40.41s**。失败为 `test_rapid_start_stop_leaks_no_threads_or_processes`、`test_stop_terminates_ffmpeg_process`，均在reader就绪5秒等待超时。使用既有shenshen待机测试媒体，未读取本轮新片；日志 `stress-gate-r2/stress-round-1.log`完整保留。
- 阅读失败日志和就绪路径后，r3暂停打包，将施压优先级设为BELOW_NORMAL，仍每200万次运算检查事件。测试文件、断言、等待预算和CI跳过条件未改。命令 `E:/dsh-pet-dev313/Scripts/python.exe E:/qilin-codex-fix-20261007/tail-root-20261007/run_timing_full_load_r3.py`，WebM reader/clip生命周期、窗口碰撞、交互锁四族三轮均 **90 passed**（pytest 16.71/19.03/16.78s；墙钟17.521/19.617/17.404s）。55个CPU样本均值99.429%，最低83.6%、最高100%；全部施压进程退出，`stress-gate-r3/stress-record.json`记录条件。
- r3结果与启动争用/饥饿解释一致，但同时改变优先级和并发打包，未分别隔离两因素，不能宣称已证明唯一根因，也不能宣称同优先级极端争用已修复。播放器和测试源码保持基线。
- 文档/品牌收尾检查、最终 `E:/dsh-pet-dev313/Scripts/python.exe -m ruff check pet tests scripts`及 `git diff --check`：**46 passed，1.45s**（`tests/test_pr_report_discipline.py`、`tests/test_qilin_product_cleanup.py`，`final-focused.log`）；ruff与diff检查通过。

## 七、已知限制与后续

台账保留52项明确问题与50项待完整时序复核，仅新增本段尾巴专项接受与当前SHA，不把它登记为所有原动作问题通过。离线参考/脚本/缓存与私有配置不随EXE分发。GitHub交付通过真实GitHub Desktop提交和Push origin；最终本地HEAD、远端及跟踪引用一致性回执写入本轮 `final-delivery-verification.json`，CLI只作只读核验。

## 八、风险与回滚

影响范围为本段视频及两份角色manifest；版本更新不新增配置键。回滚先重新核实实际EXE完整路径并正常退出，将 `before/external`与 `before/internal`中三文件分别复制回对应目录，核对备份SHA，再沿用原启动链。便携包可使用保留的2.0.21版本。不要按进程名强杀、重跑已完成安装/打包脚本，或触碰EP01、8189及未知服务。
