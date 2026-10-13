---
id: 10
title: spec 对抗性评审与定稿
type: grilling
labels: [wayfinder:grilling]
status: open
assignee:
blocked-by: [9]
---

## Question

对票据 09 产出的 spec 做定稿前的压力测试，修复问题后与用户一起定稿——本图的终点票。

要求：

1. 派 `adversarial-reviewer` subagent 攻击 spec：构造「两个模块各自完全遵守条文却仍不兼容」的场景（如 HandProfile 与中段 IK 对 DOF/关节序的假设冲突、手套契约与归一化对节点命的假设冲突、配置单一来源与 launch 覆盖顺序的歧义）。
2. 逐条修复评审发现的问题，回写 spec；对不接受的发现记录理由。
3. 技术断言若涉及外部事实（SDK 行为、版本兼容），交 `tech-fact-checker` 或 `web-researcher` subagent 核实。
4. HITL 收尾：与用户过一遍终稿，确认后关票；在 map 的 Decisions so far 记录定稿结论与文档位置。
5. 收尾时检查雾区：若「按 spec 实施迁移」需要开新图，向用户建议新 effort 的起点（不要在本图内扩边）。

验收：评审问题清零或记录豁免理由；用户确认定稿；地图到达终点。
