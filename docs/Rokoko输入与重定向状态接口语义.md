# Rokoko 输入与重定向状态接口语义

> 新会话为何需要本文：链路前半段（Rokoko 接收 → 手部重定向）的**时间语义、坐标约定和 NaN/失败约定**——哪些时间是"接收时间"、哪些数值必须原样保存、哪些 0 值是非法占位——是调试数据年龄、stale 判定和 MCAP 回放对齐时最容易踩的坑，且无法从消息定义本身读出。字段清单和枚举数值 grep `src/teleoperation_support/ros_interfaces/msg/` 即得，本文不复述。
>
> 合并自旧知识区两份契约：Rokoko 原始手部帧接口契约、手部重定向状态接口契约（2026-10 蒸馏）。

## 1. RawHandFrame：Rokoko 原始手部帧

消息 `rokoko_omnihand_msgs/msg/RawHandFrame`，左右手独立 Topic `/rokoko/{left,right}/raw_hand`。手侧由 Topic 身份确定，消息不带 `side` 字段；左右手允许独立存在、独立失败、独立 stale。

### 时间语义（最易踩坑）

- `header.stamp` 是接收节点**在本机收到 UDP 数据包时**的 ROS 接收时间——不是 JSON 解析完成时间、不是发布时刻、更不是 Rokoko 源时间。它用于 stale 判定、软平滑、端到端年龄和 MCAP 对齐；双手来自同一场景包时共享同一 `header.stamp`。
- `source_timestamp` 原样保存 JSON v3 场景级 `scene.timestamp`。**其单位与 epoch 未确认**：在真实数据验证之前不得转换成 ROS 时间、不得与 `header.stamp` 相减、不得用于控制计时；只把它当作可录制的原始数值。缺失或非有限时整包无效。
- 下游一切"数据年龄"计算都以上述接收时间为准；重定向目标、软平滑、控制目标的 `header.stamp` 全部继承该时间，链路上任何节点不得改写为本地处理时间。

### 坐标约定标签

`header.frame_id` 固定记录 `rokoko_world_y_up_z_forward`。这是**数据语义标签**，不要求存在对应 TF frame。若真实数据证明官方坐标约定与此不同，必须显式修订契约，不能静默转换后继续沿用旧标签。

### 21 节点规范顺序与按名校验

`node_names[i]`/`positions[i]`/`orientations[i]` 同索引表达同一节点。语义顺序固定为 `Hand`，随后 Thumb/Index/Middle/Ring/Little 各 `Proximal/Medial/Distal/Tip`。节点拼写（如 `leftThumbProximal`）由接收节点依据官方 Custom Streaming JSON v3 版本化 fixture 拥有；接收节点必须按 JSON 节点名称重排为规范顺序，重定向节点必须校验收到的 21 个名称与规范表完全一致——**不能只按数组索引盲用**。真实抓包若与官方示例拼写不一致，须显式修订契约而非静默兼容。

### Actor 语义

`actor_index` 是接收节点配置选中的 Actor 数组索引（默认 0），一次只处理一个；索引不存在时整包不产生手部消息。`actor_name` 只用于记录诊断，不参与路由或控制。

### 原始数值与失败隔离

- `positions` 保留 Rokoko 世界坐标数值，**不做**单位换算、掌心相对化、镜像、滤波或尺度归一化；长度单位名称未确认，但会在归一化比值中相消。
- `orientations` 以 `x,y,z,w` 保存源四元数，必须有限且范数不得接近零；不做单位化。四元数不参与当前归一化与 IK，仅为录制/诊断/未来扩展保留。
- 只有完整、名称唯一、数值有限、四元数合法的 21 节点才发布；缺失侧不补零、不复制另一侧、不复用历史帧。
- 分包失败语义：JSON 无法解析/场景级字段非法/Actor 索引不存在 → 左右均不发布；只有一侧合法 → 只发布该侧。坏包或坏侧不得终止接收进程（节流日志 + 计数器）。

### QoS 搭配及其理由

