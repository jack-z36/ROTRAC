# ROTRAC 灵巧手遥操作系统架构文档

> **版本**: 1.1（Final）  
> **状态**: 已定稿（2026-10-19 HITL 四项裁定，见附录 E 定稿记录；对抗评审与事实核查见 `review-01-adversarial.md` / `review-02-factcheck.md`）  
> **最后更新**: 2026-10-19  
> **基线**: 仓库 ADR-0014/0015/0016/0017/0018/0019/0020（换手架构 D1–D7，2026-10-15 Accepted）；与 ADR 冲突处以 ADR 为准

---

## 执行摘要

ROTRAC（Robotic Teleoperation and Retargeting Architecture for Control）是一个**手套无关 + 灵巧手无关**的遥操作重定向系统，基于 ROS 2 构建。系统采用分层架构 + 双重标准化接口，实现了：

1. ✅ **手套层标准化**（公司 21 关键点规范）
   - 当前：Rokoko 手套
   - 未来：可换 Xsens、Manus VR 等任意动捕手套
   
2. ✅ **灵巧手层标准化**（22 DoF 标准接口）
   - 当前：OmniHand O10（10 主动关节）
   - 未来：可换 Linker L20（22 主动关节）或其他灵巧手

3. ✅ **控制层完全抽象**（不感知具体手套或灵巧手型号）

**核心设计原则**：
- 双重分层隔离（手套 → 重定向 → 标准适配 → 控制 → 硬件）
- 配置驱动（所有静态参数在 YAML 配置中）
- 接口标准化（手套层 21 关键点，灵巧手层 22 DoF）

---

## 目录

