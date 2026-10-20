# 对抗性架构评审报告 — `.scratch/hand-swap/spec.md`（review-01）

- 评审对象：`/home/zh/桌面/project/ROTRAC/.scratch/hand-swap/spec.md`（v1.0 Draft）
- 评审方法：构造"下一层两个模块各自 100% 遵守 spec 条文、组合后仍不兼容/出错"的具体场景；对照仓库权威锚点（`omnihand_o10_contracts/joints.py`、`rokoko_hand_receiver/core/decoder.py`、`docs/手套21关键点标准化规范.md`、ADR-0003/0004/0005/0008/0010/0014/0015/0016）。
- 裁决：**FAIL**
- 发现总数：19（阻断 5 / 高 6 / 中 6 / 低 2）

---

## 阻断（Critical）

### C1 原生 thumb_roll / thumb_abad 在 22 DoF 面无承接，且 `from_22dof_standard` 输出秩与顺序未定义 → 关节整体错位或拇指两关节永久失控

- 严重级：阻断
- 位置：spec 附录 B（L1049–1076）、§3.1 `from_22dof_standard` docstring（L470–471）、层 4 转换示例（L367–370）、`AgilinkO10Backend._send_native_command`（L615–618）；权威锚点 `joints.py:44-55`（10 关节固定序）、`joints.py:66-85`（右手 thumb_roll 上限 1.1214 rad）。
- 攻击场景：
  - 模块 A（标准适配节点团队）按附录 B 表实现映射：表中 ✓ 只有 8 行（原生索引 2–9），原生 0（thumb_roll）、1（thumb_abad）无任何标准关节承接；`from_22dof_standard` 按 docstring"提取激活关节"返回 **8 维**向量，顺序为激活索引升序（即原生 2..9）。
  - 模块 B（硬件 backend 团队）按层 4 图"发送 10 维"（L390）与 §3.3 示例实现：`self.sdk_hand.set_joint_positions(positions.tolist())`，按 ROS/SDK 惯例假定入参与 `ACTIVE_JOINT_NAMES` 位置对齐（10 维）。
  - 组合后果：8 维列表按位置喂进 10 维 SDK → thumb_roll 拿到 thumb_mcp 的值、thumb_abad 拿到 index_abad 的值，**每个关节错位两位**。安全复核发生在 22 DoF 面（检查标准索引 2 的限位），对这种错位完全不可见；右手 thumb_roll 限位上限 1.1214 rad，一次正常捏合命令即可驱动拇指辊转超物理行程。另一支同样合规的团队实现"返回 10 维、无承接槽填 0/保持"→ 拇指两关节永久冻结。两条路都逐字符合 spec。
- spec 证据：附录 B 表 L1053–1054（索引 0/1 标"-"）、L1076（"激活关节数：9 / 22"，与表内 8 个 ✓ 又自相矛盾，见 C2）；spec 全文没有 `from_22dof_standard` 输出维度、与 SDK 位置对齐关系、以及"无标准承接的原生关节如何处置（保持/零速/拒绝）"的任何条文。
- 修法：新增条文——`from_22dof_standard` 输出必须为该手 contracts 的 `ACTIVE_JOINT_COUNT` 维、与 `ACTIVE_JOINT_NAMES` 位置对齐；YAML 映射必须显式声明**双向**覆盖（标准→native 与 native→标准），无承接的原生关节必须声明保持策略（hold-last 或零速），加载期校验原生全集覆盖，缺失即拒绝加载。

### C2 同一 spec 内存在三套互斥的激活集：附录 B 表（8 个）、附录 B 计数（"9/22"）、§5.2 集成测试（9 个且集合不同）

