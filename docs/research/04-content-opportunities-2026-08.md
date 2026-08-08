# 内容机会调研（2026-08-08）

> 6 个并行研究 agent 产出，用于 acornlib-omega 内容战役的任务队列。状态标注为调研时快照。

## 一、库内缺口（本地盘点，917 .ac 文件 / 101k 目标）

| 领域 | 现状 | 最大缺口 |
|---|---|---|
| 微积分（R） | 导数/连续性/IVT/Bolzano/exp/log/sqrt 齐全（228 个导数定理） | **无 Riemann 积分、无 MVT/Rolle/Taylor、无 sin/cos/pi、无 exp/log 导数、无一般幂级数 API** |
| 图论 | 不变量层完整（度、支配数、零强迫、团、染色、圈，76 模块） | 无匹配（Hall）、无树/生成树、无平面性、无 Ramsey、无谱 |
| 测度/概率 | 仅 sigma-代数 + Borel（99+23 定理） | 无测度定义、无 Lebesgue、无积分；概率仅离散 PMF |
| 复分析 | 复数代数/度量/序列层完整（22 模块） | 零全纯内容、无 exp/pi |
| 数论 | 基本完备：CRT、二次互反、原根、连分数、四平方和、Dirichlet 卷积（43 模块 2413 定理） | 解析数论、Pell、Bernoulli；digit_sum 展开墙 |
| 组合 | 仅二项式（92 定理） | 生成函数、分拆、Möbius、Ramsey 基础、拟阵 |
| Top-100 | **31/100** 已证 | 见 Benchmark 节 |

硬问题库（hard_problems/，10 个已陈述未证明）：4 个是证明器聚合限制（acorn#48），2 个 digit_sum 展开墙（legendre/kummer digit sum），1 个十进制字面量算术桥（`Nat.23*Nat.3+Nat.2=Nat.71`，卡 miniF2F）。

## 二、上游对比

acornlib-omega 与 acornprover/acornlib 完全同步且领先：0 落后 / 248 领先，上游全部 762 个 .ac 均在 fork 中，上游 7 月底的 baseline-* 批次已吸收。唯一分歧：`src/order_cases.ac` 两个 iff 定理命名（lt_iff_not_gte vs lt_iff_not_ge，纯命名）。

## 三、Lean 对标（卷点）

- Lean 在 Freek 100 达 **84/100**；**16 个缺失项是"首发"机会**，其中 #13 欧拉多面体公式、#92 Pick 定理最现实（acornlib 已有平面图/格点基建）。
- miniF2F 已被 LLM 证明器基本打满（95%+），不再是有效目标 → 转向 PutnamBench（672 个 Lean 语句）、miniF2F_v2、ProofNet。
- 可直接移植的定理：**Bertrand 假设**（acornlib 已有证明骨架：nat_central_binom_bound / nat_prime_central_binom / nat_prime_interval_product）；**两平方和**（二次互反基建齐备）；**n 元 AM-GM**（仅 2 元版本）；**Erdős–Szekeres**（Freek #73，order/list 基建可用）；EGZ（更难，排后）。

## 四、近期猜想（2024-2026 已证/已证伪，可形式化）

| 结果 | 状态 | 形式化要点 |
|---|---|---|
| Bunkbed 猜想**证伪**（Hollom–Portier–Verstraete, PNAS 2025） | 反例 + 已有 Lean 形式化可参照 | 图论 + 有限概率 |
| Erdős–Gyárfás #518（√n 单色路径覆盖）已解 | Pokrovskiy–Versteegen–Williams, JCTB 2025 | 图染色/路径，Gerencsér–Gyárfás 定理是现实目标 |
| Erdős 平面单位距离 #90 **证伪**（OpenAI 2026-05 + Sawin） | 反例构造需代数数论 | 语句+已知界可先形式化（M1 思路） |
| Erdős–Sárközy–Szemerédi 原始集猜想 #1196 已解（2026） | 分析数论 | 语句简单（和/对数/整除） |
| Lonely runner n=8,9 已证（Rosenfeld 2025） | 小情形 n≤4 可在库内证 | 实数 + 取整 |
| Kakeya R³ 已证（Wang–Zahl 2025） | 需 Hausdorff 维数基建 | 语句可形式化 |
| R(5,5) ≤ 46（Angeltveit 2024） | 计算机辅助 | 图论语句极简单 |

来源注册表：erdosproblems.com（已跟踪 solved 状态）、google-deepmind/formal-conjectures（350+ 语句）。

## 五、Benchmark 现状

- **Freek Top-100：29/100 已证**（0.2.6 verify 全绿）。**两个"免费"条目**：#79 IVT 与 #94 余弦定理的库内定理已存在，只差包装器模块（Wave 1 已派 agent）。
- **miniF2F：5/244**；瓶颈是环正规化（十进制算术 + 多项式重排），非库定理缺失。
- **Putnam：无轨道**；2025 年题目是"无污染"新目标（AxiomMath/putnam2025 有机器验证的 Lean 解法，B1/B2 最易移植）。

## 六、ai-kit 内部既存任务（路线图未完成项）

- 上游吸收 chunk 25–29 + 7 个 deferred 超时项（P0，已大部队完成）
- AST 重构器 M1–M4（P0，工具已就绪：reformat_probe/merge_modules/move_module）
- P1 并行管线 / P2 acorn 工具（export-ast、verify --jobs、证书压缩、strict 增量）
- Erdős 单位距离 M1（语句，仅需 Real+FiniteSet）→ M2（几何引理）→ M3（代数数论基建=类群）→ M5（组装）
- miniF2F 十进制算术桥（hard_problems/nat_decimal_arithmetic_bridge.ac）

## 结论：Wave 1 任务队列（2026-08-08 已派）

1. top100 包装器 #79 IVT + #94 余弦定理（免费条目）
2. Bertrand 假设（骨架已存在）
3. 两平方和（二次互反基建齐备）
4. Erdős–Szekeres（Freek #73）
5. n 元 AM-GM（先 3 元）
6. Putnam 2025 B1/B2（新目标）

Wave 2 候选：Riemann 积分 + FTC、sin/cos/pi（exp 级数）、MVT/Taylor、图匹配（Hall）、测度论起步（外测度+Carathéodory）、miniF2F 算术桥、Gerencsér–Gyárfás 定理、单位距离 #90 语句（M1）。
