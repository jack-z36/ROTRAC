---
id: 1
title: 盘点重定向数据链路
type: research
labels: [wayfinder:research]
status: closed
assignee: chart-2026-10-13
blocked-by: []
---

## Question

找到「Rokoko 手套数据接收 → OmniHand 手指关节角映射」完整数据链路：入口、各阶段文件与函数、所有硬编码硬件耦合点、配置清单、模块依赖关系、git/worktree 状况。为架构 spec（任务一）提供事实基础。

## Resolution

由 file-scout subagent 只读侦察完成，完整报告见 [research/01-pipeline-inventory.md](../research/01-pipeline-inventory.md)。要点：

- **链路真身**在 `Dexhit-worktrees/collection/`（ROS 2 Jazzy，11 包，六边形架构），不在根级 fixture 目录（那只是 URDF/MJCF 模型资产）。四段链路：
  1. `rokoko_hand_receiver_node`：UDP 14043，Rokoko JSON v3（可 LZ4），发布 `/rokoko/{side}/raw_hand`（RawHandFrame）。
  2. `hand_retargeting_node`：解剖学归一化 → Pinocchio/NLopt 每指独立位置 IK → 发布 `/o10_control/{side}/command`。
  3. `omnihand_o10_control_node`：slew 限速、状态机、故障锁存 → `/o10/{side}/joint_cmd`。
  4. `omnihand_o10_hardware_provider_node`：`backends.py` 的 `AgilinkO10Backend` 是全库唯一 `from omnihand import` 触点。
- **换手必改的耦合点集中在五处**：`o10_contracts/joints.py`（关节名/DOF/限位唯一权威）、MJCF 主动-被动耦合、URDF 几何、`backends.py` 后端、拇指专调参数；手套侧耦合在 receiver 整包（换手套只需重写这一个包，下游只见 RawHandFrame）。
- **中段声称手无关但有残余耦合**：21 节点名清单在 decoder 与 retargeting contracts 重复定义、`ACTIVE_JOINT_NAMES` 直接引用、max_joint_rates/平滑常数在脚本+两份 yaml 三处复制。
- **整树无版本控制**：根 `.git` 为空目录；两个 worktree 的 `.git` 文件指向本机不存在的 `/home/hit/Dexhit/.git`，已断链。
- 架构意图权威文档：`CONTEXT.md`、`DOCS/03_工程/`、`AGENTS.md`、handoff 系列。
