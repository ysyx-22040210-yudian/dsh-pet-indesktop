# 麒麟桌宠修复与品牌清理（2026-10-07）

品牌清理版本已安装并通过真实 Windows 启动：`D:/AI_helper/dsh-pet-enhanced/qilin-pet-webm-chat.exe`。桌面入口“麒麟桌宠”，原自定义接口、位置/大小和其他偏好保留。用户最新要求由 Codex继续修复，GLM移交方案已被覆盖。

## 核心行为

- 默认接口改“自定义接口”，地址/模型留空；旧 vendor provider及相关名称、原默认鲸鱼台词、彩蛋标题/目录、旧角色子槽在读取和保存时迁移。未配置Chat/vision明确提示，且不请求网络。
- 现代/经典菜单、注册表、托盘、设置搜索和控件退出旧网页/Harness/余额/消费统计；旧后台自动启动/状态服务停用，延迟安装完成信号不能重新启用它。
- 8张麒麟表情（点赞、睡觉、工作、疑惑、抱抱、加油、零食、荷包）和“瑞麟花园”背景，采用已批准圆润短腿身份。睡觉双眼全闭，保留此前伸懒腰闭眼修复。8张表情1254×1254，背景1672×941；原始生成输出与入项目文件SHA一致。
- 麒麟独立包只列麒麟角色，保留105动作。EXE、托盘、窗口、快捷方式、导出插件显示麒麟名称。旧配置/密钥标识与必要迁移识别词用于兼容。
- 双击回退不抛AttributeError；退休岛不创建碰撞体。打包固定兼容SSL，排除PATH中的外来ICU，正常退出精确核对的GUI线程。

## 修改文件说明

以下 `git diff --numstat` 是相对提交前HEAD的累计工作树统计，含此前用户/GLM修改；不是全部归因于本次续作。源码基线HEAD f4cb620、初始差异 `git-diff-before.patch`，局部修复基线 `repo-before`、品牌基线 `brand-before`，均在 E:/qilin-codex-fix-20261007。品牌清理验证完成时尚未提交；随后用户授权通过 GitHub Desktop 上传，交付记录见下文。

