# DexTwist 扭转功能层规格（第一版）

> `Status: ready-for-agent`
>
> 日期：2026-10-19
> 上游参考：`.scratch/twist-retargeting/research/核心参考论文.md`（工作树参考；稳定知识蒸馏在 `docs/扭转功能层算法与验收基线.md`）
> 现有算法基线：`docs/人手归一化与O10单指IK算法基线.md`
> 现有架构边界：`docs/系统架构与模块边界.md`
> 本规格只描述新增的扭转功能层；不改变自由空间逐指 IK、O10 控制节点安全语义和采数据 MCAP。

## Problem Statement

操作者已经可以用 Rokoko 手套驱动 OmniHand O10 完成自由空间的手指动作，但接触丰富的旋转操作仍然失败。典型场景是拧瓶盖、拧钥匙、拧螺栓：机器人指尖在物体表面切向滑动，螺旋轴漂移，三指捏合逐渐散开，物体没有被稳定地转起来。

根因是现有重定向只最小化指尖位置误差。人手和 O10 在指长、关节轴、关节限位和指尖几何上不一致；在自由空间里，指尖位置相似可以接受，但在接触旋转里，指尖位置相似不等于物体被正确转动。直接跟随人手姿势会把"绕轴旋转"变成"沿物体表面滑动"。

在本功能落地前的基线代码中，没有三指捏合检测，没有螺旋轴估计，没有累积转角，也没有面向扭转的功能目标。即使操作者做出了正确的拧动，系统也无法知道"现在是在拧"以及"已经拧了多少"。基线也没有可录制的扭转诊断，无法判断参数调整是在改善还是在转移误差，无法做回归，也无法按论文口径验收。

## Solution

在现有 `hand_retargeting` 中新增一个 **DexTwist 风格的扭转功能层**，叠加在现有逐指 IK 基线之上：

- 操作者用拇指、食指、中指形成持续的三指捏合时，系统自动进入扭转模式；张开后自动退出。
- 系统从人手三指几何估计螺旋轴和累积转角，并跨"松开再捏"保留累积转角。
- 机器人侧对 6 个 tripod 主动关节做有界残差精修，跟踪人手转角，同时保持三指 closure、轴方向和三指中心稳定。
- 精修结果有独立有效性门；失败时回退现有逐指 IK 的 baseline 命令。
- 自由空间行为完全不变；无名指和小指始终走 baseline。
- 不控制机械臂或腕部；不新增操作者控制；`clear_fault` 仍是唯一操作者控制操作。
- 新增独立的扭转诊断 topic 和独立诊断录制，不污染采数据 MCAP。
- 提供离线回放、指标计算和真机试点协议；第一版只验收"机器人转角 vs 人手意图"和轴偏差，物体实际转角明确标注未验证。

## User Stories

