---
id: 4
title: 确认清理范围、删除清单与命名规范
type: grilling
labels: [wayfinder:grilling]
status: open
assignee:
blocked-by: [1, 2]
---

## Question

与用户逐项过堂，把侦察清单（票据 02）变成**用户签字的最终 Keep / Delete / Rename 三列清单**与目标目录布局。这是 HITL 票：每一项删除决定必须由用户本人确认，agent 不得代答。

**A. 明确删除（预计无争议，仍需点头）**
node_modules(107M)、web/dist、build/install/log(31M)、__pycache__/.pytest_cache、空目录（根 .git/.agents、.broken-symlinks-old-home-hit）、runs/ 空 diagnosis_*、`src/test/rokoko_test.py`（或降级保留为调试工具？）。

**B. 需用户拍板的待定项**
1. `runs/` 79M 真机录制（验收/诊断报告引用的实验证据）——删 / 移出仓库归档 / 保留？（票据 03 发现：collection 自带 `.gitignore:43` 已整体排除 `/runs/`，即 `runs/retargeting_diag_params.yaml` 这份重定向阈值配置目前不在 git 内——请一并裁决该 yaml 是否单独纳管。）
2. `dexhit_collection/` venv 481M——原样保留，还是删除并改用 requirements 重建（重建清单与 init 脚本改造一并定）？
3. `Dexhit-worktrees/processing/` 骨架——放弃 MCAP→LeRobot 阶段即整体删？
4. `skills/`（26 个）与 `.claude/.codex/.zcode/.agents` agent 配置——留哪些？
5. `HANDOFF*.md`、`DOCS/98_archive/`、`99_learning/` 历史资料——保留还是归档压缩？
6. 诊断工具（`decode_rokoko_udp.sh`、`record_o10_diagnosis.sh`、`ik_failure_diagnose.py`）——保留于 tools/ 还是删？

**C. 命名与布局（本票同时定，供票据 06 执行）**
1. 目标顶层结构：是否把 `Dexhit-worktrees/collection/` 提升为仓库主体（扁平化）？`Dexhit-worktrees/` 与 `dexhit_collection/` 两个易混淆名字怎么改？
2. `omnihand_o10_fixture-f4fd0d913…` 长哈希目录改短名（provenance 保留在内部）。
3. 根级运维脚本是否归位到统一 `scripts/`。
4. 「重定向」边界定义写进根 README（一句话：Rokoko 接收 → OmniHand 关节角映射的完整数据链路及其运行/配置/测试/文档支撑）。

产出：Resolution 中记录最终三列清单 + 目标目录树草案。此清单是票据 05（删除）与 06（重组）的直接输入。