- 严重级：阻断
- 位置：spec L1051–1074（表，✓ 集合 = {2,6,7,11,14,15,19,20}，8 个）、L1076（"激活关节数：9 / 22"）、L913（`active_indices = [2,6,7,10,13,15,18,20,21]`）。
- 攻击场景：
  - 模块 A（适配节点团队）按附录 B 表实现：激活集 {2,6,7,11,14,15,19,20}（middle_PIP=11、ring_MCP_AA=14、pinky_MCP_AA=19 有值）。
  - 模块 B（集成测试团队）按 §5.2 L913 断言：{2,6,7,10,13,15,18,20,21} 必须非 NaN——其中 10（middle_MCP_AA）、13（ring_MCP_FE）、18（pinky_MCP_FE）、21（pinky_DIP）在附录 B 表中明确标 NaN；而 11、14、19 被要求非 NaN 却不在测试集合里。
  - 组合后果：两模块各自 100% 遵守条文，集成门禁**永远红**；若团队 B 反过来按 §5.2 实现，则附录 B 中激活的 middle_PIP/ring_AA/pinky_AA 槽位被填 NaN，控制层"只检查激活索引"（L301）将漏检这三个真实驱动关节。两套集合的交集仅 5 个索引。计数行"9/22"又构成第三套（8 行 ✓ 计成 9），任何按计数写断言的实现同样互相矛盾。
- 修法：以附录 B 表为唯一事实重写 L1076 计数与 §5.2 集合；更根本地，规定激活集唯一来源 = HandProfile 加载期从 `mapping_to_22dof` 派生并断言（`active_indices_in_22dof()` 的返回值即测试与门禁的输入），测试禁止再硬编码字面列表。

### C3 `/mocap/{side}_hand/pose` 消息类型自相矛盾：`PoseArray`（§2.2 表、§5.2 测试、维度总结）vs `StandardHandKeypoints`（层 1 图、附录 C）→ ROS 2 类型不匹配静默无连接

- 严重级：阻断
- 位置：spec L433（表："Type: `PoseArray`"）、L899（`pub_mocap.publish(PoseArray(...))`）、L409（"21 关键点 (PoseArray)"）vs L128–146（图：`StandardHandKeypoints`）、L1102–1113（附录 C：msg 定义与 topic）。
- 攻击场景：
  - 模块 A（测试/回放团队）按 §2.2 topic 表与 §5.2 示例发布 `geometry_msgs/PoseArray`。
  - 模块 B（重定向团队）按层 1 图与附录 C 订阅 `teleoperation_interfaces/msg/StandardHandKeypoints`。
  - 组合后果：ROS 2 对类型不匹配的 pub/sub **不报错、不建立连接**，链路表现为永久无数据 → stale → PAUSED，且无任何日志指向"两个团队各抄了 spec 的一节"这一根因。手套规范 §3.2（L104–107）明说"消息类型从 PoseArray 改为 StandardHandKeypoints"，spec 正文四处旧类型残留使两个真相源并存。
- 修法：全局替换 §2.2 表、L409、§5.2 L899 为 `StandardHandKeypoints`；在 §2.2 表加一列"契约来源章节"，门禁扫描 spec 内 topic-type 对一致性。

### C4 `/observation/{side}_hand/joint_states` 单 topic 承载双向流量：适配节点订阅自己发布的 topic，自回环；无方向判别字段

- 严重级：阻断
- 位置：spec §3.2（L513–518：适配节点对**同一 topic** 既发布上行又订阅下行）、层 2.5 图上行/下行框（L229–239）、下行 topic 表 L436。
- 攻击场景：
  - 模块 A（适配节点团队）严格按 §3.2 实现：pub `/observation/...`（上行 22 DoF）+ sub 同名 topic（下行 22 DoF→原生）。ROS 2 默认回环投递：适配节点把自己的 22 DoF 输出逐帧当"下行命令"收下，"提取激活关节"后发布原生 `control_command`。若该 topic 有任何消费者（见 H6），反馈被当作命令再次驱动硬件——反馈极限环；即使无消费者，也是常驻空转转换。
  - 模块 B（控制团队）发现 spec 拓扑里下行通道没有生产者（控制层实际走进程内 HandAdapter，L310–311），为让下行通道生效，让控制节点把 22 DoF 目标发布到 `/observation`——这同样符合 §3.2 的字面（"订阅 /observation 发布 control_command"）。
  - 组合后果：该 topic 上混流两类语义完全不同的帧（IK 目标流 + 反馈/命令流），类型相同、无方向字段，录制、控制、回放都无法区分；控制节点会把反馈帧当命令消费。
