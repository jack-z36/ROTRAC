# 01: 结构搬迁与归档建账

**What to build:** 文档体系迁移的物理层：先把当前未提交的票据 07/12 工作产物提交入库，然后 git mv 全部到位——旧 ADR 进 `docs/adr/`、wayfinder 全树进归档、根目录 handoff 文件进归档、DOCS 其余整体进归档，并建立 `archive/INDEX.md` 总表。旧目录从此消失，git 历史保留。

**Blocked by:** None (can start immediately)

**Status:** in-progress（2026-10-15 认领）

- [ ] 当前未提交状态已提交（收口 07/12 产物 + setup 配置三件套）
- [ ] `docs/adr/` 含全部 13 个旧 ADR（git mv，非复制）
- [ ] `archive/` 三单位齐全：wayfinder-2026-10/、old-docs-2026-10/、handoff/
- [ ] `archive/INDEX.md` 总表（单位/日期/内容/原因）
- [ ] `DOCS/`、`wayfinder/` 目录消失；git status 干净
