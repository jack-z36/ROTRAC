---
id: 2
title: 仓库全量清点与分类
type: research
labels: [wayfinder:research]
status: closed
assignee: chart-2026-10-13
blocked-by: []
---

## Question

对 ROTRAC 全仓库做条目级清点：每项的大小、类型、与重定向链路的关系分类（核心/外围/无关/待定），产出删除候选与待定清单。为代码库整理（任务二）提供事实基础。

## Resolution

由 file-scout subagent 只读侦察完成，完整报告见 [research/02-repo-census.md](../research/02-repo-census.md)。要点：

- 全库 ~724M；**核心代码仅 ~6M**（4 个链路节点包 + teleoperation_support + 92K fixture 资产）。大头全是可再生或待裁决物：`dexhit_collection/` venv 481M、launchpad `web/node_modules` 107M、`runs/` 录制 79M、colcon build/install/log 31M。
- **明确删除候选（8 类）**：node_modules、web/dist、build/install/log、194 处 __pycache__/.pytest_cache、空目录（根 .git/.agents、.broken-symlinks-old-home-hit）、processing worktree 骨架（无实现）、`src/test/rokoko_test.py` 一次性调试脚本、runs/ 空 diagnosis 目录。
- **待用户拍板（5 类）**：runs/ 79M 真机录制证据、venv（重建成本高且被脚本硬引用）、skills/ 26 个 + agent 配置、HANDOFF/98_archive/99_learning 历史资料、诊断工具脚本。
- **"Dexhit"是项目名不是另一只手**（collection→processing→training→deployment 四阶段规划，仅 collection 已实现）；全库未发现第二只灵巧手的 SDK。
- 技术栈：ROS 2 Jazzy + colcon，Python 3.12 数值链走独立 venv，Vue 3 控制面；入口 `init_omnihand.sh` + `start_omnihand_control.sh`；多处 `/home/hit`、`/home/pkw` 旧机器死路径需修。
