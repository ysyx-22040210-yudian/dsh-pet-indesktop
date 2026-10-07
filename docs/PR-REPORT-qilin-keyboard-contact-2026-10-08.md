# 麒麟电脑与指尖接触修复（3.0.2-keyboard-contact）

基线：`4c4c44296f18a07fd890a6cba909b1e054540091`；分支：`feat/running-agent-discovery`；日期：2026-10-08。
本报告补充[3.0.1动作自然度修复](PR-REPORT-qilin-natural-rig-2026-10-08.md)，只记录电脑相关的新修复及验证。
本机证据目录：`E:/qilin-codex-fix-20261007/keyboard-contact-20261008`。

## 核心特性

原电脑贴图主要显示外壳背面，键盘仅右侧一小块；双腕目标点在电脑上方，没有匹配可见按键。
“写代码”与“工作状态-忙碌点按”改用独立的显示屏、键盘与固定支撑平面，双手按真实指尖贴图触点解IK。
左右手分落键盘两侧，只有亚像素交替点按；电脑与支撑取消身体呼吸位移，准备和收回仍沿安全关节姿态过渡。
继续实时2D/2.5D建模，不添加动作视频或帧序列，68张固定贴图保持字节一致。

## 修改文件说明

以下增删相对基线以`git diff --numstat`统计，新文件按实际行数；共9文件。

| 文件 | 增删 | 改了什么及原因 |
|---|---:|---|
| `pet/rig_motion.py` | +36 / -3 | 从真实指尖解IK，并从电脑键盘平面取得目标；取消电脑/支撑的呼吸漂移。 |
| `pet/rig_model.py` | +48 / -3 | 绘制固定电脑2.5D平面、按键及支撑，使用与接触求解一致的几何。 |
| `assets/characters/qilin/rig/model.json` | +124 / -4 | 标注实测指尖触点、键盘平面、左右键位、电脑位置与固定支撑，更新动作修订。 |
| `assets/characters/qilin/manifest.json` | +1 / -1 | 根清单版本同步3.0.2-keyboard-contact；继续使用实时模型。 |
| `assets/characters/qilin/videos/manifest.json` | +1 / -1 | 动作入口清单同步同一版本，保持模型相对路径。 |
| `scripts/export_qilin_rig.py` | +19 / -2 | 作者导出同步上述触点、几何与版本，避免重导出退回错误布局。 |
| `tests/test_rig_keyboard_contact.py` | 新增 +109 / -0 | 5项回归验证两个入口的真实指尖/键位、触点皮肤像素、手部遮挡与固定支撑地面。 |
| `docs/INDEX.md` | +2 / -1 | 登记本轮报告并关联动作自然度基线。 |
| 本报告 | 新增 +101 / -0 | 保存根因、性能、实机、安装及上传证据。 |

没有删除文件。测试/制作证据、构建及私有配置备份放E盘，不提交仓库。

## 实现要点

- 触点来自左右前臂贴图上的指尖皮肤像素，而非仅将手腕当作接触点。触点随前臂旋转，原有腕骨长度保持。
- 键盘目标从实际平面双线性坐标与道具缩放/锚点变换求得，再选择安全肩肘分支；准备/收回使用五次关节插值。
- 电脑绘制在手部后方，实际截图和像素回归确认指尖在键盘上方可见。固定支撑底部与靴子实测不透明底边对齐。
- 电脑的模型局部位置抵消骨盆呼吸，因此键盘、台面与支撑脚在窗口中固定，指尖小幅点按不会带动电脑。
- 只有两个打字入口使用新电脑部件，其他入口的固定素材与原动作策略沿用。

## 性能分析

环境：Windows 11 build26200、16逻辑核；Python3.13.13、PySide6 6.11.2，解释器`E:/dsh-pet-dev313/Scripts/python.exe`。
隔离基线源码和资源保存在`baseline-code`、`baseline-character`；受影响渲染/姿态路径的交替实测在`audit_benchmark.py`。
实测命令：`& E:/dsh-pet-dev313/Scripts/python.exe E:/qilin-codex-fix-20261007/keyboard-contact-20261008/audit_benchmark.py`。
旧/新各场景3×250次交替绘制，只取35–65%到位/打字阶段，相同2倍采样；每场景每版本750次。

| 完整渲染 | 旧中位数ms | 新中位数ms | 旧p95 ms | 新p95 ms |
|---|---:|---:|---:|---:|
| 待机 | 1.880 | 1.902 | 2.744 | 2.740 |
| 写代码 | 2.186 | 2.751 | 3.065 | 3.962 |
| 忙碌点按 | 2.431 | 2.826 | 3.250 | 3.985 |

写代码的稳态完整渲染中位数增加0.565ms；按均值2.272→2.911ms和30fps估算，新增约19.161ms CPU/秒，即约1.916%单核计算预算。
这包含姿态计算，不能与下面纯姿态成本再次相加；是模型路径估计，不能写成整个EXE的实际CPU百分比。
纯姿态旧/新各10000次覆盖完整动作：中位数20.4→27.1µs，均值23.432→31.235µs，p95 37.0→53.4µs；均值增加7.803µs/帧。
新平面绘制和接触计算没有网络、磁盘、系统调用、工作线程或子进程；既有应用服务仍独立存在。
固定贴图数量不变；新绘图每帧使用局部Qt几何对象，没有常驻动作帧缓存。
同时持有旧/新模型的单个基准进程RSS从95.445增至99.438MiB，增加3.992MiB，包含Qt绘图缓冲和两版基准对象；不能据此归因单一版本或证明长期无增长。
原始数据`audit-performance.json`保留样本量、环境与测量范围。

