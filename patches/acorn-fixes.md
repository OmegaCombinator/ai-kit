# acorn 待修复项（patches/ 跟踪）

| # | 问题 | 复现 | 影响 |
|---|---|---|---|
| 1 | `simplify` masked-reproving bug | `acorn simplify --dry-run src/ballot_reflection.ac` → "candidate passed masked reproving but edited source does not verify at lines 237-238" | 大模块无法自动清理冗余证明步骤 |
| 2 | 搜索无 ring 规范化 | `(m+1)² = m²+2m+1` 超时；多项重组超时（见 translate/minif2f/notes.md） | miniF2F 代数题大面积受阻；hard_problems 应补 3 个用例 |
| 3 | `check` 不接受目录 target | `check --strict src/` → "invalid character in module name: '/'" | 全库门必须不带 target |
| 4 | `verify -j` 参数解析 | `verify -j 8` 报错（需 `--jobs 8`） | 文档/脚本一致性 |

## simplify 命令调研（2026-08-06）

- 用途："Remove proof-local propositions that weak search can rediscover"
- 参数：`--dry-run --timeout <sec> --activations <count>`
- 实测：bernoulli_pmf 正常（would remove 2 propositions）；ballot_reflection 触发 bug #1
- 相关 CLI：`export`（defs/theorems/types → JSONL）、`citations`、`lint`（unused imports）
