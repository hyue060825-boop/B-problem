
# Codex 执行提示词：B-problem Q3/Q4 结构优化、训练与严谨验收

> 目标仓库：`https://github.com/hyue060825-boop/B-problem`
>
> 目标分支：`hy_branch/b45c0d2`
>
> 本轮审查基准提交：`3ddb2d9e914de17f1d2cce8d8f7cf9f4bd423e45`
>
> 核心原则：**先修动作空间、路线、belief 和特征连接，再训练；不得用隐藏真值给部署策略；安全证书不能被近似 belief 或粒子覆盖替代。**

---

## 0. 你的角色与最终目标

你现在是该项目的主算法/工程 Codex。请不要只做局部 patch，也不要只输出建议。你需要在完整阅读仓库、现有报告、测试、训练入口和历史结果后，实际完成一轮**可回归、可消融、可复现**的 Q3/Q4 结构优化实现。

当前最新独立 3000 局结果大致为：

- Q3：3000/3000 完成，平均整局约 3322.42 s，平均约 260.63 s/source；相对旧模型只节省约 14.32 s/局。
- Q4：3000/3000 完成，平均整局约 9879.05 s，平均约 784.35 s/source；相对旧模型节省约 308.35 s/局。
- Q4 的主要耗时不是推理，而是：
  - 移动约 7426.77 s/局；
  - 测量约 1890.05 s/局；
  - 切换频道约 348.43 s/局；
  - 失败清除约 148.72 s/局。
- Q4 当前收益高度集中在 16 源场景；N<16 时仍需逐频道完成覆盖证书，尾部成本很重。
- 当前证据**不支持**“继续增加 PPO 轮数就会大幅改善”的结论。

本轮首要目标不是承诺某个固定百分比，而是：

1. 保持 Q3/Q4 完成率和安全证书不退化；
2. 显著减少 Q3/Q4 移动距离；
3. 显著减少 Q4 已知频道的无效测量、重复同点补测和失败 probe 长尾；
4. 修复候选描述与实际宏动作执行不一致；
5. 让 actor 真正看到候选对应的频道信息、扫描集合和剩余覆盖空间结构；
6. 在上述结构修复后，再做同步 SFT/DAgger/search teacher/PPO；
7. 用全新、隔离的验证和测试集做配对统计，不用已有 3000 局重新选模。

---

# 1. 开始前必须完成的仓库审查

先执行，不允许直接修改代码。

## 1.1 Git 和工作区

1. 检查当前分支、HEAD、工作区：
   ```bash
   git status --short
   git branch --show-current
   git rev-parse HEAD
   ```
2. 目标基准应为：
   ```text
   branch: hy_branch/b45c0d2
   commit: 3ddb2d9e914de17f1d2cce8d8f7cf9f4bd423e45
   ```
3. 如果工作区已有用户未提交修改：
   - 不删除；
   - 不 reset；
   - 不 checkout 覆盖；
   - 先记录清单与 diff；
   - 后续修改避免覆盖用户工作。
4. 不主动 push 远程仓库，除非用户之后明确要求。

## 1.2 必读代码和报告

至少逐文件阅读并建立执行链路图：

### 核心控制/几何/覆盖

- `solution/control/controller.py`
- `solution/geometry/core.py`
- `solution/coverage/certificates.py`
- `solution/planning/q2.py`

### RL 特征、模型、分布式训练

- `solution/rl/environment.py`
- `solution/rl/features.py`
- `solution/rl/model.py`
- `solution/rl/training.py`
- `solution/rl/joint_updates.py`
- `solution/rl/distributed.py`

### 搜索教师

- `solution/search/belief.py`
- `solution/search/teacher.py`
- `solution/search/collection.py`
- `solution/search/gpu/kernel.py`
- `solution/search/gpu/rollout.py`

### 模拟器与真实规则边界

- `bsim/reference.py`
- `bsim/scenarios.py`
- `bsim/research.py`
- `bsim/noise.py`
- `bsim/client.py`
- `bsim/protocol.py`
- 以及与计时、评测、HTTP Session 相关文件。

### 训练、部署与评估入口

完整阅读 `scripts/` 下所有 `.py/.sh`，尤其：

- `run_policy.py`
- `evaluate_checkpoint.py`
- `evaluate_latest_pair.py`
- `evaluate_3000.py`
- `train_ddp.py`
- `train_budget_ddp.py`
- `train_q3_joint.py`
- `q3_gpu_search.py`
- `generate_q3_labels.py`
- `q3_search_preflight.py`
- `q4_preflight.py`

### 当前结论/历史证据

至少阅读：

