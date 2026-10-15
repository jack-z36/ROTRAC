# 01: 反熵体系落地（规则层 + 写入门禁 + 脚本门禁）

**What to build:** 对抗文档体系熵增的三层防线一次建成：L1 规则正文 `skills/doc-writing/SKILL.md` + AGENTS.md 指针行（三端通用）；L2 写入门禁 hook（ZCode `.zcode/config.json` + Claude Code `.claude/settings.json`，PreToolUse 双段式：非法落点 deny、合法写入注入四问判定树）；L3 脚本门禁 `scripts/doc_gate.sh`（落点/断链/死路径=error，孤儿/超大/陈旧票=warning），关票验收追加门禁绿。Codex 由 L1+L3 覆盖。

**Blocked by:** None (can start immediately)

**Status:** resolved（2026-10-15）

- [x] `skills/doc-writing/SKILL.md`：四问判定树 + 硬拦截清单 + 缓存测试公理 + 蒸馏/归档/审计惯例
- [x] `scripts/hooks/doc_write_gate.py`：五输入离线测试全过（根散文件/归档/agents 配置 deny 带原因；合法注入四问；非 md 放行）
- [x] `.zcode/config.json` + `.claude/settings.json`：PreToolUse matcher `Write|Edit`（ZCode 配置最后激活）
- [x] `scripts/doc_gate.sh`：五项检查 + 分级 + 退出码；首跑抓到 3 处真死路径（src/README 与 third_party/README 的扁平化前活引用）已修，历史语境豁免（ADR、"已废弃"提及）已校准
- [x] AGENTS.md 导航区指针行；`docs/agents/issue-tracker.md` Lifecycle 追加关票门禁绿
- [x] 关票自验：`doc_gate.sh` 终跑 58 活文档 / 60 链接 / 0 error / 0 warning，exit 0

## Answer

三层防线一次建成并自举验证：L1 规则正文（三端经 AGENTS.md/CLAUDE.md 到达）；L2 写入门禁（ZCode + Claude Code 的 PreToolUse 双段式，Codex 由 L1/L3 覆盖）；L3 脚本门禁挂关票验收。门禁首跑即抓到真猎物——src/README.md 停在扁平化前的树形、构建命令与脚本路径（`src/collection/`、根目录 `./init_omnihand.sh`、`--base-paths`），连带 third_party/README 的 colcon 语义一并修正，即"体系建成当天开始还债"。
