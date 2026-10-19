# 03: 可观测、可启动的扭转 wire

**What to build:** 扭转层通过 ROS wire 可观察、可通过规范入口启动：`TwistState` 消息和 topic、节点发布、只读反馈订阅、全部 `twist_*` 必填参数、system test 参数覆盖、A18 门禁和 ASCII 构建门。工作树已有主体实现；本票负责构建、参数、测试和验收闭环。

**Blocked by:** 02、`.scratch/build-baseline-fix/01`（既有构建门票）

**Status:** resolved

- [x] ASCII 构建门自检全绿，`TwistState` 可 import。
- [x] 节点带生产参数启动；缺任一 `twist_*` 参数启动失败。
- [x] 左右手发布 `twist_state`；枚举、可用位和 NaN 正确。
- [x] 反馈缺失时 `theta_robot_fb_available=false` 且角度 NaN。
- [x] 有/无反馈控制命令一致。
- [x] system test 参数覆盖全部 `twist_*` 参数并通过。
- [x] A18 门禁覆盖 `TwistConfig`/`RetargetingConfig`；既有拇指默认值冲突另行记录。
- [x] 现有 `RetargetingState` 行为不回归；ROS graph 测试全绿。

## Resolution

- `TwistState.msg` 已加入 `ros_interfaces/CMakeLists.txt`；ASCII base 下构建成功，`from rokoko_omnihand_msgs.msg import TwistState` 通过。
- `node.py` 发布逐侧 `twist_state`，模型错误时发布 `valid=false`/`backend-unavailable` 的显式不可用快照；只读反馈订阅按 `ACTIVE_JOINT_NAMES` 重排，缺名或非有限时保持不可用。
- `test_twist_node.py` 覆盖：NaN/可用位、激活与精修、反馈可用性、左右手、缺任一 `twist_*` 参数启动失败、stale 发布。
- `system_tests/.../graph.py` 已加入全部 `twist_*` 参数；`rokoko_omnihand_system_test` 的 `test_t10_graph.py` 9 项全绿。
- `init_omnihand.sh` 增加 `--executor sequential`，消除多个测试包在同一 ROS domain 并行造成的节点名串扰；`hand_retargeting`、`omnihand_o10_control`、架构门禁在修改后全绿。
- 全量 init 仍有 5 项既有 `test_t10_faults` 故障注入时序失败；单独运行同样失败，属既有基线，与本票无关（见 STATUS 已知问题）。
- A18：`TwistConfig` 所有字段无默认值；`RetargetingConfig` 除 ADR-0017 的 3 个拇指可选字段外无默认值。拇指默认值冲突已按票要求另行记录。
- 运行：`./scripts/init_omnihand.sh --allow-live-graph`；`pytest test/test_twist_node.py` 6 项全绿。
