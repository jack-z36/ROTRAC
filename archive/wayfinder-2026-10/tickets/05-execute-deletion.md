---
id: 5
title: 执行清理：删除无关代码与目录
type: task
labels: [wayfinder:task]
status: closed
assignee: walk3-2026-10-13
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

## Resolution

walk3-2026-10-13 执行完毕。

### 已执行
1. **归档**：`~/backups/ROTRAC-runs-archive/collection-runs/`（79M：session_left*.jsonl、launchpad/、acceptance/、diag_v2/、3×diagnosis_*）与 `launchpad-node-runs/`（2M）；`runs/` 只剩 yaml。
2. **yaml 纳管**：collection/.gitignore 的 `/runs/` 改为 `/runs/*` + `!/runs/retargeting_diag_params.yaml`，入库 commit `595bc8e`。
3. **git 跟踪删除**：`4be22fe` processing 骨架（74 文件）；`de9fc2d` skills/（80 文件）+ .claude/.zcode/.agents（git rm）+ .codex（rm）；`dcf5b3c` src/test/rokoko_test.py。
4. **文件系统删除**：web/node_modules(107M)、web/dist、colcon build/install/log(31M)、52 个缓存目录、空目录（根 .agents、.broken-symlinks-old-home-hit）。仓库 650M → **509M**（本票合计释放/移出 ~215M）。

### 自检结果
- 已删项引用 grep 零命中；8 个运维脚本 `bash -n` 全过；`wayfinder/` 完好；git status 干净。
- **colcon build 11/11 通过**（12s，构建产物重定向至 /tmp 未污染仓库）。
- **测试 516 个：删除前基线 18 失败 / 删除后 19 失败，其中 17 个完全相同**；差异 2 个均为 DDS 图计数/时序类抖动（hardware_adapter 两次挂的是不同测试；omnihand_o10_control 的 1 个失败复跑 86/86 全过）。**结论：删除未造成任何测试回归。**（对照实验：git worktree 于 initial commit 34956ba 跑同一套 build+test。）
- **venv 依赖验证**：cmeel 系包（pinocchio 4.1.0/nlopt）需 `site.addsitedir()` 处理 `cmeel.pth` 才可导入——裸 PYTHONPATH 不行。票据 06 修复 venv 后此问题自然消失；本次测试用 `/tmp/rotcol-site/sitecustomize.py` 垫片跑通。

### 移交票据 06 的基线失败清单（17 个，均为迁移旧病，非本票造成）
- A27：运维脚本丢 +x（init_omnihand.sh 等，st_mode 0644）→ chmod 修复
- A19：vendor `libusb-1.0.so` 拷贝时符号链接变实体 → 恢复 symlink
- A18：experimental parameters 门禁 assert 失败 → 查因
- bringup 1 个：start 脚本内容与测试断言漂移（`o10.right.request_interval_ms=30`）→ 对齐测试或脚本
- launchpad 4 个：synthetic 子进程超时（疑 /home/hit 死路径）+ pdeathsig 进程组断言 → 随死路径修复复测
- system_test 9 个：SoftwareO10Provider 图时序（spin_until 超时）→ 环境性，单独评估
