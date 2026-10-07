# 麒麟角色去绿边、平滑轮廓与统一摆放

基线：`454477306ceebf4339ecd4c6a8715130ad8ac877`，分支 `feat/running-agent-discovery`，Windows 本机 2026-10-07。本轮角色版本为 `2.0.20-smooth-aligned`，105 段、25,182 帧、640×360 / 24fps。延续[品牌与动画修复报告](PR-REPORT-qilin-codex-repair-2026-10-07.md)，早期几何记录见[历史报告](PR-REPORT-qilin-smooth-motion-2026-10-04.md)。

## 问题与结果

实机 WebM 像素本身带绿色和橄榄色污染；原先约 3px 的处理范围漏掉宽边。多数动画比待机向右偏约 48px，挥手、写代码、轻快记录的头部约小 11.5%。部分工作动画的站立脚底 y309，其他片段 y331。

本轮采用两次离线处理：先恢复污染轮廓的前景色，再平滑 alpha 覆盖率、按头部与站立脚底做每段固定等比变换。首帧脚底范围变为 y330–332；每段原有起跳、下蹲、转身和呼吸位移保留。五段原有贴顶特效单独使用 1px 顶部余量，首帧脚底 y332。没有逐帧拉齐、拉伸身体或增删动作。

`PetWindow` 在 Windows 已采用预乘 alpha、DPR 对应物理像素和平滑插值，并保持窗口二值 mask 为空；本轮无需修改播放器。生成后实际解码、数学轮廓检查、抽帧画面检查、Qt 完整播放、安装字节核验分别记录。

## 修改文件说明

下表列出本轮全部九个新增/修改文件，增删行数对应本轮 diff；新增文件按 UTF-8 文本行计数（提交时可由 `git show --numstat` 复核）。

| 文件 | 增删 | 目的 |
|---|---|---|
| `scripts/repair_alpha_fringe.py` | 新增，+227 / −0 | 恢复 8px 边缘带绿色/橄榄污染，保护真实绿色道具，保留 alpha，外扩透明 RGB 后编码 alpha VP9。 |
| `scripts/repair_alpha_geometry.py` | 新增，+200 / −0 | 0.65 原像素 alpha 平滑、预乘 Lanczos 固定等比缩放/平移、透明 RGB 外扩及分阶段编码；拒绝源文件覆盖。 |
| `tests/test_alpha_fringe_tool.py` | 新增，+41 / −0 | 前景身份、alpha、细半透明轮廓以及真实绿色道具的公共回归。 |
| `tests/test_alpha_geometry_tool.py` | 新增，+52 / −0 | 透明绿色 RGB 不渗出、实体内部颜色不变、细角保留、动作位移按固定比例保留、无效参数拒绝。 |
| `tests/test_desktop_pet_features.py` | +3 / −0 | 构建指南包含真实制作目录和证据链接，归入工程文档豁免，修正品牌文案门禁误报；产品文案检查继续保留。 |
| `packaging/character_postprocess/qilin-alpha-geometry-20261007.json` | 新增，+2015 / −0 | 105 段的固定参数、原始/去绿/最终 SHA、帧数、站立框和边界特例；不含私有配置。 |
| `docs/ONEDIR_PACKAGING.md` | +2 / −0 | 构建角色包之前指向当前后处理与验收记录。 |
| `docs/PR-REPORT-qilin-alpha-geometry-2026-10-07.md` | 新增，+78 / −0 | 记录素材修复、性能、测试、实机与回滚证据；历史报告保留原时间范围。 |
| `docs/INDEX.md` | +1 / −0 | 登记当前报告，给后续制作和安装提供入口。 |

实际安装替换外部优先目录与包内目录各 109 文件：105 WebM、两份 manifest、RGBA 预览和步态曲线。manifest 更新版本、105 个逐段 SHA 与真实帧数，身体框 `[196,40,444,335]` 为解码待机采样并集的镜像对称框；预览取最终待机真实首帧。生成媒体保存在 E 盘交付包，不混入源码提交。

## 性能分析

制作环境：`D:/anaconda3/python.exe`，NumPy 1.26.4、OpenCV 4.13.0，FFmpeg 8.1.1；应用测试为 `E:/dsh-pet-dev313/Scripts/python.exe` / PySide6。离线制作使用四个普通工作线程；并行运行 Qt 验证和代码测试，不能把墙钟时间当独占机器基准。

| 样本与路径 | 实测 |
|---|---|
| 去绿 105 段，完整编码/解码审计 | 批次墙钟 737.41s；帧处理累计 1,978.22s。边缘绿色检测计数 14,735,685 → 110,623，减少 99.249%；真实绿色图标单独保护。 |
| 去绿阶段透明度 | 编码前 alpha 完全相同；解码舍入最大 1/255；alpha≥128 轮廓变化 0。 |
| 平滑/几何主批次 105 段 | 墙钟 910.74s；最终已接受各段编码累计 3,019.49s，像素处理累计 2,837.77s；五段边界修正另行编码，旧候选保留。 |
| 最终透明度 | 对预期平滑及固定变换逐帧复核，编码舍入最大 1/255；所有帧主要连通区域映射到画布外的像素为 0。 |
| 原生 Qt 105 段全播放 | 25,182 帧全部出现；错误 0；各段帧间隔中位数的中位数 41.987ms；超过 84ms 的间隔 0。批次 902.07s 包含等待生产输出。 |
| 实际 EXE，修改前/后待机各 3×24s | 合计 CPU 均值 32.156 / 33.772%（psutil 单逻辑核口径）；RSS 155.049 / 155.968MiB；GUI 启动中位数 1.756 / 1.738s。 |
| 同一短测后半段 RSS 增量 | 修改前 +5.285MiB，修改后 +3.255MiB；不能据此宣称长期内存不增长。主机负载均值 92.81 / 90.90%，不宣称整体提速。 |
| 安装复制与两份 SHA 核验 | 7.212s。 |
| 新便携包生成及全成员核验 | 54.257s；1,341,934,418 字节；1069 成员，其中 109 个角色文件替换，其他成员与旧包字节 SHA 相同。 |

