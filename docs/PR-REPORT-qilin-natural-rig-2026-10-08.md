# 麒麟实时骨骼动作自然度修复（3.0.1-natural-rig）

基线：`18fe2c43bc1f1b45fcbda40eeef7470dcaebb23f`；分支：`feat/running-agent-discovery`；日期：2026-10-08。
本报告补充[3.0.0模型交付](PR-REPORT-qilin-rig2d-2026-10-08.md)，只记录本轮新测结果。
完整制作及本机证据目录：`E:/qilin-codex-fix-20261007/natural-rig-20261008`。

## 核心特性

旧动作每帧将手沿直线送到肩部附近，再独立解IK，导致关节突然折叠、角度跨界和高转速。
60Hz扫描105入口，29项有角度跨界，最严重相邻帧的最短角差转速2836.50度/秒。
本轮在关节空间接近安全目标，使用五次平滑过渡及到位停顿，再收回到同一个休息姿势。
手臂不反折、不完全折闭；持花、食物及红包保持握点；站立与屈膝姿势使用移动骨盆下的地面IK，脚掌独立保持水平。
局部重复仅用于挥手、点按、书写等具体动作，取消无目的的全身周期摆动。

逐帧检查另外发现表情混合有偏色和变暗：Qt的Plus合成配合全局opacity会插值合成结果，不能直接当作加权源图。
改为两个局部透明头部缓冲分别加权，再以全不透明度相加。原不透明头发在50%混合时alpha从253降到190的回归先红后绿。

模型继续使用68张固定贴图、640×360逻辑坐标、30fps及2倍采样；没有恢复WebM或增加动作视频。

## 修改文件说明

以下行数按相对基线的`git diff --numstat`统计，新文件按实际行数；共9个文件。

| 文件 | 增删 | 改了什么及原因 |
|---|---:|---|
| `pet/rig_motion.py` | 新增 +346 / -0 | 从渲染器抽离运动学与姿态；安全肩肘分支、五次插值、持物停顿、真实脚底IK与起跳收腿连续过渡。保留通用IK几何契约。 |
| `pet/rig_model.py` | +27 / -266 | 使用独立动作模块，保留原公开函数导出；脚掌角与腿角分开；修正表情加权和缩小临时头部缓冲。 |
| `tests/test_rig_motion_naturalness.py` | 新增 +131 / -0 | 16项回归覆盖全库五组关节速度、反肘、保持阶段、首尾速度、笔/本接触、真实地面几何、全程握点及表情alpha/颜色。 |
| `assets/characters/qilin/rig/model.json` | +1 / -0 | 增加`motion_revision=natural-rig-1`以标明动作策略代际；贴图与骨长未更换。 |
| `assets/characters/qilin/manifest.json` | +1 / -1 | 根清单版本同步3.0.1-natural-rig。 |
| `assets/characters/qilin/videos/manifest.json` | +1 / -1 | 运行入口清单同步版本，仍指向实时模型。 |
| `scripts/export_qilin_rig.py` | +2 / -2 | 作者导出器同步动作修订标识与版本，避免下次导出退回旧清单版本。 |
| `docs/INDEX.md` | +2 / -1 | 登记本轮报告并区分3.0.0历史基线与当前动作修复。 |
| 本报告 | 新增 +160 / -0 | 保存根因、性能、实机与交付证据，限制视觉通过的实际范围。 |

没有删除文件。二进制贴图、窗口生命周期、IPC、持久设置及模型/Agent配置均没有改动。
制作脚本、日志、原生截图、构建和私有备份位于E盘，不提交进仓库。

## 实现要点

- 动作权重在0–22%准备/抬手、22–78%到位/保持、78–100%收回，五次曲线在接点的速度与加速度为零。
- 到位IK先选择合理目标，再投影到肩肘安全分支；左肘相对角[-132,0]、右肘[0,132]。准备与收回插值角度，不插值一条穿过肩部的手部直线。
- 持物位置来自真实腕端；花、糖葫芦、扇、镜、红包在准备和收回阶段也随握持手移动。双手道具的支撑在到位阶段成立，不宣称过渡中的另一只手已全程握上。
- `planted_feet`只是支撑状态声明，验收重新计算骨链、骨盆变换和实际踝端，防止静态字典伪造支撑。抬脚时才允许足端离开基线。
- 起跳收腿按离地高度逐渐变化，消除支撑/腾空分支切换引起的膝关节突变。
- 足端坐标仍由固定长度腿骨求解，绘制脚掌使用单独角度。书写笔尖与托书手在完整到位阶段精确接触，不因呼吸脱离。
- 表情按预乘RGBA相加，使用原头部纹理尺寸的局部缓冲，避免两个整画布缓冲。

## 性能分析

环境：Windows 11 build26200，16逻辑核；应用Python3.13.13、PySide6 6.11.2；解释器`E:/dsh-pet-dev313/Scripts/python.exe`。
下面脚本均位于本轮证据目录；运行命令为上述解释器加脚本完整路径。

`benchmark_pose.py`：旧/新各31500次，105动作各300次，复用相同纹理与骨骼。

