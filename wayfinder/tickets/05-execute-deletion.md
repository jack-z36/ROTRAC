---
id: 5
title: 执行清理：删除无关代码与目录
type: task
labels: [wayfinder:task]
status: open
assignee:
blocked-by: [3, 4]
---

## Question

按票据 04 定稿的 Delete 清单执行删除与归档（前置：票据 03 安全网已就位）。**只允许命中下列路径，清单外一律不动，有疑问停下来问用户。**

按顺序执行：

1. **runs/ 归档（先归档后删）**：`mkdir -p ~/backups/ROTRAC-runs-archive/`，把 `Dexhit-worktrees/collection/runs/` 下的录制数据（`session_left*.jsonl`、`launchpad/`、`acceptance/`、`diag_v2/`、`diagnosis_*`）移入归档；**保留** `runs/retargeting_diag_params.yaml` 原地不动。launchpad 包内 `rokoko_omnihand_launchpad_node/runs/`（2M 测试录制）一并移入归档。
2. **yaml 纳入 git**：修改 `Dexhit-worktrees/collection/.gitignore:43` 的 `/runs/` 规则为放行该 yaml（如 `/runs/*` + `!/runs/retargeting_diag_params.yaml`），`git add` 提交。
3. **删除（每大类一 commit，写明类别与释放空间）**：
   a. `web/node_modules`(107M)、`web/dist`
   b. colcon `build/`+`install/`+`log/`(31M)
   c. 全部 `__pycache__/`、`.pytest_cache/`（194 处，`find … -prune -exec rm -rf` 慎用，逐目录核对）
   d. 空目录：根 `.agents/`、`omnihand_o10_fixture…/.broken-symlinks-old-home-hit/`（**根 `.git/` 是活仓库，保留**）
   e. `Dexhit-worktrees/processing/`（整个骨架，删后 `Dexhit-worktrees/` 若空则壳一并移除）
   f. `Dexhit-worktrees/collection/skills/`（26 个）
   g. `.claude/`、`.codex/`、`.zcode/`、`.agents/`（collection 内）
   h. `src/test/rokoko_test.py`
4. **自检（本机无硬件口径）**：colcon build 全通过 + 各包 pytest + architecture_tests 通过；`start_omnihand_control.sh` 语法/dry 检查不因删除报缺文件（yaml 在位）。
5. `wayfinder/` 完好；确认 `git status` 干净。

验收：归档目录存在且可列出；git log 分批删除记录清晰；自检全绿；磁盘释放 ~220M+。