| 文件 | 增/删行（累计） | 改动与原因 |
|---|---:|---|
| `.gitignore` | 2/0 | 把新麒麟表情池加入资源例外，防止克隆或分发时遗漏8张必需图片。 |
| `assets/icon.ico` | -/- | 用麒麟图标替换原品牌图标；同字节随EXE、窗口/托盘与快捷方式分发。 |
| `docs/AGENT_LINK_PROTOCOL.md` | 10/3 | 保留既有自定义Agent协议文档与共享事件约定。 |
| `docs/INDEX.md` | 8/1 | 登记并更新本轮修复、品牌清理、安装和验收证据入口。 |
| `docs/ONEDIR_PACKAGING.md` | 16/0 | 给出可复现麒麟构建、配置目录兼容和真实GUI/安装验证命令。 |
| `pet/agent_cost.py` | 1/1 | 保持旧计算器兼容，清理其产品品牌说明；相关入口和查询已退休。 |
| `pet/agent_link.py` | 95/83 | 移除旧服务显示项，拒绝启动/启用，延迟安装回调不能复活服务；关闭消费网络路径，保留其他Agent联动。 |
| `pet/app.py` | 35/94 | 修复双击/退休岛碰撞相关生命周期；取消旧状态服务和自动启动，麒麟托盘/启动错误标题。 |
| `pet/autostart.py` | 1/1 | 自启动展示名称改麒麟，兼容原有注册标识及路径。 |
| `pet/balance.py` | 16/27 | 专属价格辅助改遗留兼容名称，移除品牌文案；不再暴露余额功能。 |
| `pet/catalog.py` | 7/0 | 麒麟冻结构建默认仅列麒麟；保留源码旧素材的兼容加载。 |
| `pet/chat/ai_settings_page.py` | 4/4 | 清理接口/模型专属默认和示例，保留用户自定义接口配置。 |
| `pet/chat/models.py` | 2/2 | 默认接口为未配置的自定义接口，不默认绑定付费服务。 |
| `pet/chat/modern_styles.qss` | 2/2 | 侧栏样式改通用对象标识，与现代聊天窗统一。 |
| `pet/chat/providers.py` | 11/0 | 未配置地址或模型时返回设置提示，禁止意外联网。 |
| `pet/chat/settings_dialog.py` | 1/1 | 接口模型示例改通用表达。 |
| `pet/chat/themes.py` | 8/35 | 旧鲸鱼主题退出注册表，增加瑞麟花园；保留其他主题。 |
| `pet/chat/widgets.py` | 5/4 | 现代聊天初始名称改麒麟；无manifest时麒麟显示名回退，保留用户正常别名。 |
| `pet/config.py` | 40/21 | 默认接口和表情改麒麟，读取/归一化时迁移退休服务及图片，Agent配置facade始终关旧服务。 |
| `pet/context_menu.py` | 1/1 | 移除默认回退模板中的旧品牌动作入口，保留新版菜单结构。 |
| `pet/context_menus/fun_entry.py` | 2/2 | 彩蛋标题和图片默认改麒麟，共用真实表情池。 |
| `pet/context_menus/legacy.py` | 0/9 | 经典右键菜单移除网页/Harness/余额/消费入口。 |
| `pet/context_menus/registry.py` | 8/16 | 语义注册表移除退休动作，旧已保存菜单覆盖无法把它们加回来。 |
| `pet/context_menus/shared.py` | 9/67 | 清理退休动作构建器，子宠入口和通用文案改麒麟。 |
| `pet/dynamic_island.py` | 2/2 | 保留通用展示兼容文案，清理角色表述；运行时岛服务已退休。 |
| `pet/fun_image_popup.py` | 7/4 | 默认图片池改麒麟，迁移旧内置绝对/相对目录，保留正常外部自选图片路径。 |
| `pet/menu_templates/modern-default-v1.json` | 246/50 | 保留此前现代菜单布局扩展，清理其中退休服务入口。 |
| `pet/menu_templates/modern.json` | 51/7 | 现代模板同步通用功能入口，避免旧品牌动作出现。 |
| `pet/modern_settings_dialog.py` | 16/269 | 删除旧服务/余额/消费/岛控件和写回，清理搜索入口，保留其他设置。 |
| `pet/node_runtime.py` | 1/1 | 运行时依赖说明改通用Agent名称；旧桥接不进入麒麟包。 |
| `pet/persona_presets/legacy.json` | 4/4 | 内置回写反馈改通用Agent，数据驱动文案结构保持。 |
| `pet/persona_presets/whale_maid.json` | 8/8 | 展示为麒麟陪伴模式，内置回写反馈改Agent；旧mode ID兼容旧配置。 |
| `pet/persona_template.py` | 2/2 | 台词模板显示麒麟陪伴模式名称，保留可导入的配置结构。 |
| `pet/self_talk_voice.py` | 1/1 | 旧鲸鱼固定台词映射改瑞麟加油，继续使用现有声音缓存契约。 |
| `pet/settings_pet_controls.py` | 6/77 | 清理退休依赖与控件工厂，麒麟陪伴模式显示名同步。 |
| `pet/settings_widgets.py` | 0/1 | 导航退出已退休岛域，其他语义设置域保持。 |
| `pet/vision.py` | 6/14 | 取消专属模型推导/thinking字段；未配置视觉地址/模型时明确提示，禁止网络请求。 |
| `pet/window.py` | 7/0 | 保留此前交互修复和新标识，退休余额自动刷新不创建新服务。 |
| `pet/window_optional_services.py` | 16/0 | 双击回退采用event.ignore；已退休的余额自动刷新停止。 |
| `pyproject.toml` | 1/1 | 保留既有Python/测试依赖配置，沿用当前解释器，不为离线模型加运行依赖。 |
| `scripts/build_linux.sh` | 1/1 | 表情资源目录改麒麟，保留平台构建入口；该平台未实测构建。 |
| `scripts/build_macos.sh` | 1/1 | 表情资源目录改麒麟；该平台未实测构建。 |
| `scripts/build_onedir.ps1` | 74/99 | 独立输出/角色根/麒麟变体；只打麒麟资源、新名称/窗口图标，退休旧集成，固定SSL、隔离ICU、真实GUI正常退出验证。 |
| `tests/test_agent_link.py` | 11/216 | 退休DSH安装UI断言和开启路径；保留解析/其他Agent生命周期、交互、模型访问及事件机制覆盖。 |
| `tests/test_agent_link_dep_specs.py` | 2/4 | 旧profile兼容回归去专属bundle默认；继续验证真实profile结构与失效安装token。 |
| `tests/test_architecture.py` | 4/1 | 架构断言同步退休配置依赖，保留模块边界检查。 |
| `tests/test_balance.py` | 24/33 | 遗留价格计算名称更新；明确给测试provider配置，保留计算边界覆盖。 |
| `tests/test_chat_subsystem.py` | 52/52 | 接口迁移/聊天请求用通用显式provider，继续真实Qt窗口和网络边界覆盖。 |
| `tests/test_chat_themes.py` | 15/15 | 注册表断言改瑞麟花园，保留裁剪、重点区域和明暗覆盖。 |
| `tests/test_config_key_migration.py` | 4/4 | 密钥迁移fixture使用通用接口；保留secret只进不出的回归。 |
| `tests/test_config_schema.py` | 2/2 | 默认接口/服务配置断言对齐麒麟迁移和facade。 |
| `tests/test_desktop_pet_features.py` | 42/115 | 设置页删退休功能断言；用语义页名和显式通用测试模型，仍测试保存/布局/交互。 |
| `tests/test_dynamic_island_balance_tier_time.py` | 2/2 | 遗留岛档位单元fixture显式配置provider，不依赖退休默认。 |
| `tests/test_feature_gating.py` | 2/2 | 设置能力组合不再要求退休服务控件，保留无Chat/平台分支。 |
| `tests/test_first_batch_features.py` | 1/1 | 用户可见标题和默认角色文案改麒麟。 |
| `tests/test_harness_launcher.py` | 3/29 | 退休自动启动app断言；保留源树历史启动器的隔离边界测试。 |
| `tests/test_harness_lifecycle.py` | 9/83 | app不再启动旧服务，历史launcher纯单元边界继续隔离。 |
| `tests/test_island_chat.py` | 9/1 | 遗留岛识屏fixture显式配置通用视觉provider，继续生命周期回归。 |
| `tests/test_island_content_cache.py` | 2/2 | 遗留缓存行为测试用通用模型，默认未配置不误触网络。 |
| `tests/test_island_shell_wiring.py` | 48/16 | 退休岛不创建碰撞服务，停止已有碰撞体；相关回归先红后绿。 |
| `tests/test_menu_layout.py` | 13/27 | 现代/经典菜单移除退休动作，保留语义布局与预览行为。 |
| `tests/test_pet_interaction_locks.py` | 27/0 | 真实QMouseEvent覆盖双击三分支与Qt事件接受/忽略，先红后绿。 |
| `tests/test_proactive.py` | 10/10 | 视觉任务测试显式配置通用provider，保留调度/取消/失败覆盖。 |
| `tests/test_requested_regressions.py` | 7/7 | 设置/聊天既有回归改语义页名和通用provider，保留窗口边缘交互。 |
| `tests/test_settings_and_resources.py` | 11/12 | 资源默认目录/设置能力断言对齐麒麟和退休功能。 |
| `tests/test_settings_interaction_tabs.py` | 4/4 | 按语义域定位控件，保留保存、Tab与布局回归。 |
| `tests/test_updater.py` | 1/1 | 测试UI展示同步，保留更新判断行为。 |
| `tests/test_vision.py` | 7/7 | 显式视觉provider和通用模型；退出专属模型推导请求断言，保留网络边界回归。 |
| `tests/test_voice_chime_service.py` | 1/1 | 语音服务展示文字同步，保持现有调度/线程/缓存边界。 |

