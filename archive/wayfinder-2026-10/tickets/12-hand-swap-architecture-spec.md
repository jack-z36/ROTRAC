---
id: 12
title: 灵巧手换手架构 Spec（22 DoF 标准适配）
type: task
labels: [wayfinder:spec]
status: open
assignee:
blocked-by: [7]
---

## Problem Statement

当前 OmniHand 重定向控制程序的架构与 OmniHand O10 硬件深度耦合，更换灵巧手（如切换到 Linker L20 或其他品牌）需要修改重定向节点、控制节点的业务逻辑代码。此外，当前架构未对齐团队的 22 DoF 标准规范（`/observation/{side}_hand/joint_states` 必须输出 22 维标准格式），导致录制、回放、可视化等下游系统无法统一处理不同灵巧手的数据。

核心痛点：
1. 重定向节点（`hand_retargeting_node`）和控制节点（`omnihand_o10_control_node`）硬编码了 O10 的 10 个关节名、限位、耦合多项式
2. 维度转换逻辑散落在多个模块中，难以维护
3. 不符合团队架构规范的 22 DoF 标准接口要求
4. 换手需要修改多个 ROS 节点的业务代码

## Solution

建立一套**手无关的 ROS 2 架构**，通过三个核心抽象层实现换手时的最小修改范围：

1. **HandProfile（数据驱动配置）**：将灵巧手的所有静态参数（关节名、限位、几何、耦合规则、22 DoF 映射）提取到 YAML 配置文件，运行时加载
2. **hand_standard_adapter（独立 ROS 节点）**：专门负责原生维度与 22 DoF 标准格式的双向转换，解耦重定向层和控制层
3. **HandAdapter（内部处理维度转换）**：在硬件适配器内部处理 22 DoF ↔ 原生维度的转换，使控制层完全工作在 22 DoF 接口

换手后的修改范围：
- ✅ 创建新的配置文件（`config/{hand_id}_hand.yaml`，含 22 DoF 映射）
- ✅ 实现新的 `HandAdapter` 子类（调用新手的 SDK）
- ✅ 更新 launch 文件中的 `hand_config` 参数
- ❌ **不需要修改**重定向节点、控制节点、标准适配节点的任何业务逻辑代码

## User Stories

### 架构层面

1. 作为系统架构师，我希望所有灵巧手的数据输出统一为 22 DoF 标准格式，以便录制、回放、可视化系统可以处理任意品牌的灵巧手数据
2. 作为系统架构师，我希望维度转换逻辑集中在明确的边界（HandProfile 和 HandAdapter），而不是散落在多个节点中，以便于维护和调试
3. 作为系统架构师，我希望控制层（安全复核、硬限速器、状态机）完全工作在 22 DoF 接口，不感知具体灵巧手的原生维度，以实现控制逻辑的完全复用

### 换手操作

4. 作为灵巧手开发者，当我要接入一只新的灵巧手时，我希望只需要编写配置文件和硬件适配器，而不需要修改重定向算法和控制算法
5. 作为灵巧手开发者，当新手的主动关节数量不同（如 10 维、16 维、22 维）时，我希望通过配置文件中的 `mapping_to_22dof` 字段声明映射关系，系统自动处理维度转换
6. 作为灵巧手开发者，当新手没有某个标准关节（如 O10 无 `thumb_CMC_FE`）时，我希望该位置在 22 DoF 输出中自动填充 NaN，下游系统正确跳过
7. 作为灵巧手开发者，当新手是 22 DoF 全激活（如 Linker L20）时，我希望映射配置是 1:1 的简单对应，输出不含任何 NaN
8. 作为系统集成者，当我完成新手接入后，我希望通过修改环境变量 `HAND_CONFIG=config/new_hand.yaml` 即可在不同灵巧手之间切换，无需重新编译

### 数据流与接口