## 实机运行记录

- 新接触与像素回归先红，原实现`pytest-red.log`为4 failed；附加几何后，真实手指与目标的偏移仍使回归失败。
- 修复后模型、自然度及接触回归35 passed；进一步校准支撑到靴子底边后，5项接触回归通过。
- 实际PetWindow原速播放左右朝向及150%缩放，最终`native-ground-left/right/highdpi`各31张、共93张截图，无错误、无超时。早期stand校准前截图仅作过程归档。
- 实测原贴图可见键位与两指尖在到位阶段相距41.018/30.804逻辑像素；新键盘平面的实际指尖最大点按离面距离0.600像素，支撑/电脑位移0。
- 其余103动作7阶段共721张渲染像素与隔离3.0.1基线完全一致；68张PNG逐SHA一致。两打字入口首尾与旧版同姿势，到位画面有实际改变。
- 全105入口60Hz扫描24597姿态，最高直接关节转速306.580度/秒，仍低于320度/秒回归阈值。
- `python -m ruff check .`通过；`python -m pytest -q`为**3026 passed, 13 skipped, 252 warnings in 204.20s**。
- `stress_natural.py`加入新键盘回归后的受影响时序族，16核满载三轮各**149 passed**，实际平均CPU99.276%，自建负载进程均退出；记录`stress/stress-record.json`。

## 已知限制及回滚

当前仍为固定2D骨骼和2.5D平面，镜头下的电脑平面强调键盘与双手接触可见性；没有完整3D反面、独立手指骨或连续袖口蒙皮。
已有乐器、杂耍、秋千等入口仍是简化表演；本轮不将电脑修复写成所有复杂动作的完整真实表演。
无新增持久配置或迁移；回滚使用本轮完整旧包及两份私有配置备份，不原样运行任何上一版安装脚本。

## 交付记录

构建命令：`scripts/build_onedir.ps1 -Variant webm-chat -QilinOnly -CharacterRoot D:/AI_helper/dsh-pet-source/assets/characters -OutputRoot <本轮证据>/build -IconPath D:/AI_helper/dsh-pet-source/assets/icon.ico -SkipZip`。
中文编码、Qt DLL、独立桌宠/设置启动与正常退出门禁通过；提取PyInstaller嵌入`pet.rig_model/rig_motion`代码确认与实测源码编译结果一致。
候选和安装EXE SHA：`0621c8e82e5e2a30a90879c53d90e083745980d1048834c7ff3ade096bd35040`，证据`candidate.json`。

已安装`D:/AI_helper/dsh-pet-enhanced/qilin-pet-webm-chat.exe`，1102文件、236080551字节；内外角色各71文件与源码逐SHA一致。
旧PID43704经完整路径核实后向所属GUI线程发WM_QUIT，正常退出0；原入口启动新版PID8024/窗口791444（后续操作须重查）。
原启动脚本SHA保持`f959fa25b6e80d25ffa8738dc9bc2a1a0f30fdb2aad2de28ef9fac2768ebb6fe`。
旧包1102文件完整备份`installed-before-keyboard-contact`，私有配置备份`private-config-before-keyboard-contact`；替换时两份真实配置逐SHA保持，不输出内容。
D盘`dsh-pet-enhanced-before-keyboard-contact-20261008`副本及所有之前保留的副本均未清理，包含此前被审批拒绝删除的before-rig2d副本。

实际主宠及独立配置的“桌宠设置”截图已查看，角色/中文正常；设置锁存在、正常退出0，主宠持续运行。证据`installed-ui.json`。
安装资源另以真实PetWindow原速播放两个打字入口，左右朝向共60截图，无错误/超时；与候选共同60帧PNG SHA及解码像素完全一致。
这里运行当前源码与实际安装资源；嵌入EXE代码相等另外验证，不将其写成通过EXE自动切换入口。
150%缩放实际DPR1.5的31截图包含准备、到位、收回，已查看七阶段；键盘和指尖可见，支撑底保持固定。
`native_review.py --character <角色目录> --out <独立证据目录> --name 写代码`，另以`--name 工作状态-忙碌点按 --facing right`检查镜像。
高DPI设置`QT_QPA_PLATFORM=windows`、`QT_SCALE_FACTOR=1.5`；截图保存占GUI线程，时点可被跳过，不能宣称无掉帧或逐帧全截图。

便携包`E:/qilin-codex-fix-20261007/qilin-pet-portable-20261008-keyboard-contact.zip`，115097719字节、1102成员逐SHA核验通过。
ZIP SHA：`bdcd298a3e2e4380da0259b9b070a97478a9e1f4e64e43401a75e521b1b363e7`，见`portable-verification.json`。
GitHub Desktop按已有授权GUI提交/Push origin；标题`fix: align qilin typing hands with keyboard`，核实当前仓库/分支及上述9文件。
本报告随提交保存，确切SHA/远端/工作树状态以本轮`final-delivery-verification.json`为准，避免报告引用自身提交SHA形成循环。
`keyboard-contact-acceptance.json`独立记录本轮范围，不覆盖历史动作/视频台账，也不声称用户已认可所有复杂表演。