新增文件及非Git运行产物：

| 文件/资源 | 说明 |
|---|---|
| `pet/product_migration.py` | 集中迁移旧provider、品牌标题/台词/别名、旧内置图片与服务设置；冻结麒麟版的旧角色子槽改麒麟。 |
| `tests/test_qilin_product_cleanup.py` | 新安装、迁移/持久化、保留自定义数据、无网络提示、Qt设置/Chat标题、跨线程延迟回调、旧子槽迁移公开回归。 |
| `scripts/bundle_python_ssl.py`、`tests/test_bundle_python_ssl.py` | 从构建Python实际加载DLL复制兼容_ssl/OpenSSL，污染PATH/覆盖旧DLL/全新进程导入回归。 |
| `scripts/verify_bundle_startup.py` | 独立配置真实Windows桌宠/设置窗口，显式兼容数据目录名，完整路径核对后给拥有GUI的线程WM_QUIT。 |
| `tests/test_removed_island_settings.py` | AI/no-AI退休页/控件/搜索不存在，无关保存保留原岛配置。 |
| `assets/qilin_memes/{praise,sleep,work,confused,hug,cheer,snack,wallet}.png` | 8张内置表情替代旧品牌图片，已入项目并随包分发。 |
| `assets/chat/qilin-garden.png` | 瑞麟花园新背景，明确实际尺寸和主题裁剪参数。 |
| `pet/agent_discovery.py`、`pet/running_agents_dialog.py` | 保留此前Agent发现/管理；本次导出插件名、注释、export改麒麟。 |
| `pet/branding.py`、`pet/codex_monitor.py`及既有相关测试/文档 | 保留此前部署图标/Codex联动，不重写或归因本轮。 |
| `.scratch/qilin-original-motion/HANDOFF.md`、本报告 | 保存实际断点、已安装与待修动作、完整证据路径。 |
| 实机 `Start-dsh-pet.ps1`、桌面“麒麟桌宠.lnk” | 现有Ollama启动链使用新EXE，快捷方式图标/名称改麒麟；原文件保存到E盘。 |
| 角色manifest与2段WebM | 清点归档/忙碌点按验收字节替换；manifest实际fps24、失败反馈118帧，内外重复manifest同步，瑞麟现世文件重命名，数量仍105。 |

