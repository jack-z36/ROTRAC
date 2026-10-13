---
id: 5
title: 执行清理：删除无关代码与目录
type: task
labels: [wayfinder:task]
status: open
assignee:
blocked-by: [3, 4]
---

## Question

按票据 04 确认的 Delete 清单执行删除（前置：安全网票据 03 已完成，有备份 + git）。

执行要求：

1. 按「大类一提交」节奏操作：每删一大类（如构建产物 / 录制数据 / 无关工程）做一次 git commit，提交信息写明类别与释放的空间。
2. 删除只允许命中票据 04 清单内的路径；对任何清单外文件保持不动，有疑问先停下来问用户。
3. 删后自检链路完整性：`init_omnihand.sh`（或至少 colcon build + 各包单测 + architecture_tests）通过，`start_omnihand_control.sh --help`/dry 检查不被清单内删除破坏。
4. `wayfinder/` 目录必须完好。

验收：git log 体现分批删除；链路自检通过；磁盘释放量与预期一致。