9. 作为 ROS 节点开发者，我希望 `/observation/{side}_hand/joint_states` Topic 始终输出 22 DoF 标准格式（sensor_msgs/JointState，22 个标准关节名），无论底层是什么灵巧手
10. 作为 ROS 节点开发者，我希望手套接收节点（`rokoko_hand_receiver`）的输出格式（21 关键点）与灵巧手类型无关，保持稳定
11. 作为 ROS 节点开发者，我希望重定向节点（`hand_retargeting`）输出的是灵巧手的原生维度（如 O10 = 10 维），通过独立的标准适配节点转换为 22 DoF
12. 作为 ROS 节点开发者，我希望控制节点（`hand_control`）接收和处理的都是 22 DoF 标准格式，内部的限位检查、硬限速器都工作在 22 维空间
13. 作为 ROS 节点开发者，我希望通过 `rostopic echo /observation/right_hand/joint_states` 可以看到 22 维数组，未激活的关节显示为 NaN

### HandProfile 配置

14. 作为配置文件编写者，我希望在 `joints.names` 字段中声明灵巧手的原生关节名称（如 O10 的 10 个关节名），顺序与 SDK 一致
15. 作为配置文件编写者，我希望在 `joints.{side}.lower_limits` 和 `upper_limits` 中声明每个原生关节的限位（单位：弧度），维度与 `names` 一致
16. 作为配置文件编写者，我希望在 `geometry.{side}.finger_roots` 中声明五指根部在掌坐标系中的位置（米），用于 IK 计算
17. 作为配置文件编写者，我希望在 `geometry.{side}.chain_lengths` 中声明五指的完整链长（米），用于残差归一化
18. 作为配置文件编写者，我希望在 `geometry.{side}.direction_mapping` 中声明 3×3 方向映射矩阵，定义人体坐标到机器人坐标的转换
19. 作为配置文件编写者，我希望在 `mapping_to_22dof` 字段中声明每个标准 22 DoF 关节对应的原生索引（null 表示无此关节），系统根据此映射自动转换
20. 作为配置文件编写者，我希望在 `model_assets.urdf` 中声明 URDF 文件路径，在 `mjcf` 中声明 MJCF 文件路径（如无被动关节则为 null）
21. 作为配置文件编写者，我希望在 `control.max_joint_rates` 中声明原生维度的速率限制（如 O10 = 10 个值），控制层自动映射到 22 DoF 空间
22. 作为配置文件编写者，我希望在 `hardware.backend_class` 中声明 HandAdapter 实现类的完整路径（如 `omnihand_o10_hardware_adapter.AgilinkO10Backend`）

### HandAdapter 实现

23. 作为 HandAdapter 开发者，我希望只需要实现两个方法：`_send_native_command(N维)` 和 `_read_native_feedback() → N维`，不需要处理 22 DoF 转换
24. 作为 HandAdapter 开发者，我希望父类 `HandAdapter` 提供公开的 22 DoF 接口（`send_command(22维)` / `read_feedback() → 22维`），自动调用内部私有方法处理维度转换
25. 作为 HandAdapter 开发者，我希望 `_translate_command_to_native()` 私有方法由父类提供，自动调用 `HandProfile.from_22dof_standard()` 完成 22 DoF → N 维转换
26. 作为 HandAdapter 开发者，我希望 `_translate_feedback_from_native()` 私有方法由父类提供，自动调用 `HandProfile.to_22dof_standard()` 完成 N 维 → 22 DoF 转换
27. 作为 HandAdapter 开发者，我希望在 `__init__` 中接收 `hand_profile` 参数，父类自动缓存原生维度信息（如 `native_dim=10`），我只需关注 SDK 初始化
28. 作为 HandAdapter 开发者，当新手的原生维度就是 22 维（如 Linker L20）时，我希望转换方法仍然正常工作，只是变成了恒等映射

### 控制层行为

