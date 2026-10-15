# 07 蒸馏日志：O10 调试复盘 → docs/ 知识层

执行日：2026-10-15。源：`archive/old-docs-2026-10/99_learning/O10调试复盘/`（INDEX + 10 篇，2025-08-18 真机调试，arm 门控时代）。
目标：只提取"仍然为真的结论"（硬件怪癖、SDK 行为、判别式、可复用方法论），叙事留在归档区。

## 逐篇记录

| 篇名 | 提取了什么 | 并入哪份文档哪节 |
| --- | --- | --- |
| INDEX.md | 无独立新结论：四问题叠加与六条教训由各分篇承载；"commu_except 不锁存仍有效"已被契约文档原有内容覆盖 | —（不单独提取） |
| 01_归因_错误字16是通信坏了吗 | 链路判活判别式：位置/温度/电流等物理量可读 ⇒ 通信链路通，不被"像故障的名字"吓住 | `docs/全流程启动手册.md` 常见现象表 `commu_except` 行（补充） |
| 02_归因_整手8关节通信异常 | SDK 批量错误接口怪癖：`get_all_error_reports()` 把单关节 commu_except 放大成整手 8 关节同值、间歇返回 0 报告（0 报告 → 错误查询超时锁存）；以单关节 `get_error_report(j)`（j=1..10）为准 | `docs/O10控制契约与安全语义.md` §6"触发式读取"段后新增一段 |
| 03_归因_commu_except是致命故障 | bit4 语义的权威出处：官方 SDK 测试套件定义为"历史通信错误"标记（有通信超时即保留），官方 demo 从不查错误报告直接控制；字段语义以官方源码为准 | `docs/O10控制契约与安全语义.md` §6 厂商位语义**坑**段（补充出处，不重复已有"16 不锁存"结论） |
| 04_归因_arm失败根源_系统锁存逻辑 | 无：修复步骤（bit4 掩蔽 + 测试）是一次性叙事，bit0–bit3 致命 / bit4 不锁存语义契约 §6/§7 已覆盖；"外因排除后回到自身加工逻辑"为通用方法论（见无处安放清单） | — |
| 05_归因_手不动是SDK配置错 | SDK 校验 `hand_device_id` 必须为 1..255 显式整数，传 0 当场 `ValueError` 拒绝；"报错方式是证据"，故意传非法值的反向实验可反证配置线 | `docs/O10控制契约与安全语义.md` §8 新增一条 bullet |
| 06_归因_手不动根源_命令缺name | 现象判读：command 有频率但手不动 ⇒ 先看 Provider 拒收日志 `command name must use the fixed O10 active-joint order`（name 违约整条拒收，与硬件无关） | `docs/全流程启动手册.md` 常见现象表新增一行 |
| 07_归因_反馈假是control逻辑错 | 判别式：feedback_ready 持续 false ⇒ 先 `ros2 topic hz` 确认数据源在发布，再查等待方逻辑 | `docs/全流程启动手册.md` 常见现象表新增一行 |
| 08_归因_反馈假根源_provider不发布 | 无独立提取：加 0.5s 定时器的修复是一次性叙事；周期反馈现状 grep 代码即得（provider `node.py` feedback timer 在）；现象判读已由 07 的新行承载 | — |
| 09_归因_超限是读数异常 | 判别式：超限时对同一关节连续多次采样（复盘 8 次）判稳——稳定 ⇒ 数据干净，是"标准错"；跳变才是数据坏 | `docs/全流程启动手册.md` 常见现象表新增超限行 + `docs/O10控制契约与安全语义.md` §2 处置原则 |
| 10_归因_超限根源_机械零位出界 | 硬件怪癖 + **活陷阱**：装配个体公差使机械零位可落在理论限位外（LEFT `pinky_abad` 实测 -0.186104 < 下限 -0.1850049，差 0.0011 rad）；实测放宽到 -0.19 的校准**未进入当前 `omnihand_o10_contracts`**（已核对 `src/teleoperation_support/o10_contracts/omnihand_o10_contracts/joints.py` `_LEFT_LOWER` 仍为理论值）——该实体手再接入会复发；硬件真实零位优先于理论限位，实测须回写校准 | `docs/O10控制契约与安全语义.md` §2"主动关节顺序与左右符号差异"末尾新增一段 + 手册超限行交叉引用 |

## 未触及的目标文档（复盘无对应域内容）

- `docs/真机IK残差失败判别报告.md`：10 篇复盘均为 control/provider 链路域，不涉及 IK 残差、统计口径或恢复死锁——无新增。
- `docs/系统架构与模块边界.md`：provider 缺周期反馈职责的架构缺口已修复，结构性教训只剩通用方法论（见下）——无新增。
- `docs/Rokoko输入与重定向状态接口语义.md`：复盘不涉及 Rokoko 输入/重定向状态语义——无新增。

## 无处安放结论清单（不硬塞，上报）

1. **通用调试方法论**（教训④"所有外因否定后回到系统自身加工逻辑"、⑥"让日志说话、先看被拒收层"、⑧"文档预告的缺口是未来故障的预告片"，及 INDEX 六条的通用半边）：知识层没有"调试方法论"落点文档，任务约束又禁止新造顶层结构。其具体化部分已分别随 01/02/03/05/06/07 各行并入；纯方法论半边建议将来若建"调试方法"类文档时回收（源：INDEX《核心教训（六条）》与各篇"结论与教训"节，原件在归档区可再查）。
2. **SDK pyi 文档签名与实际用法有出入**（复盘 05 提到 `create_hand_by_hcan(product_type, ...)` 对不上）：细节无法在当前 SDK 安装（`.venv` 编译包 + 仓库内 1.1.8 vendor 前缀）中复核，价值低，未提取。
3. **`query_errors returned 0 reports` 刷屏来自未接入的一侧**（复盘 01）：属批量接口时代日志现象，现行 Provider 已固定逐关节读取；"未接入侧无反馈"的手册既有行（`read_active_joints returned 0 positions`）已覆盖同类现象，0 报告后果已并入契约 §6 怪癖段——不另立。

## 执行备注

- **未运行 `./scripts/init_omnihand.sh`**：本票为纯文档任务（读归档、改 docs/、写日志，无代码/ROS/硬件操作）；且该脚本在本机因已知 CJK 路径构建债必然失败（`.scratch/build-baseline-fix/issues/01`），票 03 已有"与本票无关"先例。
- 所有"仍真"断言已对照当前源码核验：provider 拒收日志 `src/omnihand_o10_hardware_provider_node/omnihand_o10_hardware_adapter/adapters/ros_wire.py:44`；批量接口怪癖与 0 报告后果 `backends.py:243-265`；周期反馈定时器 `node.py:232-249`；bit4 掩蔽 `src/omnihand_o10_control_node/omnihand_o10_control/contracts.py:116-123`；LEFT 下限现值 `o10_contracts/omnihand_o10_contracts/joints.py`（`_LEFT_LOWER` pinky_abad = -0.1850049007113989）及其测试 `test_joints.py:92,96`；vendor SDK `get_error_report`/`get_all_error_reports` 于 `.venv/lib/python3.12/site-packages/omnihand/__init__.pyi:303-304`。
- 归档区原件未改动；无任何 git 操作。
