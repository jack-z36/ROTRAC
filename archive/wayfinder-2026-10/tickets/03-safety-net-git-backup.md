---
id: 3
title: 建立安全网：全量备份与 git 初始化
type: task
labels: [wayfinder:task]
status: closed
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

## Resolution

walk1-2026-10-13 执行完毕，验收四项全部通过。

1. **全量备份**：`~/backups/ROTRAC-20261013.tar.zst`，123M（源 ~724M，zstd）。条目数 30670 与源完全一致；抽查 node_modules、wayfinder、venv、worktree .git 均在。SHA256：`bef3df0b68557e0ec742ac4d08a7ed7aae3d5cea30bbdac8d0846f8249f70904`。
2. **失效 worktree 引用已移除**：`Dexhit-worktrees/{collection,processing}/.git` 均为 `gitdir: /home/hit/Dexhit/.git/worktrees/...` 指针（主仓库已丢失），删除前已入备份。
3. **git 仓库建立**：`git init -b main` 于仓库根（原空 `.git` 目录被征用）；无全局 git 身份，已设 repo 本地 `user.name=zh / user.email=zh@local`；根 `.gitignore` 排除 venv / node_modules / web/dist / build/install/log / 缓存 / runs。initial commit `34956ba`：846 文件、71081 行，含 third_party vendor SDK 二进制 344 文件（libomnihand.so 等）与 wayfinder/ 全部 14 文件。
4. **发现（移交票据 04）**：`Dexhit-worktrees/collection/.gitignore:43` 原本就整体排除 `/runs/`，因此 `runs/retargeting_diag_params.yaml`（重定向阈值配置）目前**不在版本控制内**（tar 备份已覆盖）；该 yaml 是否纳入 git 并入票据 04 的 runs 裁决一起定。

后续破坏性操作（票据 05/06）现在均可通过 git 回滚，且另有 tar 全量备份兜底。
