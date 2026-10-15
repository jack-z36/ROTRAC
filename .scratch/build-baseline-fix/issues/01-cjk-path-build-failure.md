# 01: 修复中文路径构建失败，恢复链路自检

**What to build:** `./scripts/init_omnihand.sh` 在本机必然构建失败（rokoko_omnihand_msgs 的 rosidl 接口生成报错），根因是仓库路径含中文。与用户决策修复方案并落地，使 init 自检全绿——这卡住 AGENTS.md 规定的开工自检门。接替原 wayfinder 票 11。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 与用户完成方案决策（A / B，见候选）
- [ ] 落地（脚本修改或仓库迁移）
- [ ] `./scripts/init_omnihand.sh` 构建与测试全绿，票内记录最终选择与验证输出

## 根因（已实锤，最小复现已做）

CMake `file(STRINGS)` 在非 ASCII 字节处拆行；`rosidl_adapt_interfaces`（`/opt/ros/jazzy/share/rosidl_adapter/cmake/rosidl_adapt_interfaces.cmake:82`）用它读回 `.idls` 元组列表，build 路径含「桌面」→ 每行拆 3 段：无冒号段报 list index out of range（×5 个接口），截断前缀段报"依赖不存在"。纯 Python 包不受影响（11 包中仅生成接口消息的 msgs 包挂），故 `.venv` pytest 路线一直未暴露。

## 候选方案

- **A（已验证可行）**：colcon `--build-base` / `--install-base` 指到 ASCII 路径（如 `~/rotrac-build`）。此前必失败的 msgs 包实测 8 秒构建成功。代价：偏离"仓库根 build/install"惯例，`init_omnihand.sh` 与 source `install/setup.bash` 的各处脚本要改。
- **B（最彻底）**：仓库整体迁 ASCII 路径（同盘 rename 秒级），零脚本改动；代价：改变用户目录习惯（桌面可见性、肌肉记忆）。
- **已排除**：仓库根建 ASCII 符号链接——colcon 发现包时 `realpath` 解析回中文路径，实测无效。
- **未验证**：bind mount（`realpath` 不解析，理论可行，需 sudo，不宜常态化）。
