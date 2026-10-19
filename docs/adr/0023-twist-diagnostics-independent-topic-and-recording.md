---
status: accepted
---

# 扭转诊断使用独立 topic 与独立录制边界

扭转层新增只读观测 topic `/hand_retargeting/{side}/twist_state`（消息 `rokoko_omnihand_msgs/msg/TwistState`），不复用 `RetargetingState`。`RetargetingState` 继续只描述逐指基线 IK；门控、累积转角、精修目标项、回退原因和反馈转角进入 `TwistState`。反转角、轴偏差和四项目标值不可用时用可用位 `false` + NaN，不用 0 冒充。

扭转诊断录制由仓库根规范启动入口自动拉起，写在 `runs/twist-diag/<timestamp>/`，包含独立 MCAP、配置快照、git commit、topic 列表和 README；它与采数据 MCAP 完全分开，业务节点不写 MCAP。录制器覆盖 `/rokoko/{side}/raw_hand`、`TwistState`、`RetargetingState`、`/o10_control/{side}/command`、`/o10/{side}/joint_cmd`、`/o10/{side}/joint_states` 和 `/o10_control/{side}/state`，并使用 best-effort QoS override 避免漏录。

O10 反馈 `/o10/{side}/joint_states` 只由重定向节点只读订阅，用于 `theta_robot_fb` 和轴偏差反馈字段；反馈不参与门控、精修、回退或发布决策，有无反馈时控制命令必须完全一致。这样控制安全仍由 O10 控制节点独立决定，扭转层不能借反馈绕过硬限速。

代价是：多一个 topic、多一个录制进程和一份磁盘开销；分析/回放必须使用专门脚本；`theta_robot_fb` 与 `theta_increment` 的时间配对依赖节点在发布 `TwistState` 时取样，离线分析不应把原始反馈与命令状态重新按墙钟拼接。
