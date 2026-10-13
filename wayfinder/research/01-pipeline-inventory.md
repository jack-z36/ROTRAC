# 侦察报告 01：重定向数据链路盘点

> 由 file-scout subagent 于 2026-10-13 只读侦察产出，作为票据 01 的解决依据。

## 0. 总体定位

- 真正的「Rokoko → OmniHand O10」链路**不在** `omnihand_o10_fixture-...`（那只是模型资产 URDF/MJCF），而在 `/home/zh/桌面/project/ROTRAC/Dexhit-worktrees/collection/`（ROS 2 Jazzy 多包工程）。`processing` worktree 是另一条「采集→MCAP→LeRobot→训练」数据管线骨架，与遥操作链路无关。
- `dexhit_collection/` 是 Python 3.12 Miniforge 运行时 venv（含 vendor `omnihand` SDK 1.1.8、pinocchio 4.1.0、nlopt 2.11.0），供链路运行时导入。
- 所有路径前缀 `.../Dexhit-worktrees/collection/`。

## ① 数据链路阶段图

**入口**
- `./start_omnihand_control.sh`（仓库根包装）→ `src/collection/teleoperation_support/production_bringup/scripts/start_omnihand_control.sh`：按顺序 `ros2 run` 启动 4 个节点，等待图就绪，Ctrl-C 全停。这是操作者唯一规范入口（脚本注释明示）。
- 备选：`production_bringup/launch/production.launch.py`（强制外部参数文件+vendor launch）；`rokoko_omnihand_launchpad_node`（Vue 网页一键编排器，`orchestrator.py:44` 硬编码 UDP 14043）。

**a. Rokoko 手套接收**（UDP，Rokoko Studio Custom Streaming）
- `src/collection/rokoko_hand_receiver_node/rokoko_hand_receiver/adapters/udp.py:11` — `UdpDatagramReceiver`：线程阻塞 `recvfrom`，绑定 `0.0.0.0:14043`（参数 `udp_port`，node.py:32 声明）。
- `core/decoder.py:189` `decode_scene` — 严格解析 Rokoko JSON v3（`version "3,0"`），支持 LZ4 frame 压缩（magic `04 22 4d 18`，decoder.py:45）；取 `scene.actors[actor_index].body` 下 `left/right` 各 21 个节点（`Hand` + 5 指 × Proximal/Medial/Distal/Tip，decoder.py:21-43）的 position+quaternion。
- `node.py` — 发布 `/rokoko/{side}/raw_hand`（`RawHandFrame`，消息定义在 `teleoperation_support/ros_interfaces/msg/`）。

**b. 解析与归一化**（`src/collection/hand_retargeting_node/`）
- `hand_retargeting/node.py:183-191` 订阅 raw_hand；`application/session.py:115` `process()` 为主管线。
- `core/normalization.py` — 构建人体解剖学手掌系（Hand 原点、+Y 掌根→四指根、+X 掌宽、+Z=X×Y），按冻结指链长度做尺度归一化；`core/anatomical_correction.py` 解剖修正；`core/projection.py` 可达性投影。

**c. 手指关节角映射（每指独立位置 IK）**
- `core/coupling.py` — `CouplingModel`：从 MJCF 读主动→被动关节耦合多项式（10 主动 + 6 被动 = 16 关节）。
- `adapters/pinocchio.py` — Pinocchio FK/雅可比（16 维、关 mimic）；`adapters/nlopt.py:26` — 每指有界 `LD_SLSQP`（maxeval/maxtime 由参数）；`adapters/model_geometry.py` — 从锁定 URDF 求指根、指链长、手掌方向映射 A_s。
- `application/session.py:148-159` 目标生成 `t = root + ℓʳ·A_s·(Tip−Proximal)/ℓʰ`；`:198` `_apply_thumb_adjustments` 拇指 roll/abad 增益/固定值；`core/smoothing.py` 接收时间低通（10 个 τ）。
- 产物发布 `/o10_control/{side}/command`（JointState，10 关节名自校验顺序，node.py:328-334）。

**d. 安全限速与发送 OmniHand**
- `src/collection/omnihand_o10_control_node/omnihand_o10_control/node.py` — 订阅 command、`/o10/{side}/joint_states`（真实反馈）与 joint_error_states；`core/slew_limiter.py` 硬变化率限制（须用新鲜反馈初始化）；arm/disarm/clear_fault service；发布 `/o10/{side}/joint_cmd`。
- `src/collection/omnihand_o10_hardware_provider_node/omnihand_o10_hardware_adapter/backends.py:72` `AgilinkO10Backend` — 映射 Agilink O10 官方 Python SDK（注入式），transport 支持 `zlgcan/hcan/socketcan/zlgcan_tcp` 等（backends.py:183-188）；vendor 轮子装在 `dexhit_collection/.../site-packages/omnihand`，源码副本在 `src/collection/third_party/agillink_omnihand_sdk/`。`BlockedExternalBackend` 为无硬件安全兜底。
- 合同层：`teleoperation_support/o10_contracts/omnihand_o10_contracts/joints.py` — **A11 不变量**：10 主动关节名/索引/左右限位的唯一代码所有者。

## ② 硬件耦合点清单（换手/换设备必改）