1. 作为操作者，我希望用拇指、食指、中指捏住物体时系统自动进入扭转模式，以便不需要额外按键或模式开关。
2. 作为操作者，我希望普通抓握、握拳和两指捏合不会触发扭转模式，以便自由空间动作不被改写。
3. 作为操作者，我希望系统从三指几何估计螺旋轴，以便机器人绕我意图的轴转动，而不是沿物体表面滑动。
4. 作为操作者，我希望系统累积我转过的角度，以便机器人跟踪我的拧动进度。
5. 作为操作者，我希望松开三指后再捏合时累积转角继续保留，以便完成超过手腕活动范围的多次拧动。
6. 作为操作者，我希望每次重新捏合只执行本次新增的转角，以便机器人不会把已经转过的角度再拧一遍。
7. 作为操作者，我希望张开三指时机器人立即回到普通五指跟随，以便释放物体并重新抓握。
8. 作为操作者，我希望扭转过程中三个指尖不散开、螺旋轴不漂移、三指中心不移动，以便物体被稳定转动。
9. 作为操作者，我希望精修失败时机器人退回普通逐指 IK 命令，而不是发出异常命令，以便操作安全。
10. 作为操作者，我希望扭转速度仍受 O10 控制节点现有硬限速约束，以便不会绕过已经验证的安全边界。
11. 作为操作者，我希望不新增任何模式开关，`clear_fault` 仍是唯一操作者控制操作，以便保持现有操作习惯。
12. 作为数据采集员，我希望启动整个重定向程序时自动开始扭转诊断录制，以便不遗漏试验数据。
13. 作为数据采集员，我希望扭转诊断录制与采数据的 MCAP 完全分开，以便数据集不被诊断数据污染。
14. 作为数据采集员，我希望录制包覆盖人手原始帧、扭转状态、软目标、最终命令、真实反馈和控制状态，以便事后分析完整链路。
15. 作为数据采集员，我希望录制包同时保存配置快照、git commit、topic 列表和说明文件，以便回归时确认数据对应的代码和参数。
16. 作为测试工程师，我希望从录制数据计算转角 RMSE、MAE、Pearson 相关性和轴偏差，以便按论文口径判断功能是否可用。
17. 作为测试工程师，我希望看到精修应用比例、回退比例和失败原因分布，以便判断扭转层是真的在起作用，还是一直在回退 baseline。
18. 作为测试工程师，我希望统计普通抓握和握拳等负样本中的门控误触发率，以便标定门控阈值。
19. 作为测试工程师，我希望把录制的 `raw_hand` 离线回放给重定向会话，以便不接硬件也能做回归。
20. 作为测试工程师，我希望纯核心单测覆盖门控、角度累积、目标函数、解析梯度和 trust region，以便快速定位数学错误。
21. 作为测试工程师，我希望解析梯度用离线中心差分独立对照，以便确认运行时不使用数值差分也正确。
22. 作为测试工程师，我希望真机试点先在左手、单个物体、少量试验上验证，以便降低试错成本和安全风险。
23. 作为重定向工程师，我希望看到四项目标值和总目标值，以便知道调权重时误差转移到了哪一项。
24. 作为重定向工程师，我希望看到门控孔径、伸展和连续帧计数，以便知道为什么没有进入或没有退出扭转模式。
25. 作为重定向工程师，我希望看到命令转角和反馈转角，以便区分算法目标、软目标和实际执行。
26. 作为重定向工程师，我希望看到轴偏差的命令值和反馈值，以便判断螺旋轴是否稳定。
27. 作为重定向工程师，我希望看到精修状态和失败原因，以便区分物体滑移、精修回退和门控误触发。
28. 作为重定向工程师，我希望不可用的诊断字段用可用位加 NaN 表达，而不是用 0 冒充，以便不把未知当成已知。
29. 作为重定向工程师，我希望精修结果走独立有效性门，而不是复用逐指残差门，以便功能修正不被指尖位置误差门误杀。
30. 作为重定向工程师，我希望 baseline 的最近有效目标、首次有效状态和 warm start 不被精修写入，以便自由空间语义完全不变。
31. 作为重定向工程师，我希望无名指和小指始终保持 baseline 输出，以便精修只影响三指捏合相关的关节。
32. 作为重定向工程师，我希望扭转期间忽略拇指固定值和增益，退出后恢复，以便 6 个 tripod 关节都能参与扭转，同时不永久改变已配置的拇指补偿。
33. 作为重定向工程师，我希望输入 stale 时重置扭转 episode 但保留累积转角，以便断流恢复后操作者的拧动意图仍然连续。
34. 作为重定向工程师，我希望左右手各自维护门控、参考、累积转角和精修历史，以便一侧失败不影响另一侧。
35. 作为重定向工程师，我希望扭转核心数学不依赖 ROS、Pinocchio 或 NLopt，以便换手重构时可以直接复用。
36. 作为安全评审者，我希望 O10 控制节点的最终硬限速不可被扭转层绕过，以便扭转不能突破现有安全边界。
37. 作为安全评审者，我希望 O10 反馈只用于诊断，不参与任何控制判定，以便控制安全仍由控制节点独立决定。
38. 作为安全评审者，我希望精修有每步上限、总 trust region 和轴偏差上限，以便异常候选被拒绝并回退 baseline。
39. 作为安全评审者，我希望模型资产或数值后端不可用时回退 baseline 并报告失败原因，以便不发出伪造的成功命令。
40. 作为未来维护者，我希望有 ADR 记录"残差精修叠加在 baseline 之上""运行时不使用数值差分""独立诊断 topic 与录制边界"三项决策，以便理解为什么这样分。
41. 作为未来维护者，我希望算法文档记录门控、角度测量、目标函数、有效性门和未标定项，以便新会话不必重读论文和全部代码。
42. 作为未来维护者，我希望 STATUS 记录能力基线、在途工作和已知问题，以便知道第一版做到了哪里。
43. 作为评审者，我希望"物体实际转角未测"这一限制被明确写出，以便不把"机器人转角跟上了"说成"物体拧成功了"。
44. 作为评审者，我希望所有未标定值都显式配置并标注未标定，以便不把试点初值伪装成安全默认值。
45. 作为评审者，我希望中文路径导致的 rosidl 构建门先修复并自检全绿，以便集成测试和消息生成可信。
46. 作为未来换手实施者，我希望 tripod 关节索引、tip frame 和指链长度通过参数注入，以便换手时不需要改扭转核心数学。

