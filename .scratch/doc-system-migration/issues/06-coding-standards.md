# 06: CODING_STANDARDS.md 蒸馏

**What to build:** 编程执行规则蒸馏为根目录 `CODING_STANDARDS.md`，定位为 review 阶段读物（实现阶段不占上下文）；只保留 reviewer 需要强制执行的规则，删除默认行为重述与已失效引用。

**Blocked by:** 01 结构搬迁与归档建账

**Status:** resolved（2026-10-15）

- [x] `CODING_STANDARDS.md` 落地，逐行通过 no-op 测试（能改变 agent 默认行为的才留）
- [x] 与 AGENTS.md 导航指针衔接（review 时读）→ 衔接行由迁移票 09 写入 AGENTS.md 时补

## Answer

蒸馏取向：reviewer 对 diff 可执行的硬规则全部保留（修改纪律/接口对齐/测试 red→green/硬件安全/证据诚实/生成物隔离/Git 红线）；砍掉实现期规划纪律（任务分型、七项信息、蓝图——实现 agent 默认行为或属规划期）、砍掉引用不存在的 `skills/` 目录的第 14 节、把 `src/<stage>/` 四阶段旧落点改为现行扁平包结构。原文留在 old-docs 归档区。
