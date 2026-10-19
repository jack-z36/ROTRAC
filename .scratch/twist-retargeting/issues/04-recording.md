# 04: 自动扭转诊断录制

**What to build:** 一个独立的扭转诊断录制脚本，由规范启动入口自动启停，用 `ros2 bag record` 写 MCAP，覆盖完整诊断链路；与采数据 MCAP 完全分开。软件开发、dry-run 和 MCAP 校验不需要真机；真机启动冒烟放在 06。

**Blocked by:** 03

**Status:** resolved

- [x] 独立脚本，自动启停；录制在业务节点之前启动。
- [x] 输出 `runs/twist-diag/<timestamp>/`，含 bag、配置快照、git commit、topic 列表、README。
- [x] 七个诊断 topic 全录；best-effort QoS override。
- [x] `--dry-run` 打印命令和路径，不启动录制。
- [x] 磁盘/时长保护；Ctrl-C 后 MCAP 正常关闭。
- [x] 不修改采数据 MCAP；不影响控制链路频率。
- [x] 用纯软件链或合成数据验证脚本生命周期；真机冒烟在 06。

## Resolution

- 新增 `scripts/record_twist_diagnosis.sh`：逐侧录制 7 个 topic，输出 `runs/twist-diag/<timestamp>-<pid>/`，包含 `bag/`、配置快照、git commit/status、topics、QoS override、README、metadata 和 record.log；`--dry-run` 只打印计划。
- 规范入口 `src/teleoperation_support/production_bringup/scripts/start_omnihand_control.sh` 在所有业务节点之前启动录制，`OMNIHAND_TWIST_DIAG_RECORD=0` 可关闭，`OMNIHAND_TWIST_DIAG_MAX_SEC` 控制最长时长。
- 生命周期实测（ROS_DOMAIN_ID=92，`ros2 topic pub` 合成 `TwistState`）：`--max-duration 3` 自动停止，`ros2 bag info` 可读，analysis 成功读取 76 帧并生成 summary/CSV；无残留 rosbag2 进程。
- 修复两处真实生命周期问题：后台 `ros2 bag record` 继承 SIGINT ignore（改为 PID 文件 + SIGTERM 优雅停止，SIGKILL 仅兜底）；`setsid` fork 导致错误 PID（子进程自写 PID 文件）。
- 与采数据 MCAP 完全分开；脚本不发布、不调 Service、不驱动硬件。
