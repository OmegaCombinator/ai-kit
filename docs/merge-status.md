# 上游吸收进度（2026-08-06）

## 目标

把 `upstream/master`（f32b0ac9，615 commits ahead）全部吸收进
`OmegaCombinator/acornlib-omega` 的 main。当前合并工作区：`/tmp/up-merge`
（git worktree @ a9186ce1，merge 进行中）。

## 合并执行记录

1. **merge drivers**（.gitattributes + gitconfig）：manifest per-key、cert jsonl per-goal
2. **git merge upstream/master --no-commit**：116 冲突 = 6 .ac + 18 manifest + 92 jsonl
3. **resolve_merge_union.py**：6 个 .ac 取上游版本（上游已简化/细化，fork 是旧战役输出）；
   jsonl 按 goal 并集；manifest 按 key 并集
4. **merge_repair.sh 收敛循环**：逐模块 verify（依赖序），失败回退 fork 版本重试，
   仍失败记 BLOCKED（恢复合并版本）
5. **erdos396.ac**（suzumio-acornlib 独有，1059 行）拷入合并树——唯一跨 fork 补漏

## 当前状态（修复循环进行中）

- 已处理 ~23/347 个改动模块：ok / reverted / blocked
- BLOCKED 示例：`src/geometry/point2.ac`（合并版与 fork 版在合并上下文都验证失败——
  依赖改动 + 搜索缺口；需依赖子图回退或修证）
- 预期：多数改动模块快速重放通过；少数（~10-20）回退到 fork 版本；
  个位数 BLOCKED 需要第二层"依赖子图回退"或修证

## 剩余步骤

1. 修复循环完成 → 全库 `check --strict` 门（1m43s）
2. BLOCKED 模块：第二层收敛（回退其被合并改动的依赖到 fork）或保持 fork 版 + 记录
3. 提交合并 commit（AixBot-generated，附 strict totals）→ push origin main
4. 之后：src/ 重组（org_map.json 已备好，535 模块领域映射）

## 关键事实

- 全库 strict 门基准：1m43s @ -j8，99155/99155 OK
- 合并冲突 94% 是派生文件（证书/manifest）——驱动消解
- 上游简化（proof-local 删除）与 fork 旧证明的冲突：取上游，下游由修复循环处理
