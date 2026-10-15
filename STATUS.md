# STATUS — 现状快照

> 纪律：只写结论性现状；过程与进度叙事活在 `.scratch/` 票据里。票据关闭或能力基线变化时更新本文件。

> 更新：2026-10-15（文档体系迁移完成：doc-system-migration 九票全部 resolved）

## 能力基线

- **数据链路**：Rokoko 手套（UDP 14043）→ `hand_retargeting`（归一化 + 单指 IK）→ `o10_control`（硬限速 / 状态机）→ `hardware_provider`（Agilink SDK / HCAN）；仓库根 = ROS workspace（`src/` 下 11 个 ament 包）。
- **数值环境**：`.venv` 数值栈全绿（Pinocchio / NLopt 经 cmeel.pth）。
- **测试**：pytest 11 项通过（wayfinder 票 06 清理后）；遗留 11 项失败已定性（A18 设计冲突、pdeathsig 孙进程竞态、system_test 9 项与基线一致、o10_control 1 项负载抖动）。全包 colcon test 曾 278 项 0 失败（2026-08 旧工作树）。
- **真机（2026-08，旧工作树 `4fedfaa`）**：全链路真机跑通过，四类叠加问题已修复并复验；现语义为无门控直驱，操作者唯一 Service 是 `clear_fault`（ADR-0004 已 superseded，ADR-0005 修订）。
- **触觉（2026-09-30）**：adapter 已发布 `/o10/{side}/tactile_states`（SDK 七区帧 → Image 1×268 mono16），包内 56/56 测试过；真机数值未验证。
- **换手架构**：spec 草案已完成（47 用户故事；22 DoF 标准接口 + HandProfile/HandAdapter 抽象；D1–D8 八项裁定已定），待评审定稿 → `.scratch/hand-swap/`。

## 在途（.scratch/）

- `.scratch/hand-swap/`：spec 对抗评审与定稿（票 01）
- `.scratch/build-baseline-fix/`：中文路径构建失败修复（票 01）

## 已知问题与债

- **构建门被卡**：仓库路径含中文使 rosidl 接口生成必败（CMake `file(STRINGS)` 非 ASCII 拆行，根因实锤；候选 A：ASCII 构建 base，已验证；B：仓库迁 ASCII 路径）→ `build-baseline-fix`
- **运动质量（真机，最核心待查）**：四指只出左右（abad）分量、屈伸（pip）几乎不动；拇指动作慢
- **未标定**：真机 watchdog、通信时序、安全参数、速度舒适性
- 触觉真机数值、传感器离线表现、10 Hz 轮询性能未验证；真机仅左手接入
- **左手 pinky_abad 装配公差**：机械零位 -0.1861 rad 低于配置下限 -0.1850，开机即判"超限"（装配公差而非数据故障，判活式：位置/温度/电流可读即链路通）；当年放宽到 -0.19 的校准未保留，`omnihand_o10_contracts` 仍是理论值——该手再接入必复发（源 O10 调试复盘，2026-10 核验仍真）

## 待办（雾区，不预建票）

- 按 spec 实施换手重构——spec 定稿后开新 effort
- 第二只灵巧手选型与 SDK 资料收集