29. 作为控制层开发者，我希望硬限速器的 `max_rates_22d` 是 22 维数组，只对激活的索引进行限速，NaN 位置自动跳过
30. 作为控制层开发者，我希望安全复核的限位检查使用 22 DoF 限位（从 `HandProfile.get_22dof_limits()` 获取），未激活关节的限位为 ±inf
31. 作为控制层开发者，我希望状态机（ENABLED/PAUSED/FAULT）的逻辑与维度无关，只关心"是否有激活关节超限"或"硬件是否返回错误"
32. 作为控制层开发者，我希望从 `HandProfile.active_indices_in_22dof()` 获取激活索引列表（如 O10 返回 `[2, 6, 7, 10, 13, 15, 18, 20, 21]`），只对这些索引进行安全检查

### 标准适配节点

33. 作为标准适配节点（`hand_standard_adapter`）开发者，我希望该节点是通用的、与具体灵巧手无关的，只需通过 `hand_config` 参数加载不同的 HandProfile
34. 作为标准适配节点开发者，我希望上行通道订阅 `/{hand_id}/{side}_hand/native_command`（原生维度），发布 `/observation/{side}_hand/joint_states`（22 DoF）
35. 作为标准适配节点开发者，我希望下行通道订阅 `/observation/{side}_hand/joint_states`（22 DoF），发布 `/{hand_id}/{side}_hand/control_command`（原生维度）
36. 作为标准适配节点开发者，我希望节点内部只调用 `HandProfile.to_22dof_standard()` 和 `from_22dof_standard()`，不包含任何硬编码的维度或关节名

### 测试与验证

37. 作为测试工程师，我希望可以通过单元测试验证 `HandProfile.to_22dof_standard()` 的映射逻辑：给定 O10 的 10 维输入，输出的 22 维数组在正确的位置有值，其余为 NaN
38. 作为测试工程师，我希望可以通过单元测试验证 `HandProfile.from_22dof_standard()` 的逆映射：给定 22 维标准输入，提取出正确的 10 维原生命令
39. 作为测试工程师，我希望可以通过集成测试验证完整链路：发布手套数据（21 关键点）→ 验证 `/observation/right_hand/joint_states` 输出 22 维且格式正确
40. 作为测试工程师，我希望架构门禁测试（A11）能够验证：每只手的 contracts 包是该手关节契约的唯一 owner，不存在重复定义
41. 作为测试工程师，我希望新增 A28 门禁测试：验证配置参数（设备 ID、速率限制等）只出现在 YAML 配置文件中，不硬编码在启动脚本中

### 可视化与录制

42. 作为 Launchpad UI 用户，我希望看到 22 条关节曲线，未激活的关节以灰色显示或标注 "N/A"
43. 作为 Launchpad UI 用户，我希望可以在 UI 中看到当前使用的灵巧手类型（从 `HandProfile.hand_id` 读取，如 "o10" 或 "linker_l20"）
44. 作为数据录制人员，我希望 MCAP 文件统一录制 22 DoF 格式的 `/observation/*/joint_states`，无论使用什么灵巧手
45. 作为数据回放人员，我希望可以用旧的 10 维 O10 录制数据回放到新的 22 DoF 系统中，通过迁移工具自动补全 NaN

### 文档与示例

46. 作为新手开发者，我希望有一份完整的"换手操作手册"，列出从 O10 切换到新手的所有步骤（配置文件模板、HandAdapter 模板、测试清单）
47. 作为新手开发者，我希望有 O10 和 Linker L20 的完整配置示例，可以直接参考其中的 `mapping_to_22dof` 字段格式

## Implementation Decisions

### 模块划分

**ID-1: 新增 hand_profile_interface 包**
- 位置：`src/teleoperation_support/hand_profile_interface/`
- 职责：定义 `HandProfile`、`JointContract`、`HandGeometry`、`CouplingModel`、`FingerKinematicsPort` 等抽象基类
- 关键接口：
  - `HandProfile.to_22dof_standard(native_joints: ndarray, side: str) → StandardJointState`
  - `HandProfile.from_22dof_standard(standard_joints: ndarray, side: str) → ndarray`
  - `HandProfile.active_indices_in_22dof(side: str) → list[int]`
  - `HandProfile.get_22dof_limits(side: str) → Limits22DoF`