- `reports/最新模型与3000局测评索引.MD`
- `runs/q34_3000_test_20260912/report.md`
- `reports/Q3搜索教师与专家迭代实验报告.MD`
- `reports/Q4修复与四卡同步复验.MD`
- 所有与 Q3/Q4 最新训练、验证、测试、checkpoint provenance 直接相关的 JSON/MD。

### 测试

完整阅读测试目录，确认：

- 安全证书测试；
- Q4 不存在认证；
- DDP 同步；
- checkpoint/feature version；
- 搜索历史一致性；
- 部署客户端；
- 计时公式；
- 宏动作预算。

完成后先生成：
`reports/Q34_STRUCTURAL_OPT_BASELINE_AUDIT.md`

必须写清：

- 当前执行链路；
- 当前 Q3/Q4 状态机；
- 当前候选空间；
- 当前 actor 输入；
- 当前安全边界；
- 当前训练/选模链路；
- 你实际发现的任何与本提示词不一致之处。

若仓库事实与本提示词冲突，**以固定提交中的代码事实为准，并在报告中解释差异**。

---

# 2. 必须保持不变的安全与信息边界

这是硬约束。

## 2.1 部署策略只能使用公开信息

部署 controller/actor 不得读取或间接泄漏：

- 真实源数量 N；
- 真实源位置；
- 真实半径；
- 真实源类型；
- 真实定向朝向；
- 场景 seed；
- evaluator/kernel 中隐藏 scenario；
- “最后一个真实源已经清除”这样的真值标签。

训练和离线评价端可以访问真值来计算 loss、reward、分层指标，但**不得把这些字段作为 actor 输入或在线动作选择条件**。

必须新增自动化测试，确保 strategy 模块无法接收上述真值对象。

## 2.2 安全证书与规划 belief 分层

将状态明确区分为两层：

### Safety / Certified State

只能由严格几何证明更新，用于：

- `CLEARABLE`
- `ABSENT_CERTIFIED`
- `EXIT`
- certified clear

### Planning Belief

可以是：

- 采样假设；
- 概率；
- 启发式 expected cost；
- reception probability；
- directional hypothesis。

它只能用于：

- 候选排序；
- 候选生成；
- expected cost；
- search teacher rollout。

**Planning belief 不得签发 CLEAR/ABSENT/EXIT 证书。**

## 2.3 Q4 no_signal 不能错误变成 1000m 排除圆

Q4 单次 `no_signal` 的语义可能是：

- 距离超出该源接收半径；
- 或定向源背向机器人；
- 或该频道不存在/已清除。

因此，除非已由其他公开证据证明该频道是全向源，否则：

- 不允许执行 `region.exclude(q, 1000)`；
- 不允许把单点 no_signal 当成整个圆盘不存在证据。

---

# 3. Phase A：低风险结构修复，先做再训练

这一阶段要求尽量不改变安全逻辑，优先消除确定性浪费。

---

## A1. Q3 安全清除点：使用 `safe_point()`

当前 `FeasibleRegion.safe_point(current)` 已实现，但 controller 安全 clear 仍倾向使用 MEC center。

修改：

- `solution/control/controller.py`
- 必要时 `solution/geometry/core.py`

要求：

1. 当 `cert['safe']` 时，调用 `safe_point(self.position)`；
2. 再次用 `certificate(chosen_point)` 验证；
3. 只有严格 safe 才生成 CLEAR；
4. 候选 cost 使用实际 safe point；
5. Q3/Q4 都可使用，但先做独立消融。

新增测试：

- 当前点已安全时不移动；
- MEC center 安全但更远时，safe_point 路径不更长；
- chosen point 对所有 feasible vertices 满足清除半径证书；
- 不改变清除成功保证。

---

## A2. 禁止“同频道同坐标”的无信息重复 LOCALIZE

当前固定误差场、静态源下，同频道在**完全相同坐标**重复测量不会提供新的方向信息。

实现：

- 为 `ChannelState` 提供精确坐标观测索引；
- `legal_actions()` 生成 LOCALIZE 候选前检查 `(channel, exact_position)`；
- 已测过完全相同坐标时，不再生成相同 LOCALIZE。

注意：

- 只去掉完全相同坐标；
- 不要把“附近”粗暴判成相同；
- COVER 对未知频道为证书服务时不能简单去重；
- 对已知频道的 COVER 测量另在 Phase D 处理。

新增诊断：

- `duplicate_exact_measure_candidates`
- `duplicate_exact_measure_executed`

目标：正常运行中两者应为 0（必要证书测量除外需单独分类）。

---

## A3. 修复 PROBE_CLEAR “候选描述 != 实际执行”

当前问题：

- 候选的 `position` 和 cost 根据 `clear_cover` 原顺序；
- 执行时却从全部点中不断选择“离当前位置最近”的点；
- actor 看到的路径和真正执行路径可能不一致。

