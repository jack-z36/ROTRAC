---
id: 4
title: 确认清理范围、删除清单与命名规范
type: grilling
labels: [wayfinder:grilling]
status: closed
assignee: walk2-2026-10-13
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

## Resolution

walk2-2026-10-13 与用户 7 轮问答对齐（grilling，每轮一问）。裁决如下：

### 定位与范围
- **本机 = 代码落地 + pytest 类自动化测试**，不做真机联调；**最终交付物 = 一个干净的代码仓库**。
- **本图只管 ROTRAC**：兄弟目录（`~/桌面/project/` 下 `vive-control-arm.zip`、`ROS/.rm_sdk_tmp/`、`node/src/vive_wrist_trackers/`、`Dexhit/` 副本、`node/src/rokoko_gloves_receiver/`）的清理由用户自行处理（已记入 map Out of scope；事实详见 [research/04](../research/04-sibling-dirs-arm-vive.md)）。
- **ROTRAC 是唯一权威演进副本**。

### 关键新事实（本轮查明，详见 [research/03](../research/03-runs-and-venv-refs.md)）
- `runs/retargeting_diag_params.yaml` 是手动 start 与 Launchpad 两条启动链路**共用的活参数文件**，必须保留并纳入 git（需放行 `collection/.gitignore:43` 的 `/runs/` 规则）。
- `dexhit_collection/` 是**失效 venv**（bin/ 无 python、shebang 指向 /home/pkw 死路径，链路在本机当前无法启动），但 site-packages 完好，可修复。
- ROTRAC 内**无**睿尔曼/vive 代码（11 包对账干净，脚本显式"不调用 arm"）。

### 最终三列清单

**Keep（保留）**：src/ 全部 11 个 ROS 包（含 third_party vendor SDK、launchpad web 前端源码）；模型资产（改名 `omnihand_o10_model/`）；`runs/retargeting_diag_params.yaml`（纳入 git）；`DOCS/` 全部（含 98_archive、99_learning）+ `CONTEXT.md` + `HANDOFF*.md` + `AGENTS.md` + `CLAUDE.md` + `README.md`（随迁仓库根）；诊断/录制工具 4 件（`decode_rokoko_udp.sh`、`record_o10_diagnosis.sh`、`ik_failure_diagnose.py`、`record_retargeting_session.py`，归位 `scripts/`）；`wayfinder/`；修复后的 `.venv/`（git 忽略）。

**Delete（删除，均已有 tar 备份兜底）**：① `web/node_modules`(107M)+`web/dist` ② colcon `build/install/log`(31M) ③ 194 处 `__pycache__`/`.pytest_cache` ④ 空目录（根 `.agents`、fixture 内 `.broken-symlinks-old-home-hit`；根 `.git` 已被活仓库征用**保留**）⑤ `Dexhit-worktrees/processing/` 骨架 ⑥ `skills/`(26 个)+`.claude/.codex/.zcode/.agents` ⑦ `src/test/rokoko_test.py` ⑧ `runs/` 录制数据 79M（含包内 launchpad runs 2M）→**移出**归档至 `~/backups/ROTRAC-runs-archive/`。

**Rename/Move（方案 A 扁平化）**：`Dexhit-worktrees/collection/src/collection/*` → `ROTRAC/src/*`（collection 层与 Dexhit-worktrees 壳取消）；`omnihand_o10_fixture-f4fd…` → `omnihand_o10_model/`（provenance.json 内留）；`dexhit_collection/` → `.venv/` + **就地修复**（补 `bin/python`→`/usr/bin/python3.12`、修 `pyvenv.cfg`，详见 research/03 引用清单）；collection 根级运维脚本 → `scripts/`；根 README 写入重定向边界定义；`/home/hit`、`/home/pkw` 死路径与 venv 引用全部同步修正；导出 requirements 依赖清单供真机重建。

### 执行拆分
删除+归档+yaml 纳管 → 票据 05；改名/迁移/venv 修复/死路径/README/requirements → 票据 06。验收口径统一为**本机无硬件**：colcon build + pytest + architecture_tests 通过。
