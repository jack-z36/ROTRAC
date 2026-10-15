# 侦察报告 02：仓库全量清点与分类

> 由 file-scout subagent 于 2026-10-13 只读侦察产出，作为票据 02 的解决依据。
> 分类口径：链路核心＝直接构成「Rokoko 接收 → OmniHand 关节角映射」数据链路；无关＝与该链路无运行依赖。

## ① 条目分类清单（顶层 + 重点二层）

**顶层**（`/home/zh/桌面/project/ROTRAC`，共 5 项，总 ~724M）

| 条目 | 大小/类型 | 分类 | 依据 |
|---|---|---|---|
| `Dexhit-worktrees/collection/` | 242M，ROS 2 代码工程 | **链路核心** | 主工程，git worktree（`.git` 指向 `/home/hit/Dexhit/.git/worktrees/collection`，父仓库不在本机，git 已断链） |
| `Dexhit-worktrees/processing/` | <1M，纯文档骨架 | 无关/待定 | 全部文件 mtime 同一时刻的初始骨架，src 下只有 README，无实现代码 |
| `dexhit_collection/` | 481M，Python venv | 链路外围（可再生） | `pyvenv.cfg` 显示建于 `/home/pkw/ROTRAC`（已迁移）；被 `init_omnihand.sh` 引用为数值 Python（numpy + pinocchio + nlopt） |
| `omnihand_o10_fixture-f4fd0d913…/` | 92K，模型资产 | **链路核心** | 上游 ManusOmniBridge 的 MJCF/URDF + provenance.json，`init_omnihand.sh`/start 脚本显式校验引用；`.broken-symlinks-old-home-hit/` 为空目录 |
| `.git/`、`.agents/`（顶层） | 空 | 删除候选 | 均为空目录 |

**`collection/` worktree 重点二层**（ROS 2 Jazzy colcon workspace）

- `src/collection/rokoko_hand_receiver_node/`（292K）— **链路核心**。Rokoko UDP 14043 JSON v3 → `/rokoko/{left,right}/raw_hand`（RawHandFrame），结构 core/decoder+adapters/udp。
- `src/collection/hand_retargeting_node/`（1.6M）— **链路核心**。人手归一化→O10 单指 IK（core/ik、normalization、anatomical_correction；adapters/pinocchio、nlopt）；`scripts/record_retargeting_session.py`（录会话）、`scripts/ik_failure_diagnose.py`（IK 失败诊断）。
- `src/collection/omnihand_o10_control_node/`（1.0M）— **链路核心**。软目标 `/o10_control/*/command`→厂商命令，slew limit、状态机、故障锁存。
- `src/collection/omnihand_o10_hardware_provider_node/`（680K）— **链路核心**。O10 真机 Adapter；`backends.py` 懒加载 `from omnihand import HandType, OmniHand2025`（vendor SDK）。
- `src/collection/rokoko_omnihand_launchpad_node/`（110M）— **链路外围**（网页控制面）。其中 `web/node_modules` 107M（Vue3+Vite+echarts）、`web/dist` 112K 构建产物、包内 `runs/` 2M 测试录制。
- `src/collection/teleoperation_support/`（1.8M）— **链路核心**。`ros_interfaces/`（RawHandFrame/RetargetingState/O10ControlState.msg + 2 srv）、`o10_contracts/`（关节表/限位）、`o10_model_assets/`（MJCF/URDF loader+校验；注意 `resource/omnihand_o10_model/` 为空，实际模型在根级 fixture）、`production_bringup/`（launch/config/启动实现）、`system_tests/`、`architecture_tests/`。
- `src/collection/third_party/agillink_omnihand_sdk/`（17M，二进制）— **链路核心（vendor）**。Agilink OmniHand SDK 1.1.8 x64/Jazzy 安装前缀（libomnihand.so、libcanbus/HCAN、omnihand_2025_node_msgs、omnihand_node 可执行），COLCON_IGNORE 隔离。
- `src/{processing,training,deployment}/` — 只有 README 的阶段占位；`src/test/rokoko_test.py` — 独立 LZ4+UDP 调试脚本（**实验性/一次性**）。
- `build/` 14M、`install/` 3.1M、`log/` 14M — colcon 产物/日志，可再生。
- `runs/` 79M — **录制数据**：`session_left.jsonl` 27M、`session_left_v2.jsonl` 27M、`launchpad/` 218 个会话录制 21M（jsonl/json/log）、`acceptance/` 4.5M（含 2 个 .mcap、验收报告）、3 个 `diagnosis_2026…Z/`（基本空）、`diag_v2/`。
- `DOCS/` 644K — **权威文档**：知识（O10 控制契约、归一化与 IK 算法基线、3 份 ROS 接口契约、ADR）、约束、工程（Spec/实施计划/测试矩阵/全流程启动手册）、`98_archive/`、`99_learning/O10调试复盘/`（10 篇归因复盘）。
- `skills/` 716K，26 个 — **共享工具/与链路无关**：通用 AI agent 工作流 skill（acceptance-testing、code-review、tdd 等）。
- 根级脚本（全部链路外围运维工具）：`init_omnihand.sh`（自检+构建 11 包）、`start_omnihand_control.sh`（唯一真机链入口）、`start_launchpad.sh`（控制面，**硬编码 `/home/hit/miniforge3` conda 路径，在本机不可直接用**）、`start_omnihand_right_low_latency.sh`（10月4 最新修改）、`clear_o10_fault.sh`、`decode_rokoko_udp.sh`（tcpdump 解码 Rokoko 包）、`record_o10_diagnosis.sh`（真机诊断录制）、`fix_hcan_udev.sh`。
- 根级文档：`README.md`、`AGENTS.md`（任务路由）、`CONTEXT.md`（16K 术语表）、`HANDOFF.md` + 4 个 `handoff-*.md`（交接历史）、`CLAUDE.md`。
- `.claude/`、`.agents/`、`.codex/`、`.zcode/`、194 个 `__pycache__`/`.pytest_cache` — agent 配置与缓存。

