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
- [x] `tools/merge/merge_pipeline.py`：端到端流水线，**已在 acornlib-omega 实测通过**
      （单模块合并 6.1s；全库 strict 门基准 **1m43s @ -j8，99155/99155 OK, 0 searches**）
      —— 见 docs/experiments/e2e-merge-pipeline.md
- [x] **reconciliation 核查（2026-08-06）**：acornlib-omega 全部 37 个远端分支
      （含 7 个 accepted/domain/* 与全部 integrate/submit 分支）**均已并入 origin/main**——
      7 月 27 日清理合并已吸收；账目报告中的"未合并分支"清单已过时
- [ ] 用 merge_pipeline 执行剩余上游吸收（chunk 25–29 + 7 个 deferred 超时项）
- [ ] 证书内嵌源 blake3 hash（声明级内容寻址）——把"文本冲突"变"可证明无关"
- [ ] 审计证书 JSONL 键：是否含模块路径/位置 → 决定"移动=重键"还是"移动=重证"

预期：50–70% 合并全自动，20–35% 半自动（工具提议 + agent 确认），5–15% 需人工。

## P0 — AST 重构器（M1 已确认 ✅）

目标：把 312 个扁平 `.ac` 文件整理成规范目录结构，且不重搜、只重放。

- [x] **M1 实验（2026-08-06，acorn 0.2.4，bernoulli_pmf 84 claims）**：纯格式化（import 续行
      合并/空行归一/注释微调）与同模块声明重排后 `check --strict` 均 **84/84 OK, 0 searches**——
      **证书不随格式/顺序变化**，重构器前提成立（见 docs/experiments/m1-reformat-replay.md）
- [x] `tools/refactor/reformat_probe.py`：可复现的格式化探针（原位变换 → strict check → 恢复）
- [ ] M1：`reformat` + `split-file`（不改名）—— 复用 acorn `src/syntax/` parser + `pretty` crate
- [ ] M2：`rename-decl` / `move-decl` + 自动 import 修复 + 影响闭包调度
- [ ] M3：`merge-modules` / `rename-module`（兼容 stub 策略）
- [ ] M4：接入 Suzumio toolpack，librarian 可发起重构任务
- [ ] 交付物作为 `acorn-tools refactor`（对齐 docs/acorn-tools-proposal.md）

## P1 — 并行形式化管线

目标：模块 = 工作单元，manifest hash = 缓存键；依赖前沿调度。

- [x] `tools/dup_scan.py`：证书目标指纹索引与查重（goal registry 离线版）。
      实测：99154 goals / 69531 unique；**证书含大量证明局部断言**（false、a=b 等），
      跨模块重复多为正常共享步骤——真正去重信号需声明级匹配
      （acorn-tools §2 Declaration Extractor + §7 Theorem Index，待实现）
- [ ] 目标注册表（声明级）：只索引顶层定理陈述，agent 开工前查重
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