**ID-2: 实现 ConfigDrivenHandProfile**
- 位置：`hand_profile_interface` 包内
- 职责：通用的、数据驱动的 HandProfile 实现，所有参数从 YAML 配置加载
- 关键行为：
  - `__init__(config_path: str)` 加载 YAML 并验证必需字段
  - `to_22dof_standard()` 根据 `mapping_to_22dof` 字段进行映射，未映射的索引填 NaN
  - `from_22dof_standard()` 根据 `mapping_to_22dof` 逆映射，只提取激活关节
  - `active_indices_in_22dof()` 返回 `mapping_to_22dof` 中值非 null 的键对应的标准索引

**ID-3: 新增 hand_standard_adapter_node 包**
- 位置：`src/hand_standard_adapter_node/`
- 职责：独立的 ROS 节点，专门负责原生维度与 22 DoF 标准格式的双向转换
- ROS 接口：
  - 订阅：`/{hand_id}/{side}_hand/native_command` (JointState, N 维)
  - 发布：`/observation/{side}_hand/joint_states` (JointState, 22 DoF)
  - 订阅：`/observation/{side}_hand/joint_states` (JointState, 22 DoF) - 下行通道
  - 发布：`/{hand_id}/{side}_hand/control_command` (JointState, N 维) - 下行通道
- 参数：`hand_config` (str), `side` (str)
- 实现：节点内部持有 `HandProfile` 实例，回调函数中调用 `to_22dof_standard()` / `from_22dof_standard()`

**ID-4: 修改 hand_retargeting_node**
- 移除：删除 `contracts.py` 中的 21 节点镜像 `NODE_SUFFIXES`
- 移除：删除任何 `from omnihand_o10_*` 的导入
- 修改：发布 Topic 从 `/observation/{side}_hand/joint_states` 改为 `/{hand_id}/{side}_hand/native_command`
- 修改：输出格式从 22 DoF 改为原生维度（通过 `HandProfile.joint_contract()` 获取关节名）
- 保持不变：人体侧管线（掌坐标构造、链长估计、归一化）、IK 求解、滤波、Stale 恢复的算法逻辑

**ID-5: 修改 hand_control_node（重命名并泛化）**
- 包名：从 `omnihand_o10_control_node` 重命名为 `hand_control_node`（通用包）
- 移除：删除任何 `from omnihand_o10_*` 的导入
- 修改：订阅 Topic 从 `/{hand_id}_control/{side}/command` 改为订阅标准适配节点的下行输出 `/{hand_id}/{side}_hand/control_command`（原生维度）
- 修改：安全复核、硬限速器、状态机全部工作在原生维度（不再处理 22 DoF）
- 修改：`HandAdapter` 构造时传入 `hand_profile` 参数
- 保持不变：状态机逻辑、硬限速器算法、锁存故障机制

**等等，重新修正 ID-5**：

根据最终架构设计，控制层应该**完全工作在 22 DoF 接口**，维度转换由 HandAdapter 内部处理。让我修正：

**ID-5: 修改 hand_control_node（工作在 22 DoF）**
- 包名：从 `omnihand_o10_control_node` 重命名为 `hand_control_node`（通用包）
- 移除：删除任何 `from omnihand_o10_*` 的导入
- 修改：订阅 Topic 保持为 `/observation/{side}_hand/joint_states`（22 DoF 标准）
- 修改：安全复核、硬限速器全部工作在 22 DoF 空间
  - 限位检查：使用 `HandProfile.get_22dof_limits()`，返回 22 维限位（未激活关节 = ±inf）
  - 硬限速器：基准向量为 22 维，从配置文件的 `control.max_joint_rates_22d` 加载
  - 只对 `HandProfile.active_indices_in_22dof()` 返回的索引进行检查
- 修改：调用 `HandAdapter.send_command(JointTarget_22DoF)`，传入 22 DoF 命令
- 保持不变：状态机逻辑、锁存故障机制