本轮安装的WebM增量：

| 动作 | 最终SHA256 | 验收 |
|---|---|---|
| 工作状态-清点归档 | `16ccecd72c4511740aaea53e12a5ed23b96be87e93ead66d8ee078f483fa0298` | 241帧面部/手/纸张逐帧图板，白/暗全画布、收起/首尾、边缘0，Qt完整播放。 |
| 工作状态-忙碌点按 | `e0c87187be4db1cf36f9b8ef69934fb1013d82932592f207191bd2e77288cb2a` | 241帧图板，键盘在手边、207/208收起，工作图标不裁角，首尾无原人物残片，Qt完整播放。 |

## 性能分析

Windows，Python3.13.13 / PySide6 6.11.2。命令 `E:/dsh-pet-dev313/Scripts/python.exe E:/qilin-codex-fix-20261007/benchmark_brand_release.py`。旧安装备份和新EXE各3个40秒样本，顺序交替，配置隔离、同一SHA待机素材、同一缩放，后20秒为稳态统计。具体文件/命令/每秒父子进程CPU、RSS、线程/句柄及I/O在 `performance-brand-release/record.json`。

| 路径 | 启动中位数 | 父子进程合计CPU均值（单核口径） | 父子进程RSS均值 | 同时主机CPU |
|---|---:|---:|---:|---:|
| 旧版本（3次） | 1.769s | 28.138% | 177.128MiB | 24.948% |
| 麒麟版本（3次） | 0.748s | 25.520% | 152.656MiB | 21.550% |

主机背景负载不同，旧版第一次RSS234MiB、后二次约148MiB；这些数字不证明普遍CPU改善或稳定80MiB节省。新版本后20秒RSS变化为+6.520/+8.289/+7.930MiB，短采样不能证明长期无增长，也不能单凭它判长期泄漏。整体105动作、多宠/长时间内存趋势仍待专项验收。

新增迁移扫描只在配置归一化/读取/保存触发，不创建线程或网络请求。表情/背景在打开图片窗口或选主题时读盘，无新增常驻GPU模型/解码依赖。退休余额/Harness路径不会发起周期网络/后台启动；六个性能样本末尾父进程inet连接数均0，这不是覆盖整段流量的抓包。新版本样本最后父子合计77/77/78线程、1042/1043/1041句柄，包含既有Qt/FFmpeg；未给新品牌功能新增常驻线程。