## Implementation Decisions

### 1. 范围与数据流

- 扭转层是 **叠加层**，不是替代层。自由空间仍走现有五根手指各自的位置 IK。
- 只在门控激活时改写 6 个 tripod 主动关节；其他关节和非激活帧完全走现有路径。
- 不控制机械臂或腕部；手固定或由外部系统保持位姿。
- 不新增操作者控制；`clear_fault` 仍是唯一操作者控制操作。
- 构建通过后扭转层默认开启；tripod 门控是唯一运行时条件。

数据流：

```text
Rokoko raw_hand
  -> 归一化与人体掌坐标
  -> baseline 五指 IK
  -> tripod 门控与参考锁存
  -> 6 个 tripod 关节残差精修
  -> 10 维软目标
  -> 现有低通滤波
  -> /o10_control/{side}/command
  -> O10 控制节点硬限速
  -> /o10/{side}/joint_cmd
  -> 手
```

- 门控在 baseline IK 之前更新；机器人参考在激活后的第一帧 baseline 可用时锁存。
- 精修位于 baseline 提交之后、低通滤波之前。
- 精修失败时本帧发布 baseline 命令，并通过诊断报告失败原因。
- 低通滤波对最终命令滤波；退出扭转后，滤波状态从最后一帧精修命令平滑收敛到 baseline。
- O10 控制节点的硬限速和运动许可逻辑保持不变，扭转层不能绕过。

### 2. tripod 关节与初值

精修变量固定为 6 个主动关节：

```text
thumb_roll, thumb_abad, thumb_mcp, index_abad, index_pip, middle_pip
```

- 索引来自 O10 主动关节契约的固定顺序。
- 无名指和小指不在精修变量内，保持 baseline。
- 每帧从本帧 baseline IK 结果初始化，不使用上一帧精修结果作为 warm start。
- 上下界来自 `omnihand_o10_contracts.JOINT_LIMITS`。
- 每帧候选还必须满足以 baseline 为中心的 trust region。

### 3. tripod 门控

- 三指：拇指、食指、中指指尖，表达在人体解剖学手掌坐标系。
- 尺度：三指运行期冻结指链长度的平均值。
- 孔径：三个指尖两两距离的最大值除以尺度。
- 伸展：三指中心到掌心原点的距离除以尺度。
- 进入：`aperture < gate_aperture_on` 且 `extension > gate_extension_min`，连续 `gate_on_frames` 帧。
- 退出：`aperture > gate_aperture_off` 或 `extension < gate_extension_min`，连续 `gate_off_frames` 帧。
- `gate_aperture_off > gate_aperture_on`，形成迟滞；配置层强制该不变量。
- 当前帧掌坐标无效或三指任一目标无效时，门控计数和状态都不更新，保持上一状态。
- 门控是逐侧状态；左右手互不影响。
- 门控不引入新的 Service、按键或模式开关。

### 4. 人手意图

- 螺旋轴：`unit((p_index - p_thumb) x (p_middle - p_thumb))`，符号对齐人体掌系 `+Z`。
- 激活时锁存轴 `a_task`，并锁存两条平面内单位向量：拇指→食指、拇指→中指在垂直于 `a_task` 平面上的投影。
- 每帧增量：两条平面内向量绕 `a_task` 的有符号转角取平均。
- 增量裁剪到 `±delta_theta_clip`，防止单帧跟踪跳变。
- `theta_task` 只在门控激活且几何有效时累加；跨 re-grasp 保留。
- 每次激活记录 `theta_base = theta_task`；本次目标增量 = `theta_task - theta_base`。
- 退出时只停止累加，不重置 `theta_task`。
- 轴或平面内投影退化时，本帧不累加、不精修，报告几何无效，并保持上一状态。
- 激活时检查人手轴映射到机器人掌系后与机器人参考轴同向；反向时不进入精修并报告失败。

### 5. 机器人参考与目标函数