**ID-6: 修改 HandAdapter 基类**
- 位置：`src/hand_adapter_interface/` 包
- 公开接口（22 DoF）：
  - `send_command(command: JointTarget_22DoF) → HardwareResponse[None]`
  - `read_feedback() → HardwareResponse[JointFeedback_22DoF]`
  - `query_errors() → HardwareResponse[JointError]`
- 内部私有方法（维度转换）：
  - `_translate_command_to_native(positions_22d: ndarray) → ndarray`：调用 `HandProfile.from_22dof_standard()`
  - `_translate_feedback_from_native(native_feedback: dict) → JointFeedback_22DoF`：调用 `HandProfile.to_22dof_standard()`
- 子类必须实现（原生维度）：
  - `_send_native_command(positions: ndarray) → HardwareResponse[None]`
  - `_read_native_feedback() → HardwareResponse[dict]`
- 构造函数：`__init__(hand_profile: HandProfile, side: str, **hw_params)`

**ID-7: 修改 AgilinkO10Backend**
- 位置：`src/omnihand_o10_hardware_adapter/omnihand_o10_hardware_adapter/o10_backend.py`
- 修改：继承新的 `HandAdapter` 基类，接收 `hand_profile` 参数
- 实现：`_send_native_command(positions_10d)` - 验证 10 维，调用 `sdk_hand.set_joint_positions()`
- 实现：`_read_native_feedback()` - 从 SDK 读取 10 维，返回 `{'positions': ndarray(10), 'velocities': ndarray(10), 'timestamp': float}`
- 移除：任何 22 DoF 转换逻辑（由父类处理）

### 配置文件格式

**ID-8: config/{hand_id}_hand.yaml 结构**
```yaml
hand_id: str                          # 手的唯一标识符（用于 topic 命名）

joints:
  names: list[str]                    # 原生关节名（N 个）
  right:
    lower_limits: list[float]         # N 维下限（弧度）
    upper_limits: list[float]         # N 维上限
  left:
    lower_limits: list[float]
    upper_limits: list[float]

geometry:
  right:
    palm_frame: str                   # 掌坐标系名称
    finger_roots: list[list[float]]   # 5×3 数组（米）
    chain_lengths: list[float]        # 5 个值（米）
    direction_mapping: list[list[float]]  # 3×3 矩阵
  left:
    # ... 同上

mapping_to_22dof:                     # 核心映射字段
  thumb_CMC_FE: int | null            # 标准关节名 → 原生索引（null = 无此关节）
  thumb_CMC_AA: int | null
  # ... 共 22 个标准关节名

model_assets:
  urdf:
    right: str                        # URDF 文件路径
    left: str
  mjcf: str | null                    # MJCF 文件路径（null = 无被动关节）
  provenance: str                     # provenance.json 路径

control:
  max_joint_rates: list[float]        # N 维速率限制（rad/s）
  stale_timeout_sec: float

hardware:
  backend_class: str                  # HandAdapter 类的完整路径
  transport: str                      # 通信方式（hcan/can/usb/...）
  device_id: int
  # ... 其他硬件参数
```

### 22 DoF 标准定义

**ID-9: STANDARD_22DOF_NAMES 全局常量**
- 位置：`hand_profile_interface/constants.py`
- 内容：
```python
STANDARD_22DOF_NAMES = (
    "thumb_CMC_FE", "thumb_CMC_AA", "thumb_MCP_FE", "thumb_MCP_AA", "thumb_DIP",
    "index_MCP_FE", "index_MCP_AA", "index_PIP", "index_DIP",
    "middle_MCP_FE", "middle_MCP_AA", "middle_PIP", "middle_DIP",
    "ring_MCP_FE", "ring_MCP_AA", "ring_PIP", "ring_DIP",
    "pinky_CMC_FE", "pinky_MCP_FE", "pinky_MCP_AA", "pinky_PIP", "pinky_DIP",
)
```
- 参考：团队架构规范（Sharpa Wave 22 DoF 定义）