| 纯姿态计算 | 旧版 | 新版 |
|---|---:|---:|
| 中位数 | 8.9µs | 18.3µs |
| 均值 | 9.645µs | 19.782µs |
| p95 | 15.1µs | 29.5µs |

新增地面求解和姿态策略约增加10.137µs/帧；每秒30次对应每秒0.000304秒CPU，约0.0304%单核。
这是计算路径估计，不能替代实际应用CPU。

`benchmark_renderer.py`：每动作/每版3×250次交替，相同2倍采样和贴图；采样时还有原生全库回放。

| 完整渲染中位数 | 旧版ms | 新版ms |
|---|---:|---:|
| 待机 | 1.537 | 1.596 |
| 傲娇生气 | 4.952 | 3.057 |
| 轻快记录 | 2.192 | 2.180 |
| 凭空生花 | 5.147 | 3.085 |
| 吃糖葫芦 | 3.349 | 3.083 |
| 屈膝礼 | 3.468 | 2.965 |

完整行数据及p95在`renderer-performance.json`。表情路径下降来自局部缓冲；待机渲染中位数增加0.059ms。
固定纹理数量不增长，没有新的常驻帧缓存。新路径逐帧不增加系统调用、网络、磁盘、工作线程或子进程。
既有窗口的文件签名stat/周期指纹和应用服务仍存在；不能把模型路径无IO解释成整个程序无IO。

实际EXE对照`benchmark_runtime.py`在安装前执行：两个版本按轮次交替，待机/持花各3×24秒、scale0.7，独立配置与相同68纹理。
统计每轮后12秒，合计主进程及子进程。结果和EXE SHA绑定在`runtime-performance/records.json`，汇总在`runtime-performance/summary.json`。
实际运行命令为`& E:/dsh-pet-dev313/Scripts/python.exe E:/qilin-codex-fix-20261007/natural-rig-20261008/benchmark_runtime.py`。
该脚本的旧版路径指向安装前的目录状态；安装已完成，不能原样重跑，应先重建隔离的旧/新路径。

| 场景 | 旧CPU | 新CPU | 旧RSS MiB | 新RSS MiB | 旧/新启动中位数s |
|---|---:|---:|---:|---:|---:|
| 待机 | 21.333% | 21.719% | 117.313 | 116.457 | 0.829 / 0.835 |
| 持花 | 38.786% | 25.867% | 117.171 | 118.850 | 0.821 / 0.825 |

待机CPU增加0.386个百分点，持花下降12.919个百分点。两版线程数均20、子进程均0，12次运行均正常退出。
后12秒RSS增量：待机旧0.0039MiB/新0；持花两版均0.0065MiB。新版持花平均RSS比旧版高1.679MiB。
持花旧版采样期间宿主整体CPU为23.186%，新版为19.236%；交替测试仍有系统负载差异，不能把全部下降都归因于模型修复。
以上仅是短样本，不能推断长期内存稳定或所有动作性能；应用CPU以单核100%计。

## 实机运行记录

### 根因与回归

- `audit_motion.py --out motion-before.json`：105入口，29项角度跨界，东张西望2836.50度/秒、吹笛子2755.27度/秒，按最短角差计算而非仅表示跨界。
- 初始自然度回归`pytest-red.log`：10 failed、3 passed。实现后原模型与新增回归`pytest-motion-final.log`：30 passed。
- 表情混合独立红灯`pytest-expression-red.log`：50%混合alpha190 vs源253；修复后颜色/alpha回归通过。
- `audit_physics.py`：105入口，60Hz、24597姿态、46998支撑采样；包括腿与尾巴的最高直接关节转速306.580度/秒，最大真实支撑误差8.04e-14逻辑像素。
- `motion-after-r1.json`：手臂最高281.637度/秒，角度跨界0项。此后只完善起跳腿部连续性，手臂策略保持一致。

### 原生播放与实际像素

`native_review.py --character D:/AI_helper/dsh-pet-source/assets/characters/qilin --out <证据目录>/native-full --full`，windows平台、speed=1.0。
105入口完整播放，无错误、无超时；12317次帧通知、3228张阶段截图，每动作28–31张；动作中位帧间隔的中位数33.031ms。
截图保存会占用GUI线程，部分预设截图时点被跨过，因此不宣称无掉帧或逐帧全部截图。

查看`native-atlas/page-01.png`至`page-18.png`的所有105项七阶段，重点另检查持花、挥手、书写、屈膝、进食、乐器和跳跃的31阶段完整轨迹。
接触表为便于看关节会裁剪透明边；不能用其归一化后的摆放证明跳跃高度或地面固定，后者以原窗口截图与骨链数据为准。
观察到持花不再绕肩翻转，挥手无反向弯肘，记录手/笔/书接触稳定，屈膝脚掌保持水平；表情准备和收回的头发不再变暗偏绿。
像素与几何验收不等于用户已经认可艺术自然感；完整乐器演奏与复杂交互仍受当前固定分层模型限制。

