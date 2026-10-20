# 01: 换手架构 spec 对抗评审与定稿

**What to build:** 对 `.scratch/hand-swap/spec.md`（22 DoF 换手架构 spec 草案，47 用户故事）做对抗性评审与修复，最终与用户 HITL 定稿。接替原 wayfinder 票 10（其 08/09 前置已作废：spec 已由票 12 直接产出）。

**Blocked by:** None (can start immediately)

**Status:** resolved（2026-10-19 HITL 定稿）

- [x] 派 `adversarial-reviewer` 攻击 spec：构造"两模块各自完全遵守条文却仍不兼容"场景（候选攻击面：HandProfile 与中段 IK 对 DOF/关节序的假设冲突、手套契约与归一化对节点命名的假设冲突、配置单一来源与 launch 覆盖顺序的歧义、22 DoF NaN 语义在控制层/录制层的边界）→ `review-01-adversarial.md`（19 项：阻断 5/高 6/中 6/低 2，裁决 FAIL）
- [x] 逐条修复评审发现并回写 spec；不接受的发现记录豁免理由 → spec v1.1 Final（19/19 处置：无豁免，2 项延期到实施 effort；对照表见 spec 附录 E）。核心裁定 HS-1..HS-11：拓扑为"目标面 /observation + 专用 22D 命令面 final_command + 22D 反馈面、适配节点三通道、Provider 独立节点持原生 HandAdapter"；删 enable Service
- [x] 涉外部事实的断言（SDK 行为、ROS 2 对 NaN 的序列化、版本兼容）交 `tech-fact-checker` / `web-researcher` 核实 → `review-02-factcheck.md`（NaN 链路位级保真成立——ADR-0015 风险关闭；JSON 边界禁 NaN；NaN 无生态先例=自定约定；Sharpa Wave 仅数量参考；Rokoko 命名以本地实证为准）
- [x] HITL：与用户过终稿并确认定稿；结论蒸馏（D1–D8 若尚未 ADR 化则补，见 doc-system-migration 票 03）
  - 四项裁定（2026-10-19）：① 接受三通道拓扑（final_command 命名避开现行软目标 topic `/o10_control/{side}/command`）；② thumb_roll/thumb_abad 有意不映射、`fixed_native_joints` 配置固定值驱动（激活 8/22；承载现行 `RetargetingConfig.thumb_*_fixed_value` 语义）；③ 标准面零符号变换；④ 定稿 v1.1
  - D1–D7 已 ADR 化为 docs/adr/0014–0020（迁移票 03 完成核验）；D8（spec 文档位置）迁移票 03 已裁定"随迁移消化，无需 ADR"——本票无 ADR 补录项
  - 随票同步修订 `docs/手套21关键点标准化规范.md`（M12/M13 边界澄清 + 日期修正）
- [x] 收尾检查雾区：建议"按 spec 实施"新 effort 的起点，不在本票内扩边
  - 雾区建议（已记 STATUS）：开新 effort "按 spec v1.1 实施换手重构"，建议票序：① 标准适配节点三通道 + HandProfile（含加载期全覆盖校验、fixed_native_joints 迁移）→ ② 控制节点 22 DoF 化（限位派生、状态机对齐 HS-6）→ ③ wire 切换与录制面接入；两项已裁定延期（Rokoko 接收节点非有限值行为对齐、逐 topic QoS 细化）随实施落地；构建门（中文路径）仍在 build-baseline-fix 票，实施前置依赖其结论
  - 关票杂项：删除过期 v1.0 PDF 渲染（spec.pdf，无 pandoc 再生，需要时重渲染）；删除仓库根散文件 ARCHITECTURE.md（核实为 v1.0 工作稿逐字重复拷贝，doc_gate 落点 error）
  - doc_gate 终态：本票产物 0 error / 0 warning；余 17 error 全部来自并行放入的 `thumb_mapping_teleop_with_vendor_assets_20261019_101039/`（厂商资产快照内 README 引用旧 DOCS/ 路径，非本票范围，未改动）——待其 owner 处置