不要只改 cost；要建立**单一真相的 ProbePlan**。

建议新增：
`solution/planning/probe.py`

例如：

```python
@dataclass(frozen=True)
class ProbePlan:
    channel: int
    points: tuple[tuple[float, float], ...]
    estimated_move_s: float
    worst_case_clear_s: float
    version: str
```

要求：

1. 计划生成时就确定访问顺序；
2. Action 引用 plan 或携带稳定 plan_id；
3. 特征、cost、日志和 execute 全部读取同一份 plan；
4. 不允许 execute 二次偷偷重排；
5. 加断言：首点、顺序摘要、预计成本和实际底层调用一致。

新增测试：

- `candidate_first_point == executed_first_point`
- deterministic same state -> same plan
- plan 中所有点来自合法 continuous clear cover
- plan replay 后证书兜底仍成立。

---

## A4. 把长 PROBE_CLEAR 改成可重新决策的短宏动作

当前 probe 一旦启动可能连续尝试完整 cover，策略无法利用失败后更新的可行域重新决策。

实现两级机制：

### `PROBE_STEP`

- 一次只尝试 1 个点，或最多 `K<=3` 个确定点；
- 失败后立即返回 controller；
- `clear_result(..., success=False)` 更新 20m 排除区域；
- 重新计算 feasible region / clear cover / route / next action。

### `FULL_PROBE_FALLBACK`

- 保留当前完整覆盖作为有限兜底；
- 只在：
  - 预算/状态满足明确条件；
  - 短 probe 无收益；
  - 或策略选择保守完成时触发。
- 不能删除完整证书兜底。

需要报告：

- probe macro 数；
- probe point 数；
- 失败 clear 数；
- P95/P99 失败 clear；
- 单局最大失败 clear；
- probe 移动距离。

---

# 4. Phase B：重做覆盖路线与“清除/补测插入”

Q4 最大开销是移动；Q3 移动同样占主要部分。

当前 `legal_actions()` 只暴露最近三个未访问站点，模型无法理解全局剩余路线。

新增：
`solution/planning/route.py`

---

## B1. Open route planner

输入只能包括：

- 当前机器人位置；
- 固定公开 coverage stations；
- 已完成/未完成公开 mask；
- 必要的 per-channel coverage progress；
- 公开可行域派生任务点。

不得输入真实源坐标。

至少实现：

1. nearest-neighbor 多起点构造；
2. open-path 2-opt；
3. 可选小预算 beam/local reorder；
4. 不要求返回起点；
5. deterministic tie-break；
6. 规模很小，不允许每个宏动作产生不可控计算开销。

API 建议：

```python
plan_open_route(current, points, mask, *, max_ms=...)
```

输出：

- ordered station ids
- route length
- next station
- lower/heuristic diagnostics
- compute time

---

## B2. 任务插入成本

对以下任务：

- certified CLEAR；
- PROBE_STEP；
- LOCALIZE；
- coverage station；

计算相对当前 coverage route 的增量：

```text
detour = dist(prev, task) + dist(task, next) - dist(prev, next)
```

并支持 route start 插入。

候选至少包含：

- 最近站；
- 当前全局 route next；
- 低 detour 的 safe clear；
- 低 detour 的 localize/probe；
- 定位收益高但可接受 detour 的点。

actor 不再面对“任意动作全集”，而面对若干**有意义的路线调度候选**。

---

## B3. 不要删除当前 31 站证书

第一阶段 Q4 路线优化必须：

- 保留现有 31 station set；
- 保留逐频道完整覆盖不存在认证；
- 只优化访问顺序和插入。

这样可以把“路线收益”和“证书重设计收益”分开归因。

---

# 5. Phase C：修复特征连接与模型表达

这是高优先级。不要简单把 hidden 从 128 扩成 1024。

当前网络：

- 20 个 channel token Transformer；
- 最后 `mean(dim=1)`；
- 每个 candidate 接收同一个全局 channel mean。

这会丢失“候选 A 属于频道 c，而 c 的历史几何是什么”。

---

## C1. 新特征版本

创建新版本，例如：

```text
FEATURE_VERSION = normalized-public-v3
MODEL_VERSION   = candidate-cross-attn-v1
```

旧 checkpoint 不得静默加载到新模型。

需要显式 migration policy：

- 旧模型仅作 frozen baseline；
- 新结构从旧共享 encoder 可兼容部分加载时，必须打印 missing/unexpected keys；
- 不允许伪装成无架构变化续训。

---

## C2. 单频道候选绑定对应 channel token

状态中增加：

```python
candidate_channel_index: [A]
candidate_channel_valid: [A]
```

