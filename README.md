# ROTRAC — Rokoko → OmniHand 重定向

本仓库实现**灵巧手遥操作重定向**的完整数据链路：

> **Rokoko 手套数据接收 → OmniHand 手指关节角映射**，及其运行、配置、测试与文档支撑。

链路四段（ROS 2 Jazzy，仓库根即 colcon workspace）：

```text
rokoko_hand_receiver（UDP 14043 接收/解码）
  → hand_retargeting（解剖学归一化 + 每指独立位置 IK，pinocchio/nlopt）
  → omnihand_o10_control（软目标限速/状态机/故障锁存）
  → omnihand_o10_hardware_provider（Agilink O10 SDK / HCAN 发送）
```

Launchpad（`rokoko_omnihand_launchpad`）是可选的网页一键编排控制面。

## 目录结构

```text
├── src/                    # 11 个 ROS 2 包（含 third_party vendor SDK）
├── omnihand_o10_model/     # URDF/MJCF 模型资产（provenance.json 记录上游来源）
├── scripts/                # 运维与诊断脚本（init/start/清故障/录制/解码）
├── runs/                   # 运行参数（retargeting_diag_params.yaml，活参数文件）
├── DOCS/                   # 知识 / 约束 / 工程 / 归档 / 复盘
├── CONTEXT.md              # 领域术语表（权威）
├── HANDOFF*.md             # 历次交接文档
├── .venv/                  # 数值 Python 环境（pinocchio/nlopt/vendor omnihand；git 忽略）
└── wayfinder/              # 规划地图（清理与架构重构的决策票据；勿删）
```

## 构建与测试（本机无硬件口径）

```bash
source /opt/ros/jazzy/setup.bash
./scripts/init_omnihand.sh            # 自检 + 构建 11 包 + 运行基线测试
# 或手动：
colcon build --symlink-install        # 仓库根即 workspace
colcon test && colcon test-result
```

数值依赖（pinocchio/nlopt/omnihand SDK）位于 `.venv`；Web 栈（fastapi/uvicorn）用系统 Python。重建数值环境参见 `scripts/requirements.txt`。

## 真机启动（需人工安全确认）

`./scripts/start_omnihand_control.sh`（唯一规范入口；细节见 DOCS/03_工程/09_全流程启动手册）。

## 文档入口

- 开始任何任务前先读 [AGENTS.md](AGENTS.md)（任务路由）
- [项目知识](DOCS/01_知识/INDEX.md) · [项目约束](DOCS/02_约束/INDEX.md) · [当前工程状态](DOCS/03_工程/INDEX.md)