### ROS Topic 命名规范

**ID-10: Topic 命名约定**
- 手套原始数据：`/mocap/{side}_hand/pose` (PoseArray, 21 poses)
- 原生维度命令：`/{hand_id}/{side}_hand/native_command` (JointState, N 维)
- 22 DoF 标准：`/observation/{side}_hand/joint_states` (JointState, 22 DoF)
- 原生维度控制：`/{hand_id}/{side}_hand/control_command` (JointState, N 维)
- 控制状态：`/{hand_id}_control/{side}/state` (ControlState)

**ID-11: Service 命名约定**
- 使能/禁用：`/{hand_id}_control/{side}/enable` (std_srvs/SetBool)
- 清除故障：`/{hand_id}_control/{side}/clear_fault` (std_srvs/Trigger)

### 数据流边界

**ID-12: Raw 边界（A05 约束）**
- 输入：Rokoko UDP (21 关键点)
- 输出：`/mocap/{side}_hand/pose`
- 稳定性：换手不影响此边界

**ID-13: 原生维度边界**
- 重定向输出：`/{hand_id}/{side}_hand/native_command` (N 维)
- 标准适配输入：订阅上述 Topic
- 变化：换手时 N 值变化（O10=10, L20=22）

**ID-14: 22 DoF 标准边界（团队规范）**
- 标准适配输出：`/observation/{side}_hand/joint_states` (22 维, 含 NaN)
- 控制层输入：订阅上述 Topic
- 稳定性：换手不影响此边界

### 架构门禁修订

**ID-15: 修订 A11（关节契约唯一 owner）**
- 旧规则：`omnihand_o10_contracts` 是 O10 关节契约的唯一 owner
- 新规则：每只手的 contracts 包或 HandProfile 配置是该手关节契约的唯一 owner
- 允许包：`omnihand_o10_contracts`、`linker_l20_profile`、...
- 测试：扫描所有包，确保关节名定义不重复

**ID-16: 新增 A28（配置单一来源）**
- 规则：设备 ID、速率限制、通信参数等配置项只能出现在 YAML 配置文件中，不得硬编码在启动脚本或 Python 代码中
- 测试：扫描 `scripts/` 和 Python 源码，检测硬编码的设备参数
- 例外：默认值可以在类定义中声明（如 `device_id: int = 1`），但生产使用时必须从配置覆盖

**ID-17: 保留其他架构门禁**
- A05：Raw 边界（手套 → 重定向）
- A06：软目标 wire（重定向 → 控制）
- A20/A25：节点/包 allowlist（换手时需更新）
- D54：硬件 SDK 隔离（只能在 HandAdapter 内调用）

## Testing Decisions

### 测试原则

**TD-1: 只测试外部行为，不测试实现细节**
- ✅ 测试：给定输入 Topic，验证输出 Topic 的格式和值
- ✅ 测试：给定配置文件，验证 HandProfile 返回的维度和映射结果
- ❌ 不测试：类的内部私有方法（通过公开接口间接覆盖）
- ❌ 不测试：算法的中间步骤（只测试最终输出）

**TD-2: 优先使用现有测试接缝**
- 系统测试接缝：`src/teleoperation_support/system_tests/` 中的 ROS 集成测试框架
- 架构门禁接缝：`src/teleoperation_support/architecture_tests/` 中的约束验证

### 单元测试

**TD-3: HandProfile 映射逻辑测试**
- 模块：`hand_profile_interface.ConfigDrivenHandProfile`
- 测试内容：
  - 给定 O10 配置文件，加载后 `joint_contract("right").dimension == 10`
  - 给定 O10 的 10 维输入 `[0.5, -0.3, 0.2, ...]`，`to_22dof_standard()` 输出 22 维且正确位置有值、其余为 NaN
  - 给定 22 维标准输入（含 NaN），`from_22dof_standard()` 提取出正确的 10 维
  - `active_indices_in_22dof()` 返回的索引列表与 `mapping_to_22dof` 配置一致