运行路径继续解码 640×360 / 24fps 素材，没有运行时轮廓处理、额外模型或 NumPy/OpenCV 依赖。新增 CPU、线程和读写只发生在离线制作；播放仍使用原有 FFmpeg 解码进程及 Qt GUI 路径，没有新增网络调用。短时性能测量在制作高负载下完成，CPU +1.617 百分点和 RSS +0.919MiB 仅描述这些样本。

可复现单段制作，从仓库根目录执行（示例参数来自校准配方）：

```powershell
D:/anaconda3/python.exe -m scripts.repair_alpha_fringe source.webm clean.webm --ffmpeg <ffmpeg.exe>
D:/anaconda3/python.exe -m scripts.repair_alpha_geometry clean.webm final.webm --ffmpeg <ffmpeg.exe> --scale 1 --dx -48.5 --dy -1 --sigma 0.65
```

105 段的制作、注册、审计和实测命令保存在 `E:/qilin-codex-fix-20261007/green-edge`：`batch_repair.py`、`batch_geometry.py`、`correct_boundary_clips.py`、`native_geometry_batch.py`、`benchmark_media_runtime.py`。代码 SHA 对应的制作工具原字节保存在 `production-tools`。

## 实机运行记录

1. 实际解码各段原始视频并核对 105 段首/四分位/中/四分之三/末帧。最终 525 张解码采样在白底和深底共 18 页复核；细角、发丝和尾巴保留，明显绿圈及硬锯齿改善。抽帧检查不等同完整动作剧情/道具验收。
2. 真实 Windows `PetWindow` 在 DPR1 / scale0.85 下切换 12 段，位置固定；窗口 mask 为空，QPixmap DPR 与窗口一致；保存透明绘制结果及明暗桌面截图。候选与安装目录分别运行，记录位于 `real-qt-preview` 和 `installed-qt-preview`。未实际测试其他显示器的 DPR。
3. 安装前逐项核对外部/内部备份及 EXE SHA，仅对核实的 PID33652 的窗口所属线程发送 `WM_QUIT`。替换并核验两份目录各109文件，沿用 `D:/AI_helper/dsh-pet-local/Start-dsh-pet.ps1` 启动链。
4. 安装后实际进程 PID45916，EXE 为 `D:/AI_helper/dsh-pet-enhanced/qilin-pet-webm-chat.exe`，SHA `caeae34968902f2e1ef58fe4cc3152883e68ec0e187d125765d110fe17c3cde3`。实机窗口截图 `installed-window.png` 确认干净轮廓；保持运行供用户使用。角色目录两份所有字节与候选一致，完整原生播放证据绑定同一组视频 SHA。
5. 新便携包：`E:/qilin-codex-fix-20261007/qilin-pet-portable-20261007-smooth-aligned.zip`，SHA `cae89acc99c4c1cba724ed22c72afae1d9e8b9275887d4b9c1722166a367fa78`。旧便携包及两份原角色备份保留；仅更新角色资源，无需重建 EXE。

## 测试与验证

- 媒体公共回归：`D:/anaconda3/python.exe -m pytest --noconftest -q tests/test_alpha_fringe_tool.py tests/test_alpha_geometry_tool.py`，**7 passed**。工具新增前导入失败的红灯日志保存；实际原素材污染与摆放测量另有独立诊断。`--noconftest` 避免媒体环境触发无 PySide6 的全局 Qt fixture。
- 应用全量：`QT_QPA_PLATFORM=offscreen E:/dsh-pet-dev313/Scripts/python.exe -m pytest -q`，**2977 passed / 13 skipped / 253 warnings，315.27s**。其中两个离线媒体模块因该解释器缺 NumPy/OpenCV 跳过，以上七项在 D 盘媒体解释器真实运行。首次全量发现构建指南的品牌检查误报，修正精确工程文档豁免后重跑通过。
- ruff 全仓及 `git diff --check` 通过。
- 16 逻辑核施压，WebM reader/clip 生命周期、窗口碰撞与交互锁四个相关测试族连续三轮，**每轮90 passed**；墙钟18.517 / 19.169 / 18.944s，57个 CPU 样本均值85.914%、最高100%，所有施压进程已退出。
- 所有105段实际 alpha VP9 输出完整解码，帧数与帧率保留，最终预期 alpha 及画布检查通过。原生播放器验证、视觉采样、安装 SHA 与便携包1069成员分别留存 JSON 回执。

## 独立未完成事项与回滚

本轮完成轮廓及跨动画固定摆放。以前的道具缺失、支撑姿势、抓柄、末帧残留等53项明确问题与50项待完整时序复核仍在 `visual-repair-ledger.json`；本轮不把它们标为完成。螃蟹走路初帧的既有材质偏白也不能由 alpha 后处理修复。台账保留原问题及两项此前已接受的道具修复，并更新真实安装 SHA。

回滚时先核实实际 EXE 完整路径并正常退出，将 `green-edge/before/external` 与 `before/internal` 各109文件复制回对应目录，核对备份 SHA 后用原启动链启动。精确断点记录在 `.scratch/qilin-original-motion/HANDOFF.md`。