- 机器人三指工具坐标系同样由三指尖构造，表达在规范 O10 掌系。
- 激活帧从 baseline 关节角锁存：
  - 参考轴 `a_r_ref`，符号对齐机器人掌系 `+Z`；
  - 参考 closure `e_r_ref`：三个指尖两两距离组成的 3 维向量；
  - 参考 centroid `c_r_ref`：三指中心；
  - 两条平面内参考向量。
- `theta_r(q)` 用与人体侧相同的两条平面内向量平均法，绕 `a_r_ref` 计算。
- 轴偏差为当前三指法向与 `a_r_ref` 的夹角；当前法向先对齐参考轴符号。
- 目标函数四项：

```text
J(q) = w_rot  * (theta_r(q) - (theta_task - theta_base))^2
     + w_conn * ||e_r(q) - e_r_ref||^2
     + w_axis * (1 - (a_r(q) . a_r_ref)^2)
     + w_pos  * ||c_r(q) - c_r_ref||^2
```

- closure 和 centroid 两个距离项用三指平均机器人指链长度归一化；`rot` 和 `axis` 本身无量纲。
- 四项权重由配置显式给出，不在代码中隐藏默认值。
- `e_r` 和 `c_r` 从候选关节经耦合和完整 FK 计算。

### 6. 优化器

- 变量：6 个 tripod 主动关节，带关节上下界。
- 初值：本帧 baseline IK 结果。
- 迭代次数固定为 `twist_iterations`（首版 5 次）。
- 方向：负梯度按无穷范数归一化。
- 步长：每次迭代每关节不超过 `step_max`，并裁剪到关节限位和 trust region。
- 回溯：候选目标值没有严格下降时，步长减半；最多两次减半。
- 提前停止：梯度无穷范数不超过 `gradient_tolerance`。
- 运行时禁止数值差分；梯度必须解析计算。
- 解析梯度来源：
  - Pinocchio 一次 FK 给出三个 tip 的位置和完整 3×16 平移雅可比；
  - 主动—被动耦合雅可比；
  - closure、centroid、法向、轴偏差和平均转角的链式法则。
- 解析梯度必须在离线测试中用中心差分独立验证；运行时不得调用差分。

### 7. 有效性、回退与安全

baseline 逐指 IK 继续走现有残差门，决定本帧能否进入扭转。精修结果使用独立门：

- 所有候选关节有限；
- 在关节限位内；
- 相对 baseline 的总变化在 trust region 内；
- 三指几何非退化：法向模长和平面内投影模长大于配置阈值；
- 当前三指法向与参考轴夹角不超过 `axis_deviation_limit_deg`；
- 目标函数有限。

任一门失败：

- 本帧发布 baseline 命令；
- `refinement_status = FALLBACK_BASELINE`；
- 写入失败原因（参考无效、人体几何无效、后端不可用、求解器异常、非有限、限位、trust region、几何退化、轴偏差超限、baseline 不完整等）。

安全边界：

- 扭转层不写 `q_last`、不写 `has_valid_ik`、不改变下一帧 warm start。
- 扭转层不改变逐指残差阈值和 baseline 的保持语义。
- 精修结果仍经过现有低通滤波和 O10 控制节点硬限速。
- O10 反馈只读，不参与控制；反馈不能改变命令。
- 模型资产或数值后端不可用时回退 baseline 并报告，不得伪造成功。

### 8. 与现有 pipeline 的关系

- baseline 五指 IK 的输入、目标生成、残差判定、历史保持、stale 恢复全部不变。
- 精修只替换 10 维组合中的 6 个 tripod 关节，其他 4 个关节保持 baseline。
- 门控激活时，跳过现有 `_apply_thumb_adjustments` 对 6 个 tripod 关节的处理：固定值和敏感度增益都不应用。
- 门控未激活时，现有拇指固定值/增益、低通和发布路径完全不变。
- 退出扭转后，低通输入切回经过拇指调整的 baseline；滤波状态从最后精修命令平滑收敛。
- baseline 不完整（任一手指没有提交值）时，即使门控激活也不精修；发布保持行为并报告 `baseline-incomplete`。
- stale 时重置门控、机器人参考和反馈诊断，但保留 `theta_task`；恢复后门控必须重新满足进入条件，`theta_base` 在下一次激活时重新记录。

### 9. 扭转诊断 wire

新增独立 topic：`/hand_retargeting/{side}/twist_state`，消息 `rokoko_omnihand_msgs/msg/TwistState`。

字段必须覆盖四类用途：