1. [系统概览](#1-系统概览)
2. [ROS 2 数据流架构](#2-ros-2-数据流架构)
3. [核心抽象层](#3-核心抽象层)
4. [架构扩展能力验证](#4-架构扩展能力验证)
5. [测试策略](#5-测试策略)
6. [架构决策记录](#6-架构决策记录)

---

## 1. 系统概览

### 1.1 问题域

**输入**：手套采集的人手 21 关键点（位置 + 姿态）  
**输出**：灵巧手的关节角度命令（符合物理限制和安全约束）  
**挑战**：
- **手套多样性**：不同品牌手套有不同的关键点命名和数据格式（Rokoko、Xsens、Manus VR 等）
- **人手与灵巧手的运动学差异**：DoF 不匹配、耦合关节、方向映射
- **灵巧手硬件多样性**：不同型号的关节数量、限位、通信协议差异（O10 10维、L20 22维等）
- **团队规范统一**：需要符合 22 DoF 标准规范（录制/回放/可视化统一）

**两个抽象维度**：
1. **手套抽象**：统一不同动捕手套的输出格式 → 公司 21 关键点标准
2. **灵巧手抽象**：统一不同机器人手的控制接口 → 团队 22 DoF 标准

### 1.2 解决方案

```
┌────────────────────────────────────────────────────────────┐
│  分层架构（灵巧手无关 + 手套无关）                            │
├────────────────────────────────────────────────────────────┤
│  层 1: 手套采集（标准化 21 关键点）                          │
│    • 手套 receiver → 公司标准 21 关键点                     │
│    • 当前：Rokoko，未来可换 Xsens/Manus 等                 │
│    • 稳定性：换手套或换灵巧手都不影响                        │
├────────────────────────────────────────────────────────────┤
│  层 2: 重定向计算（手侧适配）                                │
│    • 人体侧管线：掌坐标、链长估计、归一化                    │
│    • 机器人侧 IK：五指并行求解                              │
│    • 输出：手的原生维度（O10=10维, L20=22维）               │
├────────────────────────────────────────────────────────────┤
│  层 2.5: 22 DoF 标准适配（独立 Node，转换唯一 owner）        │
│    • 目标上行: 原生维度 → /observation 22 DoF 目标面         │
│    • 命令下行: 22 DoF 最终命令面 → 原生 control_command      │
│    • 反馈上行: 原生反馈 → 22 DoF 反馈面                      │
│    • 解耦：重定向层与控制层互不感知对方的维度                │
├────────────────────────────────────────────────────────────┤
│  层 3: 控制安全（完全 22 DoF）                                │
│    • 输入: /observation 22 DoF 目标面（唯一命令入口）        │
│    • 安全复核：限位检查、有限性验证（仅激活索引）            │
│    • 硬限速器：时间额度封顶（反馈初始化，ADR-0003）          │
│    • 状态机：ENABLED/PAUSED/FAULT（迁移条件见 HS-6）         │
│    • 输出: 22 DoF 最终命令面（安全链必经，不可旁路）         │
├────────────────────────────────────────────────────────────┤
│  层 4: 硬件 Provider 节点（原生维度，SDK 唯一 owner）        │
│    • HandAdapter: per-hand SDK 抽象（原生维度进出）          │
│    • 命令入口: 原生 control_command（唯一合法来源，HS-4）    │
│    • 反馈出口: 原生 joint_states + 新鲜读取 Service          │
│    • 维度转换不在本层：全部集中在层 2.5 标准适配节点         │
└────────────────────────────────────────────────────────────┘
```

---

## 2. ROS 2 数据流架构

### 2.1 完整数据流（ASCII 图）

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           ROTRAC ROS 2 数据流架构                              │
└──────────────────────────────────────────────────────────────────────────────┘


════════════════════════════════════════════════════════════════════════════════
  层 1: 手套数据采集层（手套无关接口）
════════════════════════════════════════════════════════════════════════════════

     ┌───────────────────────────────────────────────────────┐
     │  手套硬件（可替换）                                    │
     │  当前: Rokoko (UDP 14043)                             │
     │  未来: Xsens / Manus VR / 其他动捕手套                │
     └─────────┬─────────────────────────────────────────────┘
               │ 手套原生格式（Rokoko JSON v3 / Xsens 等）
               ▼
     ┌─────────────────────────────────┐
     │  Node: glove_receiver           │
     │  当前实现:                       │
     │    rokoko_hand_receiver_node    │
     │  未来可扩展:                     │
     │    xsens_hand_receiver_node     │
     │                                 │
     │  职责:                          │
     │  • 接收手套原生数据              │
     │  • 映射到公司标准 21 关键点      │
     │  • 发布标准格式                 │
     └───────────┬─────────┬───────────┘
                 │         │
          publishes       publishes
                 │         │
                 ▼         ▼
     ┌─────────────────────┐   ┌─────────────────────┐
     │ Topic:              │   │ Topic:              │
     │ /mocap/             │   │ /mocap/             │
     │ left_hand/pose      │   │ right_hand/pose     │
     │                     │   │                     │
     │ Type:               │   │ Type:               │
     │ StandardHand        │   │ StandardHand        │
     │ Keypoints           │   │ Keypoints           │
     │                     │   │                     │
     │ 数据:               │   │ 数据:               │
     │ • names[21]:        │   │ • names[21]:        │
     │   公司标准命名       │   │   公司标准命名       │
     │ • poses[21]:        │   │ • poses[21]:        │
     │   位置+姿态          │   │   位置+姿态          │
     │                     │   │                     │
     │ 频率: 100Hz         │   │ 频率: 100Hz         │
     │                     │   │                     │
     │ ⚠️  手套无关标准    │   │ ⚠️  手套无关标准    │
     └─────────────────────┘   └─────────────────────┘


════════════════════════════════════════════════════════════════════════════════
  层 2: 重定向计算层（输出原生维度）
════════════════════════════════════════════════════════════════════════════════

                 │         │
          subscribes     subscribes
                 │         │
                 ▼         ▼
     ┌────────────────────────────────┐   ┌────────────────────────────────┐
     │  Node:                         │   │  Node:                         │
     │  hand_retargeting_left         │   │  hand_retargeting_right        │
     │  ──────────────────────────     │   │  ──────────────────────────     │
     │  Package:                      │   │  Package:                      │
     │    hand_retargeting_node       │   │    hand_retargeting_node       │
     │                                │   │                                │
     │  参数:                         │   │  参数:                         │
     │  • hand_config:                │   │  • hand_config:                │
     │    config/o10_hand.yaml        │   │    config/o10_hand.yaml        │
     │  • side: "left"                │   │  • side: "right"               │
     │                                │   │                                │
     │  依赖注入:                      │   │  依赖注入:                      │
     │  • HandProfile                 │   │  • HandProfile                 │
     │                                │   │                                │
     │  计算管线:                      │   │  计算管线:                      │
     │  1. 人体侧管线                  │   │  1. 人体侧管线                  │
     │     • 构建掌坐标系              │   │     • 构建掌坐标系              │
     │     • 估计链长                  │   │     • 估计链长                  │
     │     • 归一化                    │   │     • 归一化                    │
     │                                │   │                                │
     │  2. 机器人侧 IK                 │   │  2. 机器人侧 IK                 │
     │     • 五指并行 IK               │   │     • 五指并行 IK               │
     │     • 输出: 原生维度            │   │     • 输出: 原生维度            │
     │       (O10 = 10 维)            │   │       (O10 = 10 维)            │
     │                                │   │                                │
     │  3. 滤波 & Stale 恢复           │   │  3. 滤波 & Stale 恢复           │
     │                                │   │                                │
     │  ⚠️  不做 22 DoF 映射          │   │  ⚠️  不做 22 DoF 映射          │
     └────────────┬───────────────────┘   └────────────┬───────────────────┘
                  │                                    │
           publishes                            publishes
                  │                                    │
                  ▼                                    ▼
     ┌──────────────────────┐             ┌──────────────────────┐
     │ Topic:               │             │ Topic:               │
     │ /o10/left_hand/      │             │ /o10/right_hand/     │
     │ native_command       │             │ native_command       │
     │                      │             │                      │
     │ Type: JointState     │             │ Type: JointState     │
     │                      │             │                      │
     │ 数据:                │             │ 数据:                │
     │ • name[10]: O10 关节名│             │ • name[10]: O10 关节名│
     │ • position[10]:      │             │ • position[10]:      │
     │   原生维度命令        │             │   原生维度命令        │
     │                      │             │                      │
     │ ⚠️  原生维度          │             │ ⚠️  原生维度          │
     │    (O10 = 10 维)     │             │    (O10 = 10 维)     │
     └──────────────────────┘             └──────────────────────┘


════════════════════════════════════════════════════════════════════════════════
  层 2.5: 22 DoF 标准适配层（独立 Node，维度转换唯一 owner）
  （左/右各一个实例，右侧对称，图中仅画左侧）
════════════════════════════════════════════════════════════════════════════════

                  │ (native_command, N 维)
                  ▼
     ┌────────────────────────────────────────────┐
     │  Node: hand_standard_adapter_left          │
     │  Package: hand_standard_adapter_node       │
     │  参数: hand_config / side                  │
     │                                            │
     │  转换器（经 HandProfile，本节点是全链路     │
     │  唯一的 22 DoF ↔ 原生转换点，HS-3）：       │
     │                                            │
     │  ① 目标上行: 订阅 native_command (N 维)    │
     │     → 发布 /observation 22 DoF 目标面      │
     │     (未激活槽填 NaN)                       │
     │                                            │
     │  ② 命令下行: 订阅 22 DoF 最终命令面        │
     │     → 发布原生 control_command (N 维)      │
     │     ⚠️ 输入是专用命令面，禁止订阅          │
     │        /observation 自身（自回环禁令）     │
     │                                            │
     │  ③ 反馈上行: 订阅原生 joint_states (N 维)  │
     │     → 发布 22 DoF 反馈面                   │
     │     (激活槽=真实反馈, 未激活=NaN)          │
     └──────────┬─────────────────────────────────┘
                │ publishes (①目标上行)
                ▼
     ┌─────────────────────────────────┐
     │ Topic: /observation/            │
     │   left_hand/joint_states        │
     │ Type: JointState (22 DoF)       │
     │                                 │
     │ 语义: 22 DoF 标准目标面         │
     │   （IK 目标流，非硬件反馈）     │
     │ • name[22]: 标准 22 DoF 名称    │
     │ • position[22]: 激活关节有值    │
     │   未激活 = NaN（结构性，按      │
     │   激活索引表判定，HS-5）        │
     │                                 │
     │ 唯一生产者: 本适配节点          │
     │ 消费者: 控制节点 / 录制 / 可视化│
     │ ⚠️ 团队规范 22 DoF 标准面       │
     └─────────────────────────────────┘


════════════════════════════════════════════════════════════════════════════════
  层 3: 控制安全层（完全 22 DoF 接口；左/右各一实例，图中仅画左侧）
════════════════════════════════════════════════════════════════════════════════

                │ (订阅 /observation 22 DoF 目标面——唯一命令入口)
                ▼
     ┌────────────────────────────────────────────┐
     │  Node: hand_control_left                   │
     │  Package: hand_control_node (通用包)        │
     │  参数: hand_config / side                  │
     │  依赖注入: HandProfile（激活索引/22D 限位/  │
     │  反馈转换 to_22dof；不注入 HandAdapter）    │
     │                                            │
     │  安全管线 (22 DoF):                         │
     │  1. 接收目标面命令（/observation）          │
     │  2. 安全复核（仅激活索引）                  │
     │     ✓ 有限性：激活槽非有限 → 整帧无效      │
     │       → 可恢复 PAUSED（HS-6，不部分更新）  │
     │     ✓ 限位: contracts 原生 per-side 限位    │
     │       经映射派生（HS-7，YAML 禁止自造）    │
     │  3. 状态机 ENABLED/PAUSED/FAULT            │
     │     （迁移条件与 ADR-0005 分类对齐，HS-6）  │
     │  4. 硬限速器（22 维，反馈初始化 ADR-0003；  │
     │     合格性只在激活索引集上判定，HS-8）      │
     │  5. 发布 22 DoF 最终命令                    │
     │                                            │
     │  ⚠️ 完全 22 DoF，不 import 原生关节名       │
     └────┬───────────────────────┬───────────────┘
          │ publishes             │ provides/publishes
          ▼                       ▼
     ┌──────────────────────┐   ┌───────────────────────────────┐
     │ Topic:               │   │ Service: /o10_control/left/   │
     │ /o10_control/left/   │   │   clear_fault (Trigger)       │
     │   final_command      │   │ （唯一操作者 Service；enable   │
     │ Type: JointState     │   │  SetBool 已随 ADR-0004 废弃    │
     │ (22 DoF 最终命令面)  │   │  移除，无门控直驱，HS-9）      │
     │ 消费者: 标准适配(②)  │   └───────────────────────────────┘
     │         + 录制       │   ┌───────────────────────────────┐
     └──────────────────────┘   │ Topic: /o10_control/left/     │
     ┌──────────────────────┐   │   state (ControlState)        │
     │ Topic:               │   │ （只读状态诊断）              │
     │ /o10_control/left/   │   └───────────────────────────────┘
     │   feedback           │
     │ Type: JointState     │
     │ (22 DoF 反馈面)      │
     │ 唯一生产者: 标准适配 │
     │   节点③（反馈上行）  │
     │ 消费者: 控制节点     │
     │   （限速器初始化）   │
     │   + 录制             │
     └──────────────────────┘


════════════════════════════════════════════════════════════════════════════════
  层 4: 硬件 Provider 节点（原生维度；SDK 唯一 owner）
════════════════════════════════════════════════════════════════════════════════

   标准适配节点② 命令下行:                     标准适配节点③ 反馈上行:
   订阅 /o10_control/left/final_command    订阅 /o10/left_hand/joint_states
        │ from_22dof → 发布原生               │ to_22dof → 发布
        ▼ control_command                     ▼ /o10_control/left/feedback
     ┌──────────────────────────────────────────────┐
     │  Node: hardware_provider_left                │
     │  （现状架构延续：独立 ROS 节点，              │
     │    ADR-0008 事件-效果边界）                  │
     │                                              │
     │  唯一合法命令来源: 原生 control_command      │
     │  （由标准适配节点②发布；任何其他发布者       │
     │    都是违规——安全链不可旁路，HS-4）          │
     │                                              │
     │  注入 HandAdapter（per-hand SDK 抽象，       │
     │  原生维度进出，ADR-0014）：                  │
     │  • send_native_command(N 维) → SDK 调用     │
     │  • read_native_feedback() → N 维反馈        │
     │  • 维度转换不在本层（层 2.5 已完成）         │
     │                                              │
     │  出口:                                       │
     │  • 原生 joint_states（连续反馈）             │
     │  • 新鲜读取 Service（ADR-0010，逐侧，        │
     │    无动作新读取；控制端注入 HandProfile      │
     │    完成 22 DoF 转换并拥有超时与复核）        │
     │  • 错误位 / 触觉（可选，ADR-0018/0019）      │
     └──────────────────┬───────────────────────────┘
                        │
                        ▼
     ┌─────────────────────────────┐
     │ 子类: AgilinkO10Backend     │
     │ （HandAdapter 实现）        │
     │ • SDK 初始化 / 发送 / 读取  │
     └──────────┬──────────────────┘
                │ Agilink SDK (HCAN)
                ▼
     ┌─────────────────────────────┐
     │ OmniHand O10 左手硬件       │
     │ 10 主动关节 + 6 被动关节    │
     └─────────────────────────────┘


════════════════════════════════════════════════════════════════════════════════
  数据维度变化总结（图中 /o10/ 前缀均为 /{hand_id}/ 的 O10 实例）
════════════════════════════════════════════════════════════════════════════════

  手套 UDP              →  21 关键点 (StandardHandKeypoints)
                            ↓
  重定向 IK             →  10 维原生 (O10, native_command)
                            ↓
  标准适配①目标上行     →  22 DoF 目标面 /observation (未激活 NaN)
                            ↓
  控制层（安全链）       →  22 DoF 最终命令面 {hand_id}_control/{side}/final_command
                            ↓
  标准适配②命令下行     →  10 维原生 control_command
                            ↓
  硬件 Provider/SDK     →  10 维
                            ↓
  硬件                  →  10 主动 + 6 被动
                            │
  原生反馈 joint_states  ↙ （反馈支路）
  标准适配③反馈上行     →  22 DoF 反馈面 {hand_id}_control/{side}/feedback
                            → 控制层限速初始化（ADR-0003）+ 录制


════════════════════════════════════════════════════════════════════════════════
```

### 2.2 Topic 契约总表

所有 JointState 面 QoS 统一 `reliable + KEEP_LAST(depth=10)`；`header.stamp` 全链路透传（重定向盖原始时间戳，标准适配与控制不重打，下游 stale 判定用）；频率跟随上游（设计值 100 Hz）。

| Topic | Type | 维度 | 生产者（唯一） | 消费者 | 说明 |
|-------|------|------|---------------|--------|------|
| `/mocap/{side}_hand/pose` | `teleoperation_interfaces/StandardHandKeypoints` | 21 关键点 | glove receiver | 重定向、录制 | 标准 21 关键点（附录 C；SI 米制） |
| `/{hand_id}/{side}_hand/native_command` | `JointState` | N | 重定向节点 | 标准适配① | IK 原生维度输出 |
| `/observation/{side}_hand/joint_states` | `JointState` | 22 | 标准适配① | 控制（命令入口）、录制、可视化 | 22 DoF **目标面**（IK 目标流，非硬件反馈） |
| `/{hand_id}_control/{side}/final_command` | `JointState` | 22 | 控制节点 | 标准适配②、录制 | 22 DoF **最终命令面**（安全链之后）。命名避开现行 `/o10_control/{side}/command`——那是重定向的 O10 软关节目标消息（10 维），迁移期不得同名义混载 |
| `/{hand_id}/{side}_hand/control_command` | `JointState` | N | 标准适配② | 硬件 Provider（唯一合法消费者） | 原生最终命令（平行族成员） |
| `/{hand_id}/{side}_hand/joint_states` | `JointState` | N | 硬件 Provider | 标准适配③、诊断 | 原生反馈（连续） |
| `/{hand_id}_control/{side}/feedback` | `JointState` | 22 | 标准适配③ | 控制（限速初始化）、录制 | 22 DoF **反馈面**（真实硬件状态） |
| `/{hand_id}_control/{side}/state` | `ControlState` | - | 控制节点 | 诊断 | 控制状态诊断（ADR-0019） |

生产者唯一性是硬约束：`/observation` 与 `command`/`feedback` 面各自只允许表列生产者，`ros2 topic pub` 等调试发布会被下游按普通数据处理——在 ENABLED 态即驱动真机（无门控直驱，ADR-0004 已废弃），真机调试必须经 Launchpad 编排或物理安全姿态。

### 2.3 Service 接口

| Service | Type | 说明 |
|---------|------|------|
| `/{hand_id}_control/{side}/clear_fault` | `std_srvs/Trigger` | 清除锁存故障（**唯一操作者 Service**） |
| `/{hand_id}/{side}_hand/read_active_joints`（名字按手可参数化） | per-hand srv | 新鲜读取（ADR-0010：逐侧、无动作新读取；控制端拥有超时与复核） |

**已删除**：`enable (SetBool)`。per-side 使能门已随 ADR-0004 废弃（`4fedfaa` 起无门控直驱，运动由新鲜目标驱动）；恢复使能门必须先修订 ADR，不得在实现中静默复活（HS-9）。

---

## 3. 核心抽象层

### 3.1 HandProfile（数据驱动配置）

**职责**：封装灵巧手的所有静态参数，运行时从 YAML 配置加载。

**接口**：
```python
class HandProfile(ABC):
    @property
    def hand_id(self) -> str:
        """手的唯一标识符（如 "o10"）"""

    def joint_contract(self, side: str) -> JointContract:
        """关节契约（原生维度）。O10 的唯一 owner 是 omnihand_o10_contracts
        代码包（A11/ADR-0016）；本方法只做转发，配置不得持有副本（HS-3）"""

    def geometry(self, side: str) -> HandGeometry:
        """几何参数（指根、链长、方向映射）；双侧必须齐备，缺侧加载期失败"""

    def to_22dof_standard(self, native_joints: ndarray, side: str) -> StandardJointState:
        """原生维度 → 22 DoF 标准。值原样搬运，无符号/偏移变换（HS-7）；
        未激活槽填 NaN（结构性，按激活索引表判定，不看值本身）"""

    def from_22dof_standard(self, standard_joints: ndarray, side: str) -> ndarray:
        """22 DoF 标准 → 原生维度。输出契约（HS-1，硬约束）：
        • 形状 = joint_contract(side) 的原生关节数（O10 = 10）
        • 顺序与原生 ACTIVE_JOINT_NAMES 位置对齐（SDK 假定一致）
        • 标准承接的关节取槽位值；无标准承接的原生关节按
          fixed_native_joints 配置固定值填充（O10：thumb_roll /
          thumb_abad——用户裁定：不映射进 22 DoF，固定值驱动方便遥操）
        • 每个原生关节必须有处置（标准槽承接或配置固定值），
          禁止悬空、禁止填 0 或静默截断；加载期校验"""

    def active_indices_in_22dof(self, side: str) -> list[int]:
        """激活的 22 DoF 索引列表——全系统激活集的唯一事实源（HS-2）：
        加载期从 mapping_to_22dof 派生并断言；测试与门禁的激活集
        一律取自本方法，禁止硬编码字面列表"""

    def limits_in_22dof(self, side: str) -> tuple[ndarray, ndarray]:
        """22 DoF 激活槽限位 (lower, upper)（HS-7）：由 contracts 原生
        per-side 限位经映射搬运派生；加载期按侧校验含 0、lower<=upper；
        配置禁止自造限位数值"""
```

**配置示例**（`config/o10_hand.yaml`）：
```yaml
hand_id: o10

# 原生关节事实（名称/顺序/per-side 限位）不在此文件——唯一 owner 是
# omnihand_o10_contracts 代码包（A11/ADR-0016）；加载期从包导入并与
# mapping + fixed_native_joints 做全覆盖校验：任何原生关节既无标准槽
# 承接又无固定值处置，即拒绝加载（HS-1）。

mapping_to_22dof:        # 标准 22 关节名 → O10 原生索引（null = O10 无此关节）
  thumb_CMC_FE: null     # ← thumb_roll 不映射：固定值驱动（见 fixed_native_joints）
  thumb_CMC_AA: null     # ← thumb_abad 不映射：同上（用户裁定，方便遥操）
  thumb_MCP_FE: 2        # ← thumb_mcp
  index_MCP_AA: 3        # ← index_abad（标准索引 6）
  index_PIP: 4           # ← index_pip（标准索引 7）
  middle_PIP: 5          # ← middle_pip（标准索引 11）
  ring_MCP_AA: 6         # ← ring_abad（标准索引 14）
  ring_PIP: 7            # ← ring_pip（标准索引 15）
  pinky_MCP_AA: 8        # ← pinky_abad（标准索引 19）
  pinky_PIP: 9           # ← pinky_pip（标准索引 20）
# 激活集 = {2,6,7,11,14,15,19,20}，共 8/22（与附录 B 一致，HS-2）

fixed_native_joints:     # 无标准承接的原生关节 → 固定值（HS-1，对齐 ADR-0017 逐指配置化；
  thumb_roll: 0.56       #   O10 现值经 RetargetingConfig.thumb_roll_fixed_value 语义承载，
  thumb_abad: -0.80      #   上例数值仅示意，实施时从现行 launch 参数迁移并按侧限位裁剪）

limits:
  derived_from_contracts: true   # 22D 激活槽限位由 contracts per-side 限位搬运派生
  # 禁止在此声明限位数值（HS-7；A28 门禁扫描范围含本文件）

geometry:               # 双侧必须齐备，缺侧加载期失败、不得回退另一侧（HS-10）
  left:
    palm_frame: L_palm
    # finger_roots / chain_lengths / direction_mapping 结构同 right，数值独立
  right:
    palm_frame: R_palm
    finger_roots: [[0.033, -0.011, 0.009], ...]  # 5×3
    chain_lengths: [0.087, 0.098, 0.103, 0.095, 0.082]
    direction_mapping: [[1,0,0], [0,0,-1], [0,1,0]]

model_assets:
  urdf:
    right: omnihand_o10_model/urdf/right_hand.urdf
  mjcf: omnihand_o10_model/mjcf/couplings.xml

hardware:
  backend_class: omnihand_o10_hardware_adapter.AgilinkO10Backend
  transport: hcan
  device_id: 1
```

**配置与 launch 的边界（HS-10）**：launch 只允许传 `hand_config` 路径与 `side` 两个参数，禁止覆盖 YAML 内任何参数（含安全相关阈值）；违反即 A28 门禁失败。

### 3.2 hand_standard_adapter（独立 ROS 节点）

**职责**：全链路**唯一**的 22 DoF ↔ 原生维度转换点（HS-3），承载三条通道。

**ROS 接口**：
```
① 目标上行: 订阅 /{hand_id}/{side}_hand/native_command (N 维)
            发布 /observation/{side}_hand/joint_states (22 DoF)
② 命令下行: 订阅 /{hand_id}_control/{side}/final_command (22 DoF)
            发布 /{hand_id}/{side}_hand/control_command (N 维)
③ 反馈上行: 订阅 /{hand_id}/{side}_hand/joint_states (N 维)
            发布 /{hand_id}_control/{side}/feedback (22 DoF)
```

**自回环禁令（HS-3）**：本节点不得订阅自己发布的任何 topic；`/observation` 只允许出现在通道①的**输出**侧——把通道②的输入接到 `/observation` 会形成自回环（评审 C4 的攻击路径，禁止）。

**实现**（骨架；`header.stamp` 全通道透传，不重打）：
```python
class HandStandardAdapterNode(Node):
    def __init__(self):
        self.hand_profile = ConfigDrivenHandProfile(config_path)
        self.active_idx = self.hand_profile.active_indices_in_22dof(self.side)

        # ① 目标上行
        self.sub_native = self.create_subscription(...)
        self.pub_standard = self.create_publisher(
            '/observation/%s_hand/joint_states' % self.side, ...)

        # ② 命令下行（输入是专用命令面，不是 /observation）
        self.sub_cmd = self.create_subscription(
            ..., '/%s_control/%s/final_command' % (self.hand_id, self.side), ...)
        self.pub_native_cmd = self.create_publisher(
            ..., '/%s/%s_hand/control_command' % (self.hand_id, self.side), ...)

        # ③ 反馈上行
        self.sub_feedback = self.create_subscription(...)
        self.pub_feedback = self.create_publisher(
            ..., '/%s_control/%s/feedback' % (self.hand_id, self.side), ...)

    def native_to_standard_callback(self, msg):
        """N 维 → 22 DoF（未激活槽填 NaN）"""
        standard = self.hand_profile.to_22dof_standard(
            np.array(msg.position), self.side)

    def standard_to_native_callback(self, msg):
        """22 DoF → N 维（输出与原生关节序位置对齐，HS-1）"""
        native = self.hand_profile.from_22dof_standard(
            np.array(msg.position), self.side)

    def feedback_to_standard_callback(self, msg):
        """N 维反馈 → 22 DoF 反馈面（激活槽 = 真实反馈）"""
        standard = self.hand_profile.to_22dof_standard(
            np.array(msg.position), self.side)
```

### 3.3 HandAdapter（Provider 端 per-hand SDK 抽象，原生维度）

**职责**：封装"一只手的硬件怎么通信"。公开接口为**原生维度**（HS-3 修订：原草案在 HandAdapter 内做 22 DoF 转换，会与标准适配节点形成并行的第二条转换路径，评审 H6 攻击下控制安全链可被整体旁路；现裁定维度转换唯一 owner = 标准适配节点 + HandProfile）。

**宿主**：硬件 Provider 节点（独立 ROS 节点，延续现状架构与 ADR-0008 事件-效果边界）；按 ADR-0014 由 support 包提供能力、业务节点注入。

**接口**：
```python
class HandAdapter(ABC):
    def __init__(self, hand_profile: HandProfile, side: str):
        self.hand_profile = hand_profile
        self.side = side

    # 公开接口（原生维度；本类不做 22 DoF 转换）

    def send_native_command(self, positions: ndarray) -> HardwareResponse:
        """发送原生维度命令（长度/顺序 = 该手原生契约）"""
        return self._send_native_command(positions)

    def read_native_feedback(self) -> HardwareResponse[dict]:
        """读取原生维度反馈"""
        return self._read_native_feedback()

    def query_errors(self) -> HardwareResponse[JointError]:
        """错误位查询（字段语义按手声明，ADR-0019）"""

    # 子类必须实现（SDK 绑定）

    @abstractmethod
    def _send_native_command(self, positions: ndarray) -> HardwareResponse:
        """子类实现：SDK 命令发送"""

    @abstractmethod
    def _read_native_feedback(self) -> HardwareResponse[dict]:
        """子类实现：SDK 反馈读取"""
```

**子类实现示例**（O10）：
```python
class AgilinkO10Backend(HandAdapter):
    def __init__(self, hand_profile, side, **hw_params):
        super().__init__(hand_profile, side)
        from omnihand import OmniHand2025   # Agilink SDK
        self.sdk_hand = OmniHand2025(...)

    def _send_native_command(self, positions: ndarray) -> HardwareResponse:
        """发送 10 维命令（ACTIVE_JOINT_NAMES 序，joints.py 契约）"""
        assert positions.shape == (ACTIVE_JOINT_COUNT,)  # 运行期防线（C1）
        self.sdk_hand.set_joint_positions(positions.tolist())
        return HardwareResponse(success=True)

    def _read_native_feedback(self) -> HardwareResponse[dict]:
        """从 O10 读取 10 维反馈"""
        positions = np.array(self.sdk_hand.get_joint_positions())
        return HardwareResponse(success=True, data={
            'positions': positions,
            'velocities': ...,
            'timestamp': time.time()
        })
```

---

## 4. 架构扩展能力验证

本章展示架构设计达成的目标：**换手套或换灵巧手时的代码改动范围**。以下为未来扩展的操作指南，当前实施范围仅限 Rokoko + O10。

---

## 4.1 换手套操作（当前未实施，架构已支持）

### 4.1.1 从 Rokoko 切换到 Xsens（示例）

**架构保证**：换手套时，下游 `hand_retargeting_node` 及之后的所有节点**零修改**。

**需要修改的范围**：

| 模块 | 是否修改 | 说明 |
|------|---------|------|
| `hand_retargeting_node` | ❌ 不改 | 只订阅标准 21 关键点 |
| `hand_standard_adapter_node` | ❌ 不改 | 不感知手套品牌 |
| `hand_control_node` | ❌ 不改 | 不感知手套品牌 |
| **新增 glove receiver** | ✅ **新增** | `xsens_hand_receiver_node` |
| **Launch 文件** | ✅ **修改** | 启动 Xsens receiver 代替 Rokoko |

**步骤 1：创建新 receiver package**
```bash
ros2 pkg create xsens_hand_receiver_node --dependencies rclpy teleoperation_interfaces
```

**步骤 2：实现 Xsens 解析器**
```python
# xsens_hand_receiver_node/xsens_receiver.py

class XsensReceiver(Node):
    def __init__(self):
        # 连接 Xsens 手套（TCP/UDP/其他协议）
        self.xsens_client = XsensClient.connect(...)
        
        # 发布标准格式
        self.pub_left = self.create_publisher(
            StandardHandKeypoints, '/mocap/left_hand/pose', 10
        )
    
    def parse_and_publish(self, xsens_data):
        msg = StandardHandKeypoints()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'xsens_world'
        
        # 映射 Xsens 关键点到公司标准
        msg.names = STANDARD_21_NAMES
        msg.poses = self._map_xsens_to_standard(xsens_data)
        
        self.pub_left.publish(msg)
```

**步骤 3：编写映射表**
```python
# Xsens 关键点名称可能与 Rokoko 不同
XSENS_TO_STANDARD_MAPPING = {
    'wrist': 'WRIST',
    'thumb_cmc': 'THUMB_CMC',
    # ... 根据 Xsens 文档定义
}
```

**步骤 4：更新 launch 文件**
```python
# launch/xsens_retargeting.launch.py

Node(
    package='xsens_hand_receiver_node',  # 换 receiver
    executable='xsens_receiver',
    # 其他节点不变
)
```

**验证**：
```bash
# 启动新 launch
ros2 launch xsens_retargeting.launch.py

# 检查标准 topic
ros2 topic echo /mocap/left_hand/pose
# 应该看到 StandardHandKeypoints 消息，names 为公司标准
```

### 4.1.2 Topic 变化对比（换手套）

| 项目 | Rokoko | Xsens | 是否变化 |
|------|--------|-------|---------|
| 标准输出 | `/mocap/*/pose` (StandardHandKeypoints) | `/mocap/*/pose` (StandardHandKeypoints) | ✅ 不变 |
| 重定向输入 | 订阅 `/mocap/*/pose` | 订阅 `/mocap/*/pose` | ✅ 不变 |
| 下游所有节点 | 不感知 Rokoko | 不感知 Xsens | ✅ 不变 |

---

## 4.2 换灵巧手操作（当前未实施，架构已支持）

### 4.2.1 从 O10 切换到 Linker L20（示例）

**架构保证**：换灵巧手时，`hand_control_node` 及之前的所有节点（包括手套层、重定向层）**代码零修改**。"零修改"的可操作定义（HS-11）：节点代码不得持有任何手专用知识——几何参数、关节契约、耦合表、限位、初始猜测等只允许经 HandProfile/配置注入；IK 求解框架本身手无关（O10 的 SLSQP + 耦合雅可比属于"注入的求解配置"，ADR-0001/0002 的资产以 per-hand 数据形态进入）。

**需要修改的范围**：

| 模块 | 是否修改 | 说明 |
|------|---------|------|
| `rokoko_hand_receiver_node` | ❌ 不改 | 手套层不感知灵巧手 |
| `hand_retargeting_node` | ❌ 代码不改 | 手专用知识只经 HandProfile/配置注入（HS-11） |
| `hand_standard_adapter_node` | ❌ 不改 | 只换配置 |
| `hand_control_node` | ❌ 不改 | 完全 22 DoF，不 import 原生关节名 |
| **配置文件** | ✅ **新增** | `config/linker_l20_hand.yaml`（含关节契约 owner 声明，见步骤 2） |
| **HandAdapter** | ✅ **新增** | `LinkerL20Backend`（Provider 端 SDK 子类） |
| **Launch 文件** | ✅ **修改** | 更新 `hand_config` 参数（只许传路径与 side，HS-10） |

**步骤 1：准备模型资产**
```bash
mkdir -p linker_l20_model/urdf
# 从 Linker 官方获取 URDF 文件
cp ~/linker_sdk/models/*.urdf linker_l20_model/urdf/
```

**步骤 2：编写配置文件**（`config/linker_l20_hand.yaml`）
```yaml
hand_id: linker_l20

# L20 是新手：关节契约 owner = 本配置（ADR-0016 允许 contracts 包或配置
# 二选一；一旦代码或第二处配置复制这些事实即违规，A11 逐手唯一 owner）
joints:
  names: [thumb_CMC_FE, thumb_CMC_AA, ..., pinky_DIP]  # 22 个
  limits:
    left: {lower: [...], upper: [...]}   # owner 在此，禁止他处复制
    right: {lower: [...], upper: [...]}

mapping_to_22dof:
  # L20 是 22 DoF 全激活，1:1 映射（原生名 = 标准名）
  thumb_CMC_FE: 0
  thumb_CMC_AA: 1
  thumb_MCP_FE: 2
  # ... 全部 22 个
  pinky_DIP: 21

geometry:
  right:
    palm_frame: l20_r_palm
    finger_roots: [[0.030, -0.020, 0.010], ...]
    chain_lengths: [0.095, 0.110, 0.115, 0.105, 0.090]
    direction_mapping: [[1,0,0], [0,0,-1], [0,1,0]]

model_assets:
  urdf:
    right: linker_l20_model/urdf/right_hand.urdf
  mjcf: null  # L20 无被动关节

hardware:
  backend_class: linker_l20_hardware_adapter.LinkerL20Backend
  transport: can
  can_interface: can0
  device_id: 1
```

**步骤 3：实现 HandAdapter**（`linker_l20_hardware_adapter/l20_backend.py`）
```python
class LinkerL20Backend(HandAdapter):
    def __init__(self, hand_profile, side, **hw_params):
        super().__init__(hand_profile, side)
        
        # 初始化 Linker SDK
        from linker_sdk import LinkerHand
        self.sdk_hand = LinkerHand.connect(...)
    
    def _send_native_command(self, positions: ndarray) -> HardwareResponse:
        """发送 22 维命令（L20 原生 = 22 维）"""
        self.sdk_hand.set_joint_positions(positions.tolist())
        return HardwareResponse(success=True)
    
    def _read_native_feedback(self) -> HardwareResponse[dict]:
        """读取 22 维反馈"""
        positions = np.array(self.sdk_hand.get_joint_positions())
        return HardwareResponse(success=True, data={
            'positions': positions,
            ...
        })
```

**步骤 4：更新 launch 文件**
```python
# launch/linker_l20_retargeting.launch.py

hand_config = 'config/linker_l20_hand.yaml'

# 节点配置不变，只改 hand_config 参数
Node(
    package='hand_retargeting_node',
    parameters=[{'hand_config': hand_config, 'side': 'right'}],
)
```

**步骤 5：测试**
```bash
# 运行测试
pytest src/linker_l20_hardware_adapter/test/

# 端到端测试
ros2 launch linker_l20_retargeting.launch.py
```

### 4.2.2 Topic 变化对比（换灵巧手）

| 项目 | O10 | Linker L20 | 是否变化 |
|------|-----|-----------|---------|
| 手套输入 | `/mocap/*/pose` (21) | `/mocap/*/pose` (21) | ✅ 不变 |
| 重定向输出 | `/o10/*/native_command` (10) | `/linker_l20/*/native_command` (22) | ⚠️ 变化 |
| 标准格式 | `/observation/*/joint_states` (22) | `/observation/*/joint_states` (22) | ✅ 不变 |
| 控制输入 | 22 DoF | 22 DoF | ✅ 不变 |

---

## 4.3 架构扩展能力总结

通过上述两个维度的扩展示例，验证了架构设计的核心目标：

**换手套时的改动范围**：
- ✅ 只需新增 glove receiver package
- ✅ 下游所有节点（重定向、标准适配、控制、硬件）零修改

**换灵巧手时的改动范围**：
- ✅ 只需新增配置文件 + HandAdapter 子类
- ✅ 上游所有节点（手套、重定向）零修改
- ✅ 控制层零修改

**当前实施状态**：
- 🔧 Rokoko 手套标准化：**待实施**（本次 Spec 范围）
- 📦 O10 灵巧手抽象：**已实施**（现有架构）
- 🔮 Xsens/L20 扩展：**未来计划**（架构已支持）

---

## 5. 测试策略

### 5.1 单元测试

**HandProfile 映射逻辑**
```python
def test_o10_to_22dof_mapping():
    profile = ConfigDrivenHandProfile("config/o10_hand.yaml")
    native_10d = np.array([0.5, -0.3, 0.2, ...])  # 10 维，ACTIVE_JOINT_NAMES 序

    standard = profile.to_22dof_standard(native_10d, "right")

    assert standard.positions.shape == (22,)
    assert standard.positions[2] == 0.2   # thumb_mcp → thumb_MCP_FE
    assert np.isnan(standard.positions[0])  # thumb_roll 不映射：结构性 NaN
    assert np.isnan(standard.positions[5])  # index_MCP_FE：O10 无此关节

def test_o10_from_22dof_roundtrip():
    profile = ConfigDrivenHandProfile("config/o10_hand.yaml")
    # 输出契约（HS-1）：形状=10、顺序=ACTIVE_JOINT_NAMES、与 SDK 对齐；
    # 8 个标准承接槽取槽位值，thumb_roll/thumb_abad 取配置固定值
    native = profile.from_22dof_standard(standard_22d, "right")
    assert native.shape == (10,)
    assert native[2] == standard_22d.positions[2]
    assert native[0] == profile.fixed_native_value("thumb_roll", "right")
```

**激活集唯一来源（HS-2，测试禁止硬编码字面列表）**
```python
def test_active_set_single_source():
    profile = ConfigDrivenHandProfile("config/o10_hand.yaml")
    active = profile.active_indices_in_22dof("right")
    assert len(active) == 8                     # 附录 B：8/22（thumb 两关节固定值驱动）
    assert set(active) == set(range(22)) - NAN_SLOTS  # 由 profile 派生
    # 加载期全覆盖断言：原生关节 0..9 每个要么有标准槽承接、要么有固定值
```

### 5.2 集成测试

**完整链路测试**
```python
def test_end_to_end_22dof_output():
    # 发布手套数据（标准消息，不是 PoseArray——类型不匹配会静默无连接）
    pub_mocap.publish(StandardHandKeypoints(...))  # 21 关键点

    # 等待处理
    time.sleep(0.5)

    # 订阅输出（/observation 目标面）
    msg = sub_observation.wait_for_message(timeout=5.0)

    # 验证 22 DoF 格式
    assert len(msg.name) == 22
    assert msg.name == list(STANDARD_22DOF_NAMES)
    assert len(msg.position) == 22

    # 验证激活槽有值、未激活槽为 NaN（激活集取自 profile，HS-2）
    profile = ConfigDrivenHandProfile("config/o10_hand.yaml")
    for idx in profile.active_indices_in_22dof("right"):
        assert not np.isnan(msg.position[idx])
    for idx in set(range(22)) - set(profile.active_indices_in_22dof("right")):
        assert np.isnan(msg.position[idx])
```

### 5.3 架构门禁测试

**A11：关节契约逐手唯一 owner（按 ADR-0016 重写）**
```python
def test_A11_joint_contract_per_hand_single_owner():
    # 每只手恰好一个 owner：contracts 包 或 配置，二选一
    # O10 = omnihand_o10_contracts 代码包（joints.py 是唯一事实源）
    # 扫描代码 + 所有 hand YAML：任一手的关节名/顺序/限位
    # 出现在两处即 fail（含 config/o10_hand.yaml 复制 joints 段的情况）
    owners = scan_joint_fact_owners(across="code+config")
    assert owners["o10"] == ["omnihand_o10_contracts"]
    assert all(len(v) == 1 for v in owners.values())
```

**A28：配置单一来源（扫描范围含 launch 与 YAML）**
```python
def test_A28_config_single_source():
    # 扫描代码、launch、YAML：
    # • 硬编码设备/安全参数（代码）
    # • launch 覆盖 hand_config/side 之外的参数（HS-10）
    # • YAML 自造限位数值、复制 contracts 关节事实（HS-7/HS-3）
    violations = scan_config_violations(across="code+launch+yaml")
    assert len(violations) == 0
```

**拓扑门禁：适配节点自回环（C4）**
```python
def test_adapter_no_self_subscription():
    # 标准适配节点发布的 topic 集合与其订阅的 topic 集合必须不相交；
    # 且 /observation 只允许出现在其发布侧
    pub, sub = adapter_node_io_topics()
    assert not (set(pub) & set(sub))
    assert "/observation/%s_hand/joint_states" % side in pub
    assert "/observation/%s_hand/joint_states" % side not in sub
```

---

## 6. 架构决策与仓库 ADR 对齐

本 spec 不自造 ADR 编号（原 ADR-1..5 与仓库 `docs/adr/` 0001–0020 撞号，评审 M15）。已由仓库 ADR 裁定的事项直接引用；本 spec 新增的局部裁定编号 **HS-n**（hand-swap ruling），定稿后如需升格为 ADR 另行开票。

### 6.1 继承的仓库 ADR（不重复正文）

| 仓库 ADR | 对本 spec 的约束 |
|---------|----------------|
| ADR-0003 | 硬限速器反馈初始化（层 3；"合格反馈"只在激活索引集上判定，HS-8） |
| ADR-0005 | 可恢复暂停 vs 锁存故障分类（HS-6 状态机迁移的依据） |
| ADR-0004（已废弃） | 无门控直驱：无 enable Service，运动由新鲜目标驱动（HS-9） |
| ADR-0008 | 控制↔硬件 Provider 事件-效果边界（层 4 独立 Provider 节点） |
| ADR-0010 | 逐侧新鲜读取 Service（层 4 出口；控制端拥有超时与复核） |
| ADR-0014 | HandProfile/HandAdapter 为 support 包能力、业务节点注入；标准适配节点是唯一入流新节点 |
| ADR-0015 | 平行 topic 族 + `/observation` 22 DoF 标准面；其 NaN 序列化风险已核实关闭（review-02 断言 1：Fast-CDR 位级保真） |
| ADR-0016 | 关节契约逐手唯一 owner（contracts 包或配置）（HS-3） |
| ADR-0017/0018/0019 | 拇指逐指调整可配置 / 触觉只读可选 / 诊断骨架固定字段参数化 |
| ADR-0020 | Launchpad 方块同构替换、内容数据驱动 |

### 6.2 本 spec 局部裁定（HS-n）

| 编号 | 裁定 | 来源发现 |
|------|------|---------|
| HS-1 | 原生关节全覆盖处置：每个原生关节要么有标准槽承接、要么有 `fixed_native_joints` 配置固定值，禁止悬空（O10：thumb_roll/thumb_abad 走固定值——**用户裁定 2026-10-19：不映射进 22 DoF、固定值驱动方便遥操**，激活 **8/22**）；`from_22dof_standard` 输出 = 原生维数、与原生关节序位置对齐；加载期全覆盖校验 | C1 |
| HS-2 | 激活集唯一事实源 = `HandProfile.active_indices_in_22dof()`；测试与门禁禁止硬编码字面列表 | C2 |
| HS-3 | 维度转换唯一 owner = 标准适配节点 + HandProfile（三条通道①②③）；HandAdapter 公开接口为原生维度；适配节点禁止订阅自身发布的任何 topic | C4/H6 |
| HS-4 | 命令链线性不可旁路：`/observation`（唯一生产者=通道①）→ 控制安全链 → `command` 面 → 通道② → `control_command` → Provider（唯一合法消费者） | H6 |
| HS-5 | NaN 语义三分：结构性未激活（按激活索引表判定）、瞬时缺失（手套层关键点）、无效帧（激活槽非有限）；激活槽非有限 → **整帧无效**，不部分更新 | H9/H11 |
| HS-6 | 状态机迁移对齐 ADR-0005：激活槽非有限/stale/IK 失败 → 可恢复 PAUSED（自动恢复）；硬件、通信、安全门异常 → 锁存 FAULT（clear_fault 唯一人工出口） | H9 |
| HS-7 | 标准面数值 = 原生值原样搬运，无符号/偏移变换（跨手符号统一为显式非目标，待团队规范 owner 裁定）；22D 激活槽限位由 contracts per-side 限位经映射派生，配置禁止自造 | H8 |
| HS-8 | 硬限速器：每条合法整帧目标至多一条受限命令；反馈初始化只在激活索引集上判定合格性 | H11 |
| HS-9 | 无 enable Service（对齐 ADR-0004 废除后语义）；操作者唯一 Service = clear_fault；恢复使能门必须先修订 ADR，不得实现中静默复活 | H10 |
| HS-10 | 配置边界：hand_config 双侧齐备、缺侧快速失败不回退；launch 只传 hand_config 路径与 side；A28 扫描 code+launch+YAML | M14 |
| HS-11 | "零修改"可操作定义：节点代码不持有手专用知识（几何/契约/耦合/限值/初值只经 HandProfile/配置注入） | M17 |

### 6.3 已废弃的本草案决策

- ~~原 ADR-3（HandAdapter 内部处理维度转换）~~：被 HS-3 取代——双转换路径使控制安全链可被旁路（评审 H6）。
- ~~原 ADR-4（所有参数含关节表从 YAML 加载）~~：被 ADR-0016 + HS-3 取代——O10 关节契约 owner 是 contracts 代码包。
- 原 ADR-1/2/5 的实质内容分别由仓库 ADR-0015（22 DoF 标准面）、ADR-0014 裁定 2（独立适配节点）、ADR-0015 裁定 1（平行族保留原生 topic）覆盖。

---

## 附录 A：22 DoF 标准定义

```python
STANDARD_22DOF_NAMES = (
    # 拇指 (5 DoF)
    "thumb_CMC_FE",    # 0: CMC flexion/extension
    "thumb_CMC_AA",    # 1: CMC abduction/adduction
    "thumb_MCP_FE",    # 2: MCP flexion/extension
    "thumb_MCP_AA",    # 3: MCP abduction/adduction
    "thumb_DIP",       # 4: DIP flexion/extension
    
    # 食指 (4 DoF)
    "index_MCP_FE",    # 5: MCP flexion/extension
    "index_MCP_AA",    # 6: MCP abduction/adduction
    "index_PIP",       # 7: PIP flexion/extension
    "index_DIP",       # 8: DIP flexion/extension
    
    # 中指 (4 DoF)
    "middle_MCP_FE",   # 9
    "middle_MCP_AA",   # 10
    "middle_PIP",      # 11
    "middle_DIP",      # 12
    
    # 无名指 (4 DoF)
    "ring_MCP_FE",     # 13
    "ring_MCP_AA",     # 14
    "ring_PIP",        # 15
    "ring_DIP",        # 16
    
    # 小指 (5 DoF)
    "pinky_CMC_FE",    # 17
    "pinky_MCP_FE",    # 18
    "pinky_MCP_AA",    # 19
    "pinky_PIP",       # 20
    "pinky_DIP",       # 21
)
```

**NaN 约定的边界（review-02 核实结论）**：

- 本 NaN 约定是**团队自定约定**，不是 ROS 生态惯例——`JointState` 官方注释给的惯例是"等长数组或空数组"，joint_state_broadcaster / JTC 官方文档均无 NaN 先例。全链路判定必须显式 `np.isnan` / `std::isnan`，不得引用"生态惯例"作依据。
- NaN 位模式经 Fast-CDR 序列化反序列化、rosbag2 录制回放（CDR/MCAP 路径）、`ros2 topic echo` 均**位级保真**（已核实；ADR-0015 的"早期原型验证"风险就此关闭）。
- **JSON 边界不能承载 NaN**（RFC 8259 禁止）：rosbridge、自写 JSON bridge、部分 Web 可视化无法传输 NaN——录放/可视化工具选型必须走 CDR/MCAP 路径。

## 附录 B：O10 的 22 DoF 映射

原生关节序的权威来源是 `omnihand_o10_contracts/joints.py`（A11/ADR-0016）；本表是它的映射投影，实施时以加载期派生值为准（HS-2：本表不是代码的依据，代码也不是本表的复制）。

| 标准索引 | 标准关节名 | O10 原生索引 | O10 关节名 | 映射值 |
|---------|-----------|-------------|-----------|-------|
| 0 | thumb_CMC_FE | - | - | NaN |
| 1 | thumb_CMC_AA | - | - | NaN |
| 2 | thumb_MCP_FE | 2 | thumb_mcp | ✓ |
| 3 | thumb_MCP_AA | - | - | NaN |
| 4 | thumb_DIP | - | - | NaN |
| 5 | index_MCP_FE | - | - | NaN |
| 6 | index_MCP_AA | 3 | index_abad | ✓ |
| 7 | index_PIP | 4 | index_pip | ✓ |
| 8 | index_DIP | - | - | NaN |
| 9 | middle_MCP_FE | - | - | NaN |
| 10 | middle_MCP_AA | - | - | NaN |
| 11 | middle_PIP | 5 | middle_pip | ✓ |
| 12 | middle_DIP | - | - | NaN |
| 13 | ring_MCP_FE | - | - | NaN |
| 14 | ring_MCP_AA | 6 | ring_abad | ✓ |
| 15 | ring_PIP | 7 | ring_pip | ✓ |
| 16 | ring_DIP | - | - | NaN |
| 17 | pinky_CMC_FE | - | - | NaN |
| 18 | pinky_MCP_FE | - | - | NaN |
| 19 | pinky_MCP_AA | 8 | pinky_abad | ✓ |
| 20 | pinky_PIP | 9 | pinky_pip | ✓ |
| 21 | pinky_DIP | - | - | NaN |

**激活关节数**：8 / 22。

**设计意图（用户裁定，2026-10-19 HITL）**：thumb_roll 与 thumb_abad **有意不映射**进 22 DoF 标准面——这两个关节以配置固定值驱动（`fixed_native_joints`，承载现行 `RetargetingConfig.thumb_*_fixed_value` 语义并按侧限位裁剪），方便遥操。标准面槽位 0/1 的 NaN 是结构性未激活（HS-5），不是缺陷。评审 C1/C2 修复后：`from_22dof_standard` 输出仍为 10 维（8 个标准承接值 + 2 个配置固定值）、与原生关节序位置对齐；原 spec 的"9/22"计数行与 §5.2 硬编码列表是笔误，已废除非事实源（HS-2）。

---

## 附录 C：手套层标准化规范

**设计状态**：已完成 Spec 锁定（权威文档：`docs/手套21关键点标准化规范.md`；本附录为摘要，两处冲突以该文档为准）

### C.1 公司 21 关键点标准

为实现手套无关的输入层，定义了公司统一的 21 关键点命名标准：

| 索引 | 标准名称 | 说明 |
|-----|---------|------|
| 0 | WRIST | 手腕 |
| 1-4 | THUMB_{CMC,MCP,IP,TIP} | 拇指 4 点 |
| 5-8 | INDEX_FINGER_{MCP,PIP,DIP,TIP} | 食指 4 点 |
| 9-12 | MIDDLE_FINGER_{MCP,PIP,DIP,TIP} | 中指 4 点 |
| 13-16 | RING_FINGER_{MCP,PIP,DIP,TIP} | 无名指 4 点 |
| 17-20 | PINKY_{MCP,PIP,DIP,TIP} | 小指 4 点 |

**关键点性质**：
- 空间位置点（position + orientation），不是关节角度
- 命名是规范约定，不强制精确解剖学定义
- 坐标系由手套透传，不做统一变换；"透传"只覆盖刚体变换——**尺度与单位不属于透传范围**：位置强制 SI 米制（非米制手套由 receiver 负责换算），receiver 发布期做量纲自检（如腕–中指 MCP 距离合理区间），越界告警
- `header.frame_id` 必须携带手套轴约定标签（如 `rokoko_glove`），下游不得对轴朝向做隐式假设

### C.2 ROS 消息与 Topic

**新消息类型**：`teleoperation_interfaces/msg/StandardHandKeypoints`
```
Header header
string[21] names       # 标准名称数组（每次都填）
geometry_msgs/Pose[21] poses  # 位姿数组（缺失点用 NaN）
```

**Topic 规范**：
- `/mocap/left_hand/pose` (StandardHandKeypoints)
- `/mocap/right_hand/pose` (StandardHandKeypoints)

### C.3 Rokoko 映射策略

**映射表（索引 1:1 对应）**：

| Rokoko 原生 | 公司标准 |
|------------|---------|
| Hand | WRIST |
| ThumbProximal | THUMB_CMC |
| ThumbMedial | THUMB_MCP |
| ThumbDistal | THUMB_IP |
| ThumbTip | THUMB_TIP |
| IndexProximal | INDEX_FINGER_MCP |
| IndexMedial | INDEX_FINGER_PIP |
| IndexDistal | INDEX_FINGER_DIP |
| IndexTip | INDEX_FINGER_TIP |
| MiddleProximal | MIDDLE_FINGER_MCP |
| MiddleMedial | MIDDLE_FINGER_PIP |
| MiddleDistal | MIDDLE_FINGER_DIP |
| MiddleTip | MIDDLE_FINGER_TIP |
| RingProximal | RING_FINGER_MCP |
| RingMedial | RING_FINGER_PIP |
| RingDistal | RING_FINGER_DIP |
| RingTip | RING_FINGER_TIP |
| LittleProximal | PINKY_MCP |
| LittleMedial | PINKY_PIP |
| LittleDistal | PINKY_DIP |
| LittleTip | PINKY_TIP |

**事实基础（review-02 断言 3）**：Rokoko 原生命名（Hand / Thumb{Proximal,Medial,Distal,Tip} / Index·Middle·Ring·Little 同构，共 21 点）、UDP 14043、JSON v3 已由本地 `rokoko_hand_receiver/core/decoder.py` 实证；官方公开资料不覆盖命名与 LZ4 细节（支持中心反爬），以本地实证为准。

**⚠️ 待验证**：Rokoko 关键点与解剖学术语的对应关系需戴手套实测验证（映射按 1:1 暂定，代码注释标记未经实测）。

**实施策略**：
- 在 `rokoko_hand_receiver_node` 内部硬编码映射
- 验证 Rokoko 输出的 21 个节点名称完整性（按名称查找，不依赖索引）
- 非有限值边界（HS-5 同源裁定）：数值非有限（NaN/Inf）→ 该点按缺失 NaN 标记、**帧放行**；结构性缺失/重名 → **整帧拒收**。现行 decoder 把非有限值整帧拒——实施票需对齐此裁定（差异已记录，不在本票改代码）
- 缺失点用 NaN 标记：`position=(NaN,NaN,NaN)`, `orientation=(0,0,0,1)`
- 同时发布原始格式 `/rokoko/{side}/raw_hand` (调试用，可后续删除)

### C.4 未来换手套扩展

**架构原则**：
- 每个手套独立 receiver package（如 `xsens_hand_receiver_node`）
- 统一发布到 `/mocap/{side}_hand/pose` (StandardHandKeypoints)
- 强制 21 个点，不足用 NaN 填充

**详细规范**：参见 `docs/手套21关键点标准化规范.md`

---

## 附录 D：参考文献

- **评审与核查（v1.1 依据，同目录）**：
  - `review-01-adversarial.md`：对抗评审 19 项发现（阻断 5 / 高 6 / 中 6 / 低 2），修复对照见附录 E
  - `review-02-factcheck.md`：外部事实核查（NaN 序列化 / Rokoko 协议 / Sharpa Wave / 生态先例）
- **Wayfinder 归档**（`archive/wayfinder-2026-10/`）：
  - `tickets/12-hand-swap-architecture-spec.md`：本 spec 前身
  - `tickets/07-data-flow-hardware-binding.md` 及 `research/07.2-existing-spec-constraints.md`：D1–D8 待决策清单
  - `research/07-hand-adapter-architecture-design-final.md`：设计定稿
- **团队规范**：22 DoF 标准定义——22 主动 DoF 的数量参考 Sharpa Wave（公开产品规格，sharpa.com/pages/wave）；**22 关节命名与排序表为团队内部定义，非 Sharpa 公开标准**（review-02 断言 4）
- **仓库 ADR**：`docs/adr/` 0014–0020（换手架构 D1–D7）及 0003/0005/0008/0010（继承约束），见 §6.1
- **手套标准**：`docs/手套21关键点标准化规范.md`

## 附录 E：评审修复对照（v1.1）

对 `review-01-adversarial.md` 19 项发现的处置。处置分三类：**修复**（本版条文已改）、**豁免**（不改，附理由）、**延期**（裁定已入条文，代码/流程落地在实施票）。

| 发现 | 级别 | 处置 | 落点 |
|------|------|------|------|
| C1 thumb 两关节无承接 / from_22dof 秩未定义 | 阻断 | 修复（按用户裁定收口） | HS-1：输出 10 维、原生序对齐、形状断言；thumb_roll/thumb_abad 有意不映射，走 `fixed_native_joints` 固定值（用户 2026-10-19：固定值方便遥操）；附录 B 槽位 0/1 恢复 NaN 并记设计意图 |
| C2 三套互斥激活集 | 阻断 | 修复 | HS-2；附录 B 计数改 8/22（thumb 两关节固定值驱动）；§5.1/5.2 激活集改由 profile 派生 |
| C3 PoseArray vs StandardHandKeypoints | 阻断 | 修复 | §2.2 表、§5.2、维度总结统一为 StandardHandKeypoints |
| C4 /observation 自回环 | 阻断 | 修复 | HS-3 自回环禁令；下行输入改为专用命令面 `/{hand_id}_control/{side}/final_command`（命名避开现行软目标 topic）；§5.3 拓扑门禁 |
| C5 目标流/观测面混淆、反馈无 wire 出口 | 阻断 | 修复 | §2.2 面-语义-生产者表；新增 22D 反馈面（通道③）；ADR-0003/0010 落点入层 3/4 图；访问边界注记 |
| H6 control_command 孤儿 + 双转换路径 | 高 | 修复 | HS-3/HS-4：命令链线性化，Provider 唯一合法命令来源；§3.3 HandAdapter 改原生接口 |
| H7 YAML 复制关节契约 | 高 | 修复 | §3.1 YAML 删 joints 段；HS-3；§5.3 A11 按 ADR-0016 重写（逐手唯一 owner，扫 code+config） |
| H8 22D 限位无来源 | 高 | 修复 | HS-7：contracts per-side 限位经映射派生 + 加载期校验；`limits_in_22dof()` 接口 |
| H9 NaN 三重语义未定义 | 高 | 修复 | HS-5/HS-6：三分语义 + ADR-0005 迁移条件 |
| H10 enable 复活已废弃 arming | 高 | 修复 | HS-9：删 enable，唯一 Service = clear_fault（§2.3、层 3 图） |
| H11 部分更新/反馈初始化歧义 | 高 | 修复 | HS-5 整帧无效 + HS-8 激活集上判合格 |
| M12 单位/坐标系假组合 | 中 | 修复 | 附录 C.1：SI 米制强制 + 量纲自检 + frame_id 轴约定 |
| M13 非有限关键点两可 | 中 | 修复+延期 | 附录 C.3 裁定（非有限→缺失点放行；结构缺失→拒帧）；decoder 现状对齐延期到实施票 |
| M14 配置优先级/单侧几何 | 中 | 修复 | HS-10：双侧齐备强校验、launch 只传两参数、A28 扩围 |
| M15 ADR 撞号 | 中 | 修复 | §6 重写为仓库 ADR 引用 + HS-n；§6.3 废弃清单 |
| M16 基线过期 | 中 | 修复 | 头部日期/基线声明；附录 D 路径改 `archive/wayfinder-2026-10/`；层 4 图补 Provider 边界 |
| M17 零修改承诺无操作性 | 中 | 修复 | HS-11：§4.2 架构保证改"代码零修改 + 注入物更换" |
| L18 图中硬编码 /o10/ 前缀 | 低 | 修复 | 维度总结图注（图中 `/o10/` 为 `/{hand_id}/` 实例） |
| L19 QoS/频率/stamp 未定义 | 低 | 修复（最小集） | §2.2：reliable + KEEP_LAST(10)、stamp 全链路透传、频率跟随上游；逐 topic 差异化 profile 延期到实施票 |

**事实核查处置（review-02）**：NaN 链路保真（成立）→ ADR-0015 风险关闭注记；JSON 边界禁 NaN → 附录 A 边界条款；NaN 无生态先例 → 附录 A 自定约定声明；Sharpa Wave 限定 → 附录 D 措辞修正；Rokoko 命名本地实证 → 附录 C.3 事实基础注记。

**无豁免项**：19 项发现全部在 spec 层面处置；延期项（Rokoko 接收节点非有限值行为对齐、逐 topic QoS 细化）已写入条文，归"按 spec 实施"新 effort。thumb 槽位问题（C1）经用户 HITL 裁定收口：不映射、固定值驱动（2026-10-19）。

**定稿记录（2026-10-19 HITL）**：① 拓扑 HS-3/HS-4（三通道 + final_command + 反馈面）接受；② thumb 两关节保持不映射、配置固定值驱动；③ 标准面零符号变换（HS-7）接受；④ v1.1 定稿（Draft-r2 → Final）。

---

**文档维护**：本文档随架构演进更新，任何 ADR 变更需同步修订。