安装资源另用真实PetWindow原速播放12项，共369张截图，无错误、无超时。
命令同上，将`--character`改为`D:/AI_helper/dsh-pet-enhanced/characters/qilin`，输出`native-installed`，不加`--full`。
按动作名及共同帧号对比，363张PNG SHA及解码像素均完全一致；其余截图时点在另一场回放中被跳过，不要求两场截图总数相等。
证据`installed-pixel-comparison.json`。这里运行的是当前源码及实际安装资源，EXE嵌入代码一致性另外验证，不能把这次回放写成EXE自动切换全部动作。

150%缩放另跑`QT_QPA_PLATFORM=windows`、`QT_SCALE_FACTOR=1.5`及同一命令的`--name 轻快记录`。
实际DPR1.5、31张截图，无错误/超时，帧间隔中位数33.211ms；查看准备、到位与收回图，书写到位接触与边缘正常。
数据`native-highdpi-installed/records.json`；样本的原生二值mask均为空，抗锯齿未被二值窗口裁切。

### 本地门禁及构建

- `python -m ruff check .`：通过；最终文档收尾再检结果见`ruff-final.log`。
- `python -m pytest -q`：**3017 passed, 13 skipped, 252 warnings in 210.38s**，见`pytest-full.log`。
- `stress_natural.py`：16核满载3轮，每轮**144 passed**，实际平均CPU98.095%，所有自建负载进程退出；数据`stress/stress-record.json`。
- `scripts/build_onedir.ps1 -Variant webm-chat -QilinOnly -CharacterRoot D:/AI_helper/dsh-pet-source/assets/characters -OutputRoot <证据目录>/build -IconPath D:/AI_helper/dsh-pet-source/assets/icon.ico -SkipZip`：通过中文资源、Qt DLL、独立桌宠与设置启动、正常退出门禁。
- 候选EXE SHA：`a4130a9e7fdd3bc2586a0784febc5cb70e6b6df0b7e9c4048c1b957f21c7ea64`；提取PyInstaller嵌入代码确认`pet.rig_model`、`pet.rig_motion`与当前源码编译结果一致。
- 真实Qt回归覆盖暂停同帧重绘、首尾重入、停止/清理、独立闭眼及无解码预热。所有105动作首尾图像完全一致。

## 已知限制及回滚

当前仍是2D骨骼/2.5D分层，骨长与大头短臂比例固定，没有完整3D背面或手指骨。
乐器、三球、荡秋千等入口保留简化表演；本轮只保证安全运动路径、保持、支撑与所述接触，不能写成105项都已完整还原真实表演。
固定贴图只能转动和层叠，肩肘附近的袖子缺少连续网格变形；后续增加网格蒙皮时须保持上述关节/接触/首尾回归。
没有新增配置键或迁移。回滚使用本轮完整旧包及私有配置备份；不要运行写死上一版SHA和目录的旧交付脚本。

## 交付记录

已安装3.0.1-natural-rig到`D:/AI_helper/dsh-pet-enhanced/qilin-pet-webm-chat.exe`，安装EXE与候选SHA一致。
内外角色资源各71文件与源码一致；整个新包1102文件、236073754字节。安装记录`installation.json`。
先完整备份旧包1102文件到`installed-before-natural-rig`，两份真实配置另存`private-config-before-natural-rig`。
安装替换时两份配置逐SHA保持；私有内容不进入报告、测试日志、便携包或提交。
旧PID51656经完整EXE路径核实后向所属GUI线程发WM_QUIT，正常退出0；原入口`D:/AI_helper/dsh-pet-local/Start-dsh-pet.ps1`启动新版。
启动脚本SHA保持`f959fa25b6e80d25ffa8738dc9bc2a1a0f30fdb2aad2de28ef9fac2768ebb6fe`。
新版主PID43704/窗口1118694在交付核验时正常响应；进程号只作当时证据，后续操作应重新核实。
D盘旧包副本`D:/AI_helper/dsh-pet-enhanced-before-natural-rig-20261008`保留；此前被拒绝清理的3.0.0前副本也继续保留。

查看安装主桌宠`installed-window.png`与真实“桌宠设置”窗口`installed-settings-ui/installed-window.png`，角色正常显示，中文设置未出现空白或错位。
设置使用独立配置，settings.lock存在、正常退出0；主桌宠保持运行。证据`installed-ui.json`。
便携包`E:/qilin-codex-fix-20261007/qilin-pet-portable-20261008-natural-rig.zip`，115092920字节、1102成员逐SHA通过。
ZIP SHA：`1ab41fbfab9cae0ed9380460bd6f71dcb56242d138812a4d58b84280dd3f797e`，证据`portable-verification.json`。

GitHub Desktop提交及Push origin沿用现有上传授权；核实仓库`dsh-pet-indesktop`、分支`feat/running-agent-discovery`与上述9文件。
提交标题`fix: make qilin rig motion stable and natural`。GUI操作记录及最终HEAD/跟踪分支/远端/源码blob核验保存为本轮独立证据；
本报告随该提交保存，确切提交SHA与推送结果以`final-delivery-verification.json`为准，避免在报告自身写入其提交SHA形成循环。
本轮`natural-rig-acceptance.json`独立记录运动学、像素与交付范围，不覆盖旧视频问题台账或历史模型交付结论。