- 接收节点发布：`reliable + volatile + keep_last(10)`——depth 10 吸收短时抖动，不承诺进程阻塞或磁盘过慢时绝不丢帧。
- 重定向订阅：`best_effort + volatile + keep_last(1)`——回调来不及消费时只保留最新帧，不累积旧动作队列。这是防御：正常运行前提仍是操作者把 Rokoko 发布频率配置为低于 IK 可持续吞吐，深度 1 只在违反前提时限制时延扩散。
- 录制器请求 `reliable + volatile` 以利用发布者可靠传输；这只覆盖 ROS/DDS 层，不保证上游 UDP 或磁盘写入不丢。
- `deadline`/`lifespan` 用默认值，不参与控制安全判定；stale 由应用层按接收时间和阈值判断，QoS 事件只能作诊断证据。

## 2. RetargetingState：重定向可观测状态

消息 `rokoko_omnihand_msgs/msg/RetargetingState`，Topic `/hand_retargeting/{left,right}/state`。**只读诊断**：用于操作者界面、MCAP 录制和验收，不参与 O10 控制；状态消息丢失不得改变机械手运动，控制节点的安全判定（`targetReady`/`targetFresh`）独立自有。

### 时间语义

- `header.stamp` 是本条状态快照**实际发布时**的 ROS 时间（`frame_id` 空）——状态可由帧处理、stale 定时检查或模型阶段转换触发，不得等同于输入时间。
- `input_stamp` 是当前状态关联的最近一帧 RawHandFrame 接收时间；尚未收到任何输入时由整体 `phase` 表明未初始化，零时间不得解释成真实输入时间。
- `solve_executed=true` 时 `solve_finished_stamp` 是本次同侧 IK 完成时刻、`solve_duration_sec` 是实际耗时；为 false 时消费者不得使用完成时刻，且耗时**必须为 NaN，不能用 0 冒充"未求解"**。

### 阶段与五指状态语义

整体 `phase` 枚举（数值见 msg）：INITIALIZING / COLLECTING_LENGTHS / WAITING_FIRST_VALID_IK / TRACKING / STALE / RECOVERY_CONFIRMING / RECOVERY_RESUMING / MODEL_ERROR。该阶段只描述重定向节点，不编码控制节点的 `fault_latched` 或 `motion_enabled`。

- `ready` 严格按算法基线定义：五指长度已冻结**且**五指都至少产生过一次有效 IK。它是历史就绪条件，不表示本事件发布了命令。
- `command_published` 表示本事件是否实际发布了新软目标。合法组合包括：尚未就绪 (false,false)、正常跟踪 (true,true)、整侧掌坐标无效 (true,false)、stale/恢复确认 (true,false)、单指失败但已有历史目标 (true,true)。
- `length_state[i]`：COLLECTING（冻结前，坏样本只是不推进窗口）/ FROZEN / CURRENT_INVALID（已冻结但当前帧违反冻结尺度；冻结值不改变）。
- `ik_state[i]`：VALID / INPUT_INVALID / SIDE_INVALID / RESIDUAL_EXCEEDED / SOLVER_ERROR / UNINITIALIZED / NOT_RUN_LENGTH_COLLECTING / NOT_RUN_STALE。恢复确认期间仍执行 IK 并报告各指实际结果，整体语义由 `phase` 表达。
- **残差 NaN 约定**：`residual_available[i]=true` 时 `normalized_residual[i]` 是当前无量纲残差；不可计算时可用位 false 且值为 NaN——**禁止用 0 表示缺失**（0 代表零指尖误差）。`target_projection_*` 三个可达性见证字段同理（`*_available` 位 + NaN），含义见算法基线蒸馏注记。
- `solver_result_code[i]` 保留 NLopt 原始返回码（正=成功、负=失败），`0=SOLVER_NOT_RUN`。返回码只描述停止原因，**不等于** IK 候选有效性。
- `used_previous_valid_target[i]` 表示本次组合 10 维目标时该指是否因当前失败使用了历史有效目标——只表达组合决策，`command_published=false` 时不得声称该目标已发送。
- `recovery_valid_count`/`recovery_valid_duration_sec` 仅在 RECOVERY_CONFIRMING 中表示当前连续恢复序列，其他阶段均为 0。

### 发布与录制规则