- 修法：目标面与观测面分 topic（如 `/target/{side}_hand/joint_states` 承载 22 DoF 目标），或在消息内增加 kind/direction 字段；明文禁止适配节点订阅自己发布的 topic 名；删除或重定义下行通道（见 H6）。

### C5 `/observation` 实为 IK 目标流却被定位为录制/回放"观测面"；硬件真实反馈无 wire 出口；ADR-0003 反馈初始化与 ADR-0010 新鲜读取在新链路中无落点

- 严重级：阻断
- 位置：spec L296（层 3 step 1"接收 22 DoF 命令"——证明 /observation 内容是命令）、L435（表："/observation … 22 DoF 标准（团队规范）"）、L571–577（`read_feedback()` 纯进程内调用）、L437（唯一状态出口是 ControlState 诊断）；权威锚点 ADR-0015 裁定 2（"/observation … 22 DoF 标准面 … 由标准适配节点承担双向转换；录制/回放/可视化与控制"）、ADR-0003（硬限速器必须由"硬件 Adapter 无动作读取的新鲜真实反馈"初始化）、ADR-0010（逐侧 Service 无动作新鲜读取）。
- 攻击场景：
  - 模块 A（录制/回放团队）按执行摘要与 ADR-0015 理解：录制 `/observation` = 手部 22 DoF 标准数据，用于回放与可视化。
  - 模块 B（适配/控制团队）按数据流实现：/observation 上是重定向 IK 的**目标**流；硬件真实反馈只存在于控制进程内的 `read_feedback()`，从不上 wire。
  - 组合后果：录制系统记录的是"我们想让手做什么"而非"手实际在做什么"，可视化与数据集语义系统性错误；ADR-0003 要求的"限速器由真实反馈初始化"、ADR-0010 的"新鲜读取 Service"在 spec 的层 3/层 4 图中没有对应元素。另一个合规团队按 observation 一词的字面义把 `read_feedback()` 结果桥接发布到 /observation → 第二生产者与目标流在同一 topic 交叠，控制节点把反馈帧当命令 → 手在目标与实际状态之间持续抖动。另外，任何 `ros2 topic pub /observation/...` 的调试/回放工具在 ENABLED 态即可直接驱动真机（经控制订阅），spec 无任何访问边界条文。
- 修法：显式拆分"目标面"与"观测面"两个 22 DoF topic，明确各自生产者/消费者与录制归属；把 ADR-0003 反馈初始化、ADR-0010 新鲜读取 Service 纳入层 3/4 数据流图；为 /observation 类可驱动真机的 topic 补充访问规则。

---

## 高（High）

### H6 下行 `control_command` 是孤儿 topic，且与进程内 HandAdapter 双转换路径并存——组合仓库既有硬件 Provider 可完全绕过控制安全层

- 严重级：高
- 位置：spec L436（表：control_command"原生维度控制（下行通道）"）、L236–239（下行框）、L310–311（控制节点进程内调用 HandAdapter）；权威锚点 ADR-0010（hardware_provider 是独立 ROS 节点）、ADR-0015（平行 topic 族含 control_command）。
- 攻击场景：
  - 模块 A（适配节点团队）按 §3.2 实现下行通道：订阅 /observation、发布 `/{hand_id}/{side}_hand/control_command`。
  - 模块 B（硬件侧团队）沿用仓库现状（ADR-0010）：hardware_provider 独立节点按 topic/Service 接收目标——`control_command` 是图里唯一"原生维度控制"topic，自然成为其输入。
  - 组合后果：控制层的安全复核、限位、状态机、硬限速全部发生在控制节点进程内的 HandAdapter 路径上；回放/调试数据一旦进入 /observation（C5 已证无方向判别），适配节点下行直通 `control_command` → hardware_provider 直接驱动真机，**控制安全层被整体旁路**。若 B 不订阅，则 control_command 是无人消费的死 topic，ADR-0015 的平行族成员名存实亡。两条路并存本身（wire 下行 vs 进程内 Adapter）spec 未定义谁是权威路径。
