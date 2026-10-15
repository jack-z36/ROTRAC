# Wayfinder 本地地图 · 使用说明

这是 wayfinder 规划方法的**本地 markdown 跟踪器**落地（本仓库无 issue tracker，按约定采用本地文件形式）。它指导你用多个 session 依次逐步完成两大任务：**架构 spec 重构文档**与**代码库整理**。

`map.md` 是唯一权威地图：每个 session 开场先读它。`tickets/` 下每个文件是一张票据（一个决策或一个任务单元）。

> ⚠️ 本目录（`wayfinder/`）是规划资产：任何清理、重命名、移动任务都**不得**删除或改动它（除非用户明确要求）。

## 目录结构

```
wayfinder/
├── README.md      ← 本文件：跟踪器约定与 session 协议
├── map.md         ← 地图（终点 / 约定 / 已决索引 / 雾区 / 范围外）
├── tickets/       ← 票据（frontmatter 即状态机）
│   ├── 01-pipeline-inventory.md      …已关闭（research）
│   └── …
└── research/      ← 侦察/调研报告全文（票据链接到这里）
```

## 票据 frontmatter 约定

```yaml
---
id: 4                    # 唯一编号
title: 确认清理范围…      # 票名（正文引用一律用票名，不用裸编号）
type: grilling           # research | prototype | grilling | task
labels: [wayfinder:grilling]
status: open             # open | in-progress | closed
assignee:                # 认领时填：会话标记，如 session-2026-10-14
blocked-by: [1, 2]       # 这些编号的票全部 closed 后本票才解锁
---
```

- **认领**：填 `assignee` + `status: in-progress`（必须在开工前完成，防止并行 session 撞车）。
- **关票**：在 `## Resolution` 一节写下结论/证据（资产放 `research/` 并留链接），`status: closed`。
- **解锁**：`blocked-by` 中所有票均已 `closed`。
- **frontier（当前可取之票）**：`status: open` 且已解锁且 `assignee` 为空。

## 每个 session 的标准流程

1. 读 `map.md`（低分辨率全局视图，不要一上来就读所有票据全文）。
2. 从 frontier 取**编号最小**的票（用户点名则听用户的）。
3. **先认领，再开工**。
4. 解决它：
   - `grilling` / `prototype` 票是 HITL（真人参与）：必须与用户实际对话往返，agent 不得代替用户作答；建议调用 Skill 工具的 `grilling` + `domain-modeling`（决策票）或 `prototype`（原型票）。
   - 探索、只读侦察一律交给 **subagent**（file-scout / Explore），主会话只做高层判断与写盘，避免上下文污染。**若 subagent 不可用：立即暂停当前票据并向用户报告，不得自行代跑底层探索。**
   - `task` 票直接执行落地（本 effort 明确允许执行，见 map Notes）。
5. 在票内 `## Resolution` 记录答案，`status: closed`。
6. 回到 `map.md`，在「Decisions so far」追加一行：`[票名](tickets/xx.md)：一句话结论`。
7. 若答案让「Not yet specified」雾区某块变得可以精确提问：新建票据（先建文件再补 `blocked-by` 连线），并从雾区删除该块；若答案表明某票超出终点范围，将其关闭并在「Out of scope」记一行。
8. **一个 session 只解决一张票**（research 类除外）。

## 推荐取票顺序

按编号升序即可（依赖关系已按此设计）：03 安全网 → 04 清理范围（HITL）→ 05 删除 → 06 重命名规整 → 07 模块边界（HITL）→ 08 spec 大纲（HITL）→ 09 撰写 spec → 10 评审定稿。