actor 对 `CLEAR / LOCALIZE / PROBE_*`：

- gather 对应 channel encoded token；
- 与 action/global embedding 拼接或 cross-attend。

禁止仅靠 `channel_id/20` 让网络自己猜。

---

## C3. COVER 候选绑定真实扫描频道集合

增加：

```python
candidate_channel_mask: [A, 20]
```

对 COVER/MULTI_MEASURE：

- 对 mask 内 channel tokens 做 masked mean / attention pooling；
- 同时编码：
  - unknown count
  - known count
  - certificate-required count
  - estimated useful known-channel count
- actor 必须能区分两个“频道数量相同但频道集合不同”的扫描动作。

---

## C4. 剩余 station token

不要只给 `visited_ratio`。

增加 station set：

- station xy；
- visited/global completed；
- 每站尚缺多少 unknown-channel certificate measurements；
- route rank；
- current->station distance；
- route-next 标记。

建议：

```python
stations: [S, Ds]
station_mask: [S]
candidate_station_index: [A]
```

模型使用 Set/Transformer 编码，并允许 COVER candidate 读取对应 station token。

---

## C5. 频道几何特征增强

channel token 增加公开可计算字段：

- last positive position；
- last direction position；
- feasible region center；
- radius upper；
- area；
- principal-axis orientation / extent；
- clear safe point distance；
- exact repeated measure count；
- positive observation count；
- negative observation count；
- Q4 directional-belief summary（Phase D 后）。

所有位置优先用：

- 相对当前位置；
- 相对 candidate；
- 规范化坐标。

---

## C6. 频道重编号一致性测试

物理规律不应依赖“频道 3 比频道 17 更特殊”。

新增 permutation test：

- 同一公开状态随机重编号频道；
- 同时重编号 action channel/mask；
- logits 应按 action permutation 等价；
- 数值容差明确。

如果现有绝对 `channel_id/20` 破坏该性质，评估是否：

- 删除绝对 id；
- 或只把 id 用作 gather index，不作为物理特征。

---

# 6. Phase D：Q4 directional planning belief 与自适应测点

这是 Q4 的关键结构优化，但必须与 safety certificate 分离。

新增建议：

- `solution/belief/q4_directional.py`
  或
- `solution/search/q4_belief.py`
  以及 controller 中的轻量 planning summary。

---

## D1. 联合假设变量

每个存活频道的 Q4 planning hypothesis 至少包括：

```text
source_position (x,y)
radius in [1000,1500]
kind in {omni,directional}
heading in [0,360) if directional
fixed measurement error field/hypothesis
```

所有假设只能由公开历史约束。

---

## D2. 正观测约束

`direction`：

- source position 在测向 wedge；
- distance > 5；
- distance <= radius；
- 若 directional，则 robot position 必须处于 source forward half-plane；
- 固定误差必须能重现该量化角度。

`near`：

- distance <= 5；
- 同时必须可见；
- 不代表方向类型已知。

clear success/failure：

- 使用 20m 物理约束；
- success 后该频道已清除。

---

## D3. Q4 no_signal 约束必须是析取

对仍存在的源：

```text
no_signal =
    out_of_receive_radius
 OR (directional AND robot_is_on_back_side)
```

不得变成单一排除圆。

可以：

- particle/hypothesis filter；
- 离散 heading bins；
- position × heading sample；
- conservative interval + Monte Carlo。

但：

- 只用于规划得分；
- 粒子全灭不能直接 `ABSENT_CERTIFIED`；
- belief 退化时必须 fallback 到现有安全路线。

---

## D4. LOCALIZE 候选生成

替换当前固定“左右两个侧翼，最多三次”的机械规则。

对有限候选集评估：

- expected reception probability；
- expected intersection angle；
- expected posterior radius/area；
- expected probability of certified clear；
- movement cost；
- route detour；
- future clear cost；
- channel switch cost。

综合成“预计总剩余成本”，而不是只看本次测量。

候选来源可包括：

1. 已有正观测附近的若干方位；
2. feasible-region 主轴两侧；
3. 当前 coverage route 上的将到站点；
4. 对 heading hypotheses 区分力高的点；
5. Q3 `choose_second()` 思想生成的有限候选，但不要直接把其“全向 guaranteed receive”判据搬到 Q4。

取消硬编码：

```text
localizations < 3
```

改为：

- 只要下一次补测 expected total cost 优于 probe/cover/clear，就保留；
- 同时设置安全的计算与宏动作上限。

---

# 7. Phase E：逐站扫描组合与 per-channel coverage progress

当前 COVER 一到某站会按规则扫描一大批频道，actor 只能选站，不能选 scan set。