- 修法：二选一并写死：要么删除 wire 下行、声明进程内 HandAdapter 为唯一命令路径（control_command 仅保留给诊断）；要么控制层输出经 wire 下行、进程内路径删除。并明文规定 hardware_provider 的唯一合法命令来源。

### H7 O10 关节事实在 YAML 中重复 owner，违反 A11/ADR-0016；spec §5.3 门禁 allowlist 与 ADR-0016 裁定冲突且看不见 YAML

- 严重级：高
- 位置：spec L481–482（YAML `joints.names: [thumb_roll, thumb_abad, ...]`——O10 关节名第二次成文）、L921–928（A11 门禁 `allowed_packages=[omnihand_o10_contracts, linker_l20_profile]`）；权威锚点 `joints.py:1-22`（"The single code owner … Every other package MUST import from here"）、ADR-0016 裁定 1/2（O10 事实留在 contracts 包；门禁"不再锚定单一包名"，新手指 `{hand_id}_contracts` 包**或配置**）。
- 攻击场景：
  - 模块 A（配置驱动团队）按 spec ADR-4（L983–993"不需要为每只手写子类、所有参数从 YAML 加载"）实现 `ConfigDrivenHandProfile`：关节名、顺序全读 YAML，不 import contracts。
  - 模块 B（硬件 backend 团队）按 ADR-0016 与 joints.py 头注释：一切以 `ACTIVE_JOINT_NAMES` 为准。
  - 组合后果：同一仓库存在两份 O10 关节序真相。YAML 一处笔误（如 `thumb_rol`、或两条目换序）即产生与 SDK 顺序不一致的 10 维契约——A 的链路编译、启动、spec §5.3 门禁全部通过（门禁扫描的是**包名**，YAML 不是包；allowlist 也不含任何配置 owner），到真机才表现为关节乱序。§5.3 的 `linker_l20_profile` 命名既不符合 ADR-0016 的 `{hand_id}_contracts` 模式也不承认配置 owner，按 ADR-0016 改写门禁的团队与按 spec §5.3 实现门禁的团队会互相判对方违规。
- 修法：O10 的 YAML 删除 `joints.names`（改为引用 contracts 导出），或规定配置为唯一 owner 并从 contracts 包删除（后者违反 ADR-0016，需先修订 ADR）；§5.3 门禁按 ADR-0016 重写为逐手"恰好一个 owner（包或配置）"，加载期强校验（名称数、维度、左右限位数目一致——ADR-0016 风险条已明文要求，spec 只字未提）。

### H8 "限位(22 DoF)"没有任何来源定义：YAML 无限位字段，仓库权威限位是 10 维 per-side 代码常量；per-side 符号镜像在标准面的语义未定义

- 严重级：高
- 位置：spec L300（"✓ 限位(22 DoF)"）、L477–506（YAML 示例全文无 limits 键）、L985（ADR-4"所有参数从 YAML 配置加载"）；权威锚点 `joints.py:66-85`（限位 per-side 且符号镜像：右手 thumb_mcp ∈ [0, 0.8416]，左手 ∈ [-0.8416, 0]）、ADR-0016（"配置化契约把 YAML 笔误变成运行期安全事故"）。
- 攻击场景：
  - 模块 A（控制团队）按 spec ADR-4：等 YAML 给限位 → YAML 没有 → 自行从 contracts 取 10 维原生限位，"按映射索引搬运"进 22 DoF 激活槽，**不**做符号归一。
  - 模块 B（另一分支的控制实现）：搬运时按标准名语义（`*_FE` 正=屈曲）做 per-side 符号翻转后再入表。
  - 组合后果：同一条左手命令（如 thumb 槽位 -0.5 rad）在 A 判超限拒发、在 B 判合法放行；两条实现都满足 spec 全部条文（spec 只说"限位(22 DoF)"五个字，未定来源、未定变换、未定符号约定）。更糟的分支：团队 C 在 YAML 里自造 22 维限位字段 → 与 ADR-4 自洽但与"仓库限位唯一 owner 在 contracts"冲突，A28 门禁（L933–935，只扫代码硬编码）对其不可见。
