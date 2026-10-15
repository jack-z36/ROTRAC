# ADR-0015：层间 wire 采用保守平行 topic 与统一 22 DoF 标准面

- 状态：Accepted
- 日期：2026-10-15
- 范围：重定向 ↔ 标准适配 ↔ 控制之间的 topic 契约、`ros_interfaces` wire schema

## 背景

A06 锁定重定向与控制只经 wire contract 连接；Spec D32 与 K02 锁定软目标 name 自校验和固定顺序，K06 明文 `position[10]`，A16 锁定 wire 字段单一来源。新手维度不同，wire 契约要么泛化成一套参数化 schema，要么按手平行新建，票据 7.2 列为两可的 D2。团队 22 DoF 规范又要求存在跨手统一的观测面，两个诉求必须同时安放。

## 备选方案

1. **完全泛化单一 wire**：维度与关节名进 HandProfile 参数，topic 改中性命名，一套动态 schema 服务所有手；代价是对现有 wire schema 是破坏性变更，K02/K06 的固定名逐项安全复核退化为"按配置匹配"，安全纪律从代码常量降级为配置正确性，且 A16 门禁与全部历史录制数据都要迁移。
2. **发明携带维度元数据的自定义消息**：为新链路定义专用 msg 类型；代价是放弃标准 JointState 的工具生态（rosbag2、可视化、回放），违背团队 22 DoF 标准规范，接口包负担翻倍。

## 裁定

1. 保守平行 topic：层间继续使用标准 `sensor_msgs/JointState` 与固定名自校验纪律；每只手拥有以 `hand_id` 为前缀的平行 topic 族（native_command、control_command、诊断），换手不触碰既有 topic。
2. 同时以 `/observation/{side}_hand/joint_states` 的 22 DoF 标准面（未激活关节填 NaN）作为跨手统一契约，由标准适配节点承担双向转换；控制层安全复核只作用于该手在 22 DoF 中的激活索引。
3. 不引入动态 schema；任何 wire 字段变更仍走 A16 单一来源。

## 后果

- 现有 O10 wire 不被破坏，固定名自校验的安全复核纪律按手原样保持；录制与回放按手自洽。
- 代价：topic 族随手增长，命名空间需要治理；22 维数组对未激活关节有带宽冗余（计算只对激活索引，实际计算量不变）。
- 风险：NaN 依赖 JointState `float64[]` 序列化的正确性，必须早期原型验证，若不成立退回特殊值（如 `1e9`）或独立 valid 位掩码并修订本 ADR；跨手工具（Launchpad、录制清单）必须同时理解平行族与 22 DoF 标准面。
