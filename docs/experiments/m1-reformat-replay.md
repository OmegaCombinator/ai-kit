# 实验 M1：纯格式化/重排是否破坏证书重放？—— 结论：**不破坏** ✅

- 日期：2026-08-06
- 环境：acornlib-omega worktree @ a9186ce1，acorn 0.2.4，`project_format_version = 27`
- 被测模块：`src/bernoulli_pmf.ac`（222 行，84 claims）
- 操作序列：基线 `verify`（84/84，0 searches）→ 三组源码变换 → 每次 `check --strict`

## 结果

| # | 变换 | check --strict | 结论 |
|---|---|---|---|
| 0 | 基线（未改） | 84/84 OK, 0 searches | — |
| 1 | 纯空白规范化（去行尾空白、折叠空行） | 无变化（文件已干净，跳过） | — |
| 2 | import 续行合并 + 声明间空行调整 + 注释文本微调 | **84/84 OK, 0 searches** | 格式化不破坏证书 |
| 3 | 交换两个独立定理 `bernoulli_mass_true` ↔ `bernoulli_mass_false` | **84/84 OK, 0 searches** | 同模块重排不破坏证书 |

## 解读

- 证书按（goal 字符串 + proof 步骤字符串）重放，**与源码文本布局/注释/声明顺序无关**；
  与 Acorn 设计文档 "Robustness to Refactoring"（renaming / reordering / add-remove
  definitions）一致。
- 对重构器的意义：**reformat / reorder / split-file（不重命名）可以做到"不重搜、只重放"**，
  `check --strict` 的 0 searches 就是机器可检查的保证。
- 边界（未在本实验覆盖，仍需测试）：
  - 改名/移动声明：证书里 `lib(<module>).<name>` 限定名需要文本改写，或依赖闭包重放；
  - 模块内声明顺序敏感点：`attributes`/`numerals`/`instance`/类型类实例的解析可能依赖顺序；
  - 大模块重排后全库 strict 的时间成本（本实验单模块 <1s）。

## 复现命令

```sh
git worktree add /tmp/refactor-exp HEAD   # acornlib-omega
cd /tmp/refactor-exp
export ACORN_BIN=/data/acorn_venv/workspace/acornlib/bin/acorn-0.2.4-linux-x64
$ACORN_BIN verify src/bernoulli_pmf.ac
# 对 src/bernoulli_pmf.ac 施加空白/注释变换（见 tools/refactor/experiments/）
$ACORN_BIN check --strict src/bernoulli_pmf.ac
# 期望: 84 certificates cached / 0 searches performed / 84/84 OK
```

## 下一步

- 把变换脚本化（`tools/refactor/`），接 acorn `src/syntax/` parser 做真正的 AST 重构；
- 测试改名/移动声明场景（证书文本改写的可行性）；
- 测试 `attributes`/`instance` 块随声明迁移。