- 先例：`src/teleoperation_support/o10_model_assets/test/test_contract.py`

**TD-4: HandAdapter 维度转换测试**
- 模块：`hand_adapter_interface.HandAdapter`（通过 mock 子类）
- 测试内容：
  - 调用 `send_command(22维)` → 验证子类的 `_send_native_command` 收到正确的 10 维
  - 子类的 `_read_native_feedback()` 返回 10 维 → 验证 `read_feedback()` 返回 22 维
  - 边界情况：全 NaN 输入、部分 NaN 输入、全激活输入
- 先例：`src/omnihand_o10_hardware_adapter/test/test_provider_contract.py`

### 集成测试

**TD-5: 完整链路测试（手套 → 22 DoF 输出）**
- 测试范围：`rokoko_receiver` → `hand_retargeting` → `hand_standard_adapter` → `/observation/*/joint_states`
- 测试步骤：
  1. 发布模拟的手套数据（21 个 Pose）到 `/mocap/right_hand/pose`
  2. 等待重定向节点计算
  3. 订阅 `/observation/right_hand/joint_states`
  4. 验证输出是 22 维 JointState
  5. 验证 `msg.name == STANDARD_22DOF_NAMES`
  6. 验证激活位置有值（非 NaN），未激活位置为 NaN
- 先例：`src/teleoperation_support/system_tests/` 中的链路测试

**TD-6: 控制层 22 DoF 接口测试**
- 测试范围：`hand_control` 节点订阅 → 安全复核 → HandAdapter 发送
- 测试步骤：
  1. 发布 22 DoF 命令到 `/observation/right_hand/joint_states`
  2. Mock HandAdapter，记录收到的命令
  3. 验证 HandAdapter 的 `send_command` 收到 22 维输入
  4. 验证安全复核拒绝超限的命令（只检查激活索引）
  5. 验证硬限速器正确限速（22 维空间）
- 先例：`src/omnihand_o10_control_node/test/` 中的控制层测试

### 架构门禁测试

**TD-7: A11 门禁测试（关节契约唯一 owner）**
- 测试：扫描所有包，查找定义关节名列表的位置
- 验证：每只手的关节名只在一个地方定义（contracts 包或 HandProfile 配置）
- 失败示例：`hand_retargeting` 和 `hand_control` 都定义了 `ACTIVE_JOINT_NAMES`
- 先例：`src/teleoperation_support/architecture_tests/test/test_architecture_gates.py`

**TD-8: A28 门禁测试（配置单一来源）**
- 测试：扫描 `scripts/` 和 `src/*/` 中的 Python/Bash 代码
- 验证：设备 ID、速率限制、端口号等配置项不硬编码在代码中
- 允许：默认值声明（如 `device_id: int = 1`），但必须可被配置覆盖
- 失败示例：`start_omnihand_control.sh` 中 `hand_device_id=1` 硬编码
- 先例：架构门禁测试框架（新增）

**TD-9: 22 DoF 格式验证测试**
- 测试：订阅 `/observation/*/joint_states`，验证消息格式
- 验证：
  - `len(msg.name) == 22`
  - `msg.name == list(STANDARD_22DOF_NAMES)`
  - `len(msg.position) == 22`
  - 激活位置的值在合理范围内（-π 到 π）
  - 未激活位置为 `math.isnan()`
- 先例：系统测试中的 Topic 格式验证

### 回归测试

**TD-10: O10 零回归测试**
- 测试：使用重构后的架构，运行 O10 的完整链路
- 验证：
  - 重定向输出的关节角度与重构前误差 < 1e-6
  - 控制层的限速行为与重构前一致
  - 硬件命令的维度和值与重构前一致
- 数据源：使用 `runs/` 中的历史录制数据回放
- 先例：票据 05/06 中的对照实验方法

## Out of Scope

