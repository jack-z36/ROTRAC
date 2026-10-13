# Wayfinder 地图：OmniHand 重定向程序架构 spec 与代码库整理

`label: wayfinder:map` · 建图 session：2026-10-13 · 跟踪器约定见 [README.md](README.md)

## Destination（终点）

两件事全部完成即到达终点：

1. **架构 spec 文档定稿**：重新划分 OmniHand 重定向控制程序的功能模块并解耦，使更换一款灵巧手时只需修改少数适配层模块（含「换手操作手册」级别的必改清单）。
2. **代码库整理完成**：仓库只保留与「重定向」相关的项目代码——重定向定义为 **Rokoko 手套数据接收 → OmniHand 手指关节角映射的完整数据链路**（含其运行、配置、测试、文档支撑）；无关代码与目录删除，命名规整，死路径修复，链路自检通过。

按 spec 实际重构代码**不在**本图范围（见 Out of scope）。

## Notes（约定）

- 领域：灵巧手遥操作重定向。链路真身在 `Dexhit-worktrees/collection/`（ROS 2 Jazzy，11 个 ament_python 包，六边形架构）；仓库根其余多为 venv / 模型资产 / 文档。详见 [research/01](research/01-pipeline-inventory.md)、[research/02](research/02-repo-census.md)。
- 本 effort **覆盖** wayfinder「只决策不执行」的默认：`task` 类票据直接落地执行两大任务本身。
- 探索/只读侦察一律交给 subagent（file-scout / Explore），主会话只做高层决策与写盘；**subagent 不可用则暂停并向用户报告**（用户明令）。
- HITL 票（grilling/prototype）必须与用户真人对话完成，agent 不得代替用户作答。
- 每个 session 最多解决一张票（research 类除外）；session 开场先读本 map。
- 决策类票建议调用 Skill：`grilling` + `domain-modeling`；原型票：`prototype`；09 可参考 `implement-spec`。
- `wayfinder/` 目录受保护，任何清理任务不得删除或移动。
- 全程中文。

## Decisions so far（已决索引）

- [盘点重定向数据链路](tickets/01-pipeline-inventory.md)：链路 = receiver(UDP 14043) → hand_retargeting(归一化+单指IK) → o10_control(限速/状态机) → hardware_provider(Agilink SDK/HCAN)；换手耦合点集中在五处：contracts.joints、MJCF 耦合、URDF 几何、backends.py（唯一 `from omnihand import` 触点）、拇指专调；整树无版本控制。
- [仓库全量清点与分类](tickets/02-repo-census.md)：全库 ~724M，核心代码仅 ~6M；大头是 venv 481M、node_modules 107M、runs 录制 79M、colcon 产物 31M；明确删除候选 8 类，待定项 5 类（runs 数据、venv、skills、历史文档、诊断工具）；"Dexhit"是项目名不是另一只手。
- [建立安全网：全量备份与 git 初始化](tickets/03-safety-net-git-backup.md)：备份 `~/backups/ROTRAC-20261013.tar.zst`（123M，30670 条目全数校验，sha256 bef3df0b…70904）；git 仓库建立（main 分支，initial commit 34956ba，846 文件含 vendor SDK）；两个失效 worktree .git 指针已移除；发现 collection 自带 .gitignore 已整体排除 runs/（含 yaml 配置文件），其去留并入票据 04。
- [确认清理范围、删除清单与命名规范](tickets/04-cleanup-scope-grilling.md)：7 轮 grilling 定稿三列清单与**方案 A 扁平化布局**；本机定位 = 代码落地 + pytest 测试（不做真机联调），交付物 = 干净代码仓库；venv 就地修复改名 `.venv/`；runs 录制数据移出归档、活参数 yaml 纳入 git；8 类删除项全删；**本图只管 ROTRAC**——睿尔曼/vive 代码在兄弟目录，用户自行处理。
- [执行清理：删除无关代码与目录](tickets/05-execute-deletion.md)：归档 81M 录制至 `~/backups/ROTRAC-runs-archive/`；yaml 纳管（595bc8e）；processing/skills/agent配置/rokoko_test.py 分三 commit 删除；node_modules/构建产物/缓存 rm；仓库 650M→509M；**对照实验证明删除零测试回归**（17 个基线失败为迁移旧病，清单已移交票据 06）；venv 依赖经 addsitedir 验证完好（cmeel.pth 机制）。
- [执行清理：重命名规整与目录重组](tickets/06-rename-restructure.md)：方案 A 扁平化落地（213297c：src 铺平/脚本归位/fixture 改名 omnihand_o10_model/文档上提/gitignore 合并）；venv 就地修复改名 `.venv`（数值栈全绿，Web 栈确认为系统 Python 职责）；死路径零命中；README 重写+requirements 导出；测试 19→11：顺手修复 launchpad 两个真缺陷（udp_port 吞参数、pdeath_guard 信号竞态泄漏），遗留 11 项全部定性（A18 设计冲突与 pdeathsig 孙进程竞态归 07/09；system_test 9 项名单与基线一致；o10_control 1 项为负载抖动）。

## Not yet specified（雾区）

- **按 spec 实施代码迁移**：票据 10（spec 定稿）后才能细化，且大概率作为全新 effort 另开新图，不在本图内毕业。
- **第二只灵巧手选型与 SDK 资料收集**：用于实证「只改适配层」的承诺是否成立，引入时机未定。
- **DOCS 文档体系归并**：现有 DOCS/03_工程/01_Spec、交接文档与新 spec 的关系，待票据 07/09 后才清晰。

## Out of scope（范围外）

- **按新架构实施代码重构**：本图终点 = spec 定稿 + 仓库整理完成；实施是下一个 effort，另开新图。
- **兄弟目录清理（`~/桌面/project/` 下，ROTRAC 之外）**：`vive-control-arm.zip`（睿尔曼机械臂驱动+arm 控制）、`ROS/.rm_sdk_tmp/` 空壳、`node/src/vive_wrist_trackers/`（vive tracker 接收）的删除，以及 `~/桌面/project/Dexhit/` 旧副本与 `node/src/rokoko_gloves_receiver/` 的对账——票据 04 裁决由用户自行处理（ROTRAC 是唯一权威演进副本；ROTRAC 内经对账无任何 arm/vive 代码）。注意这些目录不在 tar 备份与 git 安全网内。
- **processing/training/deployment 数据管线开发**：其骨架已在票据 04 裁决删除；管线若重启属新 effort。
- **新功能开发**：其他手套品牌的适配实现、力反馈、视觉遥操作、其他数据源。
- **性能优化与实时性改造**。
