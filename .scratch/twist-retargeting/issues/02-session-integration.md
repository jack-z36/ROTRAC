# 02: 端到端扭转路径与安全回退

**What to build:** 从一帧 raw hand 到 10 维软目标的完整会话路径：baseline 五指 IK 后，门控激活时精修 6 个 tripod 关节，失败回退 baseline；拇指固定值/增益在扭转期间跳过、退出恢复；baseline 历史不被写入；反馈只进诊断。工作树已有主体实现；本票补齐人手轴与机器人参考轴同向检查、测试和验收。

**Blocked by:** 01

**Status:** resolved

- [x] 门控激活/退出；精修 applied/fallback；失败原因正确。
- [x] 退出回 baseline，低通平滑；硬限速不变。
- [x] 无名指/小指保持 baseline；baseline `q_last`/`has_valid_ik`/warm start 不变。
- [x] 拇指固定值和增益在扭转期间跳过，退出恢复。
- [x] 有/无反馈命令完全一致；反馈只更新诊断。
- [x] stale 重置 episode 但保留 `theta_task`；恢复后重新进入。
- [x] 人手轴与机器人参考轴反向时不精修并报告失败。
- [x] 左右手状态隔离；baseline 不完整时回退并报告。
- [x] 会话测试全绿，现有逐指 IK 测试不回退。

## Resolution

- `session.py` 补齐：人手轴映射后与机器人参考轴反向/正交时 `axis-mismatch` 回退（不再翻转累积角）；后端缺失报告 `backend-unavailable`；激活失败报告 `human-reference-invalid`。
- `test_twist_session.py` 扩到 15 项：拇指固定值跳过/退出恢复、无名指小指基线、baseline warm start 不被精修写入、baseline 不完整、左右手隔离、反馈 NaN/可用位、stale 公开快照、solver 异常回退、退出低通收敛到 baseline。
- 真实左右手资产核对：映射后人手轴与机器人参考轴点积约 0.99，同向检查不会误封真实手。
- 运行：`ROS_DOMAIN_ID=79 python3.12 -m pytest test/test_twist_session.py test/test_t06_ik.py test/test_normalization.py test/test_retargeting_node.py`，全绿（含现有逐指 IK 回归）。

### Review 修正（2026-10-19）

- `theta_robot_cmd`/`axis_deviation_cmd_deg` 改为从**低通后的实际发布命令**测量，而不是精修/基线中间量；新增 `test_theta_robot_cmd_is_measured_from_the_published_command` 回归。
- 激活帧人手几何瞬时退化不再锁死整个 episode：门控激活期间只要三指几何有效且 tracker 未激活，就重试锁存螺旋轴；机器人三指参考的瞬时 `robot-reference-invalid` 也逐帧重试，`axis-mismatch` 仍视为持续符号约定失败不重试。新增 `test_transient_degenerate_activation_retries_on_later_frames`。
- 删除 `_apply_twist` 中不可达的 backend-unavailable 分支（非空参考意味着后端已在 latch 时可用；顶层 process 已处理后端缺失）；`update_feedback` 删除未使用的 `received_at_ns` 参数。