- 门控：`active`、`gate_aperture`、`gate_extension`、`gate_on_count`、`gate_off_count`。
- 角度：`theta_task`、`theta_base`、`theta_increment`、`theta_robot_cmd`、`theta_robot_fb`、`theta_robot_fb_available`。
- 轴偏差：`axis_deviation_cmd_deg`、`axis_deviation_fb_deg`、`axis_deviation_fb_available`。
- 目标：`objective_total`、`objective_rot`、`objective_conn`、`objective_axis`、`objective_pos`。
- 状态：`refinement_status`、`failure_reason`、`iterations`、`evaluations`、`solve_duration_sec`。
- 帧有效性：`valid`、`side`、`header`。

约定：

- 不可用字段用可用位 false + NaN，不用 0 冒充。
- `theta_robot_cmd` 从本帧发布命令对应的关节角计算；回退时等于 baseline 的测量值。
- `theta_robot_fb` 从最新 O10 反馈计算；反馈缺失、参考无效或几何无效时不可用。
- 诊断 topic 是只读观测，不参与控制。
- 不把逐指 baseline 残差复制到 `TwistState`；它们仍在 `RetargetingState`。

### 10. 反馈订阅

- `hand_retargeting` 只读订阅 `/o10/{side}/joint_states`。
- 按 `ACTIVE_JOINT_NAMES` 重排，忽略缺名或非有限反馈。
- 只计算诊断用反馈转角和轴偏差，不参与门控、精修、回退或发布决策。
- 反馈未到时 `theta_robot_fb_available=false` 且角度为 NaN。
- 必须有一条测试证明：有无反馈时控制命令完全一致。

### 11. 录制

- 单独录制脚本，不复用采数据 MCAP。
- 使用 `ros2 bag record` 写 MCAP；由规范启动入口自动启动和停止。
- 输出目录：`runs/twist-diag/<timestamp>/`，其中包含 `bag/`、配置快照、git commit、topic 列表和 README。
- 录制主题：
  - `/hand_retargeting/{side}/twist_state`
  - `/rokoko/{side}/raw_hand`
  - `/hand_retargeting/{side}/state`
  - `/o10_control/{side}/command`
  - `/o10/{side}/joint_cmd`
  - `/o10/{side}/joint_states`
  - `/o10_control/{side}/state`
- best-effort 话题使用 QoS override 文件，避免漏录。
- 录制进程在业务节点之外，符合"业务节点不写 MCAP"的架构规则。
- 录制脚本必须支持 `--dry-run`，打印路径和命令但不启动录制。
- 录制不得影响控制链路频率；Ctrl-C 后 MCAP 必须正常关闭。
- 与采数据 MCAP 完全分开，不改变采集数据集的目录和元数据。

### 12. 配置

- `RetargetingConfig` 增加嵌套 `TwistConfig`；`TwistConfig` 所有字段都没有代码默认值，`RetargetingConfig.twist` 必填。
- `RetargetingConfig` 现有三个带默认值的拇指字段（`thumb_abad_sensitivity`、`thumb_roll_fixed_value`、`thumb_abad_fixed_value`）属于已记录的 A18 设计冲突，本 spec 不改变它们；A18 门禁的修正另行处理。
- 节点启动时声明全部 `twist_*` 参数；缺失即启动失败。
- 生产 YAML 和规范启动脚本提供首版未标定值。
- `twist=None` 只允许测试或纯诊断路径使用；生产节点总是构造 `TwistConfig`。
- 不增加 `twist_enabled` 开关；构建通过后默认开启，门控是唯一运行时条件。
- 首版参数值（全部标注未标定，只用于试点）：

| 参数 | 首版值 | 含义 |
| --- | ---: | --- |
| `twist_gate_aperture_on` | 0.45 | 归一化孔径进入阈值 |
| `twist_gate_aperture_off` | 0.70 | 归一化孔径退出阈值 |
| `twist_gate_extension_min` | 0.50 | 归一化伸展下限 |
| `twist_gate_on_frames` | 3 | 进入连续帧数 |
| `twist_gate_off_frames` | 3 | 退出连续帧数 |
| `twist_weight_rot` | 1.0 | 转角项权重 |
| `twist_weight_conn` | 1.0 | closure 项权重 |
| `twist_weight_axis` | 0.5 | 轴项权重 |
| `twist_weight_pos` | 0.5 | centroid 项权重 |
| `twist_iterations` | 5 | 每帧迭代次数 |
| `twist_step_max` | 0.02 rad | 单次迭代每关节步长上限 |
| `twist_trust_region` | 0.10 rad | 相对 baseline 的总变化上限 |
| `twist_delta_theta_clip` | 0.52 rad | 每帧人手转角增量上限 |
| `twist_gradient_tolerance` | 1e-3 | 提前停止阈值 |
| `twist_axis_epsilon` | 1e-6 | 法向模长下限 |
| `twist_projection_epsilon` | 1e-4 | 平面内投影模长下限 |
| `twist_axis_deviation_limit_deg` | 60.0 | 当前法向与参考轴夹角硬上限 |