1. **按新架构实施代码重构**：本 spec 只定义架构设计和接口契约，实际的代码重构工作是下一个 effort（另开新票据）
2. **第二只手的实际接入**：Linker L20 或其他新手的实际 SDK 集成、配置编写、真机测试不在本 spec 范围
3. **性能优化**：维度转换的性能开销、22 DoF 数组的内存占用优化不在本 spec 考虑
4. **Launchpad UI 的 22 DoF 适配**：前端显示 22 条曲线、灰显 NaN 的 UI 改造是独立工作
5. **MCAP 录制格式迁移**：已有的 10 维录制数据如何转换为 22 DoF 格式，需要单独的迁移工具
6. **其他手套品牌适配**：当前只设计 Rokoko 手套的 Raw 边界，其他手套（如 Cyberglove）的接入不在范围
7. **中段算法改进**：IK 求解器、滤波器、Stale 恢复机制的算法优化不在本 spec 范围
8. **多手协同**：两只不同型号的灵巧手（如左手 O10 + 右手 L20）的混合使用场景暂不考虑

## Further Notes

### 与票据 7.2 约束的对齐

本 spec 继承票据 7.2（现有 spec 约束盘点）的全部 22 组必须继承项，包括：
- 分层与所有权（D1/A20/A25）
- Raw 边界（A05）
- 软目标 wire（A06）
- 控制安全机制（K02/K06）
- 硬件隔离（D54）

本 spec 取代票据 7.2 的 10 项可取代清单：
- 关节契约 → HandProfile 配置
- 模型资产 → HandProfile 资产路径
- 耦合模型 → HandProfile.coupling_model()
- FK/IK 后端 → HandProfile.kinematics_port()

本 spec 裁决票据 7.2 的 8 项待决策（D1-D8）：
- D1：模块形态 = support 包 + 独立适配节点
- D2：wire 契约 = 保守策略（平行 topic）
- D3：A11 owner = per-hand contracts 包或配置
- D4：拇指专调 = 配置化（移入 RetargetingConfig）
- D5：触觉 Port = 保留为可选
- D6：诊断字段 = 字段级参数化
- D7：Launchpad = 同构替换（数据驱动）
- D8：ARCHITECTURE.md = 推迟到票据 10

### 实施优先级建议

1. **阶段 1（基础设施）**：实现 HandProfile 接口和 ConfigDrivenHandProfile 类
2. **阶段 2（适配层）**：实现 hand_standard_adapter_node
3. **阶段 3（重定向层解耦）**：修改 hand_retargeting 输出原生维度
4. **阶段 4（控制层 22 DoF 化）**：修改 hand_control 和 HandAdapter 基类
5. **阶段 5（O10 迁移）**：修改 AgilinkO10Backend，编写 O10 配置文件
6. **阶段 6（验证）**：端到端测试，零回归验证

### 关键风险

**风险 1：NaN 在 ROS 消息中的支持**
- sensor_msgs/JointState 的 `position` 字段是 `float64[]`，需要验证 ROS 2 序列化是否正确处理 NaN
- 缓解：早期原型验证，如有问题改用特殊值（如 `1e9`）或独立的 `valid` 位掩码

**风险 2：22 DoF 限速器的性能**
- 22 维数组的硬限速器计算量是 10 维的 2.2 倍
- 缓解：只对激活索引计算，实际计算量不变（O10 仍然只处理 10 个关节）

**风险 3：配置文件格式演进**
- 随着支持更多手型，`mapping_to_22dof` 字段可能需要更复杂的表达（如区间映射）
- 缓解：当前设计支持简单的 1:1 映射，未来可扩展为 `{"target_index": source_spec}` 格式

### 参考文献

- 团队架构规范：22 DoF 定义（Sharpa Wave）
- 票据 7.1：业界调研（ros2_control、MoveIt、Drake、dex-retargeting）
- 票据 7.2：现有 spec 约束盘点
- wayfinder/research/07-hand-adapter-architecture-design-v2.md：完整架构设计文档

---

**下一步**：用户审查本 spec，确认后进入实施阶段（票据 13+）。
