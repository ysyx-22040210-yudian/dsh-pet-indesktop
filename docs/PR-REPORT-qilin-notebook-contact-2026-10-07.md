# 麒麟“轻快记录”手与本子接触修复

基线：`40d948ed4b1bb6aece0d5af3903f0b0353ea4ea4`，分支 `feat/running-agent-discovery`，Windows 本机 2026-10-07。角色资源版本 `2.0.21-note-contact`；延续[轮廓和固定摆放报告](PR-REPORT-qilin-alpha-geometry-2026-10-07.md)，构建与安装入口见[打包指南](ONEDIR_PACKAGING.md)。以下数字是本轮快照。

## 一、核心特性

用户指出“手都没碰到本子”。旧片的本子作为独立装饰层漂浮，握笔与纸面也没有稳定接触关系。本轮按逐帧手掌位置绑定书边与笔握点，让手指覆盖书边，写字时笔尖落到纸面，思考时抬笔，再平顺回到纸面。重新制作的橙金笔记本采用麒麟纹样。

成片保留241帧、640×360、24fps，沿用上一轮固定等比变换与轮廓平滑。取出和收起阶段使用卡通淡入淡出，末帧无书或笔残留。实际解码后的所有241帧已逐帧查看，包含全身、手部细节与白/暗背景。

## 二、修改文件说明

本轮六个源码文件；生成视频、便携包、测试日志和用户配置保存在E盘，不进入源码提交。增删行数来自实际diff；新增文件按UTF-8文本行计数。

| 文件 | 增删 | 改动与原因 |
|---|---|---|
| `packaging/character_postprocess/assets/qilin-notebook-20261007.png` | 新增二进制，1,661,006字节 | 真实透明橙金笔记本，替换不适合手持及写字的旧装饰道具。 |
| `packaging/character_postprocess/assets/qilin-note-pen-20261007.png` | 新增二进制，268,883字节 | 真实透明细笔，提供稳定握点与可辨认的笔尖。 |
| `packaging/character_postprocess/qilin-notebook-contact-20261007.json` | 新增，+115 / −0 | 保存原始生图提示词、实际尺寸/SHA、离线制作脚本SHA、接触配方和证据路径。 |
| `docs/PR-REPORT-qilin-notebook-contact-2026-10-07.md` | 新增，+90 / −0 | 保存本轮视觉、性能、实机与回滚证据。 |
| `docs/INDEX.md` | +2 / −1 | 登记报告，并指出轮廓修复之后的本段接触修复。 |
| `docs/ONEDIR_PACKAGING.md` | +2 / −0 | 指出2.0.21角色资源覆盖配方与三文件替换范围。 |

应用播放器与EXE字节不变。素材修复依据实际像素审查；没有为离线图层配方新增镜像实现的单元测试。

## 三、实现要点

离线制作脚本：`E:/qilin-codex-fix-20261007/notebook-contact-20261007/render_contact.py`，实际SHA在[素材配方](../packaging/character_postprocess/qilin-notebook-contact-20261007.json)。从既有角色动作帧提取手的位置，绑定本子右侧书边到支撑手掌，以肤色前景层重画手指遮挡。笔保持固定长度和手部握点，选择连续的纸面接触点，写字/思考状态采用缓动，修正初版笔方向突变。

大尺寸透明道具先做预乘alpha的Lanczos缩小，再做仿射变换；沿用scale `1.1299435028248588`、dx `-59.381355932203405`、dy `-40.62146892655369`、sigma `0.65`。没有重新生成角色动作或提交云视频。

160帧本子完全不透明时，书边到可见支撑手轮廓的合成距离最大1源像素；104帧完整写字状态中，笔尖与指定纸面点距离最大0.650119源像素。这些是制作几何记录，实际解码像素另作全帧审查，不能用数字替代视觉验收。

两个道具通过内置imagegen生成；输出实际为1610×977和1145×1374 RGBA。工具没有报告具体后端模型，配方明确保留未知，不按对话模型名称推断。

## 四、性能分析

环境：Windows / `E:/dsh-pet-dev313/Scripts/python.exe` / PySide6；制作使用 `D:/anaconda3/python.exe`、NumPy/OpenCV/Pillow与FFmpeg 8.1.1。实测命令：

```powershell
D:/anaconda3/python.exe E:/qilin-codex-fix-20261007/notebook-contact-20261007/render_contact.py --encode
E:/dsh-pet-dev313/Scripts/python.exe E:/qilin-codex-fix-20261007/notebook-contact-20261007/benchmark_contact.py
```

实际同一EXE、独立测试配置，旧/新“轻快记录”交替各3×24秒；每轮后12个一秒样本统计CPU/RSS。测试实例均正常退出。CPU是psutil单逻辑核口径，计入EXE与解码子进程。

| 指标 | 修改前 | 修改后 |
|---|---:|---:|
| 合计CPU均值 | 26.992% | 27.133% |
| 合计RSS均值 | 149.500MiB | 149.851MiB |
| 后半段RSS增量均值 | +3.301MiB | +3.932MiB |
| 主机CPU均值 | 21.281% | 22.031% |
| 线程数均值 | 81 | 81 |
| GUI启动中位数 | 0.7612s | 0.7615s |