- 修法：规定 22 DoF 激活槽限位的唯一定义式：contracts 原生 per-side 限位经 HandProfile 显式符号/偏移变换生成，变换规则写入 YAML 并在加载期按侧校验（含 0、lower≤upper）；YAML 增加限位段或显式声明"限位派生自 contracts，禁止配置"。

### H9 NaN 三重语义边界未定义：结构性未激活 / 瞬时缺失 / 原生 IK 失败；激活位出现 NaN 时 FAULT 还是 PAUSED 未定义（ADR-0005 分类未被引用）

- 严重级：高
- 位置：spec L257–263（/observation "未激活 = NaN"——结构性）、手套规范 L172–176/L261–263（关键点缺失 = position NaN + 单位四元数——瞬时性）、spec L298–301（"有限性 ✓ / 只检查激活索引"）、L307–308（限速器"跳过 NaN 位置"）、层 2 "滤波 & Stale 恢复"（L183，IK 失败时 native_command 发布什么未定义）；权威锚点 ADR-0005（IK 失败/stale = 可自动恢复暂停；硬件/安全门异常 = 锁存故障）。
- 攻击场景：
  - 模块 A（适配节点团队）：重定向 IK 失败时上游发布了含 NaN 的 native_command（或短暂停发）——spec 未规定哪种；A 选择透传 NaN 到激活槽。
  - 模块 B（控制团队甲）：激活槽 NaN 违反"有限性"→ 进 FAULT（锁存，需人工 clear_fault）。模块 B'（控制团队乙）：对照 ADR-0005，IK 失败属可恢复暂停 → PAUSED 自动恢复。
  - 组合后果：同一次手套抖动，甲的链路锁死等人工干预，乙的链路静默恢复继续运动——安全性与人因负荷完全不同，且都符合 spec（spec 层 3 状态机只列 ENABLED/PAUSED/FAULT 三个词，无迁移条件，也未引用 ADR-0005）。另外手套层 NaN（缺失点）与 22 DoF NaN（结构性未激活）共用记号但语义不同，回放/录制工具若按"NaN=未激活"解释手套缺失帧，会把手套抖动误标为换手事件。
- 修法：逐条写死迁移条件并引用 ADR-0005：激活槽 NaN/无限值 → 按可恢复暂停处理（与 stale 同类），硬件/安全门异常才 FAULT；明确 IK 失败时 native_command 的发布策略（停发 or 显式 invalid 帧）；为两类 NaN 引入区分手段（结构 NaN 由激活索引表判定，不靠值本身）。

### H10 `enable` / `clear_fault` Service 静默复活已被仓库裁定废除的 per-side arming

- 严重级：高
- 位置：spec L324–337（`/o10_control/{side}/enable (SetBool)`、`clear_fault (Trigger)`）、§2.3 L443–444；权威锚点 ADR-INDEX L8（ADR-0004"**已废弃**——`4fedfaa` 已移除 arm/disarm，运动由新鲜目标直接驱动"）、ADR-0008 修订（"`motion_enabled` 为只读派生值，不再有可写的 `armed`"）。
- 攻击场景：
  - 模块 A（控制团队）按 spec 实现 enable 门：SetBool(false) 后即使收到新鲜目标也不动。
  - 模块 B（运维/编排团队，按仓库现状语义）：新鲜目标直接驱动、无授权门（ADR-0004 废弃后的行为），其 resume/stale 恢复逻辑（ADR-0006"先重发保持目标再追赶"）在控制进程外继续供给目标。
  - 组合后果：操作员 SetBool(false) 后确认"手已断能"，但另一条合规模块（状态机未定义 enable 与 PAUSED-resume 的优先级）仍可产生受限命令——"以为断了其实会动"。反向：操作员依赖 enable 作使能步骤，而 spec 层 3 图同时画着状态机自驱——两套使能语义（service 门 vs 状态机）谁覆盖谁未定义。
