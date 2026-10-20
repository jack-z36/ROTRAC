# ROTRAC 全局路由入口

本文件是仓库唯一 agent 入口：只做导航与安全门，不承载项目知识、规则正文或执行记录。

## 工作流门：改代码必须先取票

只有用户显式调用 `/implement-spec` 后，才允许按 `.scratch/` 票据修改代码、运行修复性命令或提交代码。

- `/to-spec`、`/to-tickets`、`/grill-me`、`/diagnosing-bugs` 等只产出规格、票据或诊断，不构成实现授权。
- 用户说"先执行 / 开始做 / 执行完提交 git"但没有显式调用 `/implement-spec` 时，先停下来确认是否进入实现；不得把"执行"自行解释为改代码授权。
- 实现开始前必须读对应 spec 与票据；一次只处理已批准的票。

## Agent skills

### Issue tracker

Issues and specs live as local markdown under `.scratch/<feature>/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five canonical roles: `needs-triage` / `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` at the repo root + `docs/adr/`. See `docs/agents/domain.md`.

## 导航指针

- 开工先读 [STATUS.md](STATUS.md)：现状快照（能力基线 / 在途 / 已知问题），从中找到 `.scratch/` 活票据
- 术语唯一权威是 [CONTEXT.md](CONTEXT.md)：输出用词以其为准，概念冲突立即上报
- 稳定知识与手册在 [docs/](docs/)：架构边界、接口语义、算法基线、启动手册、真机前置条件
- 架构决策查 [docs/adr/](docs/adr/)；结论与 ADR 冲突时显式指出，不得静默覆盖
- [CODING_STANDARDS.md](CODING_STANDARDS.md) 只在 code review 阶段读，实现阶段不占上下文
- 写任何 .md 前先读 [skills/doc-writing/SKILL.md](skills/doc-writing/SKILL.md)（落点判定树；写错位置会被 hook 拦截）
- 历史默认不读；需要追溯时从 [archive/INDEX.md](archive/INDEX.md) 定位单位再全文检索
- Grilling 类对话：每轮只问 1 个问题，按回答动态调整——渐进式对话，不是问卷调查

## 安全门：Rokoko → OmniHand O10

涉及 Rokoko 手套、手部重定向、OmniHand O10、其 ROS 链路、Launchpad、回放、测试或真机适配的任务，正式执行前必须先运行 `./scripts/init_omnihand.sh`（软件基线自检；不启动节点、不驱动实体手；依赖安装需显式 `--install`）。

启动遥操作的唯一规范入口是仓库根 `./scripts/start_omnihand_control.sh`（先过 init 再启动；不要调用 `src/` 下的 package-local 实现入口）。真机人工安全检查流程见 [docs/全流程启动手册.md](docs/全流程启动手册.md)。
