---
id: 7
title: 换手适配器架构设计
type: task
labels: [wayfinder:task]
status: in-progress
assignee: session-2026-01-15
blocked-by: []
---

## Task

基于票据 7.1（业界调研）和 7.2（约束盘点），设计完整的换手适配器架构，定义模块边界、接口契约、配置收口方案，并汇总换手清单。

**核心目标**：尽可能减少更换灵巧手硬件带来的工作量。

**任务范围**（整合原票据 07-09 的所有设计工作）：

1. **模块边界设计**：
   - 定义四层架构（手套侧/中段/控制/硬件）
   - 明确每层职责与稳定边界
   - 设计 HandProfile + HandAdapter 抽象层

2. **接口契约设计**：
   - HandProfile 接口签名（关节契约/几何/耦合/FK-IK）
   - HandAdapter 接口签名（命令/反馈/错误/新读取）
   - 层间 Topic/Service 契约

3. **中段去耦方案**：
   - 删除 21 节点镜像（contracts.py）
   - 依赖注入重构（RetargetingSession）
   - 拇指专调配置化

4. **配置收口方案**：
   - 统一配置文件 `config/{hand_id}_params.yaml`
   - 启动脚本读取配置（消除硬编码）
   - 新增 A28 门禁

5. **决策裁定**（解决 7.2 的 D1-D8）：
   - D1：模块形态（support 包 vs 新节点）
   - D2：wire 契约泛化（保守 vs 参数化）
   - D3：A11 owner 落点
   - D4-D8：其他待决策项

6. **换手清单汇总**：
   - 不改清单（零修改承诺）
   - 新增替换清单（每换一手必做）
   - 修改清单（受影响需同步）

**产出**：

完整的架构设计文档（已产出：`research/07-hand-adapter-architecture-design.md`），包含：

1. ✅ 执行摘要（换手工作量承诺）
2. ✅ 四层架构边界图
3. ✅ HandProfile 接口签名（Python 伪代码）
4. ✅ HandAdapter 接口签名（复用现有）
5. ✅ 中段去耦方案（依赖注入重构）
6. ✅ 配置收口策略（YAML + 启动脚本）
7. ✅ 模块边界 Mermaid 图
8. ✅ 换手清单三列表（不改/新增/修改）
9. ✅ 设计决策记录（D1-D8 全部裁决）
10. ✅ 实施路线图（5 阶段）
11. ✅ 业界模式映射表
12. ✅ 与 7.2 约束的完整对照

**参考资料**：
- ✅ [票据 7.1：业界调研](../research/07.1-hand-adapter-survey.md)
- ✅ [票据 7.2：约束盘点](../research/07.2-existing-spec-constraints.md)
- ✅ [票据 01：耦合点清单](01-pipeline-inventory.md)

**下一步**：
- 用户审查设计方案
- 启动票据 10（spec review），基于本设计撰写正式 spec 文档
