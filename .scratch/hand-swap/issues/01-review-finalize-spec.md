# 01: 换手架构 spec 对抗评审与定稿

**What to build:** 对 `.scratch/hand-swap/spec.md`（22 DoF 换手架构 spec 草案，47 用户故事）做对抗性评审与修复，最终与用户 HITL 定稿。接替原 wayfinder 票 10（其 08/09 前置已作废：spec 已由票 12 直接产出）。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 派 `adversarial-reviewer` 攻击 spec：构造"两模块各自完全遵守条文却仍不兼容"场景（候选攻击面：HandProfile 与中段 IK 对 DOF/关节序的假设冲突、手套契约与归一化对节点命名的假设冲突、配置单一来源与 launch 覆盖顺序的歧义、22 DoF NaN 语义在控制层/录制层的边界）
- [ ] 逐条修复评审发现并回写 spec；不接受的发现记录豁免理由
- [ ] 涉外部事实的断言（SDK 行为、ROS 2 对 NaN 的序列化、版本兼容）交 `tech-fact-checker` / `web-researcher` 核实
- [ ] HITL：与用户过终稿并确认定稿；结论蒸馏（D1–D8 若尚未 ADR 化则补，见 doc-system-migration 票 03）
- [ ] 收尾检查雾区：建议"按 spec 实施"新 effort 的起点，不在本票内扩边