- 修法：明确表态：要么恢复 per-side 使能（必须先修订/撤销 ADR-0004 并写明与 motion_enabled 的关系），要么删除 enable Service、仅保留 clear_fault 与只读 state（对齐 ADR-0008 修订）。spec 不得与 Accepted ADR 静默冲突（AGENTS.md 明文要求冲突须显式指出）。

### H11 硬限速器"22 维 + 跳过 NaN"与 ADR-0003 的"每条合法新鲜目标至多一条受限命令"组合未定义：部分更新（部分槽 NaN）是否构成"一条目标"、反馈初始化在 22 维下怎么做，均无答案

- 严重级：高
- 位置：spec L307–308（"硬限速器(22 维) / 跳过 NaN 位置"）；权威锚点 ADR-0003（"每收到一条合法的新鲜上游目标，最多发送一条受限命令""必须由…新鲜、合法 10 维真实主动关节反馈初始化""无法获得合格反馈时保持未初始化并拒绝发送"）。
- 攻击场景：
  - 模块 A（控制团队甲）：把每条 22 DoF 消息视为对**全部激活关节**的一次目标——NaN 槽位仅"跳过写入"，但限速时间基准对全部激活关节重新计算。
  - 模块 B（控制团队乙）：只有非 NaN 槽位算"被命令"，仅为这些槽重置限速基准。
  - 组合后果：同一操作者数据（上游部分槽位 NaN 缺失时），甲的手整体速度包络严格 ≤ 乙；两边单元测试各自自洽、全部通过 spec 条文——真机上表现为"同样输入，两版固件一只手快一只手慢"，安全审查无法复现对方结论。初始化侧：ADR-0003 要求反馈初始化，22 DoF 反馈中 12+ 个槽是 NaN，"合格反馈"在 22 维下的判定（只验激活槽？NaN 槽算不算不合格？）spec 未定义，甲可能永不初始化（拒绝发送），乙可能跳过 NaN 槽初始化——启动行为分叉。
- 修法：写死一种语义：激活槽上出现 NaN = 整帧无效（回到 PAUSED，不部分更新），或逐槽失效 + 保持 + 不重置该槽限速基准；并规定反馈初始化只在激活索引集上判定"合格"。

---

## 中（Medium）

### M12 手套契约"单位由手套定义、坐标系透传"与下游"对输入坐标系无假设"组合为假：合规的毫米制新手套被下游绝对量纲门整帧拒收

- 严重级：中
- 位置：spec L1100（"坐标系由手套透传，不做统一变换"）、手套规范 L90（"单位由手套定义，通常为米"）、L62–64（"公司标准不规定统一坐标系……hand_retargeting_node 对输入坐标系无假设"）、§4.1（换手套下游零修改）。
- 攻击场景：Xsens receiver 团队按 §4.1.1/附录 C.4 完全透传（毫米、z-up 世界系）——合规；重定向团队按算法基线增加段长合理性门（绝对米制阈值，spec 未禁止）——合规。组合：毫米帧的段长数值大 1000 倍，合理性门整帧拒绝 → 永久 PAUSED，无任何诊断指向量纲。"无假设"的承诺只对刚体变换成立，对尺度与反射不成立，spec 未把尺度不变性列为重定向的强制要求。
- 修法：契约强制 SI 米制；receiver 加载期/发布期做量纲自检（如腕–中指尖距离合理区间），越界打点告警；frame_id 除标签外强制声明轴约定字符串。

### M13 非有限关键点：decoder 整帧拒收（仓库实证）vs 手套规范"该点 NaN 标记放行"——两种合规 receiver 实现分歧

