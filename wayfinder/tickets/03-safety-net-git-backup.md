---
id: 3
title: 建立安全网：全量备份与 git 初始化
type: task
labels: [wayfinder:task]
status: in-progress
assignee: walk1-2026-10-13
blocked-by: []
---

## Question

在任何删除发生之前，为整棵树建立可回滚的安全网。侦察（票据 01/02）已确认：**整棵 ROTRAC 树当前没有任何版本控制**——根 `.git` 是空目录，两个 worktree 的 `.git` 文件指向本机不存在的 `/home/hit/Dexhit/.git`。本票是所有破坏性操作的硬前置。

要做的：

1. **全量备份**：把 `/home/zh/桌面/project/ROTRAC` 完整打包（含 venv 与 node_modules，共 ~724M，不得为省空间裁剪）到仓库之外的位置（如 `~/backups/ROTRAC-2026xxxx.tar.zst`），校验可列出内容。
2. **git init 于仓库根**：先写 `.gitignore`（排除 `dexhit_collection/`、`**/node_modules/`、`build/`、`install/`、`log/`、`__pycache__/`、`*.pyc`、`.pytest_cache/`；`runs/` 是否入库留待票据 04 裁决，可先排除），再做 initial commit。
3. **处理失效 worktree 引用**：`Dexhit-worktrees/collection/.git` 与 `Dexhit-worktrees/processing/.git` 是指向 `/home/hit` 的 gitdir 文件，会干扰根仓库——移除这两个残留文件（备份已兜底），使子目录成为普通被跟踪目录。
4. **保护 wayfinder/**：确认它被 git 跟踪且不受后续清理影响。

验收：备份文件存在且完整；`git log` 有 initial commit；`git status` 干净；`wayfinder/` 已入库。
