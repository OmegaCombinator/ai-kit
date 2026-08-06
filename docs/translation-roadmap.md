# 翻译/形式化路线图（translate/）

> 目标：把"标准库能做什么"与"我们要形式化什么"之间的差距，变成一组按依赖顺序、
> 可并行、可验证的里程碑。翻译工作 = 在 acornlib 中补充一般性数学（非问题专属），
> 问题本身只作为验收目标。

## 现状盘点（2026-08）

| 轨道 | 现状 | 位置 |
|---|---|---|
| miniF2F | valid+test 各 1 个文件，5 题已证（mathd_algebra_462、amc12a_2009_p2、mathd_algebra_182、algebra_2rootspoly、mathd_algebra_171）；**Real/十进制算术是硬骨头**（`Nat.23 * Nat.3 + Nat.2 = Nat.71` 超时，`hard_problems/nat_decimal_arithmetic_bridge.ac`） | acornlib-omega `projects/minif2f/progress.md` |
| Top 100 | 仅 README；`src/top100/` 已建（theorem_089/091/096 有证书，疑似半成品） | acornlib-omega `projects/top100/` |
| Erdős | 622 题 AI 可攻击性排序（notes/erdos.md）；erdos396 项目有 Tier1/2 roadmap | acornlib-omega `projects/erdos396/todo.md` |
| translate-mathlib | differential-geometry-and-manifolds、dynamical-systems-and-ergodic-ideas 两个子项目 todo | acornlib-omega `projects/translate-mathlib/` |
| crypto | totient-multiplicative 有详细构造方案 | acornlib-omega `projects/crypto/` |
| hard_problems | 10 个难题文件（prover 搜索超时点） | acornlib-omega `hard_problems/` |

## 核心差距（按依赖顺序）

1. **Real 层**：`from real import Real` 已存在，但算术桥不完整（十进制乘法、
   有序域推理、`a <= b implies ...` 消解）——miniF2F 与 Erdős M1 都卡在这。
   **这是第一优先**。
2. **有限集/计数**：FiniteSet、Finset 已有相当规模（finite_set/*），够 Erdős M1。
3. **代数数论**：**完全没有**（数域、代数整数、理想、类群）——Erdős M3/M5 与
   sum-product 反例的硬需求，也是"严肃数学"的必经之路。
4. **几何/格**：point2、metric、affine 有基础；格/多圆盘/体积论证没有。

## 分轨里程碑

### A. miniF2F（可立即推进，衡量 Real 层进度）
- [ ] 清掉 `hard_problems/nat_decimal_arithmetic_bridge.ac`（十进制算术桥）
- [ ] 每解决 10 题更新 projects/minif2f/progress.md；目标：valid split 全部 122 题

### B. Erdős 单位距离反例（目标见 docs/research/03-erdos-unit-distance.md）
- [ ] **M1 语句**：`∃δ>0, ∀N, ∃n≥N, ∃P: FiniteSet(ℝ²), P.card = n ∧ n^(1+δ) ≤ ν(P)`
      —— 只需 Real + FiniteSet + 计数，是"标准库离严肃数学多远"的第一回答
- [ ] M2 几何引理（格/投影/平均）—— 独立可发表的一般数学
- [ ] M3 数论鸽巢引理 —— 代数数论基建的验收目标（类群 = quotient/equivalence 直接应用）
- [ ] M4 显式两条塔假设（Golod–Shafarevich 不等式 + Shafarevich 关系秩界）
- [ ] M5 组装 Theorem 1.1（条件化）
- [ ] M6（可选）显式指数计算证书

### C. Top 100（每完成一个公开定理才入库 src/top100/）
- [ ] 盘点 src/top100/ 现有 3 个文件状态（theorem_089/091/096）
- [ ] 与 Freek 清单对齐，按"Real 层就绪度"选前 5 个目标

### D. 上游吸收（合并推进）
- [ ] 按 docs/roadmap.md P0 的 merge_pipeline 逐步执行 acornlib-omega 的
      29 步 upstream split-merge 计划（trackers/ 有进度存档）
- [ ] 每批：源合并 → 冲突门 → 闭包重证 → 全库 strict 0 searches → 提交 main

## 工具依赖

- 翻译工作依赖 **Real 层基建**（A 轨就是为它服务的）
- 合并推进依赖 **merge_pipeline**（tools/merge/）
- 库整理依赖 **refactorer**（tools/refactor/，M1 前提已验证）
