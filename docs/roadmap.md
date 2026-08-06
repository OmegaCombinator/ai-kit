# ai-kit 主路线图

> 状态：2026-08 起，由 AI 代理自主推进。每条标注优先级与依赖。
> 详情见 `docs/research/` 三份报告；本文件是执行计划。

## 总原则

1. **验证门不可省**：任何合并/重构结果必须过 `check --strict`（0 searches）。
2. **先工具后内容**：工具能放大后续所有工作的效率。
3. **内容寻址**：manifest 的 blake3 哈希 = 缓存键；未变模块可证明不受影响。
4. **机械归脚本，语义归人/agent**。

## P0 — 合并自动化（进行中）

目标：把"46 个分支手工合并 + 每次全库 strict"降为"机械合并 + 闭包定向重证 + 全库门"。

- [x] `tools/merge/manifest_merge_driver.py`：manifest.json 每 key 3-way 合并驱动
- [x] `tools/merge/conflict_marker_gate.sh`：CI 冲突标记门
- [x] `tools/merge/impact_closure.py`：依赖闭包影响面计算
- [ ] `tools/merge/merge_pipeline.py`：端到端流水线（源合并 → manifest driver → 冲突检测
      → 闭包定向 verify（串行写 manifest）→ 全库 check --strict -jN → 报告）
- [ ] 在 acornlib-omega 上实测：对 7 个未合并 accepted 分支跑 reconciliation
- [ ] 证书内嵌源 blake3 hash（声明级内容寻址）——把"文本冲突"变"可证明无关"
- [ ] 审计证书 JSONL 键：是否含模块路径/位置 → 决定"移动=重键"还是"移动=重证"

预期：50–70% 合并全自动，20–35% 半自动（工具提议 + agent 确认），5–15% 需人工。

## P0 — AST 重构器（下一批）

目标：把 312 个扁平 `.ac` 文件整理成规范目录结构，且不重搜、只重放。

- [ ] M1 实验：验证"纯格式化/注释变化不破坏证书重放"（最关键的前提实验）
- [ ] M1：`reformat` + `split-file`（不改名）—— 复用 acorn `src/syntax/` parser + `pretty` crate
- [ ] M2：`rename-decl` / `move-decl` + 自动 import 修复 + 影响闭包调度
- [ ] M3：`merge-modules` / `rename-module`（兼容 stub 策略）
- [ ] M4：接入 Suzumio toolpack，librarian 可发起重构任务
- [ ] 交付物作为 `acorn-tools refactor`（对齐 docs/acorn-tools-proposal.md）

## P1 — 并行形式化管线

目标：模块 = 工作单元，manifest hash = 缓存键；依赖前沿调度。

- [ ] 目标注册表：证书 goal 指纹查重，杜绝重复证明
- [ ] 依赖 DAG 分层 + 前沿调度（并行度 = 每层模块数）
- [ ] 批量集成队列：staging 分支 + 每批 5–10 模块一次 rebase + 闭包 strict
- [ ] 依赖 fan-out 监控 + 大 import 增长评审门
- [ ] 成本记账：搜索 / 重放 / 集成三项成本分开度量

参照先例：mathlib（olean cache、bors merge queue）、Coq（.vo/.vos/.vok、user-overlays）、
Isabelle AFP（session heap）、Meta ATLAS（数千 agent 库级形式化）。

## P2 — Acorn 工具/补丁（patches/）

- [ ] `acorn export-ast`：暴露 `src/syntax/` parser 为机器可读 AST（JSON）——重构器的底层
- [ ] `acorn verify --jobs N`：模块内多目标并行搜索
- [ ] 证书压缩格式（Metamath 先例：压缩证明加载快 ~50%）
- [ ] `check --strict` 增量重放：只重放受影响闭包（声明级增量）

## P3 — 实际翻译/形式化工作（translate/）

- [ ] miniF2F 翻译推进（现状：valid+test 各若干题；decimal/Real 算术是硬骨头，
      `hard_problems/nat_decimal_arithmetic_bridge.ac`）
- [ ] Top 100 清单选点
- [ ] Erdős 队列（见 docs/research/03-erdos-unit-distance.md 的 M1–M6 里程碑）：
      M1 语句形式化（需实数层）→ M2 几何引理 → M3 数论鸽巢 → M4 显式塔假设 → M5 组装
- [ ] acornlib-omega 与上游合并推进（见 trackers/ 与 upstream split-merge 计划）

## 外部追踪

- 上游：acornprover/acornlib（master，持续扩充）
- 工作 fork：OmegaCombinator/acornlib-omega（235 ahead / 615 behind upstream，见 TODO.md 29 步拆分合并计划）
- 提交 fork：OmegaCombinator/suzumio-acornlib（上游 PR 渠道，head_repo）
- 平台：OmegaCombinator/suzumio（Suzumio 多智能体平台）
