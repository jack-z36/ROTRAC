# 换手适配器架构设计方案（v2 修订版）

> 票据 07 完整设计产出 · 2026-01-15 · **修订版：对齐 22 DoF 规范**
>
> **修订原因**：根据团队架构规范，所有手的接口必须统一为 22 DoF 标准格式

---

## 执行摘要

**核心策略**：将 O10 专属的三处硬绑定（关节契约、模型资产、硬件后端）收拢为可替换的适配层，并增加 **22 DoF 标准映射层**，使所有手的接口统一。

**与 v1 的关键差异**：

- ✅ **新增**：22 DoF 标准映射（`to_22dof_standard` / `from_22dof_standard`）
- ✅ **修改**：所有 Topic 统一使用 22 DoF（包含 NaN 填充）
- ✅ **修改**：控制层适配 22 维输入输出

**换手工作量承诺**：

1. ✅ **零修改**：`hand_retargeting_node`、`omnihand_o10_control_node` 的算法逻辑
2. ✅ **零修改**：中段算法（IK、滤波、stale 恢复）
3. 🔄 **新增替换**：提供新手的配置文件（含 22 DoF 映射）+ HandAdapter 实现
4. 🔄 **配置文件更新**：启动脚本、launchpad YAML

---

## 一、22 DoF 标准规范（约束来源）

### 1.1 规范要求

根据团队架构设计规范：

```
/observation/{side}_hand/joint_states  →  sensor_msgs/JointState (22 DoF)
```

**22 DoF 标准关节定义**（参考 Sharpa Wave）：

| Index | 标准关节名        | 描述                     |
| ----- | ----------------- | ------------------------ |
| 0     | thumb_CMC_FE      | 拇指 CMC 屈伸 (0-50°)   |
| 1     | thumb_CMC_AA      | 拇指 CMC 外展 (0-10°)   |
| 2     | thumb_MCP_FE      | 拇指 MCP 屈伸 (0-30°)   |
| 3     | thumb_MCP_AA      | 拇指 MCP 外展 (0-10°)   |
| 4     | thumb_DIP         | 拇指 DIP 屈伸 (0-40°)   |
| 5     | index_MCP_FE      | 食指 MCP 屈伸 (0-20°)   |
| 6     | index_MCP_AA      | 食指 MCP 外展 (-20~20°) |
| 7     | index_PIP         | 食指 PIP 屈伸 (0-20°)   |
| 8     | index_DIP         | 食指 DIP 屈伸 (0-20°)   |
| 9-12  | middle_*          | 中指 4 DoF               |
| 13-16 | ring_*            | 无名指 4 DoF             |
| 17    | pinky_CMC_FE      | 小指 CMC 屈伸 (0-10°)   |
| 18-21 | pinky_MCP/PIP/DIP | 小指 4 DoF               |

### 1.2 约束条件

1. ✅ **所有手的主动关节数 ≤ 22**（不会超出覆盖）
2. ✅ **未激活的关节位置填 NaN**
3. ✅ **控制命令、录制、可视化统一使用 22 DoF**

---

## 二、HandProfile 接口设计（修订版）

### 2.1 新增接口方法

```python
class HandProfile(ABC):
    """灵巧手的完整静态描述"""
  
    # ===== 原有方法（保持不变）=====
  
    @property
    @abstractmethod
    def hand_id(self) -> str:
        """手的唯一标识符"""
        pass
  
    @abstractmethod
    def joint_contract(self, side: str) -> JointContract:
        """获取单侧关节契约（手的原生维度）"""
        pass
  
    @abstractmethod
    def geometry(self, side: str) -> HandGeometry:
        """获取单侧几何参数"""
        pass
  
    @abstractmethod
    def coupling_model(self, side: str) -> CouplingModel:
        """获取单侧耦合模型"""
        pass
  
    @abstractmethod
    def kinematics_port(self, side: str) -> FingerKinematicsPort:
        """获取单侧 FK/IK 端口"""
        pass
  
    # ===== 新增：22 DoF 标准映射 =====
  
    @abstractmethod
    def to_22dof_standard(
        self,
        native_joints: np.ndarray,  # 手的原生维度（10/16/22/...）
        side: str
    ) -> StandardJointState:
        """将手的原生关节映射到 22 DoF 标准格式
      
        Args:
            native_joints: 手的原生关节位置（如 O10 = 10 维）
            side: "left" 或 "right"
      
        Returns:
            StandardJointState:
                names: 22 个标准关节名（固定顺序）
                positions: 22 维数组（未激活关节 = NaN）
        """
        pass
  
    @abstractmethod
    def from_22dof_standard(
        self,
        standard_joints: np.ndarray,  # 22 维标准
        side: str
    ) -> np.ndarray:
        """从 22 DoF 标准格式提取手的原生关节命令
      
        Args:
            standard_joints: 22 维标准关节位置（含 NaN）
            side: "left" 或 "right"
      
        Returns:
            native_joints: 手的原生维度（如 O10 = 10 维）
        """
        pass
  
    @abstractmethod
    def active_indices_in_22dof(self, side: str) -> list[int]:
        """返回该手在 22 DoF 中激活的索引
      
        用于控制层判断哪些关节需要限速/限位检查
      
        Returns:
            [2, 7, 8, 11, 13, 15, 18, 20, 21]  # 示例：O10 激活的 9 个
        """
        pass
```

