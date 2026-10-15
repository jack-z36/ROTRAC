# 票 02 判定表：知识层蒸馏（逐份缓存测试）

> 判据：新会话的再生成本。grep `src/`（含 `.msg/.srv` 注释、`package.xml`、脚本默认值）就能便宜再生的不写；深读全库、跑实验、踩坑才能得到的必须保留。死路径（`src/collection/` 前缀、`/home/hit` 机器路径）逐处修正。
>
> 执行日：2026-10-15。抽样验证：话题/触觉/read_active_joints 在 provider/retargeting/receiver 源码命中；`RawHandFrame.msg`/`RetargetingState.msg`/`O10ControlState.msg` 注释携带大量语义；`init_omnihand.sh` 列全 11 包；`provenance.json` license_confirmed=false；`anatomical_correction.py` 证实左右手符号修正已演化为代码级实现。

## 01_知识（12 份正文，INDEX/ADR 按票不计）

| 原文档 | 判定 | 去向 | 理由（一句） |
| --- | --- | --- | --- |
| 00_项目总览.md | 并 | `docs/系统架构与模块边界.md` §1 | 四阶段主链与产物边界语义是定位知识，但正文大半是旧文档体系自述（已失效），只剩半页值得保 |
| 01_模块边界与数据流.md | 并 | `docs/系统架构与模块边界.md` §1 | 跨阶段边界原则 4 条有长期价值，阶段表本身随主链表合并，无独立成篇必要 |
| 02_OmniHand_O10控制契约与模块边界.md | 并 | `docs/O10控制契约与安全语义.md` | 硬限速公式/使能派生条件/故障锁存判别是安全核心；其"当前实现缺口/目标设计"状态口径已过时（限速已实现、arm 已移除），按现状重写 |
| 03_人手归一化与O10单指IK算法基线.md | 保留 | `docs/人手归一化与O10单指IK算法基线.md` | 全库最贵文档：坐标系约定、冻结规则、耦合多项式系数、IK 判别式全靠它穿越会话；仅修链接/限位单一来源注记/§14 过时未决项 |
| 04_Rokoko原始手部帧ROS接口契约.md | 并 | `docs/Rokoko输入与重定向状态接口语义.md` | 消息字段/QoS 数值 grep 即得；保留的是时间语义、坐标标签、按名校验、失败隔离这些"读不出的语义"，与 05 合并成一篇 |
| 05_手部重定向状态ROS接口契约.md | 并 | `docs/Rokoko输入与重定向状态接口语义.md` | 枚举值已在 msg 文件；保 NaN-not-0 约定、ready 与 command_published 组合语义、诊断不驱动控制的安全理由；字段表与 04 大量同构 |
| 06_O10控制状态ROS接口契约.md | 并 | `docs/O10控制契约与安全语义.md` §5–6 | 与 02 重复 motionEnabled 公式和故障位语义（commu_except 理由只讲一次）；保 phase/event/result 的语义解读与"布尔与 phase 冲突即不变量失效" |
| 07_Collection运行环境与真机前置条件.md | 保留（改写） | `docs/运行环境与真机前置条件.md` | 硬件前置条件/环境双边界/Launchpad 安全红线是环境知识；conda 路径与 `src/collection/` 死路径已按 `.venv`/`init_omnihand.sh` 现状重写 |
| 07_O10操作者控制操作ROS接口契约.md | 并 | `docs/O10控制契约与安全语义.md` §7 | clear_fault 同步流程/失败优先级/幂等边界是操作安全知识；为什么是 Service 的论证值得留；结果码枚举值留 srv 文件 |
| 人手归一化算法细节设计：坐标系转换.md | 删 | —（不迁出归档） | ChatGPT 聊天导出（非成文文档），内容被算法基线 §3/§6 完全覆盖，且其左手 +X 约定（拇指侧→小指侧）已被基线冻结约定（小指根→食指根）推翻 |
| ARCHITECTURE.md | 并 | `docs/系统架构与模块边界.md` | 分层理由/禁止边动机/Port 所有权/未决问题贵；A01–A27 门禁表与依赖 DAG 图是 architecture_tests 与 package.xml 可再生的，压缩为指针；`src/collection/` 布局全部修正为扁平 11 包 |
| INDEX.md | 跳过 | — | 票面豁免；新 docs/ 索引由票 09 统一处理 |

## 03_工程（候选筛查）

| 原文档 | 判定 | 去向 | 理由（一句） |
| --- | --- | --- | --- |
| 00_当前状态.md | 留归档 | — | 状态类：已被仓库根 `STATUS.md` 取代 |
| 01_Rokoko到OmniHand_O10实时遥操作系统Spec.md | 留归档 | — | Spec 类：一次性需求裁定，其稳定结论已沉淀进 ADR 与知识文档 |
| 02_Rokoko到OmniHand_O10实施计划.md | 留归档 | — | 计划票据，再生价值为零 |
| 03_测试总览与追踪矩阵.md | 留归档 | — | 测试票据：矩阵随测试代码演化，`colcon test`/pytest 即现状 |
| 04_接口模型与算法契约测试.md | 留归档 | — | 测试票据类 |
| 05_组件与ROS图行为测试.md | 留归档 | — | 测试票据类 |
| 06_系统集成与架构门禁测试.md | 留归档 | — | 测试票据类；门禁真身在 architecture_tests 包 |
| 07_真机IK残差失败判别报告.md | 保留（迁移） | `docs/真机IK残差失败判别报告.md` | 跑实验才有的数字（折返半径、‖u‖ 全帧统计、B/C 排除证据）+ stale 恢复死锁坑；修 `src/collection/` 路径并标注旧工作树证据，加 2026-10 后见注记 |
| 08_Launchpad网页一键启动遥操作系统Spec.md | 留归档 | — | Spec/launchpad 票据类 |
| 09_Rokoko到OmniHand_O10全流程启动手册.md | 保留（迁移） | `docs/全流程启动手册.md` | 硬件安全操作知识基本全保；修入口路径（`scripts/`）、env（`.venv`/仓库根模型资产）、wrapper 路径，补 BLOCKED_ENV 常见现象 |
| launchpad/ | 留归档 | — | launchpad 票据目录，票面明示跳过 |

## 产出对照

- 写入 `docs/`（7 份，平铺中文文件名）：`人手归一化与O10单指IK算法基线.md`、`O10控制契约与安全语义.md`、`Rokoko输入与重定向状态接口语义.md`、`系统架构与模块边界.md`、`运行环境与真机前置条件.md`、`全流程启动手册.md`、`真机IK残差失败判别报告.md`。
- 未触碰：`docs/adr/`、`docs/agents/`、仓库根所有文件；归档区只读。
- 置信度最低判定：ARCHITECTURE.md 的压缩尺度——A01–A27 门禁表按缓存测试应删（测试代码可再生），但其中 A14/A21 两条 manual-review 项和无 DAG 图后的"禁止边+理由"是否够新会话重建全貌，没有第二个会话验证过。
