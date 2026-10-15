# 08: 活票重建

**What to build:** 在途工作全部迁入 `.scratch/`：根 ARCHITECTURE.md 移为 `.scratch/hand-swap/spec.md` 并建"spec 评审定稿"票（原票 10 的职责）；11 号票（构建基线 CJK 路径修复，含基线失败名单）重建为 `.scratch/build-baseline-fix/`；票据 07/12 在归档树内正式收口。

**Blocked by:** 01 结构搬迁与归档建账

**Status:** resolved（2026-10-15）

- [x] `.scratch/hand-swap/spec.md` 存在且根目录 ARCHITECTURE.md 消失（git mv）
- [x] `.scratch/hand-swap/issues/` 含评审定稿票（Matt 模板）
- [x] `.scratch/build-baseline-fix/issues/` 含 CJK 路径修复票（根因 + 候选 A/B 全文随迁）
- [x] 归档树内 07/12 改 closed、10/11 改 superseded 并加收口注记，commit 完成

## Answer

原票 11 正文并无独立的基线失败名单——11 项遗留失败的定性结论在 map.md 票 06 决策里，已蒸馏进 `STATUS.md` 能力基线节，重建票指向它即可。10 号票的 08/09 前置链已随旧方案归档，重建票说明此前置作废（spec 由 12 直接产出）。
