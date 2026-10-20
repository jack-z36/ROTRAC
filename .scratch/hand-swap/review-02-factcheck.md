# review-02 事实核查报告：hand-swap spec（NaN / 22 DoF / Rokoko 协议断言）

> 核查对象：`.scratch/hand-swap/spec.md`（版本 1.0, Draft）
> 核查环境：ROS 2 Jazzy / 默认 RMW = Fast DDS (rmw_fastrtps) / Python 3.12
> 核查日期：2026-10-15
> 结论分级：事实成立 / 有条件成立 / 无法核实 / 断言错误
> 说明：本次核查的 WebSearch 后端配额耗尽（返回非真实检索结果，已弃用），全部结论基于 WebFetch 直接抓取的一手来源。

---

## 核查表

| # | 文档断言 | 结论 | 证据与来源 URL |
|---|---------|------|---------------|
| 1a | NaN 填入 `sensor_msgs/JointState.position`（float64[]）后，经 Fast DDS 序列化/反序列化可无损往返 | **事实成立** | eProsima Fast-CDR（ROS 2 Jazzy 的 CDR 实现）源码：`serialize(double)` / `deserialize(double&)` 均为 8 字节原样拷贝（直接内存读写或逐字节交换），全文件唯一值校验是 bool 的 0/1 检查，double 无任何 NaN/Inf 检查 → NaN 位模式逐比特保留。https://raw.githubusercontent.com/eProsima/Fast-CDR/v2.2.6/src/cpp/Cdr.cpp |
| 1b | `ros2 topic echo` 能显示 NaN | **事实成立** | `ros2topic/verb/echo.py`（Jazzy）：默认路径为 rclpy 反序列化后 `message_to_yaml()`，无任何 NaN 过滤；YAML 1.1 输出 NaN 为 `.nan`，`--csv`/raw 路径为 `nan`。仅用户自定义 `--filter` 表达式可能丢弃（用户逻辑，非内建）。https://raw.githubusercontent.com/ros2/ros2cli/jazzy/ros2topic/ros2topic/verb/echo.py |
| 1c | rosbag2 录制/回放 NaN 保真 | **事实成立** | rosbag2 官方 README：默认按中间件原生序列化格式存储（"If not specified, ros2 bag record -a will record all data in the middleware specific format"；"The default middleware for ROS 2 is DDS which has cdr as its default binary serialization format"），仅显式配置转换插件才重编码 → CDR 字节（含 NaN 位模式）原样落盘/回放。https://github.com/ros2/rosbag2 |
| 1d | NaN 传输存在已知坑（typesupport、C++ vs Python 差异） | **有条件成立** | 已检索范围内未发现任何 typesupport 层的 NaN 已知问题；C++/Python 在线级（CDR）无差异。**但 JSON 边界是实证的坑**：RFC 8259 §6 "Numeric values that cannot be represented in the grammar below (such as Infinity and NaN) are not permitted." → 任何 JSON 化环节（rosbridge、自写 JSON bridge、部分 Web 可视化）无法承载 NaN。spec 若只走 ROS 2 CDR 链路则无此问题。https://www.rfc-editor.org/rfc/rfc8259 |
| 2 | ROS 2 消息层（rosidl）不拒绝/不校验 NaN；发布含 NaN 的 `geometry_msgs/Pose` 无消息层运行时问题 | **事实成立** | ROS 2 Jazzy 官方接口概念文档：float64 映射 C++ double / Python float / DDS double；文档只描述"比 ROS 定义更宽松的宿主类型按范围/长度强制约束"（数组长度、有界 string），没有任何浮点数值运行时校验，无 NaN 拒绝逻辑。结合 1a 的 Fast-CDR 无值校验，发布含 NaN 的 Pose 在消息层合法。**注意**：下游消费者（tf2、RViz、IK 库）对 NaN 的行为不在本次核查范围，spec 需自行验证。https://docs.ros.org/en/jazzy/Concepts/Basic/About-Interfaces.html |
| 3a | Rokoko UDP 默认端口 14043 | **事实成立** | Rokoko 官方插件 README 两处佐证：Blender 插件 "Verify port settings: Default port is 14043"；Unity 插件 "Receive Port ... 14043 is by default"。https://github.com/Rokoko/rokoko-studio-live-blender ；https://github.com/Rokoko/rokoko-studio-live-unity |
| 3b | Rokoko 前向数据格式为 JSON v3 | **事实成立** | Rokoko 官方 Unity 插件 README FAQ 原文："Please ensure you are using JSON v3 as forward data format"。https://github.com/Rokoko/rokoko-studio-live-unity |
| 3c | 关键点命名 Hand / ThumbProximal / ThumbMedial / ThumbDistal / ThumbTip / Index{Proximal,Medial,Distal,Tip} / Middle·Ring·Little 同构，共 21 点 | **公开资料未覆盖，以本地实证为准** | 官方插件 README 均不含具体命名；官方支持中心（support.rokoko.com）对自动化抓取返回 403，无法核读 Studio Live 数据格式文章；Bing 多轮检索未见公开 schema。旁证：Unity README 确认 actor "Can all include body, face (52 blendshapes) and finger data"。本地实证存在且自洽：`src/rokoko_hand_receiver_node/rokoko_hand_receiver/core/decoder.py` 的 `_SEMANTIC_NODE_SUFFIXES` 严格校验 21 个后缀名（前缀 left/right）。 |
| 3d | LZ4 帧压缩 | **公开资料未覆盖，以本地实证为准** | Blender/Unity 官方 README 均未提及 LZ4；官方文档不可达（403）。本地 `decoder.py` 已按 LZ4 帧魔数 `04 22 4d 18` 实证处理，属代码级事实而非公开文档级事实。 |
| 4 | "22 DoF 标准规范"来自 Sharpa Wave（团队规范引用） | **事实成立（有重要限定）** | Sharpa Wave 是公开可查的真实产品：官网规格页明确 "a human-scale, five-finger dexterous hand with 22 active DoF"、"Active Degrees of Freedom: 22"（配套 22 个自研执行器）；公司 Sharpa（禾赛科技三位创始人 2024 年底创立）。**限定**：公开页面只证实"22 主动 DoF"这一产品规格；spec 附录 A 的具体 22 关节命名/排序表（thumb_CMC_FE … pinky_DIP）在任何公开资料中查不到，该命名表应视为团队内部规范（受 Sharpa Wave 启发），不得表述为 Sharpa 官方公开标准。https://www.sharpa.com/pages/wave |
| 5 | ros2_control / ROS 2 生态存在"用 NaN 表示不可用关节"的先例 | **无法核实（已查官方源无先例，且有反向证据）** | ① `sensor_msgs/JointState.msg` 官方注释无任何 NaN 约定，官方惯例是："All arrays in this message should have the same size, or be empty. This is the only way to uniquely associate the joint name with the correct states." https://raw.githubusercontent.com/ros2/common_interfaces/jazzy/sensor_msgs/msg/JointState.msg ；② ros2_control 的 joint_state_broadcaster 文档：缺失接口时"print a warning about that, but work for other interfaces"（省略 + 告警，不用 NaN）https://control.ros.org/jazzy/doc/ros2_controllers/joint_state_broadcaster/doc/userdoc.html ；③ JointTrajectoryController 文档全文无 NaN，partial goals 用 `allow_partial_joints_goal` 参数而非 NaN https://control.ros.org/jazzy/doc/ros2_controllers/joint_trajectory_controller/doc/userdoc.html 。结论：在已核查的官方核心文档中**未找到支持该约定的先例**；亦不能排除生态中存在个别项目自用 NaN（如 hardware_interface 初始化值等说法，本轮预算内未能核实）。 |

