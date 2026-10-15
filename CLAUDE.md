# Dexhit Agent 入口

请先阅读仓库根目录的 [AGENTS.md](AGENTS.md)，再按其中的任务路由加载上下文。权威 Skill 位于 [skills/](skills/INDEX.md)；`.agents/skills` 和 `.claude/skills` 只是兼容入口。

## Wayfinder 跟踪器约定

**本仓库的 wayfinder 使用本地 markdown 文件，不使用 GitHub issues。**

- 地图：`wayfinder/map.md`
- 票据：`wayfinder/tickets/*.md`（frontmatter 即状态机）
- 研究报告：`wayfinder/research/*.md`

完整协议见 [wayfinder/README.md](wayfinder/README.md)。忽略 `DOCS/02_约束/编程执行/issue-tracker.md` 中关于 wayfinder 使用 GitHub API 的描述——那是通用模板，本仓库不适用。

## Grilling Skill 使用规则

调用 `grilling` 或 `grill-me` skill 时：

- **每轮只问 1 个问题**，不要一次抛出多个问题（Q1/Q2/Q3...）
- 根据用户的回答调整下一轮提问方向
- 这是渐进式对话，不是问卷调查
