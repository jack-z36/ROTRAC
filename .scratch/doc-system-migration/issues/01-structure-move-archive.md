# 01: 结构搬迁与归档建账

**What to build:** 文档体系迁移的物理层：先把当前未提交的票据 07/12 工作产物提交入库，然后 git mv 全部到位——旧 ADR 进 `docs/adr/`、wayfinder 全树进归档、根目录 handoff 文件进归档、DOCS 其余整体进归档，并建立 `archive/INDEX.md` 总表。旧目录从此消失，git 历史保留。

**Blocked by:** None (can start immediately)

**Status:** resolved（2026-10-15）

- [x] 当前未提交状态已提交（收口 07/12 产物 + setup 配置三件套）→ commit 4287975
- [x] `docs/adr/` 含全部 13 个旧 ADR（git mv，非复制）→ 0001–0013 + INDEX.md
- [x] `archive/` 三单位齐全：wayfinder-2026-10/、old-docs-2026-10/、handoff/
- [x] `archive/INDEX.md` 总表（单位/日期/内容/原因）
- [x] `DOCS/`、`wayfinder/` 目录消失；git status 干净 → commit 33aa260

## Answer

结构搬迁一次完成：先收口提交（4287975），再四个 git mv（ADR→docs/adr、DOCS→archive/old-docs-2026-10、wayfinder→archive/wayfinder-2026-10、根 handoff 5 件→archive/handoff），archive/INDEX.md 建账，提交 33aa260。git 历史全程保留（rename 追踪）。注意：AGENTS.md 旧路由表此刻指向已搬走的 DOCS 路径，属预期中间态，由迁移票 09 收口。