## ② 无关-删除候选汇总

1. `web/node_modules`（107M）— npm install 再生；`web/dist`（112K）构建产物。
2. `dexhit_collection/` venv（481M）— 可再生，但 `init_omnihand.sh` 按路径引用它，删除前需保留重建清单。
3. `build/`+`install/`+`log/`（31M）— colcon 再生。
4. 全部 `__pycache__/`、`.pytest_cache/`（194 处）。
5. `ROTRAC/.git`、`ROTRAC/.agents`、`omnihand_o10_fixture…/.broken-symlinks-old-home-hit`（空目录）。
6. `Dexhit-worktrees/processing/`（<1M 纯骨架，无实现；若放弃 MCAP→LeRobotDataset 阶段可整体删）。
7. `src/test/rokoko_test.py`（一次性 Rokoko UDP/LZ4 调试脚本）。
8. `runs/` 中的 3 个空 `diagnosis_*` 目录。

## ③ 待定项及待定原因

- **`runs/` 录制数据（79M）**：真机会话/验收/诊断证据，`DOCS/03_工程/07_真机IK残差失败判别报告.md` 与 acceptance 报告引用，删除会丢失实验依据。
- **`dexhit_collection/` venv**：虽可再生，但 pinocchio/nlopt 环境重建成本高且被 init/start 脚本硬引用。
- **`skills/`（26 个）+ AGENTS.md/CLAUDE.md/`.claude` 等**：与链路无关但是既有 agent 开发流程的一部分；`processing/skills/`（18 个）是旧版重复。
- **`HANDOFF.md` + 4 个 handoff-*.md、`DOCS/98_archive`、`99_learning`**：历史/交接资料，非运行必需。
- **`decode_rokoko_udp.sh`、`record_o10_diagnosis.sh`、`ik_failure_diagnose.py`**：诊断/实验工具，链路不依赖但真机排障有用。

## ④ 其他灵巧手/设备相关代码盘点

- **未发现其他灵巧手 SDK**：grep inspire/shadow/ability/leap/dynamixel 在 src 下无命中。
- "Dexhit" **不是另一只手**，是项目名（GitHub `jack-z36/Dexhit`）：总体规划 collection→processing→training→deployment 四阶段，仅 collection（即 Rokoko→O10 链）已实现，processing/training/deployment 只有 README 占位。
- 硬件相关只有两处：`third_party/agillink_omnihand_sdk/`（OmniHand 官方二进制 SDK，含 omnihand_2025/omnihand_3_ultra/omnihand_3_lite 多型号节点可执行 + HCAN USB-CANFD 库 + udev 脚本 `fix_hcan_udev.sh`）与 `omnihand_o10_hardware_provider_node` 的 `backends.py`（唯一 `from omnihand import …` 触点，即未来适配其他手的唯一硬件接缝，已按 ports/contracts 抽象）。
- 模型资产两条来源：根级 `omnihand_o10_fixture-f4fd…`（运行时校验用，上游 ManusOmniBridge commit f4fd0d9）与 `o10_model_assets` 代码内嵌的耦合/限位契约。

## ⑤ 技术栈与运行方式概述

- **语言/框架**：ROS 2 Jazzy + colcon（11 个 ament_python 包，hexagonal 架构 core/adapters/application）；Python 3.12（数值链 numpy/pinocchio/nlopt 走独立 venv `dexhit_collection`）；控制面前端 Vue 3 + Vite 6 + echarts（源码 `web/src` 仅 56K）。
- **依赖管理**：package.xml/setup.py（ROS）、手工 venv、`web/package-lock.json`；无统一 lock。
- **数据流**：Rokoko Studio（UDP 14043，JSON v3，可 LZ4 压缩）→ receiver → `RawHandFrame` → hand_retargeting（解剖坐标归一化 + pinocchio/nlopt 单指 IK）→ `RetargetingState`/软目标 → o10_control（限幅/状态机）→ hardware_provider（Agilink SDK/HCAN）→ O10 真机；Launchpad 为 127.0.0.1:8710 网页控制面。
- **运行方式**：`./init_omnihand.sh`（自检+构建+测试）→ `./start_omnihand_control.sh`（真机链，bringup 实现在 `teleoperation_support/production_bringup/`）→ 可选 `./start_launchpad.sh`；注意脚本含对旧机器路径 `/home/hit/…` 与 `/home/pkw/…` 的兼容回退，在本机迁移后需修正。