- 严重级：中
- 位置：手套规范 §4.3（L172–176：非有限值 → 该点 NaN 标记）vs §6.1 条 5（L265–267：缺失/重复"拒绝整帧"——边界模糊）；权威锚点 `decoder.py:124-130`（`_finite_number` 对非有限值直接 raise → `side_rejections` 整帧拒）。
- 攻击场景：receiver 团队 A 沿用现 decoder：偶发非有限值 = 整帧丢弃；receiver 团队 B（按规范 §4.3 字面）= 该点 NaN 标记、帧照发。下游 stale 恢复按 ADR-0006 数"连续整侧有效帧"：B 的链路里 NaN 帧算不算"有效帧"未定义——若算，恢复提前、带着缺失点进 IK；若不算，A/B 在同一手套抖动下恢复时间不同。两团队互指对方违规，规范自身两处条文即可各自援引。
- 修法：规范二选一（建议：非有限值按缺失点 NaN 标记，仅结构性缺失/重复拒帧），同步修订 decoder 行为或在其文档中声明差异；定义"有效帧"是否容忍缺失点及其最大数量。

### M14 配置优先级未定义（YAML vs launch 覆盖）；geometry 示例只有 `right`，`side` 来自 launch——左手启动存在"快速失败"与"静默错几何"两种合规实现

- 严重级：中
- 位置：spec L818（launch `parameters=[{'hand_config': ..., 'side': 'right'}]`）、L490–495（YAML geometry 仅 `right` 子键）、L167（side 为节点参数）。
- 攻击场景：团队 A 实现 `geometry('left')` 缺键即 KeyError——启动失败，安全但违背"换手只改配置"的顺畅承诺；团队 B 缺侧回退 right 值（不镜像）——启动成功、左手 IK 几何全错，且 A28 门禁不扫 YAML。另：ROS 2 中 launch 参数覆盖与 YAML 文件值的生效顺序取决于声明顺序，spec ADR-4 说"所有参数从 YAML"，却未禁止 launch 直传覆盖——测试台架 launch 覆盖某个安全阈值后，"配置单一来源"承诺（§5.3 A28）对 launch 通道失效。
- 修法：规定 hand_config 必须双侧齐备、加载期强校验（引用 ADR-0016 的强校验要求）；launch 只允许传 hand_config 路径与 side，禁止覆盖 YAML 内任何安全参数，并写入 A28 扫描范围。

### M15 spec §6 自造 ADR-1..ADR-5 与仓库 ADR-0001..0020 撞号且内容冲突，引用不可解析

- 严重级：中
- 位置：spec L940–1008；权威锚点 `docs/adr/INDEX.md`（仓库 0001–0020：spec"ADR-4 配置驱动"撞已废弃的 0004 arming；spec"ADR-1 22 DoF 统一接口"与 0015 内容重叠但未引用）。
- 攻击场景：代码注释/评审意见写"见 ADR-4"——一半人理解成 spec 的配置驱动，一半人理解成仓库已废弃的 arming 决策；两个团队各自"遵守 ADR-4"得出相反实现（一个加了 enable 门，一个没加——与 H10 复合）。spec 的 ADR-1..5 均未标注对应仓库 ADR 号，ADR-0014..0020 已就同一换手架构定案而 spec 只字未引。
- 修法：§6 重写为对仓库 ADR-0014/0015/0016/0017/0020 的引用与 delta 说明；本地新增决策改用非撞号命名（如 HS-1..）。

### M16 文档基线过期：头部日期 2025-01-15、附录 D 旧路径、§5.3 旧 A11 锚定——spec 整体基于被 2026-10 ADR 系列取代的草案

