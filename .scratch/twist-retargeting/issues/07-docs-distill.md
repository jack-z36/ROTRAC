# 07: 文档、ADR、STATUS 与文档门禁

**What to build:** 把扭转层变成可维护的稳定知识并完成关票蒸馏：三项 ADR、算法文档、`TwistState` 接口语义、STATUS 更新、术语裁定、根目录论文散文件处置和 `doc_gate.sh` 清零。真机试点结果由 06 提供；06 未完成时明确标注未验证。

**Blocked by:** 02、03、04、05（试点结果部分由 06 提供）

**Status:** resolved

- [x] ADR：残差精修叠加 baseline；运行时解析梯度、禁止差分；独立诊断 topic 与录制边界。
- [x] 算法文档：门控、角度、目标、有效性门、未标定项、与论文差异。
- [x] 接口文档登记 `twist_state` 的 topic、字段、枚举和 NaN 约定。
- [x] STATUS：能力基线、在途、已知问题（物体转角未测、参数未标定、O10 6 关节限制、左手试点）。
- [x] 新术语裁定：CONTEXT 或局部定义，避免重复。
- [x] 根目录 `核心参考论文.md` 散文件处置有明确结论。
- [x] `scripts/doc_gate.sh` error 为 0；warning 记录。
- [x] 06 未完成时，试点结果和分析数字标注“未验证”，不得写成通过。

## Resolution

- 新增 `docs/adr/0021-twist-refinement-layered-on-baseline.md`、`0022-twist-runtime-analytic-gradient.md`、`0023-twist-diagnostics-independent-topic-and-recording.md`，并登记 `docs/adr/INDEX.md`。
- 新增 `docs/扭转功能层算法与验收基线.md`：门控、人手意图、机器人参考、四项目标、解析梯度、有效性门、失败原因、诊断/录制/分析/回放、未标定参数、与论文差异和已知限制。
- `docs/Rokoko输入与重定向状态接口语义.md` 新增 `TwistState` 一节（topic、字段组、枚举、NaN/可用位、反馈只读、发布与录制边界），相关文档编号顺延。
- `CONTEXT.md` 新增“扭转功能层”六个术语：三指捏合门控、螺旋轴、累积转角、本次目标增量、扭转残差精修、扭转诊断录制。
- 根目录 `核心参考论文.md` 移入 `.scratch/twist-retargeting/research/核心参考论文.md`（外部文献不复制进稳定知识层）；算法文档以文字引用工作树路径，spec 的两处指针同步。
- `STATUS.md` 更新能力基线、在途、已知问题（物体转角未测、参数未标定、O10 6 关节、左手试点、5 项既有 fault 失败、A18 拇指默认值冲突）。
- `./scripts/doc_gate.sh`：74 个活文档、74 条链接，**0 error, 0 warning**。
- 票 06 未执行；所有文档明确写“未验证”，没有把试点结果或物体级成功写成通过。
