# 实验：merge_modules —— 文件整合保留证书（调研问题 2 的答案落地）

- 日期：2026-08-06
- 环境：acornlib-omega 可丢弃 worktree @ a9186ce1，acorn 0.2.4
- 工具：`tools/refactor/merge_modules.py`

## 结论

**把散落的 .ac 小模块整合成一个模块，可以做到"不重搜、只重放"**（0 searches）：
证书随声明迁移、下游 import 与 `lib(...)` 限定名自动改写、受影响闭包全部
`check --strict` 通过。之前"一整合就要重新搜索证书"的顾虑不再成立。

## 测试 1：两个无下游叶子模块

`bernoulli_pmf`（222 行）+ `affine_span_map`（259 行）→ `merge_demo`（482 行）

- 证书拼接：84 + 42 = 126 行
- verify: 126/126 OK；check --strict: **0 searches, 126/126 OK**

## 测试 2：有下游引用的模块（验证引用改写）

`binary_words`（2138 行，5 个 importer）+ `algebraic_congruence`（1204 行）→ `word_congruence`（3343 行）

- import 改写：5 个文件（`from binary_words/algebraic_congruence import` → `from word_congruence import`）
- 证书 `lib()` 改写：3 个证书文件（ballot_reflection / finite_set binomial / binomial_count）
- 闭包验证：合并模块 + 6 个下游模块全部 `check --strict` **0 searches**
- 修复项：verify 刷新下游包 manifest 的依赖哈希（"dependency hashes out of date" 是预期现象，
  跑 `verify` 即更新；证书本身全部重放成功）

## 过程中发现并修复的工具 bug

1. **import 去重按模块名是错的**：同一模块（如 `list`）可被多次 `from list import <不同名字集>`；
   必须按语句文本去重，否则丢掉名字集合 → `map_contains not found`
2. **import 语句可跨行续行**（行尾逗号），需按"行尾逗号"收集完整语句
3. **旧代码残留 + 变量遮蔽**：`out` 循环变量遮蔽模块名参数，导致 target 路径变成 verify 输出文本
4. **闭包须用新模块名计算**：合并后旧文件已删、下游已改写为引用 `out`，反向闭包以 `out` 为根

## 使用

```sh
python3 tools/refactor/merge_modules.py --root <acornlib> \
  --out merged_module --modules a,b --acorn <bin> [--dry-run] [--commit "msg"]
```

## 下一步

- 真实库整合：把 `simple_graph_*` 系列（或 number_theory 小模块群）按领域整合成规范文件；
- 配套 `split-file`（反向操作）；
- 目录包模块（src/<pkg>/*.ac）支持；
- 名称稳定性协议：拆文件时新模块只承载新声明，旧声明留在原地（见 docs/roadmap.md）。
