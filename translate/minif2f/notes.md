# miniF2F 翻译笔记（2026-08-06）

## 目标问题

`induction_divisibility_3divnto3m2n`：∀n∈ℕ, 3 ∣ n³ + 2n（miniF2F valid 集）。

## 结论：未完成，但产出 prelude + 精确诊断

翻译到 222/224（仅剩两处"多项重组"步骤超时）后，深挖发现是 **prover 搜索能力的
环形规范化缺口**，不是标准库缺定理。按"失败尝试与已验证子引理保留为 proof prelude"
的原则，把已验证引理沉淀为 `prelude_nat_ring.ac`（235/235 OK, 0 searches）。

## 诊断：搜索能做什么 / 不能做什么（acorn 0.2.4）

| 能力 | 结果 |
|---|---|
| 单步分配 `m.suc * m = m*m + m` | ✅ 搜索直接完成 |
| `m.suc = m + 1`、`2m = m + m` | ✅ |
| 复合因子分配 `(m*m+m)*(m+1) = ...` | ✅ |
| 显式 `distrib_left/right`、`add_assoc` 单步实例化 | ✅（作为证明步骤） |
| 多项加法/乘法 **重组**（如 `2x²+x+(x²+2x+1) = 3x²+3x+1`） | ❌ 超时——需 18 步显式链 |
| 多项式展开 `(m+1)³ = m³+3m²+3m+1` | ❌ 超时——需 ~40 步显式链 |
| 多 term 场景下把 `add_assoc` 当重写用 | ❌ 4+ summand 时搜索不尝试 |

本质：prover 没有 ring 规范化/重写链；多项式算术必须手工逐步展开。
这与 `hard_problems/` 里 decimal 算术桥、`nat_decimal_arithmetic_bridge` 同源。

## 对 prover/训练的启示

- hard_problems 应新增：`polynomial_expansion_sq`、`polynomial_expansion_cube`、
  `multi_term_regroup` 三个代表性失败用例（本笔记即完整复现路径）。
- 若给搜索加一个"展开环恒等式"的规范化步骤（如 `(a+b)²`、`(a+b)³` 模式重写），
  miniF2F 代数题会成片解锁。

## prelude 已验证引理（translate/minif2f/prelude_nat_ring.ac）

`dist_suc_left_nat`、`dist_suc_right_nat`、`sq_suc_step_nat`、`suc_eq_add_one_nat`、
`two_mul_unfold_nat`、`compound_dist_nat`、`two_mul_suc_nat`、`regroup_lemma`（18 步）、
另含完整的三次展开链（cube_suc_nat 18/20，未全验证——见下）。

## 未验证的中间引理（保留供后续）

- `cube_suc_nat`（18/20）：`(m+1)³ = m³+3m²+3m+1`，差最后一步重组
- `step_regroup`（10/14）：展开式与 `2(m+1)` 合并到目标形式，差 add_assoc 链

## 复现

```sh
# 需要的引理链（逐步）：d1-d3, s1, s2, s3 → cube 展开 → regroup → step_regroup
# 见 prelude_nat_ring.ac 与上方诊断表；每步独立 verify 均可通过。
```