需要重构。

---

## E1. 区分两类频道

### 未知频道

其 no_signal 可能用于不存在证书，所以不能随意删除。

### 已发现频道

本次 COVER 是否顺带测量应由：

- directional planning belief；
- reception probability；
- localization gain；
- route cost；
  决定。

---

## E2. MULTI_MEASURE / COVER_SCAN_SET

对同一站提供有限几个 scan set，而不是 2^20 全枚举，例如：

1. `CERT_REQUIRED`：只扫本频道证书仍缺失的 unknown channels；
2. `CERT_PLUS_HIGH_VALUE_KNOWN`：+ 若干高定位价值 known channels；
3. `CURRENT_CHANNEL_FIRST`：若切换节省明显；
4. 必要的保守 full scan fallback。

每个候选携带真实 `candidate_channel_mask`。

---

## E3. 修复 visited 语义

如果一个站只扫描部分频道：

- 不能简单 `self.visited.add(station)` 后永远不再提供该站；
- station 全局到访 != 所有频道该站证书完成。

改为：

- physical_station_visited；
- per-channel station measured；
- per-station required_remaining；
- route planner 根据剩余证书需求决定是否需要返回。

需要测试：

- partial scan 不会导致未知频道永远无法完成证书；
- complete grid 仍能退出；
- 不完整 grid 不能误认证。

---

# 8. Phase F：Q4 可累积覆盖证书（第二优先级研究项）

注意：这一项风险最高，必须在 B/C/D/E 稳定后再做。

当前固定 31 站规则是可靠基线，不可直接删除。

目标：允许任意有效历史测量点逐步形成 directional absence certificate，从而减少 N<16 尾部。

---

## F1. 需要证明的几何命题

要对任意可能 source position `x` 和任意 directional heading `h` 保证：

- 至少存在一个已测量点 q；
- `|q-x| < minimum_receive_radius`；
- q 位于 source 的可见半平面；
- 且不是“仅依赖 source 与 q 完全重合”的退化证明。

可利用：

- 小直径三角形；
- x 位于三角形凸包；
- 对任意方向，不可能所有非退化顶点同时严格落在背向半平面；
- 顶点重合需额外邻点/fan guard。

---

## F2. 建议实现方式

新增：
`solution/coverage/cumulative.py`

输入：

- arena disk；
- 该频道已完成 no_signal 的测量点集合。

输出：

- `certified: bool`
- covered continuous geometry
- residual geometry
- proof diagnostics
- witness triangles / guards

允许使用：

- Delaunay/triangulation；
- 所有边长/直径 < 1000 的合格三角形；
- union 覆盖连续 arena；
- 边界与 coincident guards 的严格验证。

禁止：

- 仅采样若干点“看起来覆盖”就签证书；
- 粒子覆盖率 99.9% 就签证书；
- Monte Carlo 代替连续域证明。

若任何条件无法严格证明：

```text
fallback -> current 31-station certificate
```

---

## F3. 先做离线实验再接 controller

先评估：

- 现有运行历史能否在少于 31 个固定站时完成累积证明；
- 平均可减少多少 station；
- 边缘/顶点/退化情况；
- proof runtime。

只有证明和测试充分后再接入在线 `ABSENT_CERTIFIED`。

---

# 9. Phase G：改进 clear_cover 几何与 probe 路线

当前 `clear_cover()` 主要沿 x/y 最大跨度切分。

增加候选：

- feasible region PCA / principal axis；
- oriented bounding box；
- 非凸 component 分别处理；
- hole 周边覆盖；
- 候选点访问顺序的 open-route 优化。

硬约束：

- 每个生成的圆集合必须连续覆盖整个 feasible region；
- 不能用 sampled particles 替代；
- non-convex、MultiPolygon、holes、窄斜区域都要测试；
- 几何证书和路线排序分开。

输出两个 cost：

1. `worst_case_certified_cost`
2. `planning_expected_cost`

actor 可看到二者，但安全决策只认第 1 类证书。

---

# 10. Phase H：Q4 public-history search teacher

现有 Q3 search teacher 和 `Q3TensorKernel` 明确只支持 Q3 omni，不能简单改 `problem=4`。

在 C/D 稳定后实现新的 Q4 搜索闭环。

---

## H1. Q4 belief world sampler

新增 Q4 公开历史条件假设世界：

- 10–16 source 数的条件提议；
- mixed omni/directional；
- radius；
- directional heading；
- fixed error field；
- 所有历史请求从头 replay；
- 必须逐个响应和 virtual time 完全匹配。

真实 scenario/seed 不传入 teacher。

---

## H2. 搜索动作

至少比较：