事件驱动发布（帧处理、进入 stale、恢复转换、模型初始化成败、阶段变化），不要求固定周期重复相同快照；监控方按 `header.stamp` 判断状态自身是否过旧。两个状态 Topic 必须可由外部 rosbag2/MCAP 录制；重定向节点不直接写 MCAP。

## 3. TwistState：扭转功能层只读诊断

消息 `rokoko_omnihand_msgs/msg/TwistState`，Topic `/hand_retargeting/{left,right}/twist_state`，与 `RetargetingState` 平行存在。它只描述扭转门控和 6 个 tripod 关节的精修，不复制逐指基线残差；逐指基线仍看 `RetargetingState`。字段完整清单以 `src/teleoperation_support/ros_interfaces/msg/TwistState.msg` 为准。

### 字段语义

- **帧与门控**：`header.stamp` 是本条诊断实际发布时间；`side`、`valid` 标识帧有效性；`active` 是门控状态。`gate_aperture`/`gate_extension` 是已按冻结三指尺度归一化的无量纲量，`gate_on_count`/`gate_off_count` 是当前连续帧计数。
- **角度**：`theta_task` 是跨 re-grasp 保留的人手累积转角；`theta_base` 是本次激活锁存的起点；`theta_increment = theta_task - theta_base` 是本次目标增量。`theta_robot_cmd` 从本帧发布命令对应的关节角计算，回退时等于 baseline 测量值；`theta_robot_fb` 从最新 O10 反馈计算。
- **轴偏差**：`axis_deviation_cmd_deg`/`axis_deviation_fb_deg` 是当前三指法向与锁存参考轴的夹角，单位度。
- **目标项**：`objective_total` 及 `objective_rot/conn/axis/pos` 是四项无量纲目标值，总值为四项之和。
- **求解状态**：`refinement_status` 为 `REFINEMENT_NOT_ACTIVE / REFINEMENT_APPLIED / REFINEMENT_FALLBACK_BASELINE`；`failure_reason` 的数值到语义映射见 msg，包含参考无效、人体几何无效、后端不可用、求解器异常、非有限、限位、trust region、几何退化、轴偏差超限、baseline 不完整、精修被拒和轴反向。`iterations`/`evaluations`/`solve_duration_sec` 只描述本帧精修尝试。

### NaN 与可用位约定

- 反馈转角、反馈轴偏差各自带 `*_available` 位；不可用时位为 `false` 且值为 NaN，**禁止用 0 冒充**。
- 参考无效、几何无效、反馈缺失或门控未激活时，对应的命令侧/反馈侧角度和轴偏差可以为 NaN；消费者必须先看可用位，再看数值。
- `objective_*` 在未尝试精修或精修无有效评估时为 NaN；`solve_duration_sec` 在未求解时为 NaN。
- `theta_task`/`theta_base`/`theta_increment` 是纯累积量，门控未激活时仍可有历史值（0 是合法历史值，不是"未知"）。

### 发布与反馈边界

- 每帧 raw hand 处理、进入 stale 时发布；模型资产不可用时发布 `valid=false`、`failure_reason=BACKEND_UNAVAILABLE` 的显式不可用快照。
- `/o10/{side}/joint_states` 由重定向节点只读订阅，只用于 `theta_robot_fb` 和反馈轴偏差；它不参与门控、精修、回退或发布决策，有无反馈时控制命令必须完全一致。
- 扭转诊断录制独立于采数据 MCAP：`runs/twist-diag/<timestamp>/`，录制主题、QoS override 和配置快照见《扭转功能层算法与验收基线》与 `scripts/record_twist_diagnosis.sh`。

## 4. 相关文档

- [手套21关键点标准化规范](手套21关键点标准化规范.md)（公司标准命名、Rokoko 映射策略、未来换手套扩展）
- [人手归一化与O10单指IK算法基线](人手归一化与O10单指IK算法基线.md)（状态背后的算法语义与式（62）输出顺序）
- [扭转功能层算法与验收基线](扭转功能层算法与验收基线.md)（门控、转角、目标、有效性门与验收口径）
- [O10控制契约与安全语义](O10控制契约与安全语义.md)（软目标被谁消费、安全为何独立）
