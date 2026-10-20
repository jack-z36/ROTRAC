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
├── docs/                   # 知识层：架构/接口语义/算法基线/手册 + adr/ + agents/
├── archive/                # 历史归档（默认不读，见 archive/INDEX.md）
├── .scratch/               # 在途工作：spec + 票据（本地 markdown tracker）
├── STATUS.md               # 现状快照：能力基线 / 在途 / 已知问题
├── CONTEXT.md              # 领域术语表（唯一权威）
└── .venv/                  # 数值 Python 环境（pinocchio/nlopt/vendor omnihand；git 忽略）
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

`./scripts/start_omnihand_control.sh`（唯一规范入口；细节见 [docs/全流程启动手册.md](docs/全流程启动手册.md)）。

## 文档入口

- 开始任何任务前先读 [AGENTS.md](AGENTS.md)（agent 路由）与 [STATUS.md](STATUS.md)（现状快照）
- 知识与手册：[docs/](docs/) ｜ 架构决策：[docs/adr/INDEX.md](docs/adr/INDEX.md) ｜ 术语：[CONTEXT.md](CONTEXT.md)
- 跨机器部署：[docs/跨机器部署与构建指南.md](docs/跨机器部署与构建指南.md)
- 在途工作：`.scratch/`（票据）｜ 历史追溯：[archive/INDEX.md](archive/INDEX.md)