新版40秒父进程I/O read_bytes约976–979MB、write_bytes54.7–55.4KB；psutil Windows口径包括管道读写，不能将其当磁盘媒体读取量。双击/图标/迁移的新路径成本通过GUI冒烟和公开回归记录；本轮没有对每次配置归一化做微秒级单独bench。

清点归档/忙碌点按真实Qt播放器241帧全部出现，无错误、>84ms间隔0，中位帧间隔45.618/45.513ms。此前旧全库105段25182帧Qt通过仅绑定旧字节，不能套作新动作全库的视觉完成证据。

## 实机运行记录

- 有效迁移red：旧provider未删除；Chat/vision未配置会尝试网络；旧角色子槽保留shenshen；旧品牌台词/标题/别名留存。各处focused先红后绿，日志 `brand-migration-corrected-red.log`、`unconfigured-red.log`、`unconfigured-vision-red.log`、`brand-character-red.log`、`brand-captions-red.log`。子槽test补version4以符合原配置版本规则，未改变原size迁移语义。
- 最后全量 `python -m pytest -q`：**2977 passed、11 skipped、251 warnings，200.31s**（`brand-full-final-r3.log`）。退休角色相关族75passed；最后ruff与diff--check通过。剩余warnings为既有Qt/Python弃用提示。
- 本机构建 `build-release-r2.log`：SSL与编码/真实QtDLL链PASS；桌宠0.710s、设置1.419s各单次冒烟，两个进程退出码0。初次按新EXE stem寻找旧数据锁目录导致smoke误判，改显式config-dir-name后通过。
- `verify_brand_gui.py` 新EXE从隔离旧子槽配置真实启动；角色、provider、图片池/标题、旧服务开关迁移通过。Windows上下文菜单消息打开菜单，退出码0，没有旧服务node/npm子进程。
- 48个真实Windows Qt设置截图：明暗、720/800/1120宽、13/17px字体、桌宠/互动/自动化/AI；label低于最小宽0，Tab焦点记录。逐页公开语义回归仍通过。真实布局代表图在 `settings-matrix-brand-final`；macOS/Linux未实际构建或启动。
- 8张内置图经真实Windows Qt表情窗口渲染和正常关闭，sleep图双眼闭合（`meme-widget-evidence`）。原生成PNG及精确提示词：`qilin-image-provenance.json` / `qilin-image-prompts.md`；通过内置imagegen生成，复制保留实际原像素与SHA。
- 安装前核完整旧EXE路径无进程，未强杀；旧包1199文件和EXE字节、真实配置复制备份。106原始制作参考另存E盘，继续修复不依赖删除的安装资源。旧品牌/旧角色/集成资源退出当前安装。
- `installation.json`、`real-profile-migration.json`：新包替换完成，两个真实配置保存迁移；新桌面快捷方式“麒麟桌宠”。Windows PowerShell无BOM把首次快捷方式名误解码，已从精确记录路径更正并将本地安装脚本/启动器写为兼容编码。
- **已安装EXE**真实Windows鼠标双击打开唯一独立设置进程，再次双击仍唯一；settings.lock取得，测试实例均正常退出（`exe-interaction-installed-brand.log`）。真实配置随后通过原本地启动链恢复运行，最终运行记录见 `installed-runtime.json`。

## 构建、安装与交付

构建命令见 [onedir文档](ONEDIR_PACKAGING.md)，Windows实测。新EXE SHA256：`caeae34968902f2e1ef58fe4cc3152883e68ec0e187d125765d110fe17c3cde3`。

便携包：`E:\qilin-codex-fix-20261007\qilin-pet-portable-20261007-brand-cleanup.zip`，1470203266字节；SHA256：`3c7739002e467839308ee3d1239c752893aa22de4fcde0cd26be06fbab41d6a1`。1069个包内文件与安装字节和ZIP成员逐一校验一致（`release-files-sha256.json`、`release-verification.json`）；仅麒麟、105动作、8表情。zip不含用户配置或生成模型。安装外部characters与内置包用相同staging，避免外部优先级复活旧动画。

