---
id: 7
title: 确定换手适配的模块边界与接口契约
type: grilling
labels: [wayfinder:grilling]
status: open
assignee:
blocked-by: [1]
---

## Question

决定「换一款灵巧手只改少数模块」的架构边界与接口契约——这是任务一 spec 的骨架。HITL 票：与用户真人讨论定案。侦察（票据 01）已给出事实基础：手侧耦合集中在五处、手套侧一个包、中段有残余耦合。

必须讨论并定案的：

1. **手侧适配层的形状**：`o10_contracts/joints.py`（关节名/DOF/限位）+ MJCF 主动-被动耦合 + URDF 几何 + `backends.py`（唯一 vendor SDK 触点）+ 触觉分区——是否收敛为一个 per-hand 的 `HandProfile`/`HandAdapter` 模块（每只手一份实现 + 一份配置资产）？接口签名长什么样（输入软目标关节角，输出厂商命令；错误位/反馈如何进契约）？
2. **手套侧**：receiver 整包即手套适配器，对下游只暴露 `RawHandFrame`——是否把该消息冻结为「通用手套契约」？21 节点名清单目前在 `decoder.py` 与 `hand_retargeting/contracts.py` 重复，收敛到哪一侧？
3. **中段去耦**：归一化/IK/平滑声称手无关，但有拇指专调参数、`ACTIVE_JOINT_NAMES` 引用、耦合模型读取——如何改成由 HandProfile 注入配置，使中段代码零手名硬编码？
4. **配置单一来源**：max_joint_rates / smooth_time_constants 现在散在 shell 脚本 + 两份 launchpad yaml 三处——统一收口到哪？
5. **与现状的关系**：现有 `DOCS/03_工程/01_Spec` 与 CONTEXT.md 的 A11/A12 不变量如何被新 spec 继承或取代？

产出：Resolution 记录模块划分图 + 各适配层接口签名草案（换手 = 换一个 HandProfile 包 + 一份模型资产 + 一份后端配置的「换手清单」雏形），供票据 08/09 写正式文档。