### 2.2 数据结构

```python
@dataclass(frozen=True)
class StandardJointState:
    """22 DoF 标准关节状态"""
    names: tuple[str, ...]       # 固定 22 个标准关节名
    positions: np.ndarray        # 22 维，未激活 = NaN


# 22 DoF 标准关节名（全局常量）
STANDARD_22DOF_NAMES = (
    "thumb_CMC_FE", "thumb_CMC_AA", "thumb_MCP_FE", "thumb_MCP_AA", "thumb_DIP",
    "index_MCP_FE", "index_MCP_AA", "index_PIP", "index_DIP",
    "middle_MCP_FE", "middle_MCP_AA", "middle_PIP", "middle_DIP",
    "ring_MCP_FE", "ring_MCP_AA", "ring_PIP", "ring_DIP",
    "pinky_CMC_FE", "pinky_MCP_FE", "pinky_MCP_AA", "pinky_PIP", "pinky_DIP",
)
```

### 2.3 通用实现（数据驱动）

```python
class ConfigDrivenHandProfile(HandProfile):
    """数据驱动的通用 HandProfile，所有参数从 YAML 配置加载"""
  
    def __init__(self, config_path: str):
        import yaml
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
      
        # 验证 22 DoF 映射配置
        if "mapping_to_22dof" not in self.config:
            raise ValueError("Config missing 'mapping_to_22dof' field")
  
    # ... 原有方法实现（joint_contract, geometry 等）...
  
    def to_22dof_standard(
        self,
        native_joints: np.ndarray,
        side: str
    ) -> StandardJointState:
        """O10 (10维) → 22 DoF 标准"""
        mapping = self.config["mapping_to_22dof"]
      
        # 初始化为 NaN
        standard_positions = np.full(22, np.nan)
      
        # 映射激活的关节
        for std_idx, std_name in enumerate(STANDARD_22DOF_NAMES):
            native_idx = mapping.get(std_name)
            if native_idx is not None:
                standard_positions[std_idx] = native_joints[native_idx]
      
        return StandardJointState(
            names=STANDARD_22DOF_NAMES,
            positions=standard_positions
        )
  
    def from_22dof_standard(
        self,
        standard_joints: np.ndarray,
        side: str
    ) -> np.ndarray:
        """22 DoF 标准 → O10 (10维)"""
        mapping = self.config["mapping_to_22dof"]
        native_dim = self.joint_contract(side).dimension
        native_positions = np.zeros(native_dim)
      
        # 逆映射：从标准提取原生关节
        for std_idx, std_name in enumerate(STANDARD_22DOF_NAMES):
            native_idx = mapping.get(std_name)
            if native_idx is not None and not np.isnan(standard_joints[std_idx]):
                native_positions[native_idx] = standard_joints[std_idx]
      
        return native_positions
  
    def active_indices_in_22dof(self, side: str) -> list[int]:
        """返回 O10 在 22 DoF 中激活的索引"""
        mapping = self.config["mapping_to_22dof"]
        active_indices = []
      
        for std_idx, std_name in enumerate(STANDARD_22DOF_NAMES):
            if mapping.get(std_name) is not None:
                active_indices.append(std_idx)
      
        return active_indices
```

### 2.4 配置文件示例（O10）

