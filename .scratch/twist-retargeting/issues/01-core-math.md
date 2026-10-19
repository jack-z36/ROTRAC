# 01: 扭转纯核心与数学验证

**What to build:** 一个与 ROS、Pinocchio、NLopt 无关的纯扭转核心：三指捏合门控、人手螺旋轴与累积转角、机器人三指参考、四项目标函数、解析梯度、固定迭代投影梯度和有效性门。工作树已有主体实现；本票负责按 spec 复核、补齐梯度覆盖并验收。

**Blocked by:** None

**Status:** resolved

- [x] 门控迟滞、无效帧不更新、伸展下限排除握拳。
- [x] 人手意图锁存、两条边平均、累积、裁剪、跨 re-grasp 和 `theta_base`。
- [x] 四项目标项和维度归一化可独立观察。
- [x] 解析梯度与离线中心差分一致，覆盖 6 个关节、左右手、多个状态和边界附近。
- [x] trust region、回溯、提前停止和失败回退。
- [x] `.venv` 纯核心测试全绿，核心不导入 ROS/Pinocchio/NLopt。

## Resolution

- `core/twist.py` 的孔径改为按冻结三指尺度归一化（此前实现直接比较原始距离，违反 spec §3）。
- `test_twist_core.py` 扩到 19 项：左右手多状态中心差分、参考锁存/退化、法向符号对齐、四条目标项与尺度归一化、step/trust region、提前停止、非有限/限位/退化回退、核心导入白名单。
- 运行：`ROS_DOMAIN_ID=79 python3.12 -m pytest test/test_twist_core.py test/test_twist_session.py`（`hand_retargeting_node` 目录，source ROS + install），全绿。
