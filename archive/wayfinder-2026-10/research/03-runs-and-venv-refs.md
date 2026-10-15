# 侦察报告 03：runs/ 与 venv 引用核查

> 由 file-scout subagent 于 2026-10-13 只读侦察产出，作为票据 04 裁决与票据 05/06 执行的依据。

## ① runs/ 引用分类

**运行时读取（启动链路，2 处）**
- `src/collection/teleoperation_support/production_bringup/scripts/start_omnihand_control.sh:23,222,304`：`RETARGET_PARAMS="$WORKSPACE_ROOT/runs/retargeting_diag_params.yaml"`，启动前检查存在（:222），作为 ROS `--params-file` 传给 hand_retargeting 节点（:304）。根级 `start_omnihand_control.sh` 与 `start_omnihand_right_low_latency.sh` 均 exec 到此脚本。
- `runs/launchpad/`：Launchpad 网页历史 API 只读——`app.py:61,115-117` GET /api/runs → `run_session.py:64-84 list_run_sessions()`（只读遍历各 run 目录的 metadata.json/artifacts）；同一目录又被 `orchestrator.py:398-408`（RunSession/Recorder/sysmon）作为录制输出**写入**。读写混合。

**仅写入（录制输出）**
- `record_o10_diagnosis.sh:100`：`RUN_ROOT="$COLLECTION_ROOT/runs/diagnosis_$RUN_STAMP"`。
- `hand_retargeting_node/scripts/record_retargeting_session.py:18`：`--output runs/session_left.jsonl`。
- `hand_retargeting_node/scripts/ik_failure_diagnose.py:698,1159`：默认 `--out runs/ik_diagnosis`。
- Launchpad profile yaml（default.yaml:10 / diagnostic.yaml:9）经 `orchestrator.py:342-347` 解析 `runs/retargeting_diag_params.yaml` 后作为 `--params-file` 传给节点（**读取**）。

**仅文档提及**：`HANDOFF.md:44`（人工离线分析示例）。`runs/acceptance、diag_v2、session_left*.jsonl、diagnosis_*` 无代码自动读取。

## ② retargeting_diag_params.yaml 使用方式

是 hand_retargeting 节点的 **ROS 参数文件**（`/**: ros__parameters:`，含 ik_residual_thresholds、frozen_length 阈值等），不是录制产物。手动 start 链路与 Launchpad 链路都在启动时读取。**删除它会同时弄断两条链路。** 目前被 `collection/.gitignore:43` 的 `/runs/` 规则排除在 git 外。

## ③ dexhit_collection venv 硬引用清单

形式 A：`/home/hit/miniforge3/envs/dexhit_collection`（原工作站 conda env）；形式 B：`$COLLECTION_ROOT/../../dexhit_collection`（仓库根相对路径）。
- `start_launchpad.sh:8,9,21,29,35`：A——python + PYTHONPATH + conda activate。
- `init_omnihand.sh:11-13`：B 优先、A 兜底——数值 python 解释器。
- `record_o10_diagnosis.sh:167,169`：A——DEXHIT_COLLECTION_PREFIX + PYTHONPATH。
- `production_bringup/launchpad/default.yaml:12`、`diagnostic.yaml:11`：A——环境变量传给子节点。
- `production_bringup/scripts/start_omnihand_control.sh:27-31,214-215,224,226`：B 优先、A 兜底——PYTHONPATH/LD_LIBRARY_PATH 前缀 + 解释器预检。
- 文档：HANDOFF.md:33,41-42、handoff-o10-control-fix.md:42-43、DOCS/01_知识/07、DOCS/03_工程/00 与 09。
- 第三种历史路径 `/home/pkw/ROTRAC/ROTRAC/dexhit_collection` 仅在 build 缓存 env 中（随 build/ 删除）。

## ④ venv 有效性

`dexhit_collection` 是从 `/home/pkw/ROTRAC` 搬迁来的**失效 venv**：`bin/` 中无任何 python 可执行文件；console 脚本 shebang 指向不存在的 `/home/pkw/.../bin/python`；A、B 两种硬编码目标在本机均缺失，所有脚本的 venv 分支都会死在前置检查。但 `lib/python3.12/site-packages`（pinocchio/cmeel/coal/eigenpy/nlopt/vendor omnihand）完好，可借本机 `/usr/bin/python3.12` 修复利用。
