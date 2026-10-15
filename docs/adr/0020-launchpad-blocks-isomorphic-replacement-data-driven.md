# ADR-0020：Launchpad 方块同构替换、内容数据驱动

- 状态：Accepted
- 日期：2026-10-15
- 范围：`rokoko_omnihand_launchpad` 方块语义、编排配置、前端面板

## 背景

L-Spec 七方块（receiver/retargeting/control/hcan provider/sim provider/合成源/录制器）与业务节点一一对应；其中 hcan provider 方块名、10 关节曲线、错误位事件流绑定 O10/Agilink。ADR-0012 已锁定 Launchpad 是最外层设备编排层，业务包不得反向依赖。换手后方块语义如何泛化，票据 7.2 列为两可的 D7。

## 备选方案

1. **Provider 无关的抽象方块层**：前端完全不感知具体 Provider 类型；代价是在只有一种真机 Provider 的现实下过早抽象，方块—节点一一对应结构被破坏，组合校验规则（hcan/sim 互斥、合成源红横幅等）失去具体锚点。
2. **每手一套面板与编排配置副本**：改动最局部；代价是工具层分叉，每手维护一份前端与校验逻辑，必然漂移，违背 ADR-0012 的单点编排定位。

## 裁定

同构替换：方块结构不变（仍与业务节点/Provider 一一对应），方块内容由 `config/{hand_id}_params.yaml` 数据驱动——hcan provider 方块中性化为"hardware provider"，关节曲线由前端读取该手关节契约的名称动态渲染，录制清单随该手 topic 族生成。编排安全底线（PDEATHSIG、崩溃不自动拉起、不暴露操作 Service、真机禁引 system_test）原样继承。

## 后果

- 新手接入 Launchpad 只需新增编排配置，前端框架与组合校验规则零分叉。
- 代价：前端必须实现动态关节数渲染与 NaN 灰显（票据 12 明确列为独立后续工作）；"hardware provider"中性命名丢失传输方式具象信息，操作者需从配置确认实际传输。
- 风险：配置错误会直接改变编排行为，per-hand 编排配置必须纳入组合校验门禁；录制清单若漏跟该手 topic 族，会出现录制覆盖缺口。