```yaml
# config/o10_hand.yaml

hand_id: o10

joints:
  names:
    - thumb_roll      # 原生索引 0
    - thumb_abad      # 原生索引 1
    - thumb_mcp       # 原生索引 2
    - index_abad      # 原生索引 3
    - index_pip       # 原生索引 4
    - middle_pip      # 原生索引 5
    - ring_abad       # 原生索引 6
    - ring_pip        # 原生索引 7
    - pinky_abad      # 原生索引 8
    - pinky_pip       # 原生索引 9
  
  right:
    lower_limits: [-0.0297, -1.6424, 0.0, -0.1641, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    upper_limits: [1.1214, 0.0454, 0.8416, 0.0, 1.4835, 1.4835, 0.1693, 1.4835, 0.1850, 1.4835]
  
  left:
    lower_limits: [-1.1214, -0.0454, -0.8416, 0.0, 0.0, 0.0, -0.1693, 0.0, -0.1850, 0.0]
    upper_limits: [0.0297, 1.6424, 0.0, 0.1641, 1.4835, 1.4835, 0.0, 1.4835, 0.0, 1.4835]

# ===== 新增：22 DoF 映射 =====
mapping_to_22dof:
  # 格式：标准关节名 → O10 原生索引（null 表示 O10 无此关节）
  thumb_CMC_FE: null       # O10 无，填 NaN
  thumb_CMC_AA: null
  thumb_MCP_FE: 2          # O10 的 thumb_mcp → 标准 index 2
  thumb_MCP_AA: null
  thumb_DIP: null
  index_MCP_FE: null
  index_MCP_AA: 3          # O10 的 index_abad → 标准 index 6
  index_PIP: 4
  index_DIP: null
  middle_MCP_FE: null
  middle_MCP_AA: null
  middle_PIP: 5
  middle_DIP: null
  ring_MCP_FE: null
  ring_MCP_AA: 6
  ring_PIP: 7
  ring_DIP: null
  pinky_CMC_FE: null
  pinky_MCP_FE: null
  pinky_MCP_AA: 8
  pinky_PIP: 9
  pinky_DIP: null

# O10 激活的 22 DoF 索引：[2, 6, 7, 10, 13, 15, 18, 20, 21]
# （配置中有值的对应标准索引）

geometry:
  # ... 同 v1

model_assets:
  # ... 同 v1

control:
  # ⚠️ 注意：max_joint_rates 仍然是原生维度（10 维）
  max_joint_rates: [3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0, 3.0]

hardware:
  # ... 同 v1
```

---

## 三、中段重定向层适配

### 3.1 输出 22 DoF 标准格式

```python
# hand_retargeting_node/adapters/ros_node.py

class RetargetingNode:
    def __init__(self, hand_profile: HandProfile):
        self.hand_profile = hand_profile
      
        # 发布 22 DoF 标准 Topic
        self.pub_left = self.create_publisher(
            JointState,
            "/observation/left_hand/joint_states",
            10
        )
        self.pub_right = self.create_publisher(
            JointState,
            "/observation/right_hand/joint_states",
            10
        )
  
    def publish_command(self, side: str, native_joints: np.ndarray):
        """发布命令（映射到 22 DoF）"""
      
        # 1. 映射到 22 DoF 标准
        standard = self.hand_profile.to_22dof_standard(native_joints, side)
      
        # 2. 构造 ROS 消息
        msg = JointState()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.name = list(standard.names)  # 固定 22 个名称
        msg.position = standard.positions.tolist()  # 含 NaN
        msg.velocity = []  # 空
        msg.effort = []    # 空
      
        # 3. 发布
        if side == "left":
            self.pub_left.publish(msg)
        else:
            self.pub_right.publish(msg)
```

---

## 四、控制层适配

### 4.1 订阅 22 DoF 输入

```python
# omnihand_o10_control_node/adapters/ros_node.py

class ControlNode:
    def __init__(self, hand_profile: HandProfile):
        self.hand_profile = hand_profile
      
        # 订阅 22 DoF 标准 Topic
        self.sub = self.create_subscription(
            JointState,
            "/observation/right_hand/joint_states",
            self.command_callback,
            10
        )
      
        # 激活的索引（用于限速/限位检查）
        self.active_indices = hand_profile.active_indices_in_22dof("right")
  
    def command_callback(self, msg: JointState):
        """接收 22 DoF 命令"""
      
        # 1. 验证格式
        if len(msg.position) != 22:
            self.get_logger().error("Expected 22 DoF, got {}".format(len(msg.position)))
            return
      
        standard_joints = np.array(msg.position)
      
        # 2. 安全复核（只检查激活的关节）
        for idx in self.active_indices:
            if np.isnan(standard_joints[idx]):
                self.get_logger().error(f"Active joint {idx} is NaN!")
                return
      
        # 3. 硬限速器（22 维，NaN 位置跳过）
        limited_22d = self.rate_limiter.limit(standard_joints, self.active_indices)
      
        # 4. 映射回原生维度（O10 = 10 维）
        native_command = self.hand_profile.from_22dof_standard(limited_22d, "right")
      
        # 5. 发送给 HandAdapter
        self.hardware_adapter.send_command(JointTarget(positions=native_command))
```