### 13. 构建门

- 中文路径会导致 rosidl 接口生成失败，必须先恢复构建门。
- 使用 ASCII colcon build/install/log/test-result base；源仓库路径保持不变。
- 规范初始化脚本和规范启动脚本都必须 source 同一份 workspace 路径配置。
- 验收要求：初始化自检全绿，消息包可 import，`TwistState` 可生成。
- 在构建门未验证前，不得宣称 ROS 集成验收通过。

### 14. 架构与换手复用

- 扭转数学在 Core 层，只依赖 numpy 和本包纯类型；不导入 ROS、Pinocchio、NLopt。
- 运动学通过 Protocol 注入：三 tip 位置和完整平移雅可比。
- 耦合通过现有 `CouplingModel` 注入。
- Application 层负责每侧门控、参考、累积转角、精修调度、baseline 历史和回退。
- Adapter 层负责 Pinocchio 多 tip FK/雅可比和 NLopt 单指 IK。
- Node 是薄组合根：参数、topic、消息转换、只读反馈订阅。
- 扭转核心接受 tripod 关节索引、tip frame 名称和指链长度参数；未来换手时通过手型 profile 注入，不重写数学。
- 不新增业务包；不把扭转逻辑放进 O10 控制节点或硬件 Provider。

### 15. 验收

- 第一版只验收机器人侧：
  - `theta_robot_fb - theta_increment` 的 RMSE、MAE、Pearson 相关性；
  - 轴偏差均值和最大值（反馈计算）。
- 物体实际转角不测，明确标注未验证；ArUco 和外部物体位姿后置。
- 同时报告：
  - 精修应用/回退比例；
  - 失败原因分布；
  - 负样本会话中的门控误触发率；
  - 自由空间回归对比。
- 真机试点：1 名操作者、左手、1 个物体、3 次扭转 × 10 秒；另录 2 分钟自由空间和普通抓握负样本。试点通过后扩到 3 种物体 × 5 次。
- 未标定参数不得写成已验证；没有真机数据不得宣称功能可用。

## Testing Decisions

### 测试原则

- 只测试外部可观察行为，不测试私有实现细节。
- 纯核心测试使用确定性的 fake coupling 和 fake tripod kinematics；不依赖 ROS、Pinocchio、NLopt。
- 会话测试通过 `RetargetingSession.process()` 的公开决策结果断言命令、状态、目标和回退；不直接断言私有状态。
- ROS 测试通过 topic 和消息断言，不直接调用节点回调。
- 解析梯度只在离线测试中用中心差分验证；运行时测试不得依赖差分。
- 不可用字段必须断言可用位 false 且值为 NaN。
- 真机试点不进入 CI；CI 只覆盖纯核心、会话、ROS graph 和录制 dry-run。

### Seams

按从高到低的顺序：

1. **纯核心 seam**：`TwistGate`、`HumanTwistTracker`、`build_tripod_reference`、`measure_tripod_state`、`evaluate_tripod_objective`、`refine_tripod`。注入 fake coupling 和 fake tripod kinematics。这是覆盖门控、角度、目标、梯度和 trust region 的最高纯 seam。
2. **会话 seam**：`RetargetingSession.process()`。注入 fake optimizer、fake coupling、fake kinematics，断言 `RetargetingDecision` 中的命令、`TwistSnapshot`、回退和 baseline 历史。
3. **ROS graph seam**：`HandRetargetingNode` + `TwistState` topic + `RetargetingState` topic。使用现有 ROS graph 测试模式，断言消息字段、枚举、NaN 和反馈缺失。
4. **回放 seam**：录制的 `raw_hand` 离线喂给会话，不启动 ROS；对比录制时的命令和 `twist_state`。
5. **分析 seam**：合成的短 MCAP/CSV 输入分析脚本，断言指标公式、回退比例和门控误触发率。

