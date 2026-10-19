# 05: 离线回放与验收指标

**What to build:** 把录制数据变成可判断的指标和回归证据：分析 MCAP，计算转角 RMSE/MAE/Pearson、轴偏差、精修应用/回退比例、失败原因和负样本门控误触发率；离线回放 `raw_hand` 通过会话；输出 summary 和逐帧 CSV。

**Blocked by:** 03、04

**Status:** resolved

- [x] 指标公式在合成短 MCAP/CSV 上验证。
- [x] 回放同一段 `raw_hand` 与录制输出在容差内一致。
- [x] summary 含全部指标、回退统计和“物体转角未测”。
- [x] 负样本误触发率可计算。
- [x] 缺失反馈、无激活区间、零方差和 NaN 不崩溃。
- [x] 时间对齐使用消息 stamp 并写清口径。
- [x] 不接管真机；使用合成或录制数据。

## Resolution

- 新增 `scripts/analyze_twist_diagnosis.py`：读取 `TwistState` MCAP，输出 `summary_<side>.json` 与 `frames_<side>.csv`；覆盖反馈/命令转角 RMSE、MAE、Pearson，反馈/命令轴偏差，精修 applied/fallback 比例、失败原因分布、负样本窗口误触发率与激活 episode；缺失反馈、无激活、零方差、NaN 都返回 `available=false`/null 而不崩溃。
- 新增 `scripts/replay_twist_diagnosis.py`：录制 `raw_hand` 离线喂给生产 `RetargetingSession`（同一配置快照、Pinocchio/NLopt 后端），按 stamp 对齐命令、按序列对齐 TwistState，输出差异 JSON。
- `test_twist_analysis.py` 6 项：合成指标、负样本窗口、NaN/零方差、CSV、合成 MCAP 读写。
- `test_twist_replay.py` 4 项：命令按 stamp 对齐、枚举/数值差异、NaN 处理、配置重建。
- `test_twist_replay_integration.py`：真实资产 + 合成 20 帧 MCAP，录制后再回放，17 个命令帧 `max_abs_diff=0.0`，TwistState active/status/failure/角度/目标项全部在 1e-9 内一致。
- 时间口径固定为消息 `header.stamp`；负样本窗口相对该侧首条 `TwistState` 时间。物体实际转角未测在 summary 中显式标注。