### 4.2 硬限速器适配

```python
class RateLimiter:
    def __init__(self, max_rates_native: np.ndarray, hand_profile: HandProfile, side: str):
        """初始化限速器
      
        Args:
            max_rates_native: 原生维度的速率限制（10 维 for O10）
            hand_profile: 用于映射
            side: 侧别
        """
        self.hand_profile = hand_profile
        self.side = side
      
        # 将原生速率映射到 22 DoF
        self.max_rates_22d = np.full(22, np.inf)  # 默认无限制
        active_indices = hand_profile.active_indices_in_22dof(side)
      
        for native_idx, rate in enumerate(max_rates_native):
            # 找到该原生关节对应的 22 DoF 索引
            std_idx = self._native_to_std_index(native_idx)
            if std_idx is not None:
                self.max_rates_22d[std_idx] = rate
      
        self.last_command_22d = None
        self.last_timestamp = None
  
    def limit(self, command_22d: np.ndarray, active_indices: list[int]) -> np.ndarray:
        """限速（22 维输入输出）"""
        if self.last_command_22d is None:
            # 首次调用，需要初始化
            return command_22d
      
        dt = self.get_dt()
        limited = command_22d.copy()
      
        # 只对激活的关节限速
        for idx in active_indices:
            if not np.isnan(command_22d[idx]):
                delta = command_22d[idx] - self.last_command_22d[idx]
                max_delta = self.max_rates_22d[idx] * dt
                limited[idx] = self.last_command_22d[idx] + np.clip(delta, -max_delta, max_delta)
      
        self.last_command_22d = limited
        self.last_timestamp = time.time()
        return limited
```

---

## 五、换手清单（修订版）

### 5.1 ✅ 不改（零修改承诺）

| 模块     | 文件/包                                                   | 理由                             |
| -------- | --------------------------------------------------------- | -------------------------------- |
| 手套接收 | `rokoko_hand_receiver_node/`                            | Raw 边界不变，输出仍是 21 关键点 |
| 中段算法 | `hand_retargeting_node/core/`（IK/滤波/stale）          | 算法手无关，只是输出时映射       |
| 控制算法 | `omnihand_o10_control_node/application/`（状态机/限速） | 逻辑不变，输入输出增加映射       |
| 启动监控 | `production_bringup/launchpad/`                         | 框架不变                         |

### 5.2 🔄 新增替换（每换一只手）

| 类别                  | 必需产出                                         | 工作量   |
| --------------------- | ------------------------------------------------ | -------- |
| **配置文件**    | `config/{hand_id}_hand.yaml`（含 22 DoF 映射） | 1-2 小时 |
| **模型资产**    | URDF + MJCF + provenance.json                    | 1-2 小时 |
| **HandAdapter** | ~150 行 SDK 调用代码                             | 2-3 小时 |

### 5.3 ⚠️ 修改（受影响需同步）

| 位置                   | 修改内容                                | 原因             |
| ---------------------- | --------------------------------------- | ---------------- |
| **wire schema**  | 确认`sensor_msgs/JointState` 支持 NaN | 标准格式包含 NaN |
| **Launchpad UI** | 显示 22 条曲线，灰显未激活关节          | 可视化适配       |
| **MCAP 录制**    | 统一录制 22 DoF                         | 回放兼容性       |

---

## 六、验收标准

| # | 标准                   | 验证方法                                                                |
| - | ---------------------- | ----------------------------------------------------------------------- |
| 1 | O10 输出严格 22 DoF    | rostopic echo`/observation/right_hand/joint_states`，验证 22 维 + NaN |
| 2 | 控制层接受 22 DoF 输入 | 发送 22 维命令，验证只有激活关节生效                                    |
| 3 | 配置驱动映射           | 修改`mapping_to_22dof`，验证输出变化                                  |
| 4 | 换手零回归             | L20 配置 22 DoF 映射后，测试全链路                                      |

---

## 附录 A：设计决策记录（修订）

### D0：22 DoF 标准强制（新增）

**决策**：所有手的接口统一为 22 DoF 标准格式，未激活关节填 NaN。

**理由**：

1. 符合团队架构规范
2. 录制/回放/可视化统一格式
3. 控制层接口稳定（不随换手改变）

**实施**：

- HandProfile 新增 `to_22dof_standard` / `from_22dof_standard`
- 配置文件新增 `mapping_to_22dof` 字段
- 控制层适配 22 维输入输出

---

**下一步**：用户审查修订方案，确认 22 DoF 映射策略。