现有 seam 优先复用；只有录制和分析需要新增文件级 seam。若上述 seam 与实施预期不符，先修订本 spec，再写代码。

### 测试清单

纯核心：

- 门控：迟滞进入/退出、连续帧、无效帧不更新、伸展下限排除握拳。
- 人手意图：轴锁存、符号对齐、两条边平均、`theta_task` 累积、`delta_theta_clip`、跨 re-grasp 保留和 `theta_base`。
- 机器人参考：轴/closure/centroid/平面内向量锁存、符号对齐、几何退化失败。
- 目标函数：四项分别可观察；归一化后量纲一致；权重为 0 时对应项消失。
- 解析梯度：与中心差分对照，覆盖 6 个关节、左右手、多个可行域内部状态和接近边界但扰动后仍合法的状态。
- 优化器：每步不超过 `step_max`、总变化不超过 trust region、回溯、提前停止、失败回退。
- 有效性门：有限、限位、trust region、几何退化、轴偏差超限、baseline 不完整。

会话：

- 门控激活后精修应用；`theta_increment` 跟踪人手旋转。
- 退出后回到 baseline；低通从最后精修命令收敛。
- 精修失败回退 baseline，失败原因正确。
- 有/无反馈时控制命令完全一致。
- 反馈更新只影响 `theta_robot_fb` 和轴偏差反馈字段。
- stale 重置门控和参考但保留 `theta_task`；恢复后重新满足进入条件。
- 拇指固定值和增益在扭转期间跳过，退出后恢复。
- 无名指和小指保持 baseline。
- 左右手状态隔离。
- baseline 不完整时门控激活也不精修。
- 人手轴映射到机器人掌系后与机器人参考轴反向时，不精修并报告失败。

ROS wire：

- `TwistState` 在每帧 raw hand 和 stale 时发布。
- `active`、`refinement_status`、`failure_reason` 枚举映射正确。
- 反馈缺失时 `theta_robot_fb_available=false` 且角度 NaN。
- 反馈只读订阅不改变命令。
- 启动参数缺失时节点启动失败。

录制与分析：

- `--dry-run` 打印完整命令和路径，不启动录制。
- 自动启动/停止；Ctrl-C 后 MCAP 可读；主题齐全。
- 合成 MCAP/CSV 上 RMSE、MAE、Pearson 和轴偏差公式正确。
- 回放同一段 `raw_hand` 的命令与录制结果在容差内一致。
- 负样本会话的门控误触发率可计算。

系统测试：

- 更新 system test 参数覆盖，加入全部 `twist_*` 参数，保证节点可启动。
- 更新 A18 参数门禁，覆盖 `TwistConfig` 和 `RetargetingConfig` 的所有必填字段。
- 现有自由空间回归测试保持通过。

### 先例

- 纯核心与 fake 运动学：现有单指 IK 测试的 fake coupling/kinematics 模式。
- ROS graph 测试：现有 `RetargetingState` 话题测试的 publisher/observer/executor 模式。
- 真实数据回归：现有真实 `RawHandFrame` 保存副本回归测试。
- 录制 dry-run：现有诊断录制脚本的 `--dry-run` 模式。
- 离线分析：现有 `ik_failure_diagnose` 的诊断脚本模式。

### 测试缺口

- 没有物体位姿测量，无法测物体实际转角和滑移。
- 没有真机 CI；真机试点必须人工执行并记录。
- 解析梯度测试目前只覆盖有限状态；需要扩到左右手、多个状态和边界附近。
- 当前 system test 参数覆盖尚未加入 `twist_*`，实施时必须补上。
- 当前工作树未验证构建门全绿；验收前必须运行初始化自检并记录输出。
- 根目录 `核心参考论文.md` 散文件已按票 07 移入 `.scratch/twist-retargeting/research/`（外部文献不复制进稳定知识层）；`scripts/doc_gate.sh` 的既有 error 随之清零，文档门禁结果记录在票 07。

## Out of Scope

