# 09: 入口定稿与断链清零

**What to build:** 迁移收口：AGENTS.md 重写为三块结构（`## Agent skills` 块保留 + 导航指针 + Rokoko/O10 安全门压缩至 3–4 行）；CLAUDE.md 瘦成一行指针；README.md 人类门面更新；全库断链扫描清零。

**Blocked by:** 02, 03, 04, 05, 06, 07, 08

**Status:** resolved（2026-10-15）

- [x] AGENTS.md 三块结构（Agent skills / 导航指针 / 安全门；安全门含 init_omnihand.sh 与根入口 start_omnihand_control.sh 两条硬规则；grilling 单题纪律收编进导航区）
- [x] CLAUDE.md 仅一行指针指向 AGENTS.md（原 wayfinder 约定与 skills/ 幽灵引用清除）
- [x] README.md 目录树与文档入口反映新结构；真机启动指向 docs/全流程启动手册.md
- [x] 全库断链扫描零命中（59 条活链接；src/README 与 ADR-0004 的 3 处旧路径断链已修；archive/ 按设计豁免冻结历史；算法基线 LaTeX 记号为假阳性已豁免）

## Answer

入口定稿与断链清零一次完成。遗留中间态（AGENTS.md 旧路由表指向已搬迁路径）消除；`src/README.md:81` 与 `docs/adr/0004` 头注的三处旧契约链接改指合并后文档。
