# O10 架构决策索引

本目录记录 OmniHand O10 控制链中难以逆转、具有真实取舍且仅看代码难以理解的架构决策。不记录普通实现选择、当前进度或测试结果。

- [O10 IK 以主动关节为唯一求解空间](0001-o10-active-joint-constrained-kinematics.md)：以 10 个主动关节求解，并显式派生 6 个被动耦合关节后计算运动学。
- [Phase 1 单指 IK 使用 SLSQP 与解析耦合梯度](0002-phase1-single-finger-ik-slsqp-analytic-gradient.md)：运行时使用 Pinocchio 完整指链雅可比与 MJCF 耦合雅可比组成的解析梯度，中心差分只作离线验证。
- [O10 最终命令使用反馈初始化的事件触发硬限速](0003-o10-feedback-initialized-event-driven-slew-limit.md)：以真实启动反馈和最后实际发送命令为基准，用单调时钟与封顶时间额度约束每关节命令变化率。
- [O10 真机运动需要逐侧显式操作者授权](0004-o10-explicit-per-side-operator-arming.md)：**已废弃**——曾要求每侧显式使能；`4fedfaa` 已移除 arm/disarm，运动由新鲜目标直接驱动。
- [区分可自动恢复暂停与锁存控制故障](0005-o10-recoverable-pause-vs-latched-fault.md)：stale/退化/IK 失败属可自动恢复暂停，硬件、通信和安全门异常属锁存故障；`4fedfaa` 起授权措辞已随 arm 门控移除，暂停/锁存区分仍成立。
- [stale 恢复使用连续整侧验证和既有两级平滑](0006-stale-recovery-validation-and-bounded-resume.md)：恢复必须满足连续整侧有效帧和最短观测时间，先重发保持目标，再由低通与硬限速逐步追赶；`4fedfaa` 起授权措辞已移除。
- [O10 在线模型使用版本锁定的最小资产包](0007-o10-versioned-minimal-runtime-model-assets.md)：核心运行资产仅含左右 URDF、左右 MJCF 和 provenance；通过 ROS 安装空间加载、关闭 URDF mimic 并严格校验耦合。
- [O10 控制使用事件—效果边界接入可替换硬件 Provider](0008-o10-control-event-effect-hardware-port.md)：控制 Application 只处理纯事件和效果；生产厂商 Provider 与无真机纯软件 Provider 实现同一 O10HardwarePort wire contract。
- [Phase 1 自有运行包固定使用 Python 3](0009-phase1-owned-runtime-python.md)：自有运行代码统一使用 Python/ament_python，使框架边界和依赖门禁具有单一可执行语言范围；跨语言迁移必须先升级门禁。
- [O10 无动作主动关节读取使用逐侧 Service](0010-o10-fresh-active-joint-read-service.md)：生产与纯软件 Provider 通过同一逐侧 Service 在请求后执行无动作新读取，控制端拥有超时与复核。
- [Launchpad 真机与 system_test 编排边界](0011-launchpad-real-hardware-test-boundary.md)：真机模式禁止编排配置引用 `system_test`；mock 模式允许复用纯软件 Provider 与场景生成器。
- [Launchpad 作为设备编排层](0012-launchpad-device-orchestration-layer.md)：Launchpad 位于控制面最外层，按模式选择业务包和替身 Provider，业务包不得反向依赖 Launchpad。
- [Collection 源码按生产节点优先组织](0013-collection-production-node-first-source-layout.md)：顶层只展示五个生产期节点，并将接口、模型、bringup、测试和第三方运行时隔离到显式支撑目录。
- [换手适配模块以 support 包承载并增设独立标准适配节点](0014-hand-swap-adapter-support-packages-and-standard-adapter-node.md)：HandProfile/HandAdapter 能力收进 `teleoperation_support/` 支撑包由业务节点注入，仅 22 DoF 双向转换是独立节点。
- [层间 wire 采用保守平行 topic 与统一 22 DoF 标准面](0015-conservative-parallel-topic-wire-with-22dof-standard-surface.md)：每手 `hand_id` 前缀平行 topic 族保持固定名自校验，`/observation` 22 DoF（未激活 NaN）为跨手统一契约。
- [关节契约按手单 owner 落在 per-hand contracts 包或配置](0016-per-hand-joint-contract-single-owner.md)：O10 事实留在 `omnihand_o10_contracts`，新手建 `{hand_id}_contracts` 包或配置承载，A11 门禁改写为逐手唯一 owner。
- [拇指专调保留为配置化的可选逐指调整](0017-thumb-adjustments-as-optional-per-finger-config.md)：真机验证的拇指补偿移入 `RetargetingConfig` 逐指钩子，O10 携带现值，新手缺省无此行为。
- [触觉 Port 保留为只读可选能力](0018-tactile-port-optional-read-only-capability.md)：只读不进安全原则通用化，无触觉的 HandAdapter 返回 `NOT_SUPPORTED`。
- [诊断消息继承结构骨架、O10 专属字段按手参数化](0019-diagnostics-skeleton-fixed-fields-parameterized-per-hand.md)：逐侧/事件驱动/只读骨架跨手固定，残差、错误位等字段维度与语义按手声明。
- [Launchpad 方块同构替换、内容数据驱动](0020-launchpad-blocks-isomorphic-replacement-data-driven.md)：方块与节点一一对应不变，provider 命名、关节曲线与录制清单由 per-hand 编排配置驱动。
- [扭转残差精修叠加在逐指 IK 基线之上](0021-twist-refinement-layered-on-baseline.md)：只改写 6 个 tripod 主动关节，基线历史与自由空间语义不变，精修失败回退基线。
- [扭转运行时使用解析梯度，禁止数值差分](0022-twist-runtime-analytic-gradient.md)：运行时固定迭代投影梯度，中心差分只用于离线测试解析梯度。
- [扭转诊断使用独立 topic 与独立录制边界](0023-twist-diagnostics-independent-topic-and-recording.md)：`TwistState` 与 `runs/twist-diag/` 独立于采数据 MCAP；反馈只读且不参与控制。