- 机械臂或腕部控制；论文 Eq.(4) 的 `T_cmd` 不在本版实现。
- 物体位姿、ArUco、相机标定、滑移测量和接触力测量。
- 两指、四指、柱面抓握、强力抓握和工具专用抓握。
- 学习式/数据驱动重定向、DexMachina 类功能策略。
- 修改 O10 控制节点的硬限速、运动许可、故障语义或安全门。
- 把扭转诊断写入采数据 MCAP 或改变采集数据集格式。
- 第一版右手真机；先只采左手。
- 标定值的最终确定和真机验收结论；本 spec 只给未标定试点初值。
- 换手架构的完整重构；本 spec 只要求扭转核心与手型解耦，便于后续复用。
- 新增操作者控制、Service、按键或 Launchpad 开关。
- 触觉数据进入扭转控制或验收；触觉仍保持只读可选能力。

## Further Notes

### 当前工作树状态

以 2026-10-19 实施完成后的工作树为准：

- 纯核心 `core/twist.py`、`TwistConfig`、`TwistSnapshot`、session 集成、`TwistState.msg`、节点发布和只读反馈订阅已经落地。
- `test_twist_core.py`、`test_twist_session.py`、`test_twist_node.py`、`test_twist_analysis.py`、`test_twist_replay.py` 覆盖门控、累积、四项目标、左右手中心差分对照、trust region/回溯/提前停止、会话激活/退出、拇指跳过/恢复、无名指小指基线、baseline 历史、反馈隔离、stale、wire 字段与 NaN、MCAP 读取和回放比较。
- 激活时人手轴映射到机器人掌系后与机器人参考轴同向的检查已实现：反向或正交时 `axis-mismatch` 回退，不翻转累积角；真实左右手资产点积约 0.99。
- 中文路径构建门候选 A 已落地并跑过全量初始化；构建、消息生成和扭转相关测试通过，`test_t10_faults` 的 5 项既有故障注入失败单独运行同样失败，与本功能无关。
- 录制脚本 `scripts/record_twist_diagnosis.sh`、离线分析 `scripts/analyze_twist_diagnosis.py`、回放 `scripts/replay_twist_diagnosis.py`、ADR-0021/0022/0023 和算法文档已落地。
- system test 参数覆盖已加入全部 `twist_*`；规范启动入口自动启停独立扭转诊断录制。
- 真机试点（票 06）未执行：没有真机数据，不得宣称功能可用或物体级成功。

### 与论文的差异

以下差异是有意为之，不是遗漏：

- 不控制机械臂；扭转只在掌心坐标系内完成。
- 人手和机器人转角用两条平面内向量的平均有符号角，而不是完整工具坐标系的 log map；在每帧小角度下等价，且更抗单指噪声。
- 运行时用解析梯度和固定迭代次数，而不是论文的中心差分梯度；保留"每帧轻量迭代"的结构，避免运行时差分。
- 目标函数距离项按机器人指链长度归一化；论文未规定归一化，本版选择无量纲化以便调参和换手。
- re-grasp 时使用 `theta_task - theta_base` 作为本次目标，避免机器人重复已完成的转角；论文没有明确这一点。
- 反馈转角只用于诊断；控制仍基于命令和 baseline，不闭环到硬件反馈。

### 已知限制

- O10 tripod 只有 6 个主动关节，扭转能力受机械结构限制；精修可能频繁碰限位。
- 物体实际转角、滑移和接触力不可测；第一版只能验收机器人转角 vs 人手意图和轴偏差。
- 四个权重、门控阈值、步长、trust region、`delta_theta_clip` 都未标定；首版值只用于试点。
- 扭转期间忽略拇指固定值和增益；如果操作者依赖这些补偿，扭转期间的手型会不同，退出后恢复。
- 扭转层构建通过后默认开启；门控误触发会直接改写命令，试点必须在安全台架上进行。
- 真机第一版只采左手。
- 中文路径构建门必须先恢复；构建门未绿时不得宣称集成验收通过。

### 文档蒸馏

实施完成后，关闭票据前必须完成：

- 新增 ADR：残差精修叠加在 baseline 之上；运行时不使用数值差分；独立扭转诊断 topic 与录制边界。
- 新增或更新算法文档：门控、角度测量、目标函数、有效性门、未标定项和与论文差异。
- 更新接口语义文档：登记 `TwistState` 的 topic、字段、枚举和 NaN 约定。
- 更新 `STATUS.md`：能力基线、在途工作、已知问题（物体转角未测、参数未标定、O10 6 关节限制、左手试点）。
- 运行文档门禁并记录结果；error 必须清零。
- 新增术语（三指捏合、螺旋轴、累积转角、本次目标增量、扭转残差精修）在进入稳定知识前，先判断是否应登记到 `CONTEXT.md`，避免在多个文档里形成第二份定义。