| 位置 | 内容 |
|---|---|
| `o10_contracts/.../joints.py:44-55,66-85` | 10 个关节名 `thumb_roll…pinky_pip`、DOF=10、左右各自弧度限位（唯一权威） |
| `rokoko_hand_receiver/core/decoder.py:21-43` | Rokoko 21 节点名后缀 + JSON v3 + LZ4（换手套必改） |
| `hand_retargeting/contracts.py:12-19` | 同一份 21 节点后缀（重复定义，接收侧的镜像） |
| `hand_retargeting/core/coupling.py` + MJCF | 主动-被动耦合多项式（OmniHand 专有） |
| `production_bringup/scripts/start_omnihand_control.sh:41-49,296-346` | UDP 14043、actor_index=0、HCAN 左 device_id=1/右=0、hand_device_id=1、channel=0、10 维 max_joint_rates/时间信用 0.1s |
| 同脚本 `:230` | lsusb 预检 `a8fa:8598`（HCAN USB-CANFD 适配器 VID:PID） |
| `session.py:198-221` + 参数 | thumb_roll/thumb_abad 灵敏度/固定值（拇指专调） |
| `o10_model_assets/omnihand_o10_model/loader.py:109-116` | 资产根解析：显式 > `OMNIHAND_O10_MODEL_FIXTURE` 环境变量 > install share（A12 禁止源码内绝对路径） |
| `omnihand_o10_fixture-f4fd0d913c2151bcb4be0d29fbc02761b9638009/` | URDF(23 joint/16 可动)/MJCF + provenance.json（upstream manusvr/ManusOmniBridge @f4fd0d9，license_confirmed=false） |
| `backends.py:100-103` | vendor 错误位（stalled/overheat/over_current/motor_except/commu_except） |
| `production_bringup/launchpad/*.yaml` env 段 | **已失效旧机器路径** `/home/hit/miniforge3/...`、`/home/hit/dexhit-external/...`（本机无 /home/hit） |
| provider `contracts.py` | TACTILE_REGIONS 触觉分区（OmniHand 专有） |

## ③ 配置文件清单

- `runs/retargeting_diag_params.yaml` — 重定向阈值（MAD 0.01×5、冻结偏差 0.10、IK 残差 0.05、100 evals/0.02s、平滑 τ 0.1×10、stale 0.5s）。
- `production_bringup/launchpad/default.yaml` — Launchpad 基线（8-17 真机验证值，含 4 命令、safety 参数、env）；`diagnostic.yaml` — 无硬件诊断档（rate 0.1）。
- `production_bringup/config/production.example.yaml` — 刻意空壳（生产须外部填写）。
- `third_party/agillink_omnihand_sdk/.../config/omnihand_*_node.yaml` — vendor SDK 节点配置（zlgcan/hcan/socketcan/rs485/usb 示例）。
- `omnihand_o10_fixture.../provenance.json` — 模型来源与 SHA-256。
- wire 契约（非配置但属接口）：`ros_interfaces/msg/{RawHandFrame,RetargetingState,O10ControlState}.msg`、`srv/{ControlOperation,ReadO10ActiveJoints}.srv`。

## ④ 依赖关系与模块边界判断

依赖方向：receiver→`rokoko_omnihand_msgs`；retargeting→`omnihand_o10_contracts`+`o10_model_assets`+pinocchio/nlopt；control→contracts；provider→contracts+vendor SDK（注入）；launchpad 仅子进程编排。`architecture_tests`/`test_control_import_guard.py` 有边界门禁。

天然解耦边界（架构本身已按此设计，CONTEXT.md 术语表是权威）：
- **手套侧**＝receiver 节点整体（协议/节点名/端口），对下游只暴露 `RawHandFrame`（21 节点 position+quaternion）——换手套只需重写这一个包。
- **手侧**＝contracts.joints（名/限位）+ MJCF 耦合 + URDF 几何 + AgilinkBackend + 触觉——换手集中在这五处。
- **中段**（归一化/投影/IK/平滑）理论上手无关，但 21 节点后缀、拇指调整、`ACTIVE_JOINT_NAMES` 直接引用仍把它与两端拉住。
- 最需治理的重复：max_joint_rates/smooth_time_constants 在 shell 脚本 + 两个 launchpad yaml 三处复制；decoder.py 与 hand_retargeting/contracts.py 的节点名清单重复；launchpad yaml 中 /home/hit 死路径。
- 已知算法缺陷记录：`HANDOFF.md`/`DOCS/03_工程/07_真机IK残差失败判别报告.md` — IK 失败主因「几何不可达（A-dir）」，建议在目标生成处加可达性投影（`core/projection.py` 即其产物）。

## ⑤ git / worktree 状况结论

- 仓库根 `.git` 是**空目录**，`git status`/`rev-parse` 均报「不是 git 仓库」——根目录无版本历史。
- 两个 `Dexhit-worktrees/{collection,processing}` 各有 `.git` **文件**指向 `gitdir: /home/hit/Dexhit/.git/worktrees/...`，而 `/home/hit` 在本机不存在 → **两个 worktree 全部失效**（主仓库 /home/hit/Dexhit 已随旧机器丢失）。fixture 目录下的空 `.broken-symlinks-old-home-hit/` 也印证整树从 /home/hit 迁来。当前整个 ROTRAC 树处于无版本控制状态，任何继承动作前建议先重建 git。

架构意图权威文档：`Dexhit-worktrees/collection/CONTEXT.md`（38 条领域词汇，含整链安全/标定设计意图）、`DOCS/03_工程/01_Spec、02_实施计划、09_全流程启动手册`、根目录 4 份 `handoff-*.md` 交接文档、`AGENTS.md`（文档路由）。
