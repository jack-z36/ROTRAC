# 侦察报告 04：睿尔曼机械臂 / vive tracker 代码定位与兄弟目录状况

> 由 file-scout subagent 于 2026-10-13 只读侦察产出。结论已用于票据 04 的范围裁决（全部裁出图外，用户自行处理）。

## ① 睿尔曼/RealMan 相关：ROTRAC 内不存在

- `/home/zh/桌面/project/vive-control-arm.zip`（134MB，2026-08-28）— **唯一含实际代码处**。内含 `node/ros2_rm_robot-jazzy/`（睿尔曼官方 ROS2 Jazzy 驱动仓库，含 `control_arm_move` 示例包及已编译 `move_demo` 二进制 6.4MB）、`node/windows_openvr_sender.py`。
- `/home/zh/桌面/project/ROS/.rm_sdk_tmp/` — 仅剩 `RM_API2/`、`ros2_rm_robot/` 两个**空目录**。
- ROTRAC 全树零命中：CONTEXT.md、Spec、基线文档中的"机械臂"均为**否定式范围声明**（"不控制机械臂"）。

## ② Vive tracker 相关：ROTRAC 内不存在

- `/home/zh/桌面/project/node/src/vive_wrist_trackers/ros2_vive_tracker/` — ROS 2 Jazzy 包（"UDP bridge for SteamVR VIVE Tracker poses"），`launch/vive_tracker.launch.py`、`config/tracker_roles.json`，发布 `/raw/vive/{left,right}_wrist_tracker/pose`。
- `/home/zh/桌面/project/node/src/vive_wrist_trackers/windows_openvr_sender.py` — Windows 端 OpenVR/SteamVR 发送端（zip 内同款）。
- ROTRAC 内命中全为假阳性（survive、issue-tracker）。

## ③ ROTRAC src/ 包清单对账：11 包成立

rokoko_hand_receiver、hand_retargeting、omnihand_o10_control、omnihand_o10_hardware_adapter(provider)、rokoko_omnihand_launchpad、rokoko_omnihand_msgs、rokoko_omnihand_bringup、o10_contracts、o10_model、rokoko_omnihand_system_test、rokoko_omnihand_architecture_test。third_party 仅 agillink_omnihand_sdk。venv 无 rm/vive 第三方包。8 个根级脚本均不启动 arm/vive 节点（record_o10_diagnosis.sh:12/128、start_launchpad.sh:5/62 显式注明"不调用 arm"）。**删除兄弟目录的 arm/vive 对 ROTRAC 零波及。**

## ④ 兄弟目录其他发现（均已裁出图外，此处留档）

1. `/home/zh/桌面/project/Dexhit/src/collection/` 是另一份副本，比 ROTRAC worktree **多**一个 `rokoko_receiver_node/` 与《职责文档-数据采集与一键启动.md》（两副本不同步；用户裁决：ROTRAC 为唯一权威演进副本，兄弟副本自行处理）。
2. `/home/zh/桌面/project/node/src/rokoko_gloves_receiver/` — 另一套 Rokoko 接收代码（同名异码，含 dexhit_msgs，与 ROTRAC 无依赖）。
3. `git-snapshots-20261009/`、`Projects-git-backup…bundle` 等只读归档未展开。
4. ⚠️ 兄弟目录不在 ROTRAC 的 tar 备份（~/backups/ROTRAC-20261013.tar.zst）与 git 安全网覆盖范围内——用户自行删除前请自行备份。
