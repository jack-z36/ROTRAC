---
id: 6
title: 执行清理：重命名规整与目录重组
type: task
labels: [wayfinder:task]
status: open
assignee:
blocked-by: [4, 5]
---

## Question

按票据 04 的命名与布局决定执行仓库重组，让目录「规整、只含重定向相关项目代码」。

要做的：

1. **目录重组/改名**：一律 `git mv` 保留历史（如 collection 提升扁平化、fixture 哈希目录改短名、根级脚本归位 `scripts/` 等，以票据 04 的目录树草案为准）。
2. **修复死路径**：`start_launchpad.sh` 与 `production_bringup/launchpad/*.yaml` env 段中 `/home/hit/miniforge3`、`/home/hit/dexhit-external`、`/home/pkw/...` 等本机不存在的路径；venv 引用按票据 04 的裁决同步调整。
3. **引用同步**：init/start 脚本、`package.xml`/`setup.py`、`o10_model_assets/loader.py` 的资产根解析、DOCS 与 README 中的路径全部指向新布局。
4. 删除 `omnihand_o10_fixture…/.broken-symlinks-old-home-hit` 等迁移残留（若票据 05 未覆盖）。
5. 重组后跑完整链路自检（colcon build + 单测 + architecture_tests + `init_omnihand.sh`），并把新目录结构与「重定向边界定义」写进根 README。

验收：无任何指向旧路径/死路径的引用（可 grep `/home/hit`、`/home/pkw`、旧目录名为零命中）；链路自检通过；README 反映最终布局。