- 先 COVER；
- 先 LOCALIZE；
- 先 certified CLEAR；
- 先 PROBE_STEP；
- route insertion；
- 不同 scan set。

比较的是**完整后续成本**，不是单步启发式。

同一根状态所有候选必须使用：

- 同一组相容 hypothesis worlds；
- 同一 frozen continuation policy；
- 同一预算。

---

## H3. GPU 加速

可以分两步：

1. 先用 CPU ReferenceKernel 得到正确 Q4 teacher；
2. 再实现 Q4 tensor kernel。

Q4 GPU kernel 必须支持：

- omni/directional visibility；
- heading half-plane；
- radius；
- clear；
- fixed error；
- discrete boundary fallback；
- 与 reference 的逐操作对拍。

不要为了 GPU 速度牺牲物理一致性。

---

# 11. Phase I：训练策略

只有 A-E 至少完成并通过回归，才开始大训练。

---

## I1. 必须保持“四卡一个模型”

每道题可以有独立模型：

- Q3 model
- Q4 model

但同一道题：

- 4 GPU 是同步训练同一个 checkpoint；
- 不允许四卡独立训练四个模型再挑最好；
- 参数、Adam moments、step 必须同步审计。

继续使用/扩展现有：

- DDP 等步更新；
- global sample weighting；
- empty shard zero-weight；
- global advantage normalization；
- joint KL stop；
- checkpoint provenance。

---

## I2. 训练顺序

建议：

### Q3

1. new feature/model BC warm-start；
2. 新候选下 Q3 search teacher labels；
3. 小规模 overfit test；
4. SFT；
5. DAgger；
6. limited PPO。

### Q4

1. route/feature/belief 规则策略建立强基线；
2. Q4 search teacher；
3. SFT/DAgger；
4. limited PPO；
5. 不盲目延长 PPO。

---

## I3. 蒸馏前必须先做可拟合性检查

当前 Q3 历史中：

- 搜索标签 CE 降低；
- 推荐动作一致率上升；
- 但完整回合收益没有稳定转移。

因此新增：

1. 256–1024 行小数据过拟合实验；
2. 训练集动作 KL/CE；
3. teacher soft target entropy；
4. candidate rank correlation；
5. label weight 分布；
6. anchor KL ablation；
7. softmax temperature ablation；
8. feature-binding old/new ablation。

如果新模型连小数据都拟合不了，不允许继续扩大标签规模。

---

# 12. Phase J：评分目标核对

当前训练 reward 主要优化：

```text
-T
```

而报告重点之一是：

```text
mean_i (T_i / N_i)
```

先阅读正式题目/评分规则，确认真正排名目标。

如果官方目标确实是逐局 `T/N` 再平均：

- N 可以在**训练评价端**用于 episode loss/reward scale；
- N 不得进入 actor state；
- N 不得用于在线选动作；
- 可以在完整回合收集后按真实 N 对该回合所有 time reward 做 `1/N` 权重；
- completion penalty 要独立保留，不能让低 N 失败变得便宜。

做对照：

1. optimize T
2. optimize T/N
3. completion-constrained T/N

若官方目标不是 T/N，不要擅自改奖励。

---

# 13. 实验与消融顺序

严格按以下层次，避免所有模块一次性改完无法归因。

| ID  | 改动                                        | 主要问题         |
| --- | ------------------------------------------- | ---------------- |
| E0  | Frozen current baseline                     | 基准             |
| E1  | exact dedup + safe_point + ProbePlan 一致性 | 确定性浪费       |
| E2  | PROBE_STEP + replan                         | probe 长尾       |
| E3  | global open route + insertion               | 移动             |
| E4  | candidate↔channel binding                  | 表达             |
| E5  | station tokens + scan-set mask              | 覆盖调度         |
| E6  | Q4 directional planning belief              | 无效补测         |
| E7  | adaptive scan sets                          | 已知频道无效测量 |
| E8  | search teacher + SFT/DAgger                 | teacher transfer |
| E9  | limited PPO                                 | 策略微调         |
| E10 | cumulative directional certificate          | N<16 尾部        |

至少额外做以下 2×2 消融：

```text
old candidates + old features
new candidates + old features
old candidates + new features
new candidates + new features
```

---

# 14. 数据集划分与防泄漏

已有 3000 局：

- Q3 `310000000–310002999`
- Q4 `320000000–320002999`

以及审查中额外诊断种子，都视为**已使用分析数据**。

新实验必须新建不重叠区间，并写入 manifest。

至少分：

- train
- validation
- development diagnostic
- final frozen test

final test 只运行冻结模型，不参与：

- 超参数选择；
- checkpoint 选择；
- 阈值调整；
- candidate 规则调优。

---

# 15. 新测试分层

