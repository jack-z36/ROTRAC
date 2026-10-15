# Wayfinder 子地图：换手适配器架构边界与接口设计

`label: wayfinder:map` · 父票据：[07-hand-adapter-boundaries](../tickets/07-hand-adapter-boundaries.md) · 建图时间：2026-01-13

## Destination（终点）

完整定义换手适配器的模块边界与接口契约设计，产出：

1. **模块划分图**：清晰标识手侧适配层、手套侧适配层、中段处理层的边界与职责
2. **接口签名草案**：每个适配层的输入输出契约、错误处理、反馈机制
3. **换手清单雏形**：更换一款灵巧手需要修改的模块、配置、资产的完整列表
4. **配置收口方案**：统一配置源的设计决策

这些产出将直接支撑票据 08/09 撰写正式 spec 文档。

## Notes（约定）

- 本子地图从父地图票据 07 拆解而来，解决其中的架构设计任务
- 领域：灵巧手遥操作重定向架构设计（非实施）
- HITL 票（grilling/prototype）必须与用户真人对话
- Research 票可并行执行（通过 subagent）
- 每个 session 最多解决一张非 research 票
- 侦察基础：票据 01 已给出换手耦合集中在五处（contracts.joints、MJCF、URDF、backends.py、触觉分区）+ 手套侧一个包 + 中段残余耦合
- 全程中文

## Tickets（票据列表）

### 可立即启动（frontier，无依赖）
- [7.3 手套侧契约冻结决策](../tickets/07.3-glove-contract-decision.md) - **grilling**，需 HITL
- [7.4 HandProfile/HandAdapter 接口原型](../tickets/07.4-hand-adapter-prototype.md) - **prototype**，HITL，已随 7.1 关票解锁

### 依赖关系（按拓扑排序）
- [7.4 HandProfile/HandAdapter 接口原型](../tickets/07.4-hand-adapter-prototype.md) - **prototype**，blocked by 7.1（已解锁）
- [7.5 中段去耦策略定案](../tickets/07.5-middle-layer-decoupling.md) - **grilling**，blocked by 7.4
- [7.6 配置单一来源收口决策](../tickets/07.6-config-consolidation.md) - **grilling**，blocked by 7.4, 7.5
- [7.7 绘制模块边界图](../tickets/07.7-draw-boundary-diagram.md) - **task**，blocked by 7.3, 7.4, 7.5
- [7.8 汇总换手清单与接口签名草案](../tickets/07.8-consolidate-artifacts.md) - **task**，blocked by 7.3, 7.4, 7.5, 7.6, 7.7

### 工作流可视化
```
并行启动（session 1-3）:
  7.1 (research) ──┐
  7.2 (research) ──┼─> 调研完成后开始设计
  7.3 (grilling)   │
                   ↓
  7.4 (prototype) ←┘  依赖 7.1
                   ↓
  7.5 (grilling)  ←┘  依赖 7.4
                   ↓
  7.6 (grilling)  ←┴─  依赖 7.4, 7.5
                   ↓
  7.7 (task)      ←┴─  依赖 7.3, 7.4, 7.5
                   ↓
  7.8 (task)      ←┴─  依赖 7.3, 7.4, 7.5, 7.6, 7.7（汇总所有决策）
```

**并行工作建议**：
- **Wave 1**（3 个 session 并行）：7.1 + 7.2（research，subagent）+ 7.3（grilling，HITL）
- **Wave 2**（1 session）：7.4（prototype，依赖 7.1）
- **Wave 3**（2 sessions 并行）：7.5 + 7.6（grilling，均依赖 7.4）
- **Wave 4**（1 session）：7.7（task，依赖 7.3/7.4/7.5）
- **Wave 5**（1 session）：7.8（汇总，依赖所有前序票据）

## Decisions so far（已决索引）

- [现有架构模式调研：业界手适配器设计](../tickets/07.1-hand-adapter-survey.md)：ros2_control（lifecycle+read/write+URDF 声明插件+pluginlib）/ MoveIt 2（ControllerManager 抽象+YAML 控制器清单+SRDF 语义组）/ Drake（driver 只接线、controller 做语义翻译）三大先例；关键事实：URDF mimic 与 MJCF tendon 均只支持线性耦合，本项目非线性多项式需自定义扩展；dex-retargeting per-hand YAML 是"换手只换配置"最贴近先例；13 条模式→耦合点对照表供 7.4/7.5/7.6 取用。全文见 [research/07.1](../research/07.1-hand-adapter-survey.md)
- [盘点现有 spec 约束与不变量](../tickets/07.2-existing-spec-constraints.md)：权威其实是 `DOCS/03_工程/01_Rokoko…Spec.md`+`08_Launchpad…Spec.md` 与 `DOCS/01_知识/ARCHITECTURE.md` 的 A01–A27（票据原注的 01_Spec 目录与 A11/A12 含义均纠偏）；约束三档分类 = 必须继承 22 组 / 可取代 10 项 / 待决策 D1–D8（关键：模块边界 vs A20/A25 门禁、wire 契约 10 维泛化）；12 耦合点中 7 个被成文锁定、4 个属约定俗成（→ 7.5/7.6 直接标的）。全文见 [research/07.2](../research/07.2-existing-spec-constraints.md)

## Not yet specified（雾区）

- **与现有 spec 的继承关系细化**：已由票据 7.2 盘点出待决策清单 D1–D8（见 [research/07.2](../research/07.2-existing-spec-constraints.md)），其中 D1（模块边界 vs A20/A25 门禁）、D2（wire 契约维度泛化）将在 7.4/7.5/7.6 中裁决；其余 D 项随相应票据处理
- **第二只手的实证验证**：设计是否真正支持"只改少数模块"，需引入第二只手 SDK 验证（时机未定）

## Out of scope（范围外）

- **按架构设计实施代码重构**：本子图只产出设计决策与文档草案，不写实施代码
- **性能优化与实时性调优**：架构设计阶段不涉及性能指标
- **其他手套品牌适配**：当前只设计 Rokoko 手套侧契约
