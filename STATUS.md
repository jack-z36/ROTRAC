# STATUS — 现状快照

> 纪律：只写结论性现状；过程与进度叙事活在 `.scratch/` 票据里。票据关闭或能力基线变化时更新本文件。

> 更新：2026-10-19（twist-retargeting 软件层落地：门控 / 累积转角 / 6 关节残差精修 / TwistState / 独立诊断录制与分析；真机试点未执行）

## 能力基线

- **数据链路**：Rokoko 手套（UDP 14043）→ `hand_retargeting`（归一化 + 单指 IK + 扭转叠加层）→ `o10_control`（硬限速 / 状态机）→ `hardware_provider`（Agilink SDK / HCAN）；仓库根 = ROS workspace（`src/` 下 11 个 ament 包）。
- **数值环境**：`.venv` 数值栈全绿（Pinocchio / NLopt 经 cmeel.pth）；构建产物放在 ASCII base `~/rotrac-build`（`scripts/workspace_paths.sh`）。
- **构建门**：中文路径 rosidl 失败的候选 A 已落地——colcon build/install/log/test-result 全部指向 ASCII base；`ros2 pkg prefix rokoko_omnihand_msgs` 可见，`TwistState` 可 import。`./scripts/init_omnihand.sh` 在存在无关 ROS 节点时需显式 `--allow-live-graph`（默认 fail-closed）。
- **测试**：
  - `hand_retargeting`：109 passed / 14 skipped（真实资产 opt-in 与模块级跳过）；含扭转核心、会话、wire、分析、回放测试与 flake8/pep257。
  - 架构门禁：24 passed（A18 覆盖 `RetargetingConfig`/`TwistConfig`，拇指三字段按 ADR-0017 显式可选）。
  - system test：全量 init 为 20 passed / 6 failed；其中 5 项是既有 `test_t10_faults` 故障注入时序失败（单独运行同样失败），另 1 项 `test_t10_graph::test_three_calibrated_public_replays...` 是负载下的既有时序 flake（单独运行 9 项全绿），均与扭转层无关。
  - Launchpad：80 passed / 2 xfailed。
- **扭转功能层（软件，第一版）**：三指捏合门控、跨 re-grasp 累积转角、6 个 tripod 主动关节解析梯度残差精修、独立有效性门与 baseline 回退、`/hand_retargeting/{side}/twist_state`、只读 O10 反馈、独立 `runs/twist-diag/` 录制、离线分析与回放脚本均已落地；算法/验收口径见 `docs/扭转功能层算法与验收基线.md`。
- **真机（2026-08，旧工作树 `4fedfaa`）**：全链路真机跑通过，四类叠加问题已修复并复验；现语义为无门控直驱，操作者唯一 Service 是 `clear_fault`（ADR-0004 已 superseded，ADR-0005 修订）。扭转层真机试点尚未执行。
- **触觉（2026-09-30）**：adapter 已发布 `/o10/{side}/tactile_states`（SDK 七区帧 → Image 1×268 mono16），包内 56/56 测试过；真机数值未验证。
- **换手架构**：spec **v1.1 已定稿**（2026-10-19 HITL；对抗评审 19 项发现全部处置、事实核查闭合）→ `.scratch/hand-swap/`。核心：22 DoF 目标面/命令面/反馈面三通道拓扑（适配节点为唯一转换点、Provider 持原生 HandAdapter）、thumb 两关节配置固定值驱动（激活 8/22）、标准面零符号变换、NaN 为自定约定（JSON 边界禁 NaN）。按 spec 实施开新 effort。

## 在途（.scratch/）

- `.scratch/twist-retargeting/`：扭转功能层软件票 01–05、07 已实施；票 06 真机试点与首轮标定待执行（需左手 O10 + Rokoko + 安全台架）。

## 已知问题与债

- **扭转层未真机验证**：参数全为未标定试点初值；`theta_robot_fb` vs `theta_increment` 的 RMSE/MAE/Pearson、轴偏差、精修应用/回退比例都还没有真机数据。
- **物体实际转角未测**：没有物体位姿/ArUco/滑移/接触力测量；只能验收机器人转角 vs 人手意图和轴偏差，不能宣称物体被拧成功。
- **O10 tripod 只有 6 个主动关节**：扭转能力受机械结构限制，精修可能频繁碰限位。
- **第一版真机只采左手**：右手 wire 已通，未做真机验收。
- **运动质量（真机，最核心待查）**：四指只出左右（abad）分量、屈伸（pip）几乎不动；拇指动作慢。
- **未标定**：真机 watchdog、通信时序、安全参数、速度舒适性。
- 触觉真机数值、传感器离线表现、10 Hz 轮询性能未验证；真机仅左手接入。
- **左手 pinky_abad 装配公差**：机械零位 -0.1861 rad 低于配置下限 -0.1850，开机即判"超限"（装配公差而非数据故障，判活式：位置/温度/电流可读即链路通）；当年放宽到 -0.19 的校准未保留，`omnihand_o10_contracts` 仍是理论值——该手再接入必复发（源 O10 调试复盘，2026-10 核验仍真）。
- **既有 system test 故障注入 5 项失败**：`test_t10_faults` 的 error/readback/invalid-feedback/disconnect/restart 时序失败，单独运行与全量运行均失败，属既有基线；关闭扭转票时未把它当作本功能引入的问题。
- **A18 拇指默认值冲突**：`RetargetingConfig` 的 `thumb_abad_sensitivity`/`thumb_roll_fixed_value`/`thumb_abad_fixed_value` 仍带代码默认值；ADR-0017 将其作为可选逐指调整保留，A18 门禁已显式白名单，后续单独处理。

## 待办（雾区，不预建票）

- 执行 `.scratch/twist-retargeting/` 票 06：左手真机试点、首轮门控/权重标定、自由空间回归与试点报告。
- 按 spec 实施换手重构——spec 定稿后开新 effort。
- 第二只灵巧手选型与 SDK 资料收集。