不能只沿用固定“空间类型 × 误差类型”的旧配对。

至少覆盖交叉分层：

### N

- 10
- 11–15
- 16

### Q4 directional composition

- low directional ratio
- medium
- high

### heading

- outward
- inward
- tangent-ish
- uniform random

### radius

- near 1000
- middle
- near 1500

### location

- center
- edge
- clustered
- separated
- arena boundary stress

### error field

- smooth
- zero
- extreme
- 量化边界 stress

报告不得把研究生成器称为官方分布。

---

# 16. 必须记录的新诊断指标

每局至少记录：

```text
virtual_time_s
time_per_source_s
completion
path_length_m
measure_count
channel_switches
successful_clears
failed_clears
probe_macros
probe_points
macro_steps
```

新增：

```text
duplicate_exact_measure_candidates
duplicate_exact_measure_executed

active_localize_count
active_localize_no_signal_count
active_localize_positive_count

cover_unknown_measure_count
cover_known_measure_count
cover_known_no_signal_count

probe_plan_first_point_match
probe_plan_route_match
probe_move_m
probe_failed_clear_count

coverage_route_length_planned_m
coverage_route_actual_m
route_detour_m
clear_insertion_count
localize_insertion_count

station_visits
station_revisits
per_channel_certificate_measurements

q4_belief_effective_hypotheses
q4_belief_reception_probability_at_selected
q4_belief_entropy_or_dispersion

tail_time_after_last_true_clear_s   # 仅离线诊断，绝不能作为在线输入
```

---

# 17. 统计判定

所有新旧模型比较必须：

- same seeds；
- same scenario；
- same physical rules；
- same max_macros；
- same success definition；
- paired comparison。

至少报告：

- completion；
- mean T；
- mean(T/N)；
- median；
- P95；
- P99；
- paired mean delta；
- paired 95% CI；
- faster/tie/slower counts；
- path delta；
- measure delta；
- switch delta；
- failed-clear delta。

Q4 必须单独报告：

- N=16；
- N<16；
- 10–15 各组或至少细分；
- directional ratio 分组；
- radius 分组；
- edge/outward stress。

---

# 18. 验收门槛

## 18.1 硬门槛

任何候选版本若出现以下情况直接拒绝：

1. 完成率低于冻结基线；
2. 非法提前 EXIT；
3. Q4 单点 no_signal 被错误用于安全位置排除；
4. 不完整 directional certificate 被当作 ABSENT；
5. certified clear 失败；
6. 读取隐藏真值；
7. ProbePlan 描述与执行不一致；
8. DDP 参数/Adam 不同步；
9. checkpoint feature/model version 不匹配却静默加载；
10. final test 被用于选模。

## 18.2 性能门槛

不要预先写“必须提升 20%/50%”。

采用分阶段判定：

- E1/E2：确定性 bug/浪费指标明显改善，T 不显著退化；
- E3：paired path length 必须降低，且 T 的配对 CI 至少不明显恶化；
- E4/E5：小数据拟合和完整回合至少一项有可靠改善；
- E6/E7：Q4 known-channel no_signal、重复定位、probe long tail 显著下降；
- 最终模型：completion 100% 后，以官方目标指标为主进行配对统计。

---

# 19. 需要新增/更新的文档

最终必须生成：

## 19.1 `reports/Q34_STRUCTURAL_OPT_IMPLEMENTATION.md`

写：

- 改了什么；
- 每个文件为什么改；
- 算法公式；
- safety vs planning belief；
- feature schema；
- model schema；
- route planner；
- scan set；
- ProbePlan；
- directional belief；
- coverage certificate；
- checkpoint migration。

## 19.2 `reports/Q34_STRUCTURAL_OPT_ABLATION.md`

包含 E0–E10 所有实际完成实验：

- 配置；
- seeds；
- checkpoint；
- 指标；
- paired CI；
- 结论；
- 是否进入下一阶段。

不要隐藏失败实验。

## 19.3 `reports/Q34_STRUCTURAL_OPT_RUNBOOK.md`

必须给其他人复制执行的命令：

- 环境安装；
- pytest；
- CPU smoke；
- CUDA smoke；
- Q3 train；
- Q4 train；
- search label generation；
- checkpoint eval；
- final paired eval；
- resume；
- 日志位置；
- 如何确认 4 GPU 同步；
- 如何确认 seed 不重叠。

## 19.4 `reports/Q34_STRUCTURAL_OPT_FINAL.md`

写清：

- 最终推荐 Q3 checkpoint；
- 最终推荐 Q4 checkpoint；
- SHA256；
- feature/model/code version；
- 相对冻结 baseline 的收益；
- 局限；
- 尚未实施项；
- 哪些成绩只是 LOCAL-RESEARCH，不是官方成绩。

