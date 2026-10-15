---
id: 11
title: 修复中文路径下的构建失败，恢复链路自检
type: grilling
labels: [wayfinder:grilling]
status: superseded
assignee:
blocked-by: []
---

> 收口注记（2026-10-15）：工作移交 `.scratch/build-baseline-fix/issues/01`（根因与候选方案已随文迁移）。

## Question

`./scripts/init_omnihand.sh` 在本机必然构建失败（rokoko_omnihand_msgs 的 rosidl 接口生成报错），根因是**仓库路径含中文**（`/home/zh/桌面/project/ROTRAC`）。需要与用户决策修复方案并落地，使 init 自检全绿——这是父图终点第 2 条（「链路自检通过」）的硬性要求，也卡住 AGENTS.md 规定的开工自检门。

### 根因（已实锤，最小复现已做）

CMake 的 `file(STRINGS)` 会在非 ASCII 字节处拆行。`rosidl_adapt_interfaces`（/opt/ros/jazzy/share/rosidl_adapter/cmake/rosidl_adapt_interfaces.cmake:82）用它把 `rosidl_adapter/<pkg>.idls` 读回元组列表；`.idls` 每行是 `<build路径>:<idl相对路径>`，其中 build 路径含「桌面」两个汉字 → 每行被拆成 3 段：

```
/home/zh/            ← 无冒号 → rosidl_generate_interfaces.cmake:234 报 list index out of range（×5 个接口）
（空段）
/project/ROTRAC/…    ← 即 /home/zh/桌面/project/ROTRAC/… 被截掉前缀 → type_description 报"依赖不存在"
```

纯 Python 包不受影响（11 包里只有生成接口消息的 msgs 包挂），此前测试多走 `.venv` pytest，故一直未暴露。

### 候选方案

- **方案 A（已验证可行）**：colcon `--build-base`/`--install-base` 指到 ASCII 路径（如 `~/rotrac-build`）。实测此前必失败的 msgs 包 8 秒构建成功（`.idls` 元组只含 build 路径；源码路径经参数 JSON 由 Python 读取，不受 CJK 影响）。代价：偏离「仓库根 build/install」惯例，`init_omnihand.sh` 与 source `install/setup.bash` 的各处脚本要改。
- **方案 B（最彻底）**：仓库整体迁到 ASCII 路径（如 `~/dev/ROTRAC`，同盘 rename 秒级）。零脚本改动；代价：改变用户目录习惯（桌面可见性、快捷方式、肌肉记忆）。
- **已排除**：仓库根建 ASCII 符号链接——colcon 发现包时 `realpath` 解析回中文路径，实测无效。
- **未验证**：bind mount（`realpath` 不解析 bind mount，理论可行，需 sudo，不宜常态化）。

### 产出

选定方案 → 落地（脚本修改或仓库迁移）→ `./scripts/init_omnihand.sh` 构建与测试全绿，并在票内记录最终选择与验证输出。