本组样本CPU增加0.142百分点，RSS增加0.351MiB，不能据此推断普遍提速或长期内存无增长。播放仍使用同尺寸、同帧率的预合成WebM，运行时没有新图层计算、模型、依赖、线程、系统调用或网络路径。新增离线制作一次约113.903s；运行时按原有动作调度触发。复制三个资源并核对两份各109文件SHA耗时1.822s；新便携包生成及全部成员核验55.782s。记录在本轮 `runtime-performance/summary.json`、`artifact.json`、`installation.json` 和 `portable-verification.json`。

## 五、实机运行记录

证据根目录：`E:/qilin-codex-fix-20261007/notebook-contact-20261007`。

1. 完整实际编码输出SHA：`03b9f8c30a592de157663ee94baefa6a07f022a060490f6cf9793fc1c310442f`。11页覆盖全部241帧的全身和手部白/暗底，已全部查看。支撑、握笔、写字到思考过渡与收起阶段通过；几何检测与实际像素审查分别记录。
2. 原生Qt完整播放：241帧全部出现、错误0，帧间隔中位数42.002ms，超过84ms为0。`native-candidate.json`绑定上述SHA。
3. 真实Windows `PetWindow`按实际播放帧0、48、56、80、96、120、128、160、208、224、240抓取绘制结果，另抓前后待机；白/暗底13组实际绘制检查通过。位置固定、Windows二值mask为空、DPR1/scale0.85；未测试其他DPR。对候选目录与真实安装目录分别运行，回执在 `real-pet-preview`、`installed-pet-preview`。抽样不替代第1项的全帧像素检查。
4. 先备份内外两目录的三个受影响文件，仅对完整路径核实的旧PID45916窗口所属线程发送WM_QUIT。安装后两份角色目录各109文件全部SHA与候选一致；其他104段WebM字节不变。原启动链 `D:/AI_helper/dsh-pet-local/Start-dsh-pet.ps1`重启成功，记录PID40744、窗口1577626，实际EXE路径 `D:/AI_helper/dsh-pet-enhanced/qilin-pet-webm-chat.exe`。
5. EXE SHA仍为 `caeae34968902f2e1ef58fe4cc3152883e68ec0e187d125765d110fe17c3cde3`。配置保留。真实桌宠继续运行供用户使用；安装证据与当前媒体SHA绑定。
6. 新便携包 `E:/qilin-codex-fix-20261007/qilin-pet-portable-20261007-note-contact.zip`，1,342,175,729字节，SHA `b332c659505bccc998a8a17d14b60787024c9b66ae3b884247471d1a98650851`。1069成员全部核验，仅三个角色成员改变，其余成员SHA与smooth-aligned旧包一致。旧包保留。

复验命令：

```powershell
E:/dsh-pet-dev313/Scripts/python.exe E:/qilin-codex-fix-20261007/notebook-contact-20261007/preview_contact_pet.py D:/AI_helper/dsh-pet-enhanced/characters/qilin installed-pet-preview
```

视觉边界：取出/收起是刻意的透明度过渡；思考阶段笔尖离开纸面，不能将它当写字接触失败。初版候选因笔方向跳变被弃用，保留为诊断记录，未安装。接触几何和冷色像素探针均不作为品牌检测；实际成片书面及道具已查看。

## 六、测试与验证

- `E:/dsh-pet-dev313/Scripts/python.exe -m ruff check pet tests scripts` 与 `git diff --check`通过，文档收尾后再检查。
- 报告纪律、桌面功能、品牌清理与WebM reader/clip生命周期聚焦：**161 passed，23.82s**。命令与真实输出保存于 `focused.log`；媒体公共回归在 `D:/anaconda3/python.exe -m pytest --noconftest -q tests/test_alpha_fringe_tool.py tests/test_alpha_geometry_tool.py`实跑，**7 passed，0.65s**。
- `QT_QPA_PLATFORM=offscreen E:/dsh-pet-dev313/Scripts/python.exe -m pytest -q`：**2981 passed / 13 skipped / 251 warnings，196.58s**，本轮完整日志 `full-tests.log`。应用解释器未安装NumPy/OpenCV，媒体相关跳过另在制作解释器真实补跑。
- `E:/dsh-pet-dev313/Scripts/python.exe E:/qilin-codex-fix-20261007/notebook-contact-20261007/run_timing_gate.py`：16逻辑核施压，WebM reader/clip生命周期、窗口碰撞和交互锁四族三轮各**90 passed**，墙钟20.378s / 18.819s / 20.654s。60个CPU样本均值92.510%、最高100.0%；全部施压进程已退出，原始记录 `stress-gate/stress-record.json`。

## 七、已知限制与后续

仅将“轻快记录”接触修复在安装核验后记为接受。台账还有52项明确道具/支撑问题和50项待完整时序复核；本轮不代表其他动画通过。保留角色大小、位置、轮廓专项结论及其他未完成项。

## 八、风险与回滚

本轮仅替换本段视频与两份角色manifest。先核实实际EXE完整路径并正常退出，将本轮 `before/external` 和 `before/internal` 中三个文件分别复制回原目录，核对备份SHA，再沿用原启动链。便携包回滚可直接使用保留的smooth-aligned旧包。离线制作环境和原始参考不随EXE分发。