---

## 需要修正的表述

1. **spec 附录 D / ADR-1**："符合团队架构规范（参考 Sharpa Wave 22 DoF 定义）" —— 22 主动 DoF 作为 Sharpa Wave 产品规格公开属实（https://www.sharpa.com/pages/wave ），但 22 关节命名表为团队内部定义，建议明确标注"命名与排序为本团队定义，Sharpa Wave 仅提供 22 DoF 数量参考"，避免被理解为 Sharpa 公开标准。
2. **spec C.2 / C.3**（NaN 标记缺失关键点 + 22 DoF NaN 填充）：消息层与 CDR/CDR 链路无障碍（断言 1、2 成立），可放心走 ROS 2 原生链路；但应补充一条已知边界：任何 JSON 化工具（rosbridge、Web 前端、某些录放/可视化桥）按 RFC 8259 无法承载 NaN，选型录放/可视化工具时需确认其走 CDR/MCAP 路径。
3. **生态惯例提示**（不构成对 spec 的架构要求，仅事实）："NaN 表示不可用关节"在 JointState 消息注释、joint_state_broadcaster、JTC 三处官方文档中均无先例；官方消息注释给出的可区分约定是"等长数组或空数组"。spec 采用 NaN 属自定约定，需在 spec 中声明并全链路自行保证 `std::isnan`/`np.isnan` 判定，不能引用"生态惯例"作依据。

## 核查方法与局限

- 来源优先级：官方源码（raw.githubusercontent）、官方文档（docs.ros.org / control.ros.org）、厂商官方仓库与官网（Rokoko GitHub、sharpa.com）、RFC。
- 局限：support.rokoko.com 全站 403（Zendesk 反爬），Studio Live 的完整 JSON schema、LZ4 压缩说明未能从公开渠道核读；ros2_control hardware_interface 层是否存在 NaN 初始化惯例未能核实。以上均已在对应条目标注。
- WebSearch 后端本轮配额耗尽，未采信任何搜索摘要式内容；全部判定基于可直接点击的一手 URL。