回滚：先核完整新EXE路径并通过GUI正常退出，恢复 `installed-before-brand-cleanup`、`private-config-before-brand-cleanup`、`Start-dsh-pet.before-brand-cleanup.ps1` 和旧快捷方式备份。配置备份含私有数据，不把内容放进报告或分发包。

## GitHub 源码交付（2026-10-07）

用户授权通过 GitHub Desktop 上传。Desktop 登录账号 `ysyx-22040210-yudian` 对原仓库没有写入权限，因此已通过 Desktop 创建个人 Fork，选择“用于自己的项目”；`origin` 指向个人 Fork，原仓库保留为 `upstream`。上传目标是 [feat/running-agent-discovery 分支](https://github.com/ysyx-22040210-yudian/dsh-pet-indesktop/tree/feat/running-agent-discovery)。

本批 98 个源码、资源、测试和文档文件约 18.7MB，包含此前累计修改及新模块的全部依赖；最大文件 1,936,216 字节。候选文件扫描没有发现常见访问令牌或私钥格式。构建包、私有配置备份、模型、临时制作和测试产物不在本批源码提交中；完整便携包仍保留在上文 E 盘位置。

推送前本地门禁：ruff 与 `git diff --check` 通过；全量 2977 passed 的记录见上文。另用 `E:/dsh-pet-dev313/Scripts/python.exe E:/qilin-codex-fix-20261007/github-desktop-upload/stress_gate.py`，在 16 个逻辑 CPU 上持续施加负载，将受影响的 Agent/Qt/生命周期/IPC/播放器相关 20 个测试族复跑三遍：每遍 **617 passed、2 skipped**，pytest 耗时 **51.91 / 50.32 / 51.17 秒**。主机 156 个一秒 CPU 样本平均 **96.46%**，最大 **100%**；负载子进程均已退出。原始命令、三轮日志与采样在 `github-desktop-upload/stress-record.json`、`stress-round-{1,2,3}.log`。

**源码已上传**：在 Desktop 中点击提交与 Publish branch，生成 [a7d5160b34f92a423a546587be341c11fe791175](https://github.com/ysyx-22040210-yudian/dsh-pet-indesktop/commit/a7d5160b34f92a423a546587be341c11fe791175)。提交包含全部 98 个候选文件，逐文件 Git blob 与提交前记录一致，工作树清洁；只读 `git ls-remote` 确认线上分支哈希与本地提交相同。原克隆只抓取 `main`，发布后本地缺少当前分支的远端跟踪引用；补充仅针对当前分支的 fetch 映射，并由 Desktop Fetch 同步。证据保存在 `github-desktop-upload/commit-verification.json` 和界面截图；本段上传回执作为文档补充提交。

## 后续动画修复断点

**品牌清理阶段已交付；105动作的完整视觉修复尚未完成。** 初始台账55个观察问题，新增2个候选通过并安装；其余53个观察问题及50个待全时序审查动作继续保留，没有通过删动作缩小范围。

- 轻快记录SHA `7abdf2183cf200ebfbdb34786d4c32c7c0db4d0727b3f2b0585de3f6d699e156` Qt/边缘通过，但笔记本仍有鲸鱼logo，拒绝安装；需换麒麟书封，复核f32/48/56/120笔和手遮挡以及241帧时序。
- 木马motion-r3失败：f120双手合掌未抓柄，f240木马残留，拒绝安装。下一版要精准接触关键帧/分段收起，避免重复同一失败prompt。
- 其他缺失道具/坐姿支撑、手物接触、原人物残片与首尾状态逐项复核，不能把Qt解码、IOU或文件完整判成视觉通过。
- 本地制作作品`/result/...`链接404仍需补取件接口；只在已授权本任务8772/8191范围处理，不触及EP01或8189。
- 完成后还需按最终SHA全库Qt播放、完整视觉台账、长时间/多宠性能、必要重新构建和实机验收。

精确断点在 `.scratch/qilin-original-motion/HANDOFF.md` 与 `E:/qilin-codex-fix-20261007/visual-repair-ledger.json`。
