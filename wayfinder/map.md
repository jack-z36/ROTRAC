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

## Not yet specified（雾区）

- **按 spec 实施代码迁移**：票据 10（spec 定稿）后才能细化，且大概率作为全新 effort 另开新图，不在本图内毕业。
- **第二只灵巧手选型与 SDK 资料收集**：用于实证「只改适配层」的承诺是否成立，引入时机未定。
- **依赖环境文档化**（venv → requirements/锁定清单、init 脚本路径修正方案）：取决于票据 04 对 venv 的裁决，暂不切票。
- **DOCS 文档体系归并**：现有 DOCS/03_工程/01_Spec、交接文档与新 spec 的关系，待票据 07/09 后才清晰。

## Out of scope（范围外）

- **按新架构实施代码重构**：本图终点 = spec 定稿 + 仓库整理完成；实施是下一个 effort，另开新图。
- **processing/training/deployment 数据管线开发**：即使票据 04 决定保留其骨架，其开发也不在本图。
- **新功能开发**：其他手套品牌的适配实现、力反馈、视觉遥操作、其他数据源。
- **性能优化与实时性改造**。
