# Wayfinder 归档目录

本目录存放已废弃或过时的票据和研究文档，防止未来的 agent 加载错误版本导致理解偏差。

## 归档原则

1. **已废弃的设计**：被新版本取代的架构设计文档
2. **临时票据**：grilling 过程中的临时探索票据
3. **过时的调研**：已被新决策覆盖的调研报告

## 当前归档内容

### research/
- `07-hand-adapter-architecture-design-v1-deprecated.md` - 旧版架构设计（未对齐 22 DoF 规范）
  - **为何归档**：该版本未考虑团队的 22 DoF 标准规范，维度转换逻辑耦合在业务节点中
  - **被取代**：`research/07-hand-adapter-architecture-design-final.md`（v2 修订版，对齐 22 DoF 规范，独立适配节点，HandAdapter 内部处理维度转换）

### tickets/
- `archive-old-07-design/` - 票据 07 的早期草稿（已在 v2 整合）

---

**⚠️ 注意**：归档内容仅供历史追溯，不应作为实施依据。所有当前有效的决策请查看 `wayfinder/map.md` 的 "Decisions so far" 索引。
