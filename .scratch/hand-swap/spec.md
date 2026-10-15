# ROTRAC 灵巧手遥操作系统架构文档

> **版本**: 1.0  
> **状态**: Draft（基于 wayfinder 票据 12 spec）  
> **最后更新**: 2025-01-15

---

## 执行摘要

ROTRAC（Robotic Teleoperation and Retargeting Architecture for Control）是一个**手无关的灵巧手遥操作重定向系统**，基于 ROS 2 构建。系统采用四层分层架构 + 独立的 22 DoF 标准适配层，实现了：

1. ✅ **统一 22 DoF 标准接口**（符合团队架构规范）
2. ✅ **换手只需修改配置文件和硬件适配器**（业务逻辑零修改）
3. ✅ **控制层完全手无关**（限速、安全、状态机不感知具体灵巧手）

**核心设计原则**：
- 分层隔离（手套 → 重定向 → 标准适配 → 控制 → 硬件）
- 配置驱动（所有手的静态参数在 YAML 配置中）
- 接口标准化（/observation/* 统一 22 DoF）

---

## 目录

1. [系统概览](#1-系统概览)
2. [ROS 2 数据流架构](#2-ros-2-数据流架构)
3. [核心抽象层](#3-核心抽象层)
4. [换手操作](#4-换手操作)
5. [测试策略](#5-测试策略)
6. [架构决策记录](#6-架构决策记录)

---

## 1. 系统概览

### 1.1 问题域

**输入**：手套采集的人手 21 关键点（位置 + 姿态）  
**输出**：灵巧手的关节角度命令（符合物理限制和安全约束）  
**挑战**：
- 人手与灵巧手的运动学差异（DoF 不匹配、耦合关节、方向映射）
- 不同灵巧手的硬件差异（关节数量、限位、通信协议）
- 需要符合团队的 22 DoF 标准规范（录制/回放/可视化统一）

### 1.2 解决方案

```
┌────────────────────────────────────────────────────────────┐
│  分层架构（手无关）                                          │
├────────────────────────────────────────────────────────────┤
│  层 1: 手套采集（Raw 边界）                                  │
│    • Rokoko 手套 → 21 关键点                               │
│    • 稳定性：换手不影响                                     │
├────────────────────────────────────────────────────────────┤
│  层 2: 重定向计算（手侧适配）                                │
│    • 人体侧管线：掌坐标、链长估计、归一化                    │
│    • 机器人侧 IK：五指并行求解                              │
│    • 输出：手的原生维度（O10=10维, L20=22维）               │
├────────────────────────────────────────────────────────────┤
│  层 2.5: 22 DoF 标准适配（独立 Node）                       │
│    • 双向转换：原生维度 ↔ 22 DoF 标准                      │
│    • 解耦：重定向层与控制层互不感知对方的维度                │
├────────────────────────────────────────────────────────────┤
│  层 3: 控制安全（完全 22 DoF）                              │
│    • 安全复核：限位检查、有限性验证                          │
│    • 硬限速器：时间额度封顶                                 │
│    • 状态机：ENABLED/PAUSED/FAULT                          │
├────────────────────────────────────────────────────────────┤
│  层 4: 硬件隔离（内部处理维度转换）                          │
│    • HandAdapter 接口：统一 22 DoF                         │
│    • 内部私有方法：22 DoF ↔ 原生维度转换                   │
│    • 子类实现：调用硬件 SDK（原生维度）                     │
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
  层 1: 手套数据采集层
════════════════════════════════════════════════════════════════════════════════

     ┌───────────────────┐
     │  Rokoko 手套硬件   │
     │  UDP 14043        │
     └─────────┬─────────┘
               │ Rokoko JSON v3 (21 关键点)
               ▼
     ┌─────────────────────────────────┐
     │  Node: rokoko_receiver          │
     │  Package:                       │
     │    rokoko_hand_receiver_node    │
     │                                 │
     │  职责:                          │
     │  • 接收 UDP 数据包              │
     │  • 解析 21 关键点               │
     │  • 发布双手 PoseArray           │
     └───────────┬─────────┬───────────┘
                 │         │
          publishes       publishes
                 │         │
                 ▼         ▼
     ┌─────────────┐   ┌─────────────┐
     │ Topic:      │   │ Topic:      │
     │ /mocap/     │   │ /mocap/     │
     │ left_hand/  │   │ right_hand/ │
     │ pose        │   │ pose        │
     │             │   │             │
     │ Type:       │   │ Type:       │
     │ PoseArray   │   │ PoseArray   │
     │ (21 poses)  │   │ (21 poses)  │
     │             │   │             │
     │ 频率: 100Hz │   │ 频率: 100Hz │
     └─────────────┘   └─────────────┘


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
  层 2.5: 22 DoF 标准适配层（独立 Node，双向转换）
════════════════════════════════════════════════════════════════════════════════

                  │                                    │
           subscribes                           subscribes
                  │                                    │
                  ▼                                    ▼
     ┌──────────────────────────────┐   ┌──────────────────────────────┐
     │  Node:                       │   │  Node:                       │
     │  hand_standard_adapter_left  │   │  hand_standard_adapter_right │
     │  ──────────────────────────   │   │  ──────────────────────────   │
     │  Package:                    │   │  Package:                    │
     │    hand_standard_adapter_    │   │    hand_standard_adapter_    │
     │    node                      │   │    node                      │
     │                              │   │                              │
     │  参数:                        │   │  参数:                        │
     │  • hand_config               │   │  • hand_config               │
     │  • side                      │   │  • side                      │
     │                              │   │                              │
     │  功能: 双向转换器             │   │  功能: 双向转换器             │
     │  ┌────────────────────────┐  │   │  ┌────────────────────────┐  │
     │  │  上行通道:             │  │   │  │  上行通道:             │  │
     │  │  10 维 → 22 DoF        │  │   │  │  10 维 → 22 DoF        │  │
     │  │  (含 NaN 填充)         │  │   │  │  (含 NaN 填充)         │  │
     │  └────────────────────────┘  │   │  └────────────────────────┘  │
     │                              │   │                              │
     │  ┌────────────────────────┐  │   │  ┌────────────────────────┐  │
     │  │  下行通道:             │  │   │  │  下行通道:             │  │
     │  │  22 DoF → 10 维        │  │   │  │  22 DoF → 10 维        │  │
     │  │  (提取激活关节)         │  │   │  │  (提取激活关节)         │  │
     │  └────────────────────────┘  │   │  └────────────────────────┘  │
     └──────────┬───────────────────┘   └──────────┬───────────────────┘
                │                                  │
         publishes                          publishes
                │                                  │
                ▼                                  ▼
     ┌─────────────────────┐          ┌─────────────────────┐
     │ Topic:              │          │ Topic:              │
     │ /observation/       │          │ /observation/       │
     │ left_hand/          │          │ right_hand/         │
     │ joint_states        │          │ joint_states        │
     │                     │          │                     │
     │ Type: JointState    │          │ Type: JointState    │
     │                     │          │                     │
     │ 数据:               │          │ 数据:               │
     │ • name[22]:         │          │ • name[22]:         │
     │   标准 22 DoF 名称  │          │   标准 22 DoF 名称  │
     │                     │          │                     │
     │ • position[22]:     │          │ • position[22]:     │
     │   [NaN, NaN, 0.5,   │          │   [NaN, NaN, 0.5,   │
     │    NaN, NaN, NaN,   │          │    NaN, NaN, NaN,   │
     │    -0.1, 0.8, ...]  │          │    -0.1, 0.8, ...]  │
     │   ↑                 │          │   ↑                 │
     │   激活关节有值       │          │   激活关节有值       │
     │   未激活 = NaN      │          │   未激活 = NaN      │
     │                     │          │                     │
     │ ⚠️  22 DoF 标准      │          │ ⚠️  22 DoF 标准      │
     │    (团队规范)       │          │    (团队规范)       │
     └─────────────────────┘          └─────────────────────┘


════════════════════════════════════════════════════════════════════════════════
  层 3: 控制安全层（完全 22 DoF 接口）
════════════════════════════════════════════════════════════════════════════════

                │                                  │
         subscribes                         subscribes
                │                                  │
                ▼                                  ▼
     ┌────────────────────────────┐   ┌────────────────────────────┐
     │  Node:                     │   │  Node:                     │
     │  hand_control_left         │   │  hand_control_right        │
     │  ──────────────────────────  │   │  ──────────────────────────  │
     │  Package:                  │   │  Package:                  │
     │    hand_control_node       │   │    hand_control_node       │
     │    (通用包)                 │   │    (通用包)                 │
     │                            │   │                            │
     │  参数:                      │   │  参数:                      │
     │  • hand_config             │   │  • hand_config             │
     │  • side                    │   │  • side                    │
     │                            │   │                            │
     │  依赖注入:                  │   │  依赖注入:                  │
     │  • HandProfile             │   │  • HandProfile             │
     │  • HandAdapter             │   │  • HandAdapter             │
     │                            │   │                            │
     │  安全管线 (22 DoF):         │   │  安全管线 (22 DoF):         │
     │  ┌──────────────────────┐  │   │  ┌──────────────────────┐  │
     │  │ 1. 接收 22 DoF 命令   │  │   │  │ 1. 接收 22 DoF 命令   │  │
     │  │                      │  │   │  │                      │  │
     │  │ 2. 安全复核          │  │   │  │ 2. 安全复核          │  │
     │  │    ✓ 有限性          │  │   │  │    ✓ 有限性          │  │
     │  │    ✓ 限位(22 DoF)    │  │   │  │    ✓ 限位(22 DoF)    │  │
     │  │    ✓ 只检查激活索引   │  │   │  │    ✓ 只检查激活索引   │  │
     │  │                      │  │   │  │                      │  │
     │  │ 3. 状态机            │  │   │  │ 3. 状态机            │  │
     │  │    ENABLED/PAUSED/   │  │   │  │    ENABLED/PAUSED/   │  │
     │  │    FAULT             │  │   │  │    FAULT             │  │
     │  │                      │  │   │  │                      │  │
     │  │ 4. 硬限速器(22 维)    │  │   │  │ 4. 硬限速器(22 维)    │  │
     │  │    跳过 NaN 位置     │  │   │  │    跳过 NaN 位置     │  │
     │  │                      │  │   │  │                      │  │
     │  │ 5. 调用 HandAdapter  │  │   │  │ 5. 调用 HandAdapter  │  │
     │  │    传入 22 DoF       │  │   │  │    传入 22 DoF       │  │
     │  └──────────────────────┘  │   │  └──────────────────────┘  │
     │                            │   │                            │
     │  ⚠️  完全 22 DoF            │   │  ⚠️  完全 22 DoF            │
     │     不知道原生维度          │   │     不知道原生维度          │
     └────┬────┬──────────────────┘   └────┬────┬──────────────────┘
          │    │                           │    │
          │    └─publishes                 │    └─publishes
          │                                │
    provides                         provides
    Services                         Services
          │                                │
          ▼                                ▼
    ┌─────────────────┐            ┌─────────────────┐
    │ Service:        │            │ Service:        │
    │ /o10_control/   │            │ /o10_control/   │
    │ left/enable     │            │ right/enable    │
    │ (SetBool)       │            │ (SetBool)       │
    └─────────────────┘            └─────────────────┘

    ┌─────────────────┐            ┌─────────────────┐
    │ Service:        │            │ Service:        │
    │ /o10_control/   │            │ /o10_control/   │
    │ left/           │            │ right/          │
    │ clear_fault     │            │ clear_fault     │
    │ (Trigger)       │            │ (Trigger)       │
    └─────────────────┘            └─────────────────┘

          │                                │
          ▼                                ▼
    ┌─────────────────┐            ┌─────────────────┐
    │ Topic:          │            │ Topic:          │
    │ /o10_control/   │            │ /o10_control/   │
    │ left/state      │            │ right/state     │
    │ (ControlState)  │            │ (ControlState)  │
    └─────────────────┘            └─────────────────┘


════════════════════════════════════════════════════════════════════════════════
  层 4: HandAdapter（内部处理维度转换 + 硬件通信）
════════════════════════════════════════════════════════════════════════════════

          │                                │
   内部调用                          内部调用
          │                                │
          ▼                                ▼
    ┌──────────────────────────────────────────────────────────┐
    │  HandAdapter (Python 类，非 ROS Node)                     │
    │  ─────────────────────────────────────────────────────    │
    │  公开接口（22 DoF）:                                      │
    │  • send_command(22 DoF)    → HardwareResponse            │
    │  • read_feedback()         → JointFeedback (22 DoF)      │
    │  • query_errors()          → JointError                  │
    │                                                          │
    │  内部私有方法（维度转换）:                                 │
    │  ┌────────────────────────────────────────────────────┐  │
    │  │ _translate_command_to_native(22 DoF → 10 维)       │  │
    │  │   • 调用 HandProfile.from_22dof_standard()         │  │
    │  │   • [0.5, NaN, 0.3, ...] → [0.5, 0.3, ...]        │  │
    │  └────────────────────────────────────────────────────┘  │
    │                                                          │
    │  ┌────────────────────────────────────────────────────┐  │
    │  │ _translate_feedback_from_native(10 维 → 22 DoF)    │  │
    │  │   • 调用 HandProfile.to_22dof_standard()           │  │
    │  │   • [0.5, 0.3, ...] → [0.5, NaN, 0.3, ...]        │  │
    │  └────────────────────────────────────────────────────┘  │
    │                                                          │
    │  子类实现（硬件通信）:                                    │
    │  • _send_native_command(10 维)    → SDK 调用            │
    │  • _read_native_feedback()        → 10 维反馈           │
    └──────────────────────────────────────────────────────────┘
          │                                │
          ▼                                ▼
    ┌─────────────────┐            ┌─────────────────┐
    │ 子类:           │            │ 子类:           │
    │ AgilinkO10      │            │ AgilinkO10      │
    │ Backend         │            │ Backend         │
    │                 │            │                 │
    │ • SDK 初始化    │            │ • SDK 初始化    │
    │ • 发送 10 维    │            │ • 发送 10 维    │
    │ • 读取 10 维    │            │ • 读取 10 维    │
    └────────┬────────┘            └────────┬────────┘
             │                              │
       Agilink SDK                    Agilink SDK
             │                              │
             ▼                              ▼
    ┌─────────────────┐            ┌─────────────────┐
    │ OmniHand O10    │            │ OmniHand O10    │
    │ 左手硬件         │            │ 右手硬件         │
    │ 10 主动关节      │            │ 10 主动关节      │
    │ 6 被动关节       │            │ 6 被动关节       │
    └─────────────────┘            └─────────────────┘


════════════════════════════════════════════════════════════════════════════════
  数据维度变化总结
════════════════════════════════════════════════════════════════════════════════

  手套 UDP              →  21 关键点 (PoseArray)
                            ↓
  重定向 IK             →  10 维原生 (O10)
                            ↓
  标准适配 Node         →  22 DoF 标准 (含 NaN)
                            ↓
  控制层                →  22 DoF (完全手无关)
                            ↓
  HandAdapter 公开接口  →  22 DoF
                            ↓
  Adapter 内部转换      →  10 维原生
                            ↓
  SDK 调用              →  10 维
                            ↓
  硬件                  →  10 主动 + 6 被动


════════════════════════════════════════════════════════════════════════════════
```

### 2.2 Topic 命名规范

| Topic 名称 | Type | 维度 | 说明 |
|-----------|------|------|------|
| `/mocap/{side}_hand/pose` | `PoseArray` | 21 poses | 手套原始数据（Raw 边界） |
| `/{hand_id}/{side}_hand/native_command` | `JointState` | N 维 | 原生维度命令（重定向输出） |
| `/observation/{side}_hand/joint_states` | `JointState` | 22 DoF | 22 DoF 标准（团队规范） |
| `/{hand_id}/{side}_hand/control_command` | `JointState` | N 维 | 原生维度控制（下行通道） |
| `/{hand_id}_control/{side}/state` | `ControlState` | - | 控制状态诊断 |

### 2.3 Service 接口

| Service 名称 | Type | 说明 |
|-------------|------|------|
| `/{hand_id}_control/{side}/enable` | `std_srvs/SetBool` | 使能/禁用控制 |
| `/{hand_id}_control/{side}/clear_fault` | `std_srvs/Trigger` | 清除锁存故障 |

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
        """获取关节契约（原生维度）"""
    
    def geometry(self, side: str) -> HandGeometry:
        """获取几何参数（指根、链长、方向映射）"""
    
    def to_22dof_standard(self, native_joints: ndarray, side: str) -> StandardJointState:
        """原生维度 → 22 DoF 标准（含 NaN）"""
    
    def from_22dof_standard(self, standard_joints: ndarray, side: str) -> ndarray:
        """22 DoF 标准 → 原生维度（提取激活关节）"""
    
    def active_indices_in_22dof(self, side: str) -> list[int]:
        """返回激活的 22 DoF 索引列表"""
```

**配置示例**（`config/o10_hand.yaml`）：
```yaml
hand_id: o10

joints:
  names: [thumb_roll, thumb_abad, thumb_mcp, ...]  # 10 个

mapping_to_22dof:
  thumb_CMC_FE: null       # O10 无此关节
  thumb_MCP_FE: 2          # O10 的 thumb_mcp → 标准索引 2
  index_MCP_AA: 3          # O10 的 index_abad → 标准索引 6
  # ... 共 22 个标准关节名

geometry:
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

### 3.2 hand_standard_adapter（独立 ROS 节点）

**职责**：双向转换原生维度与 22 DoF 标准格式。

**ROS 接口**：
```
订阅: /{hand_id}/{side}_hand/native_command (N 维)
发布: /observation/{side}_hand/joint_states (22 DoF)

订阅: /observation/{side}_hand/joint_states (22 DoF)
发布: /{hand_id}/{side}_hand/control_command (N 维)
```

**实现**：
```python
class HandStandardAdapterNode(Node):
    def __init__(self):
        # 加载 HandProfile
        self.hand_profile = ConfigDrivenHandProfile(config_path)
        
        # 上行通道
        self.sub_native = self.create_subscription(...)
        self.pub_standard = self.create_publisher(...)
        
        # 下行通道
        self.sub_standard = self.create_subscription(...)
        self.pub_native = self.create_publisher(...)
    
    def native_to_standard_callback(self, msg):
        """10 维 → 22 DoF"""
        standard = self.hand_profile.to_22dof_standard(
            np.array(msg.position), self.side
        )
        # 发布 22 DoF
    
    def standard_to_native_callback(self, msg):
        """22 DoF → 10 维"""
        native = self.hand_profile.from_22dof_standard(
            np.array(msg.position), self.side
        )
        # 发布原生维度
```

### 3.3 HandAdapter（内部处理维度转换）

**职责**：统一 22 DoF 硬件接口，内部处理与原生维度的转换。

**接口**：
```python
class HandAdapter(ABC):
    def __init__(self, hand_profile: HandProfile, side: str):
        self.hand_profile = hand_profile
        self.side = side
    
    # ===== 公开接口（22 DoF）=====
    
    def send_command(self, command: JointTarget_22DoF) -> HardwareResponse:
        """发送 22 DoF 命令（公开方法）"""
        # 1. 调用内部转换
        native_pos = self._translate_command_to_native(command.positions)
        # 2. 调用子类硬件发送
        return self._send_native_command(native_pos)
    
    def read_feedback(self) -> HardwareResponse[JointFeedback_22DoF]:
        """读取 22 DoF 反馈（公开方法）"""
        # 1. 调用子类硬件读取
        response = self._read_native_feedback()
        # 2. 调用内部转换
        feedback_22d = self._translate_feedback_from_native(response.data)
        return HardwareResponse(success=True, data=feedback_22d)
    
    # ===== 内部私有方法（维度转换）=====
    
    def _translate_command_to_native(self, positions_22d: ndarray) -> ndarray:
        """22 DoF → 原生维度（只能内部调用）"""
        return self.hand_profile.from_22dof_standard(positions_22d, self.side)
    
    def _translate_feedback_from_native(self, native_feedback: dict) -> JointFeedback_22DoF:
        """原生维度 → 22 DoF（只能内部调用）"""
        standard = self.hand_profile.to_22dof_standard(
            native_feedback['positions'], self.side
        )
        return JointFeedback(positions=standard.positions, ...)
    
    # ===== 子类必须实现（原生维度）=====
    
    @abstractmethod
    def _send_native_command(self, positions: ndarray) -> HardwareResponse:
        """子类实现：发送原生维度命令到硬件"""
        pass
    
    @abstractmethod
    def _read_native_feedback(self) -> HardwareResponse[dict]:
        """子类实现：从硬件读取原生维度反馈"""
        pass
```

**子类实现示例**（O10）：
```python
class AgilinkO10Backend(HandAdapter):
    def __init__(self, hand_profile, side, **hw_params):
        super().__init__(hand_profile, side)
        
        # 初始化 Agilink SDK
        from omnihand import OmniHand2025
        self.sdk_hand = OmniHand2025(...)
    
    def _send_native_command(self, positions: ndarray) -> HardwareResponse:
        """发送 10 维命令到 O10"""
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

## 4. 换手操作

### 4.1 从 O10 切换到 Linker L20

**步骤 1：准备模型资产**
```bash
mkdir -p linker_l20_model/urdf
# 从 Linker 官方获取 URDF 文件
cp ~/linker_sdk/models/*.urdf linker_l20_model/urdf/
```

**步骤 2：编写配置文件**（`config/linker_l20_hand.yaml`）
```yaml
hand_id: linker_l20

joints:
  names: [thumb_CMC_FE, thumb_CMC_AA, ..., pinky_DIP]  # 22 个

mapping_to_22dof:
  # L20 是 22 DoF 全激活，1:1 映射
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

### 4.2 Topic 变化对比

| 项目 | O10 | Linker L20 | 是否变化 |
|------|-----|-----------|---------|
| 手套输入 | `/mocap/*/pose` (21) | `/mocap/*/pose` (21) | ✅ 不变 |
| 重定向输出 | `/o10/*/native_command` (10) | `/linker_l20/*/native_command` (22) | ⚠️ 变化 |
| 标准格式 | `/observation/*/joint_states` (22) | `/observation/*/joint_states` (22) | ✅ 不变 |
| 控制输入 | 22 DoF | 22 DoF | ✅ 不变 |

### 4.3 代码修改范围

| 模块 | 是否修改 | 说明 |
|------|---------|------|
| `rokoko_hand_receiver_node` | ❌ 不改 | Raw 边界稳定 |
| `hand_retargeting_node` | ❌ 不改 | 算法手无关 |
| `hand_standard_adapter_node` | ❌ 不改 | 只换配置 |
| `hand_control_node` | ❌ 不改 | 完全 22 DoF |
| **配置文件** | ✅ **新增** | `config/linker_l20_hand.yaml` |
| **HandAdapter** | ✅ **新增** | `LinkerL20Backend` |
| **Launch 文件** | ✅ **修改** | 更新 `hand_config` 参数 |

---

## 5. 测试策略

### 5.1 单元测试

**HandProfile 映射逻辑**
```python
def test_o10_to_22dof_mapping():
    profile = ConfigDrivenHandProfile("config/o10_hand.yaml")
    native_10d = np.array([0.5, -0.3, 0.2, ...])  # 10 维
    
    standard = profile.to_22dof_standard(native_10d, "right")
    
    assert standard.positions.shape == (22,)
    assert standard.positions[2] == 0.5  # thumb_mcp → 索引 2
    assert np.isnan(standard.positions[0])  # thumb_CMC_FE = NaN
```

**HandAdapter 维度转换**
```python
def test_adapter_dimension_conversion():
    profile = ConfigDrivenHandProfile("config/o10_hand.yaml")
    adapter = MockO10Backend(profile, "right")
    
    # 发送 22 DoF
    command_22d = JointTarget(positions=np.array([...]))  # 22 维
    adapter.send_command(command_22d)
    
    # 验证子类收到 10 维
    assert adapter.last_native_command.shape == (10,)
```

### 5.2 集成测试

**完整链路测试**
```python
def test_end_to_end_22dof_output():
    # 发布手套数据
    pub_mocap.publish(PoseArray(...))  # 21 poses
    
    # 等待处理
    time.sleep(0.5)
    
    # 订阅输出
    msg = sub_observation.wait_for_message(timeout=5.0)
    
    # 验证 22 DoF 格式
    assert len(msg.name) == 22
    assert msg.name == list(STANDARD_22DOF_NAMES)
    assert len(msg.position) == 22
    
    # 验证激活位置有值
    active_indices = [2, 6, 7, 10, 13, 15, 18, 20, 21]
    for idx in active_indices:
        assert not np.isnan(msg.position[idx])
```

### 5.3 架构门禁测试

**A11：关节契约唯一 owner**
```python
def test_A11_joint_contract_single_owner():
    allowed_packages = [
        "omnihand_o10_contracts",
        "linker_l20_profile",
    ]
    # 扫描所有包，验证关节名定义不重复
```

**A28：配置单一来源**
```python
def test_A28_config_single_source():
    # 扫描代码，检测硬编码的设备参数
    hardcoded_params = scan_for_hardcoded_config()
    assert len(hardcoded_params) == 0
```

---

## 6. 架构决策记录

### ADR-1: 统一 22 DoF 标准接口

**决策**：所有手的接口统一为 22 DoF 标准格式（`/observation/*/joint_states`），未激活关节填 NaN。

**理由**：
- 符合团队架构规范（参考 Sharpa Wave 22 DoF 定义）
- 录制/回放/可视化系统统一格式
- 控制层接口稳定（不随换手改变）

**实施**：HandProfile 提供 `to_22dof_standard()` / `from_22dof_standard()` 方法。

---

### ADR-2: 独立的标准适配 Node

**决策**：创建独立的 `hand_standard_adapter_node`，专门负责原生维度与 22 DoF 的双向转换。

**理由**：
- 解耦重定向层和控制层（各自保持手无关）
- 转换逻辑集中，易于测试和调试
- 支持双向通道（上行：原生→22DoF，下行：22DoF→原生）

**备选方案**：在重定向节点或控制节点内部做转换  
**拒绝原因**：耦合业务逻辑，换手需要修改多个节点

---

### ADR-3: HandAdapter 内部处理维度转换

**决策**：HandAdapter 公开接口为 22 DoF，内部通过私有方法 `_translate_*()` 处理与原生维度的转换。

**理由**：
- 控制层完全工作在 22 DoF 接口，不感知具体灵巧手的原生维度
- 子类只需实现硬件通信（`_send_native_command` / `_read_native_feedback`），职责单一
- 维度转换逻辑封装在父类，复用性高

**备选方案**：控制层直接处理原生维度  
**拒绝原因**：控制层需要感知每只手的维度，无法复用

---

### ADR-4: 配置驱动的 HandProfile

**决策**：HandProfile 是通用类（`ConfigDrivenHandProfile`），所有参数从 YAML 配置加载，不需要为每只手写子类。

**理由**：
- 换手只需修改配置文件，不需要写新的 Python 类
- 配置文件格式统一，易于验证和生成
- 支持运行时加载不同配置

**备选方案**：每只手一个 HandProfile 子类（如 `OmniHandO10Profile`）  
**拒绝原因**：换手需要写代码，违背配置驱动原则

---

### ADR-5: 保留原生维度 Topic

**决策**：重定向层输出原生维度 Topic（`/{hand_id}/{side}_hand/native_command`），而不是直接输出 22 DoF。

**理由**：
- 重定向算法保持手无关（IK 求解输出的就是原生维度）
- 标准适配节点专职转换，职责清晰
- 支持调试（可以 echo 原生维度 topic 查看 IK 输出）

**备选方案**：重定向层直接输出 22 DoF  
**拒绝原因**：重定向层需要感知 22 DoF 映射，耦合了标准适配逻辑

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

## 附录 B：O10 的 22 DoF 映射

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

**激活关节数**：9 / 22

---

## 附录 C：参考文献

- **Wayfinder 票据**：
  - 票据 12：灵巧手换手架构 Spec
  - 票据 7.1：业界调研（ros2_control、MoveIt、Drake）
  - 票据 7.2：现有 spec 约束盘点
- **团队规范**：22 DoF 标准定义（Sharpa Wave）
- **设计文档**：`wayfinder/research/07-hand-adapter-architecture-design-final.md`

---

**文档维护**：本文档随架构演进更新，任何 ADR 变更需同步修订。
