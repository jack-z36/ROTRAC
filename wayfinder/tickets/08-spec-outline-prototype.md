---
id: 8
title: 起草 spec 大纲并获取反馈
type: prototype
labels: [wayfinder:prototype]
status: open
assignee:
blocked-by: [6, 7]
---

## Question

产出架构 spec 文档的**低保真原型**：章节目录 + 每章要点 + 关键接口草案（HandProfile/HandAdapter、手套契约、中段注入配置的签名），交用户反馈后再写正文（票据 09）。宁可粗糙具体，不要空泛完整。

要求：

1. 调用 Skill 工具的 `prototype`；大纲落在 `wayfinder/research/spec-outline.md`（或票据 04 定下的 DOCS 草稿区），票内留链接。
2. 大纲必须包含「换手操作手册」一节：按票据 07 的结论列出换一只手时必改的文件/配置清单。
3. 必须包含「迁移策略」一节的提纲：从当前结构到目标结构的分步计划（供下一 effort 执行，本 effort 不实施）。
4. HITL：把大纲给用户过目，收集修改意见并回炉，直到用户点头才关票；Resolution 记录大纲链接 + 用户反馈要点。
