# 实验 E2E：merge_pipeline 端到端实测

- 日期：2026-08-06
- 环境：acornlib-omega 可丢弃 worktree @ a9186ce1，acorn 0.2.4
- 场景：合成分支 `test/ai-kit-merge-demo`（新增 1 个模块 `src/ai_kit_demo.ac`，
  1 条定理 `ai_kit_demo_add_zero`，含证书与 manifest 条目）→ 合并回基线

## 结果（`--strict-scope closure`）

| 步骤 | 结果 | 耗时 |
|---|---|---|
| ① 源合并（git merge --no-commit --no-ff） | 干净（Automatic merge went well） | — |
| ② 冲突标记门 | OK | — |
| ③ 影响面（git diff --cached → impact_closure） | changed=[ai_kit_demo], closure=1 | — |
| ④ 闭包定向 verify | 1/1 OK, **0 searches**（证书缓存命中） | 2.3s |
| ⑤ strict 门（closure 范围） | OK | 2.5s |
| 总计 | **6.1s** | |

## 过程中发现并修复的问题

1. **复制已验证模块会触发搜索超时**：把 `bernoulli_pmf.ac` 复制成新模块名后 verify
   5/84 搜索超时——**证明搜索不稳定**，证书是搜索的缓存，新名字 = 重新搜索。
   佐证：新建模块应尽量"小 + 显式证明步骤"（demo 模块 1 定理 0 searches 通过）。
2. **`check` 不接受目录 target**：全库模式必须不带 target（默认扫 `src/`）。
3. **根 `build/manifest.json` 不跟踪新模块**：新模块记录在 `src/certs/manifest.json`；
   影响面计算改用 `git diff --cached --name-only`（merge --no-commit 后的暂存差异）
   作为变化来源，比 manifest diff 可靠。
4. **包内模块私有**：`from nat.nat_base import` 报 "private to its package"，
   必须从公共接口 `from nat import` 导入；数值字面量需要显式类型（`Nat.0`）。

## 结论

- 机械合并流程（源合并 + 冲突门 + 影响面 + 定向重验 + strict 门）**全自动可行**，
  单模块合并 <10s（不含全库门）。
- 全库 strict 门是唯一昂贵步骤（见下方基准计时）；开发期用 closure 范围迭代，
  集成时跑一次全库门（`check --strict -jN`，只读可并行）。
- 下一步：对真实未合并分支（origin/accepted/domain/* 7 个）跑 reconciliation。
