# 麒麟实时2.5D骨骼模型（2026-10-08）

基线`c7f64685e02a4f451354be12b83bbe81907805a8`，分支`feat/running-agent-discovery`。
用户确认没有现成模型、2D或2.5D都可以，并建议参考Q版角色骨骼。
历史交付见[尾根修复报告](PR-REPORT-qilin-tail-root-2026-10-08.md)，入口见[INDEX](INDEX.md)。

## 核心特性

将麒麟动作从预制WebM改为运行时2D骨骼与2.5D分层绘制：105个入口共用同一套
固定形象、关节与坐标，左右眼独立控制，手臂使用固定长度双骨IK，记录动作绑定
托书手掌和笔尖，双段尾巴固定在后臀。动作首尾回到同一姿势，避免切换时闪光与跳位。
30fps、2倍采样、预乘alpha输出1280×720；运行不新增NumPy、OpenCV、Live2D或3D引擎依赖。

这是正面分层模型。现有“360度展示”入口实际表现为转头摆姿，**没有完整3D背面**；
部分动作采用简化姿态和卡通道具淡入淡出，105入口覆盖不代表逐项还原原视频表演。
参考[蓝色大肥鱼作者页面](https://booth.pm/en/items/8777527)的Q版结构，以及
[独立表情参数约定](https://docs.live2d.com/en/cubism-editor-manual/standard-parameter-list/)。
没有下载、提取或分发第三方模型资产。闭眼源图的工具、提示词、实际尺寸和SHA
在`packaging/rig_sources/provenance.json`；工具未报告具体后端模型，记录为null。

## 修改文件说明

共87文件，8个修改、79个新增；无删除文件。已有文件的增删来自`git diff --numstat`，
新增文本按完整行数登记，PNG在Git中是二进制，故列字节而不伪造行数。
生成EXE、ZIP、测试日志、安装备份和私有配置均放E盘，不入源码提交。

| 文件 | 增删 | 改了什么与原因 |
|---|---|---|
| `assets/characters/qilin/manifest.json` | +46 / -0（新增） | 根清单声明3.0.0-rig2d、画布、角色名与模型入口。 |
| `assets/characters/qilin/rig/body.png` | 新增二进制 86,847 B（numstat为-/-） | 新增固定躯干与服装层，由对应关节变换驱动，维持统一轮廓与尺度。 |
| `assets/characters/qilin/rig/head_angry.png` | 新增二进制 222,913 B（numstat为-/-） | 新增配准的生气头部层，保持形象与表情切换轮廓一致。 |
| `assets/characters/qilin/rig/head_blink.png` | 新增二进制 218,159 B（numstat为-/-） | 新增配准的闭眼头部层，保持形象与表情切换轮廓一致。 |
| `assets/characters/qilin/rig/head_happy.png` | 新增二进制 218,553 B（numstat为-/-） | 新增配准的开心头部层，保持形象与表情切换轮廓一致。 |
| `assets/characters/qilin/rig/head_neutral.png` | 新增二进制 223,927 B（numstat为-/-） | 新增配准的中性头部层，保持形象与表情切换轮廓一致。 |
| `assets/characters/qilin/rig/head_sad.png` | 新增二进制 223,301 B（numstat为-/-） | 新增配准的低落头部层，保持形象与表情切换轮廓一致。 |
| `assets/characters/qilin/rig/head_shy.png` | 新增二进制 223,466 B（numstat为-/-） | 新增配准的害羞头部层，保持形象与表情切换轮廓一致。 |
| `assets/characters/qilin/rig/head_surprise.png` | 新增二进制 224,027 B（numstat为-/-） | 新增配准的惊讶头部层，保持形象与表情切换轮廓一致。 |
| `assets/characters/qilin/rig/l_foot.png` | 新增二进制 30,995 B（numstat为-/-） | 新增固定左脚层，由对应关节变换驱动，维持统一轮廓与尺度。 |
| `assets/characters/qilin/rig/la_lower.png` | 新增二进制 9,296 B（numstat为-/-） | 新增固定左前臂与手层，由对应关节变换驱动，维持统一轮廓与尺度。 |
| `assets/characters/qilin/rig/la_upper.png` | 新增二进制 5,865 B（numstat为-/-） | 新增固定左上臂层，由对应关节变换驱动，维持统一轮廓与尺度。 |
| `assets/characters/qilin/rig/ll_lower.png` | 新增二进制 3,551 B（numstat为-/-） | 新增固定左小腿层，由对应关节变换驱动，维持统一轮廓与尺度。 |
| `assets/characters/qilin/rig/ll_upper.png` | 新增二进制 3,389 B（numstat为-/-） | 新增固定左大腿层，由对应关节变换驱动，维持统一轮廓与尺度。 |
| `assets/characters/qilin/rig/model.json` | +1879 / -0（新增） | 登记关节、贴图位置、SHA、105动作参数与30fps/2倍采样。 |
| `assets/characters/qilin/rig/prop_ball.png` | 新增二进制 60,527 B（numstat为-/-） | 新增固定抛接球贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_balloon.png` | 新增二进制 51,662 B（numstat为-/-） | 新增固定气球贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_bow.png` | 新增二进制 23,447 B（numstat为-/-） | 新增固定琴弓贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_brush.png` | 新增二进制 47,761 B（numstat为-/-） | 新增固定毛笔贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_cake.png` | 新增二进制 50,184 B（numstat为-/-） | 新增固定蛋糕贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_candy.png` | 新增二进制 36,008 B（numstat为-/-） | 新增固定糖果贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_cat.png` | 新增二进制 203,259 B（numstat为-/-） | 新增固定猫贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_chopsticks.png` | 新增二进制 32,397 B（numstat为-/-） | 新增固定筷子贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_coin.png` | 新增二进制 57,786 B（numstat为-/-） | 新增固定硬币贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_cone.png` | 新增二进制 39,053 B（numstat为-/-） | 新增固定冰淇淋贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_controller.png` | 新增二进制 93,218 B（numstat为-/-） | 新增固定游戏手柄贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_crab.png` | 新增二进制 65,546 B（numstat为-/-） | 新增固定螃蟹贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_cube.png` | 新增二进制 60,050 B（numstat为-/-） | 新增固定魔方贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_desk.png` | 新增二进制 38,072 B（numstat为-/-） | 新增固定桌子贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_dumplings.png` | 新增二进制 61,966 B（numstat为-/-） | 新增固定饺子贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_emptybag.png` | 新增二进制 50,211 B（numstat为-/-） | 新增固定空袋贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_fan.png` | 新增二进制 103,428 B（numstat为-/-） | 新增固定扇子贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_flower.png` | 新增二进制 62,496 B（numstat为-/-） | 新增固定花贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_flute.png` | 新增二进制 37,973 B（numstat为-/-） | 新增固定笛子贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_fullbag.png` | 新增二进制 69,059 B（numstat为-/-） | 新增固定钱袋贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_goboard.png` | 新增二进制 51,819 B（numstat为-/-） | 新增固定棋盘贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_goldlantern.png` | 新增二进制 42,051 B（numstat为-/-） | 新增固定灯笼贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_greenball.png` | 新增二进制 49,013 B（numstat为-/-） | 新增固定青团贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_horse.png` | 新增二进制 60,237 B（numstat为-/-） | 新增固定木马贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_kite.png` | 新增二进制 52,074 B（numstat为-/-） | 新增固定风筝贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_laptop.png` | 新增二进制 76,034 B（numstat为-/-） | 新增固定电脑贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_lion.png` | 新增二进制 83,655 B（numstat为-/-） | 新增固定狮头贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_lotus.png` | 新增二进制 159,652 B（numstat为-/-） | 新增固定莲花贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_mirror.png` | 新增二进制 40,176 B（numstat为-/-） | 新增固定镜子贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_mooncake.png` | 新增二进制 46,628 B（numstat为-/-） | 新增固定月饼贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_notebook.png` | 新增二进制 1,576,680 B（numstat为-/-） | 新增固定笔记本贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_pen.png` | 新增二进制 219,734 B（numstat为-/-） | 新增固定笔贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_present.png` | 新增二进制 64,577 B（numstat为-/-） | 新增固定礼物贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_pumpkin.png` | 新增二进制 51,766 B（numstat为-/-） | 新增固定南瓜贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_redpacket.png` | 新增二进制 51,389 B（numstat为-/-） | 新增固定红包贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_rice.png` | 新增二进制 41,677 B（numstat为-/-） | 新增固定饭碗贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_shuttle.png` | 新增二进制 45,756 B（numstat为-/-） | 新增固定毽子贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_skylamp.png` | 新增二进制 124,860 B（numstat为-/-） | 新增固定孔明灯贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_snowman.png` | 新增二进制 54,294 B（numstat为-/-） | 新增固定雪人贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_token.png` | 新增二进制 55,579 B（numstat为-/-） | 新增固定Token道具贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_top.png` | 新增二进制 36,718 B（numstat为-/-） | 新增固定陀螺贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_toycar.png` | 新增二进制 49,323 B（numstat为-/-） | 新增固定玩具车贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_tree.png` | 新增二进制 61,904 B（numstat为-/-） | 新增固定树贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_violin.png` | 新增二进制 49,914 B（numstat为-/-） | 新增固定小提琴贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_watergun.png` | 新增二进制 35,528 B（numstat为-/-） | 新增固定水枪贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_watermelon.png` | 新增二进制 46,583 B（numstat为-/-） | 新增固定西瓜贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/prop_whale.png` | 新增二进制 51,375 B（numstat为-/-） | 新增固定动物环绕中的鲸鱼贴图，供相应动作在模型坐标中摆放、持握或支撑。 |
| `assets/characters/qilin/rig/r_foot.png` | 新增二进制 31,037 B（numstat为-/-） | 新增固定右脚层，由对应关节变换驱动，维持统一轮廓与尺度。 |
| `assets/characters/qilin/rig/ra_lower.png` | 新增二进制 9,572 B（numstat为-/-） | 新增固定右前臂与手层，由对应关节变换驱动，维持统一轮廓与尺度。 |
| `assets/characters/qilin/rig/ra_upper.png` | 新增二进制 5,634 B（numstat为-/-） | 新增固定右上臂层，由对应关节变换驱动，维持统一轮廓与尺度。 |
| `assets/characters/qilin/rig/rl_lower.png` | 新增二进制 3,850 B（numstat为-/-） | 新增固定右小腿层，由对应关节变换驱动，维持统一轮廓与尺度。 |
| `assets/characters/qilin/rig/rl_upper.png` | 新增二进制 3,747 B（numstat为-/-） | 新增固定右大腿层，由对应关节变换驱动，维持统一轮廓与尺度。 |
| `assets/characters/qilin/rig/tail_lower.png` | 新增二进制 43,037 B（numstat为-/-） | 新增固定尾末段层，由对应关节变换驱动，维持统一轮廓与尺度。 |
| `assets/characters/qilin/rig/tail_upper.png` | 新增二进制 83,562 B（numstat为-/-） | 新增固定尾根段层，由对应关节变换驱动，维持统一轮廓与尺度。 |
| `assets/characters/qilin/rig/wing.png` | 新增二进制 54,086 B（numstat为-/-） | 新增固定翼层，由对应关节变换驱动，维持统一轮廓与尺度。 |
| `assets/characters/qilin/videos/manifest.json` | +46 / -0（新增） | 保持原角色加载入口，以renderer=rig2d指向固定模型。 |
| `docs/INDEX.md` | +1 / -0 | 登记模型报告，使新的运行机制与验收入口可检索。 |
| `docs/ONEDIR_PACKAGING.md` | +4 / -0 | 说明无视频模型资源门禁、构建与便携交付形态。 |
| `docs/PR-REPORT-qilin-rig2d-2026-10-08.md` | +219 / -0（新增） | 登记逐文件改动、实测成本、原生画面、安装与便携包证据。 |
| `packaging/rig_sources/provenance.json` | +25 / -0（新增） | 保存闭眼素材完整提示词、真实尺寸和SHA；未报告的生图后端记null。 |
| `packaging/rig_sources/qilin-closed-eyes.png` | 新增二进制 1,357,495 B（numstat为-/-） | 新增固定闭眼源图，仅将眼区配准到批准母版，去除残留瞳孔。 |
| `pet/animation_thumbnail.py` | +10 / -0 | 优先获取模型的代表姿势缩略图，保留媒体解码回退接口。 |
| `pet/catalog.py` | +16 / -1 | 通过renderer与包内模型路径发现无WebM角色，避免错误回退到旧角色。 |
| `pet/library.py` | +46 / -2 | 共享固定贴图，按动作创建RigClip并绕过解码预熱；将参数版本加入绘制签名。 |
| `pet/rig_clip.py` | +148 / -0（新增） | 在GUI线程适配播放契约、调速、暂停、节流与清理，防止末帧重入后陈旧finished。 |
| `pet/rig_model.py` | +454 / -0（新增） | 增加双骨IK、眼睑、首尾缓动、尾根与道具接触约束及Qt预乘绘制。 |
| `pet/window.py` | +5 / -6 | 调用模块辅助接口更新模型缩略图和同帧参数；保留原窗口行数预算。 |
| `scripts/check_bundle_encoding.py` | +19 / -1 | 检查UTF-8动作名与真实包内贴图，支持模型包的中文资源门禁。 |
| `scripts/export_qilin_rig.py` | +176 / -0（新增） | 把既有作者素材编译为固定贴图与坐标；剥离预制视频，实现可编辑模型包。 |
| `scripts/preview_qilin_rig.py` | +123 / -0（新增） | 独立配置回放真实PetWindow，按帧采集DPR、位置、mask、间隔及错误。 |
| `tests/test_bundle_encoding_check.py` | +24 / -0 | 覆盖模型资源中文门禁及无有效贴图时的拒绝路径。 |
| `tests/test_rig_model.py` | +202 / -0（新增） | 覆盖105入口、统一首尾、IK长度、闭眼遮瞳、接触、尾根与真实Qt生命周期。 |

## 性能分析

环境为Windows 11 build 26200、16逻辑核、应用Python3.13.13／PySide6 6.11.2，
作者环境`D:/anaconda3/python.exe`。实测记录根目录：
`E:/qilin-codex-fix-20261007/realtime-rig-20261008`。

实际EXE对照命令（安装前执行）：
`E:/dsh-pet-dev313/Scripts/python.exe E:/qilin-codex-fix-20261007/realtime-rig-20261008/benchmark_runtime.py`。
旧／新交替各3轮24秒，独立配置、scale0.7、同一待机动作，统计后12秒，进程及子进程合计。
`runtime-performance/records.json`绑定当时EXE的SHA，汇总在`summary.json`。
该脚本的before路径原指向D盘旧安装，**安装后不能原样重跑**；复测需要指向完整旧版备份及其待机素材。

| 指标 | 旧视频版 | 新模型版 |
|---|---:|---:|
| CPU（单核为100%的口径） | 33.717% | 26.617% |
| RSS | 149.273 MiB | 116.322 MiB |
| 后半段RSS增量 | 6.371 MiB | 0 MiB |
| 线程数 | 81 | 20 |
| 子进程数 | 2 | 0 |
| 启动中位数 | 0.672 s | 0.820 s |

样本内稳态CPU下降7.100个百分点，RSS下降32.951 MiB；启动增加0.148秒。
新模型仍约占26.6%单核CPU，不能称为零开销或推断普遍提速，24秒样本也不能证明长期无内存增长。
模型在GUI线程以30fps运行，纯绘制各150次的中位数：待机1.592ms、生气4.716ms、
记录2.321ms、尾巴2.770ms；p95分别2.272／6.074／3.472／4.653ms。
模型热文件缓存加载0.149秒，68贴图17.495MiB，单输出帧3,686,400字节；
探针调用`RigModel.render(action, seconds)`，数据在`renderer-performance.json`，采样时还运行原生回放与EXE对照。

纹理读取发生在模型加载时；模型逐帧绘制没有新增网络、磁盘、系统进程或工作线程。
现有PetWindow帧签名仍包含文件stat及周期性弱指纹检查，不能把纯模型的无IO说成整个窗口无IO。
表情混合临时创建同尺寸头部缓冲，切走和清理释放显示帧，105动作不各自常驻完整帧。
既有应用服务线程仍在。模型模式跳过媒体预热，实际对照中没有解码子进程。
作者导出器仍依赖本项目已有的本地制作源目录；克隆后的构建使用已提交的固定模型包，不依赖这些作者路径。

## 实机运行记录

### 回归与高负载

- 核心14项模型回归先红后绿，覆盖左右眼闭合遮瞳、IK长度／接触、所有入口统一首尾、
  末帧同步切换、重复播放、停止、清理与暂停时参数版本重绘。
- 最终全量命令：`E:/dsh-pet-dev313/Scripts/python.exe -m pytest -q`，
  `QT_QPA_PLATFORM=offscreen`；`pytest-full-r2.log`：
  **3001 passed, 13 skipped, 251 warnings in 194.66s**。
- `python -m ruff check .`及`git diff --check`收尾通过；报告／品牌／编码门禁59 passed in 1.92s，见`pytest-final-doc-brand.log`。
- 第一组16核施压均通过128项，但含收尾采样的平均CPU为87.411%。为满足满载门禁，
  用`stress_rig_r2.py`固定核亲和、BELOW_NORMAL优先级、200万次运算才检查停止信号，
  无并行打包，复跑9个受影响时序族3遍：**每轮128 passed**，墙钟9.325／8.905／11.095秒。
  30个一秒CPU样本平均98.513%、最高100%，所有施压进程已退出。
  命令与原始日志在`stress-r2/stress-record.json`；没有修改测试断言、等待预算或CI跳过。

验收期间的实际修正保留在日志：第一轮全量2995 passed、2 failed、13 skipped，
原因是窗口超过原行数预算5行、长角色名改变聊天品牌标题；拆出辅助函数并恢复“麒麟”后通过。
第一次构建被旧“吃Token.webm”资源门禁拒绝，改为校验真实模型贴图后通过。
第一轮批量窗口取证未清理动作间隔状态，在第33项停下；预览脚本在强制切换前
调用`_cancel_animation_gap()`，第二轮105项全部通过。没有把前一轮失败算成成功。

### 原生窗口与视觉范围

完整命令为`python scripts/preview_qilin_rig.py --character <最终候选角色目录> --out <real-window-full-r2> --full`，
解释器为上述应用Python，`QT_QPA_PLATFORM=windows`。真实PetWindow全部105动作完整播放，
错误0、超时0、截图525张；DPR1、scale0.85、位置均(100,100)、窗口二值mask全空。
动作帧间隔中位数的中位数33.039ms，数据在`real-window-full-r2/records.json`与`native-summary.json`。
七页浅／暗底截图板均已逐页看过，关键记录、尾根和生气画面另以原尺寸检查；
本轮样本未见明显绿边、瞳孔残留、尾根漂移与生气初帧亮度跳变。
五个时点的视觉抽样不能等同105动作每一帧的完整视觉验收或用户主观确认。

补充`QT_SCALE_FACTOR=1.5`，以同一原生窗口完整播放“轻快记录”121帧，五张截图均DPR1.5，
无错误／超时，间隔中位数33.004ms，见`native-dpr-1p5/records.json`；
这是Qt强制150%缩放验证，不称为另一台高DPI显示器实测。

安装后使用实际角色目录回放12个关键动作，60张原生窗口截图与最终候选逐文件SHA一致，
见`native-installed/records.json`与`paint-equivalence.json`。
真实安装EXE的PrintWindow画面`installed-window.png`已检查，
设置进程使用独立测试配置，实际“桌宠设置”窗口截图已检查、锁存在、WM_QUIT退出码0。
最初UI探针错误地选中了标题为可执行文件名的启动过渡窗口，后以“桌宠设置”标题选择真实窗口；
证据在`installed-ui.json`和`installed-settings-ui-r3/`，不把过渡窗口截图算设置验收。
聊天品牌“麒麟 AI”由真实Qt回归覆盖，未对用户实际配置发起聊天请求。

### 构建、安装与回退

最终隔离构建为`build-r2/qilin-pet-webm-chat`，命令入口为
`scripts/build_onedir.ps1 -Variant webm-chat -QilinOnly -SkipZip -CharacterRoot <模型角色根目录> -OutputRoot <build-r2>`；
构建环境Python3.13.13、PyInstaller6.22.3，中文编码、DLL依赖链、瘦身及GUI启动门禁均PASS，见`build-r2.log`。
最终EXE SHA `89ce535e88ded0b7995a3fb149584fb7fde322940a3f046a443e3b7f17d47b49`。

已安装`D:/AI_helper/dsh-pet-enhanced/qilin-pet-webm-chat.exe`，模型版本3.0.0-rig2d。
旧PID54688经完整EXE路径核实后向拥有窗口的GUI线程发WM_QUIT退出。
原`D:/AI_helper/dsh-pet-local/Start-dsh-pet.ps1`字节不变，经原入口重启，记录PID51656／窗口6490046；后续操作必须重新核实身份。
安装1102文件均与候选SHA相符，内外两份模型各71文件完全一致，均无WebM。
两份真实配置在交换安装目录时逐字节保留，私有备份不入包／不入库。
完整旧安装1178文件在`installed-before-rig2d`，旧EXE SHA
`caeae34968902f2e1ef58fe4cc3152883e68ec0e187d125765d110fe17c3cde3`。
安全交换采用工作区内已经解析与核验的目录重命名，复制／校验失败会恢复旧目录。
重复旧副本`D:/AI_helper/dsh-pet-enhanced-before-rig2d-20261008`也保留：其清理删除操作被自动审批策略拦截，
没有改用其他删除途径；E盘完整回退备份已校验，当前安装不受影响。

便携ZIP：`E:/qilin-codex-fix-20261007/qilin-pet-portable-20261008-rig2d.zip`，115,088,990字节（约115MB），
SHA `c26bfdfc4b456a33c956ff609cb6335d121a2cde2b9005cc809c4a8b5102dc83`。1102个ZIP成员逐一SHA验证，私有配置未包含，制作及核验11.198秒；
见`portable-verification.json`与`staged-files-sha256.json`。
旧便携包保留。GitHub交付使用已获授权的Desktop GUI提交／Push origin；
HEAD、origin跟踪引用和远端`ls-remote`的一致性以`final-delivery-verification.json`回执为准。
当前报告登记本地已完成的验收，不将旧视频台账中的52问题／50待复核直接改成新模型全通过。
新模型验收范围与限制另存`rig2d-acceptance.json`；不创建PR、Release或合并分支。