- 严重级：中
- 位置：spec L5（"最后更新: 2025-01-15"）、L1082（"Spec 锁定（2025-01-15）"）、L1169（`wayfinder/research/07-hand-adapter-architecture-design-final.md`，实际已迁 `archive/wayfinder-2026-10/`）；权威锚点 ADR-0014..0020 均为 2026-10-15 Accepted。
- 攻击场景：不构成两模块不兼容，但构成系统性风险：实现者按 spec 层 4 图（进程内 SDK 调用）与 §5.3（旧 A11 allowlist）实施，门禁团队按 ADR-0014..0020 验收——双方各有一份"现行"文档，集成阶段才发现层 4 缺 Provider 边界（ADR-0008/0010）、A11 锚定错误（ADR-0016）。日期矛盾使"哪份更新"无法机械判定。
- 修法：spec 重定基线到 ADR-0014..0020，修正日期与附录 D 路径，层 4 图补 O10HardwarePort/Provider 边界。

### M17 §4.2 "换手时 hand_retargeting_node 零修改"与"IK 输出原生维度 + O10 专用耦合梯度 IK"自相矛盾——字面合规而承诺落空

- 严重级：中
- 位置：spec L737（表：retargeting ❌ 不改）、L71/L180–185（"IK 输出原生维度（O10=10 维）/不做 22 DoF 映射"）；权威锚点 ADR-0001/0002（O10 IK 以 10 主动关节为求解空间、SLSQP + MJCF 耦合雅可比——手专用算法资产）。
- 攻击场景：换 L20 时，IK 求解维度从 10 变 22、关节语义全变、耦合结构消失。团队 A 把耦合梯度/求解器写在节点内（spec 层 2 图把"IK"画成节点内部职责，L178–185 支持）→ 换手必改节点代码，"零修改"承诺破产；团队 B 把求解器做成随 HandProfile 注入的策略 → 达标。两种架构都符合 spec 文本，但 §4.3 的扩展能力验收结论相反——"零修改"在 spec 中无操作性定义。
- 修法：定义重定向节点内"手专用知识"的合法形态：只允许经 HandProfile 注入的数据（几何/契约/耦合表）或显式策略接口；把"IK 核心属于节点代码还是可注入组件"写成条文，并据此改写 §4.2 的零修改验收标准。

---

## 低（Low）

### L18 ASCII 图硬编码 `/o10/...` 前缀与参数化 topic 表并存

- 严重级：低。位置：L193/L326 等硬编码 `/o10/` vs §2.2 表 L434/L436/L443 的 `/{hand_id}/` 参数化。攻击：换手后照抄图示 topic 名的调试脚本/录包清单指向不存在的 topic。修法：图注"图中 `/o10/` 仅为 `/{hand_id}/` 的实例"。

### L19 各层频率/QoS/reliability 与时间戳重打策略未定义

- 严重级：低。位置：仅 L143 给了手套层 100Hz；native_command / observation / control 的频率、QoS（reliable/best_effort、depth）未定义；适配节点转发时 header.stamp 重打还是透传未定义。攻击：控制团队按 reliable + 透传 stamp 做 stale 判定，适配团队按 best_effort + 重打本机 stamp——偶发丢帧与 stale 阈值联动出难以复现的 PAUSED 抖动。修法：topic 表补频率/QoS/stamp 策略列。

---

## 核对无误的点（避免误伤）

- 附录 B 的原生索引列与 `joints.py:44-55` 的固定序逐项一致（thumb_mcp=2 … pinky_pip=9）；问题只在原生 0/1 无承接与计数行（C1/C2），映射本身无误。
- `hand_id` 前缀平行 topic 族、`/observation` 22 DoF + 未激活 NaN、标准适配节点为唯一入流新节点、求解留在重定向节点内部——这四点与 ADR-0015/0014 一致，方向正确。
- 手套层 21 点、按名查找、NaN 缺失标记的原则与 `docs/手套21关键点标准化规范.md` 一致；问题在类型残留（C3）与非有限值边界（M13）。

## 修复优先级建议

1. 先修 C1/C2（激活集与映射唯一事实源）——这是安全关键，其他一切测试都建立在它之上。
2. 再修 C3/C4/C5（wire 契约三处方向/类型矛盾）——决定两个团队能否各自开工。
3. H6–H11 需要与 ADR-0008/0010/0003 对齐后一并落条文；M15/M16 的文档基线问题应在下一版 spec 一并清理。
