# 09: 入口定稿与断链清零

**What to build:** 迁移收口：AGENTS.md 重写为三块结构（`## Agent skills` 块保留 + 导航指针 + Rokoko/O10 安全门压缩至 3–4 行）；CLAUDE.md 瘦成一行指针；README.md 人类门面更新；全库断链扫描清零。

**Blocked by:** 02, 03, 04, 05, 06, 07, 08

**Status:** ready-for-agent

- [ ] AGENTS.md 三块结构（安全门含 init_omnihand.sh 与根入口 start_omnihand_control.sh 两条硬规则）
- [ ] CLAUDE.md 仅一行指针指向 AGENTS.md
- [ ] README.md 反映新结构
- [ ] 全库 md 断链扫描零命中（含旧 CLAUDE.md 的 skills/ 幽灵引用清除）
