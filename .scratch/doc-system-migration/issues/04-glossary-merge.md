# 04: 术语合并进 CONTEXT.md

**What to build:** 消灭双词汇表：用户概念体系·术语规则（含四阶段名称表）并入根 `CONTEXT.md`，成为全库唯一词汇表；口径冲突以用户概念体系为准。

**Blocked by:** 01 结构搬迁与归档建账

**Status:** resolved（2026-10-15）

- [x] `CONTEXT.md` 收编术语规则全部活术语（Avoid 标注保留）
- [x] 全库不再有第二处术语权威

## Answer

术语规则的 10 个术语（主链/阶段/模块/产物/接口/契约/生成物/raw MCAP/LeRobotDataset v3/ACT bundle）进 Language 上的"主链与阶段"节；元规则（权威顺序/四种口径/最低信息/表达偏好/退役概念）压缩为文末"语言与维护约定"。顺手修正 4 条与现行代码不符的旧语义：`arm`/`disarm` 已随直驱语义移除（2026-08 `4fedfaa`，ADR-0004 superseded），操作者唯一操作是 `clear_fault`——操作者控制授权条目删除并列入退役概念，操作者控制操作/手侧运动许可/锁存控制故障/清除锁存故障四条同步改写。原文件留在 old-docs 归档区。
