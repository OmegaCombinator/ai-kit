# acornlib 库组织提案（src/ 重组蓝图）— 更新版

> 现状：重组进行中（7 批已提交），根目录散件从 535 降到 ~230。
> 参考结构：mathlib（Lean 标准库）的目录约定。

## 命名依据（回应"为什么叫 data"）

mathlib 的标准布局正是把"类型"放在 `Data/` 下：

```
Mathlib/Data/Nat      Mathlib/Data/Int     Mathlib/Data/List
Mathlib/Data/Fin      Mathlib/Data/Set     Mathlib/Data/Rat   Mathlib/Data/Real
Mathlib/Algebra/Group Mathlib/Algebra/Ring Mathlib/Algebra/Field
Mathlib/NumberTheory  Mathlib/Topology     Mathlib/Analysis
Mathlib/Combinatorics Mathlib/CategoryTheory Mathlib/Probability
```

所以 `data/nat`、`data/int`、`data/fin`、`data/list`、`data/basic(set/function/relation)`
与 mathlib 一致。**`data/arithmetic` 是过渡分组**：把暂不能并入 nat/int/real/rat/zmod
包（interface 机制未就绪）的根散件集中；将来应拆到各自类型目录（mathlib 式）。

## 目标结构（最终）

```
src/
  logic/  algebra/（group/monoid/ring/field/module/basic/order/hom）
  data/（nat/int/real/rat/zmod/fin/list/set/function/relation/cardinal）
  analysis/（topology/metric/sequence/dynamical/real）
  geometry/  category/  complex/  combinatorics/  graph/
  number_theory/  probability/  crypto/  polynomial/
  order/  top100/  minif2f/
```

## 迁移机制与门控

- reorg_batch.py：org_map 驱动批量移动（包守卫：目标首段是已有包则跳过）
- 每批：移动 → 全库 verify → check --strict 101653/101653 OK → commit
- **教训：模块移动可能破坏 sugar 的 strict-replay**（`ideal` 移动后 real_field 的
  `∈` trace 不匹配）——algebra ring/field/module 移动已回退，待"移动前 replay
  稳定性检查"机制

## 已提交批次

1. probability 2. complex+category 3. graph 4. logic
5. data/arithmetic+nat+int+fin 6. data/basic+list+finite+cardinal
7. algebra/group+monoid+basic 8. analysis/topology+metric+sequence+dynamical

## 待办

- [ ] analysis 批次收尾（verify/门/commit）
- [ ] 安全移动 algebra 剩余（add_*/comm_*/semigroup 等，避开 ideal/field/ring）
- [ ] 包接口机制：50 个包内目标根模块（geometry/order/number_theory/polynomial/
      combinatorics/crypto）并入各自包
- [ ] replay 稳定性检查器：移动前对闭包跑 check --strict，不稳定则跳过
- [ ] erdos396 适配（旧 API → 新 list/nat）

## 2026-08-08 更新：analysis 批次回退

- analysis/topology+metric+sequence+dynamical（46 模块）移动后，全库 verify 通过
  （搜索重生成证书）但 **check --strict 失败**：ideal/ideal_product/integral_domain/
  ideal_quotient_universal/group_hom_kernel_subgroup 的 `x0 ∈ Ideal.zero[T0]`
  replay 报 "certificate trace br step does not apply"——`∈` 糖的 elaborate
  受实例解析环境影响，模块移动改变实例作用域 → 旧证书 trace 不匹配，
  且 verify 生成的替代证书也不可重放（prover 生成 bug，与 Top100 #52 同类）
- 已回退；树保持在 9d596902（7 批提交，101653/101653 OK）

## 前置机制（未做不能安全移动）

- [ ] **replay 稳定性检查器**：移动一批模块后，先对受影响闭包跑
      check --strict，任何 replay 失败即回退该批——脚本化到 reorg_batch
- [ ] `∈` 等 sugar 的证书生成 bug 修复（acorn 侧）或绕行
- [ ] 包接口机制（50 个包内目标根模块）

## Replay 稳定性检查器 ✅（2026-08-08 验证）

reorg_batch --verify 现在：移动 → 全库 verify → 全库 check --strict →
**任何 replay 失败自动回退整个批次**。实测：analysis 批（38 模块）移动后
check 命中 `∈` replay 失败（acorn issue #64），自动回退，树回到
9d596902（101653/101653 OK）。

这使得剩余批次（analysis、algebra ring/field/module）可以在
acorn issue #64 修复后安全重试；当前它们被该 kernel bug 阻塞。