---

# 20. 必须新增/更新的测试

至少覆盖：

### controller

- Q3/Q4 状态机；
- 16 源上界；
- partial scan；
- repeated exact localization；
- ProbePlan；
- PROBE_STEP；
- macro budget。

### geometry

- safe_point；
- clear cover；
- oriented cover；
- nonconvex/hole/boundary；
- certified clear invariant。

### Q4 directional

- front/back visibility；
- no_signal disjunction；
- positive direction consistency；
- heading wrap；
- source/measurement coincident；
- radius 1000/1500 boundary；
- quantization boundary。

### coverage

- current 31-grid certificate；
- incomplete grid rejection；
- cumulative certificate proof；
- fallback correctness。

### features/model

- shapes；
- masks；
- candidate-channel binding；
- scan-set aggregation；
- channel permutation equivariance；
- checkpoint version mismatch。

### distributed

- unequal trajectory length；
- zero local sample；
- global weighting；
- PPO advantage；
- parameter + Adam exact sync；
- resume.

### search

- public-history-only schema；
- Q3 world replay；
- Q4 world replay；
- no hidden field；
- CPU vs tensor kernel parity；
- insufficient hypotheses -> skip/fallback。

---

# 21. 不允许的“伪优化”

以下做法禁止：

1. 直接把真实源坐标做 TSP；
2. 给 actor 输入真实 N；
3. 用真实 heading/type/radius；
4. 用“最后真实源已清除”直接退出；
5. Q4 no_signal 直接 `exclude(1000)`；
6. 粒子 99% 覆盖当安全证书；
7. 只调大网络不改信息连接；
8. 只增加 PPO 轮数；
9. 四卡各训一个模型再挑最好；
10. 在已有 3000 测试集上反复改规则；
11. final test 用于 checkpoint 选择；
12. 为了好看删除慢样本/失败样本；
13. 只报告 T/N 不报告 completion 和 T；
14. 把 LOCAL-RESEARCH 成绩说成官方成绩；
15. 为追求速度去掉 reference fallback/边界审计。

---

# 22. 推荐实际开发顺序

严格按下面执行，每一步通过测试后再进入下一步：

```text
Step 0  baseline audit + freeze provenance
Step 1  exact dedup + safe_point
Step 2  ProbePlan consistency
Step 3  PROBE_STEP + replan
Step 4  open coverage route + task insertion
Step 5  feature v3 + candidate-channel binding
Step 6  station tokens + scan-set masks
Step 7  Q4 directional planning belief
Step 8  adaptive LOCALIZE + known-channel scanning
Step 9  ablation / regression
Step 10 Q3 search teacher refresh + SFT/DAgger
Step 11 Q4 public-history search teacher
Step 12 limited PPO
Step 13 cumulative directional certificate research
Step 14 frozen final paired test
Step 15 final reports + runbook
```

每完成一个 Step：

- 运行对应 unit tests；
- 运行小规模 deterministic regression；
- 保存指标；
- 在报告中记录结果；
- 不允许把多个失败原因堆到最后一起排查。

---

# 23. 你最终向用户交付什么

完成后不要只回复“代码已修改”。

最终回复必须列出：

1. 修改文件清单；
2. 新增文件清单；
3. Q3 新方案一句话总结；
4. Q4 新方案一句话总结；
5. 安全性是否保持；
6. 单元测试结果；
7. smoke 结果；
8. 每个消融结果；
9. 最终推荐 checkpoint；
10. 与冻结 baseline 的 paired 指标；
11. 复现命令文档路径；
12. 所有报告路径；
13. 尚未完成/无法证明的事项；
14. 是否运行了官方模拟器（默认应为“没有”，除非用户另行授权/提供环境）。

不要夸大结论。若某项优化没有收益，要保留代码分支/实验记录并明确说明为什么没有进入最终模型。

---

# 24. 本轮最重要的判断原则

请始终用下面这个优先级做决策：

```text
正确完成与安全证明
    >
公开信息边界
    >
减少结构性移动/无效操作
    >
让模型看到正确的信息
    >
搜索教师质量
    >
SFT/DAgger
    >
PPO 微调
    >
单纯增加训练时长
```

当前 Q4 的主要机会来自：

- 路线；
- directional belief；
- probe 重新决策；
- scan scheduling；
- candidate-channel/station 信息连接；
- 后期的 coverage certificate。

当前 Q3 的主要机会来自：

- safe clear；
- 覆盖路线与清除/补测联合插入；
- Q2 测点质量的有限在线化；
- probe consistency；
- candidate-channel binding；
- 更可拟合的 search distillation。

不要颠倒这个优先级。
