# acornlib 库组织提案（src/ 重组蓝图）

> 现状：345 个根级 .ac 文件散放在 src/（143 个无法按前缀归类），
> 与 719 个模块的依赖图混在一起。目标：mathlib 风格的分领域组织。
>
> 状态：草案。合并上游完成（verify 通过）后执行；每批一个领域，全库门把关。

## 目标结构

```
src/
  logic/          命题/量词/经典逻辑（logic.ac 等）
  algebra/        群、环、域、模、理想、子结构、同态
    interface.ac  包接口（再导出公共 API）
    group.ac  ring.ac  field.ac  module.ac  ideal.ac ...
    order/        有序群/环
    hom/          hom set 类
  data/           数据结构：nat/ int/ fin/ list/ set/ multiset/ function/ relation
  analysis/       拓扑/度量/连续性/紧致/实数分析
  geometry/       affine/ point2/ 欧氏空间
  category/       范畴论
  combinatorics/  组合（已有包）
  number_theory/  数论（已有包，吸收根级散件）
  complex/        复数分析
  probability/    pmf/测度
  graph_theory/   simple_graph 系列（9 个根文件）
  crypto/         （已有包）
  top100/ minif2f/ 基准（保持）
```

## 迁移机制（验证过的工具链）

1. **move_module.py（待实现，复用 merge_modules 的改写逻辑）**：
   - 根模块 M → 包 P 的子模块 P.M（`src/P/M.ac`）
   - 全部 `from M import` → `from P.M import`（若 M 是包接口则 → `from P import`）
   - 全部证书 `lib(M).` → `lib(P.M).`
   - 移动 `src/certs/M.jsonl` → `src/P/certs/M.jsonl`
2. **包接口**：新包需要 `interface.ac` 再导出公共 API；
   跨包引用一律走接口（与 nat/list/finite_set 现模式一致）。
3. **门控**：每批迁移后闭包 `check --strict` 0 searches + 全库门（1m43s）。

## 分批复盘（每批一个领域，review-sized）

| 批 | 内容 | 根文件数 |
|---|---|---|
| 1 | graph_theory：simple_graph_* 9 个 + 杂散 graph | ~10 |
| 2 | algebra 基础：group/ring/field/monoid/semigroup 家族 | ~60 |
| 3 | algebra 结构：module/ideal/submodule/subgroup/... | ~30 |
| 4 | data：set/function/relation/list 根件 | ~30 |
| 5 | analysis：topology/metric/compact/continuous/... | ~40 |
| 6 | geometry/category/complex/probability | ~40 |
| 7 | 其余 misc（logic/multiset/dynamical/...）逐件归类 | ~140 |

## 命名规则（对齐现有规范）

- 模块名 = 领域前缀 + 原根名（如 `add_group` → `algebra.add_group`）；
- 保留公共定理名不变（证书按名解析，改名会失效）；
- 包接口再导出保持 `from algebra import ...` 兼容旧式导入（迁移期）。

## 风险

- 包私有性：新包子模块若被跨包直接引用会报 "private to its package"——
  必须全部改走接口（脚本强制检查：禁止跨包直接 import 子模块）；
- 接口再导出的名字集合必须覆盖全部使用者（用 decl_extract + import 扫描校验）；
- 每批移动都会触发一次全库 strict（可接受：1m43s）。
