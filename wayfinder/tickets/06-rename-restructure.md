---
id: 6
title: 执行清理：重命名规整与目录重组
type: task
labels: [wayfinder:task]
status: open
assignee:
blocked-by: [4, 5]
---

## Question

按票据 04 定稿的**方案 A 扁平化**执行仓库重组与修复，使 ROTRAC 根 = ROS workspace、目录规整、死路径清零。

1. **目录迁移映射**（一律 `git mv` 保留历史）：
   - `Dexhit-worktrees/collection/src/collection/*` → `src/*`（11 包直接铺开，collection 层取消；`Dexhit-worktrees/` 壳移除）
   - `Dexhit-worktrees/collection/DOCS/` → `DOCS/`
   - `Dexhit-worktrees/collection/{README.md,AGENTS.md,CLAUDE.md,CONTEXT.md,HANDOFF*.md}` → 仓库根
   - collection 根级运维+诊断脚本（`init_omnihand.sh`、`start_omnihand_control.sh`、`start_launchpad.sh`、`start_omnihand_right_low_latency.sh`、`clear_o10_fault.sh`、`decode_rokoko_udp.sh`、`record_o10_diagnosis.sh`、`fix_hcan_udev.sh`）→ `scripts/`
   - `omnihand_o10_fixture-f4fd…/` → `omnihand_o10_model/`（provenance.json 留在内部）
   - `runs/`（仅剩 yaml）→ 仓库根 `config/` 或原地 `runs/`（执行时按最小引用改动定，说明理由）
2. **venv 就地修复并改名**：`dexhit_collection/` → `.venv/`（git 忽略，普通 `mv`）；补 `bin/python` 符号链接 → `/usr/bin/python3.12`；修 `pyvenv.cfg`（home/exec_prefix 指向本机）；验证 `.venv/bin/python -c "import pinocchio, nlopt, omnihand"` 通过（vendor SDK 不重装）。
3. **死路径与引用修复**（完整清单见 [research/03](../research/03-runs-and-venv-refs.md)）：`start_launchpad.sh`（/home/hit conda 路径）、`init_omnihand.sh`、`record_o10_diagnosis.sh`、`production_bringup/launchpad/default.yaml:12` 与 `diagnostic.yaml:11`（DEXHIT_COLLECTION_PREFIX）、`production_bringup/scripts/start_omnihand_control.sh`（B 优先/A 兜底逻辑统一指向 `.venv/`）、模型资产根引用（`OMNIHAND_O10_MODEL_FIXTURE` 与 loader 解析指向 `omnihand_o10_model/`）、`retargeting_diag_params.yaml` 新路径。验收：`grep -r "/home/hit\|/home/pkw\|dexhit_collection\|Dexhit-worktrees"` 在源码与脚本中零命中（文档中历史叙述性提及除外）。
4. **requirements 导出**：基于 `.venv` site-packages 生成依赖清单（供真机重建），放 `scripts/` 或 `DOCS/03_工程/`。
5. **根 README 重写**：写入重定向边界定义（Rokoko 手套数据接收 → OmniHand 手指关节角映射的完整数据链路及其运行/配置/测试/文档支撑）、新目录结构说明、构建与测试入口。
6. **自检（本机无硬件口径）**：colcon build（根为 workspace）+ 全部 pytest + architecture_tests 通过。

验收：目标目录树与票据 04 方案 A 一致；死路径 grep 零命中；自检全绿；`wayfinder/` 完好。

### 基线测试债（票据 05 对照实验确认的 17 个迁移旧病，修复后须转绿）
- `chmod +x` 全部运维脚本（A27：init_omnihand.sh 现为 0644）
- 恢复 vendor `third_party/…/lib/libusb-1.0.so` 符号链接（A19，应指向同目录 libusb-1.0.so.x）
- 查明 A18 experimental parameters 门禁失败原因并修复
- bringup `test_right_one_click_starts_tactile_at_30_hz`：脚本 10-4 修改后与测试断言漂移，二选一对齐
- launchpad synthetic/pdeathsig 4 失败：疑死路径致子进程 spawn 超时，随死路径修复复测
- system_test 9 失败：SoftwareO10Provider 图时序（spin_until），评估是否环境性（ROS_DOMAIN_ID/DDS 配置）而非代码问题
- 已知抖动（不阻塞验收，但记录）：hardware_adapter 图计数测试与 o10_control spin 时序测试偶发互换失败
