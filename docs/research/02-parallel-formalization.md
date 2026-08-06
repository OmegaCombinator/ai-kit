# 研究报告：AI 辅助形式化的快速并行化与 Acorn `.ac` AST 重构工具

> 面向对象：Acorn（Rust 证明助手）/ `acornlib`（标准库）/ Suzumio（多智能体形式化平台）
> 日期：2026-08-05 ｜ 作者：研究智能体
> 图例：【惯例/已证实】= 文献与既有工程实践中被确认的做法；【推测】= 基于本项目事实的推断或设计建议，尚未验证。

---

## 0. 执行摘要（TL;DR）

1. **并行化的最大杠杆不在"更多智能体"，而在"更少的重复验证与更快的集成"**。2024–2026 年所有规模化系统（AlphaProof、DeepSeek-Prover-V2、Hilbert、OProver、Meta ATLAS）的共同点都是：把"搜索/提议"与"验证/裁判"分离，用形式化验证器（Lean 内核 / Acorn `check --strict`）作为廉价且可靠的裁判，并把搜索状态、已证引理、模块产物做成可缓存、可复用的资源。公开实测（"Keep the Proof State Live"）显示**重新 elaboration/重放占并行搜索 wall time 的 >99%**——重放成本远高于 LLM token 成本，这正好对应 Acorn 团队"证书重放主导战役成本"的观察。
2. **对 Acorn/Suzumio 而言，`build/manifest.json`（模块 → blake3 哈希）天然就是内容寻址缓存**。把"模块 = 工作单元 + 缓存键"落实为调度与集成的唯一事实来源，就能把 2 周 / ~10,729 次激活 / ~53 次提交 中浪费在"审计、阻断、手工重放证书"上的时间压缩一个数量级。
3. **可以构建一个 `.ac` 的 AST 重构器**，且成本很低：Acorn 已有完整的 Rust `syntax/` 解析器（AST 节点带 `first_token`/`last_token` 源码区间）、`pretty` 打印 crate、`export --proof-deps` 依赖导出、manifest 哈希。基于"证书按（模块限定）名字引用声明"这一事实，可以精确算出"哪些变换保留证书、哪些必须重验、重验闭包有多大"。
4. **建议的优先级**：(P0) 先把"单模块 `check --strict` 门禁 + manifest 缓存 + 串行写 build/" 固化到 Suzumio 工具链；(P0) 交付 AST 重构器 M1（格式化/文件拆分，不重命名）；(P1) 依赖前沿分片 + 目标注册表去重 + 批量集成队列；(P2) 重命名/移动/合并变换 + 自动 import 修复 + 重验闭包调度。

---

## 1. 2024–2026 AI 形式化系统图景与可借鉴经验

### 1.1 系统总览

| 系统 | 时间/出处 | 架构要点 | 关键结果 |
|---|---|---|---|
| **AlphaProof / AlphaGeometry2** | DeepMind；2024 年 7 月公布 IMO 银牌，2025 年 7 月 Nature 论文 | 形式化数学模型（基于 Lean 的定制语言/证明搜索）、token 级搜索树、与 AlphaZero 式 RL 训练、自生成 8000 万道数学题；"先翻译成形式化问题，再由搜索求解" | IMO 2024 获 28/42（银牌水平，P4/P6 满分）；Nature: https://www.nature.com/articles/s41586-025-09833-y ｜ https://research.google/pubs/olympiad-level-formal-mathematical-reasoning-with-reinforcement-learning/ |
| **DeepSeek-Prover-V1 / V1.5** | DeepSeek-AI；2024 | Lean 4；V1 用 Lean 4 数据训练 + 证明助手反馈；V1.5 引入证明助手反馈的 RL 与蒙特卡洛树搜索（MCTS），"prover-verifier" 思路 | miniF2F 等基准显著提升；V1.5: https://arxiv.org/abs/2408.08152 ｜ V1: https://huggingface.co/deepseek-ai/DeepSeek-Prover-V1 |
| **DeepSeek-Prover-V2** | DeepSeek-AI；2025 年 5 月 | **子目标分解 RL**：LLM 提议（proposer）把大目标拆成子目标，Lean 验证器（verifier）过滤/校验，critic 模型（referee）评分——"提议–验证–裁判"式分工；擅长把大目标分解成可验证子目标 | PutnamBench 等大幅领先开源模型；https://arxiv.org/abs/2504.21801 |
| **InternLM2.5-StepProver** | InternLM；2024/2025 | **step-by-step 证明**（细粒度 tactic 级） + **expert iteration**，在大规模 Lean 问题上训练；验证器作为过滤/评分器 | miniF2F 上刷新 SOTA（发布时）；https://arxiv.org/abs/2410.15700 |
| **Goedel-Prover** | 2025 | 高质量数据 + Lean 4 定理证明；开源前沿模型 | miniF2F 达 ~92%（SOTA 级别）；https://arxiv.org/abs/2502.07640 ｜ https://goedel-lm.github.io/ |
| **Llemma** | EleutherAI；2023 | 开放数学语言模型（继续预训练 + 形式化数据），提供工具调用接口 | miniF2F 早期强基线；https://arxiv.org/abs/2310.10631 |
| **Lean Copilot / LeanDojo / ReProver** | 2023–2024 | 检索增强（LeanDojo 的 retrieval）；在证明状态上做模型推理；tactic 建议 | LeanDojo: https://arxiv.org/abs/2306.15626 ｜ Lean Copilot: https://arxiv.org/abs/2404.12534 |
| **Draft, Sketch, and Prove** | 2023 | 先由 LLM 生成非形式化证明草稿/草图，再用形式化 prover 并行填充缺口——**"并行化证明搜索"的早期代表** | https://arxiv.org/abs/2210.12283 |
| **Hilbert** | Apple/UCSD；NeurIPS 2025 | 非形式化推理 LLM + 专业 prover LLM + 形式化验证器 + 语义定理检索器；**递归分解 + 验证器反馈** | miniF2F 99.2%、PutnamBench 462/660（70.0%）；https://arxiv.org/abs/2509.22819 ｜ https://machinelearning.apple.com/research/hilbert |
| **OProver** | 2026 | agentic 循环：失败尝试用 Lean 编译器反馈修订；训练数据 **OProofs（177 万条语句、686 万条编译器验证证明）** | miniF2F Pass@32 93.3%、ProverBench 58.2%；https://arxiv.org/abs/2605.17283 |
| **Seed-Prover** | ByteDance；2025 | lemma 式整证明模型 + Lean 反馈迭代 | 已形式化 IMO 历年题 78.1%、PutnamBench >50%；https://arxiv.org/abs/2507.23726 |
| **ATLAS / AutoformBot** | Meta；2026 | **"规模化形式化"：编排数千个 LLM 智能体，形式化验证工具 + 依赖感知任务调度 + 协作版本控制**，把 26 本开放教科书翻译成 **45,000+ 条 Lean 声明（约 50 万行）**（~183B token） | 与 Suzumio 目标最接近的直接先例；https://arxiv.org/abs/2605.29955 ｜ https://github.com/facebookresearch/atlas-lean |
| **LeanAgent** | ICLR 2025 | 终身学习智能体：课程化难度 + 动态知识库 + 渐进训练防遗忘 | 为 23 个 Lean 仓库的 155 条定理生成形式化证明；https://arxiv.org/abs/2410.06209 ｜ https://leandojo.org/leanagent.html |
| **Lean-STaR** | NeurIPS 2024 | 专家迭代：交错训练"思考 + tactic"序列 | miniF2F-test 43.4%；https://arxiv.org/abs/2407.10040 |
| **ECP（Enumerate–Conjecture–Prove）** | 2025 | 通用 LLM 枚举/猜想答案，prover LLM 证明，**可接受性检查作裁判**阻断循环 witness | PutnamBench 17/346、MathArena 18/75；https://arxiv.org/abs/2505.18492 |
| **BFS-Prover-V2** | ByteDance-Seed；2025 | 大语言模型驱动的**并行最佳优先搜索（BFS）**证明搜索 | 证明搜索并行化的直接工程范例；https://github.com/ByteDance-Seed/BFS-Prover-V2 |
| **Prover-Verifier Games** | Anthropic；2024 | 训练 prover 与 verifier 博弈，使输出"可读/可验证"——"验证器作为可扩展监督"的理论基础 | https://arxiv.org/abs/2407.13692 |

### 1.2 基准表现（数字以原文为准）

- **miniF2F**（488 条奥赛级陈述，https://arxiv.org/abs/2109.00110）：从 ReProver 时代（~30% 级）一路推高——Lean-STaR 43.4% → DeepSeek-Prover-V2 88.9% → OProver 93.3% → Hilbert 99.2%。**基准已接近饱和，不再是区分度高的指标**。【惯例/已证实】
- **PutnamBench**（https://arxiv.org/abs/2407.11214；1,692 条手工形式化，覆盖 640 道 Putnam 定理，Lean4+Isabelle，部分 Coq）：2024 年推出时全系统 <10%；2025–2026 年推进到 DeepSeek-Prover-V2 49/658、Seed-Prover >50%、Hilbert 462/660（70%）。
- **FrontierMath**（Epoch AI）：2024 年发布时声称前沿模型 <2%；OpenAI 2025 年宣称 o3 在"放宽设置"下可达 20%+，随后被第三方复测质疑（TechCrunch 报道实测远低于宣称）。教训：**基准的"宣称成绩"不等于可复现成绩；自家验证器回放（Acorn 的 `check --strict`）才是唯一可信口径**。参考：https://techcrunch.com/2025/04/20/openais-o3-ai-model-scores-lower-on-a-benchmark-than-the-company-initially-implied/
- **AIME 2024/2025**：正式化后由 prover 求解的最大公开规模仍小——DeepSeek-Prover-V2 在 ProverBench 的 15 道 AIME 题中形式化解决 6 道（对比 DeepSeek-V3 非形式化 8/15），"形式化差距"在缩小但未关闭（https://arxiv.org/abs/2504.21801）；autoformalization（自然语言 → 形式化陈述）本身仍是主要误差来源（综述：https://arxiv.org/abs/2505.23486）。
- **大规模库级形式化**：ATLAS（Meta）把 26 本教科书翻译为 45,000+ 条 Lean 声明（~183B token，https://arxiv.org/abs/2605.29955）；ProofNet 371 条（https://arxiv.org/abs/2302.12433）；MSC-180 暴露领域偏差（最佳模型 pass@32 仅 18.89%，https://arxiv.org/abs/2512.18256）。

### 1.3 关键架构模式（为什么它们能规模化）

1. **proposer–verifier–referee（提议者–验证者–裁判）**：【惯例/已证实（模式在多个系统出现，措辞为综述性概括）】DeepSeek-Prover-V2 用"LLM 提议子目标 + Lean 验证器校验 + critic 评分"；AlphaProof 用 Lean 内核做验证器；Anthropic 的 prover–verifier games 给出理论解释。核心洞察：**让不可靠但便宜的"提议"（LLM 生成证明步骤）与可靠但昂贵的"验证"（内核重放）解耦，用验证器反馈做强化学习/数据过滤**。对 Acorn 的映射：提议 = Suzumio formalizer 智能体生成 `.ac` 语句；验证 = `verify`（搜索+写证书）；裁判 = `check --strict`（零搜索重放）。
2. **专家迭代（expert iteration）+ 验证器过滤数据**：【惯例/已证实】InternLM2.5-StepProver、DeepSeek-Prover-V2、Goedel-Prover 都用"搜索出的可验证证明"回流训练。**对 Acorn 的落地含义：每一次智能体成功 `verify` + `check --strict` 的模块/引理，都应进入一个可检索的"已证引理库"（Acorn 标准库本身就是），避免重复证明**。
3. **tactic 级 vs term 级**：【惯例/已证实】tactic 级（逐步小步）更容易用验证器反馈学习、更容易并行搜索（每个状态独立可续搜）；term 级（一次性生成完整证明项）依赖模型更强。InternLM2.5-StepProver 的 step-by-step 与 AlphaProof 的 token 级搜索都是"小步 + 搜索"路线。**对 Acorn 的映射：Acorn 的 proof block 是"语句序列"（claim 级步骤），天然是 tactic 级的类似物；`verify --line/--goal/--print-proof` 已支持单目标定位，应把"单目标/单语句"作为并行搜索的最小单元**。
4. **搜索并行与状态缓存**：【惯例/已证实】AlphaProof 大规模并行 token 搜索；BFS-Prover-V2 显式并行 BFS；"Keep the Proof State Live: Snapshotting for Efficient Tactic Search in Lean 4"（https://arxiv.org/abs/2605.25556）专门讨论**证明状态快照/缓存以复用搜索**。**对 Acorn 的映射：`verify` 的证书缓存本身就是搜索状态缓存；确保"稳定 prelude 不重搜"（AGENTS.md 已总结的教训）属于同一类优化**。
5. **human-in-the-loop 评审**：【惯例/已证实】mathlib 社区把人工评审作为质量门槛；LeanAgent 等智能体工作最终仍需人审。Acorn 的 librarian 角色与此一致。

### 1.4 规模化经验总结（哪些有效、哪些无效）

**【惯例/已证实】有效的**：
- 验证器回放作为唯一可信门禁（等价于 `check --strict`）。
- 证明状态/证书缓存，避免重复搜索。"Keep the Proof State Live"（https://arxiv.org/abs/2605.25556）实测：**并行草稿式搜索中，重新 elaboration 占每个分支 wall time 的 >99%**（import 加载约 60s/分支，定理体 elaboration 18–735s/分支，视复杂度而定）——这是"重放/elaboration 是主导成本，而非 LLM token"的最强公开证据，与 Acorn 团队"大 prelude 让每次尝试先重验数百行"的教训同构。
- 子目标分解 + 并行搜索（把大目标切成可独立验证的小目标）。
- 高质量、可检索的引理库（训练数据回流 / 标准库）。
- **依赖感知调度 + 大规模并行**：ATLAS（Meta）编排**数千个** LLM 智能体做库级形式化，依赖感知任务调度 + 协作版本控制（https://arxiv.org/abs/2605.29955）；Lean Atlas 的 "Lean Compass" 计算"哪些依赖图节点必须评审"以缩小人工评审集（https://arxiv.org/abs/2604.16347）。
- **写时冲突检测优于纯 worktree 隔离**：STORM（2026）在写时检测冲突编辑，优于逐 agent worktree 隔离（Commit0-Lite +18.7）（https://arxiv.org/abs/2605.20563）。
- 明确的停止条件与失败保留（失败尝试里的已验证引理可复用）。
- **HITL 聚焦语义而非语法**：FormalScience 让单领域专家以低成本产出语法正确、语义对齐的证明（https://arxiv.org/abs/2604.23002）；Tao 的 Lean+Claude Code 实验是人工驾驶 agentic 证明的范例（https://mathstodon.xyz/@tao/114531073456744061）。

**【惯例/已证实】无效或代价高的**：
- 无限长跑、无停机的智能体循环（Suzumio 两周 10,729 次激活中大量进入审计/阻断）。
- 把"能证"当成"该入库"（Acorn 团队自己的规则：允许 rough proof，不允许 rough API）。
- 依赖未复测的第三方基准宣称（FrontierMath/o3 教训）。
- 逐条小提交 + 每次全库 strict（Acorn 2026-06 战役改为 3 个宽 stacked PR 后才把全库回放次数降下来）。【惯例/已证实（本工作区记录）】
- read-only 审计/阻断型激活产出（2026-06 有 5 个 real 分析快照因此被排除在 accepted 之外）：审计应当由确定性的脚本/工具完成，而不是消耗智能体激活。【惯例/已证实（本工作区记录）＋推测（一般化）】

**【推测】对 Acorn/Suzumio 的映射**：
- 智能体的"搜索"应下沉到 `verify` 内部（多 `--jobs` 并行、单目标搜索），而不是让智能体在源码层反复试错——源码层的"搜索"既不缓存也不可回放。
- 证书重放（`check --strict`）是团队 53 次提交成本的主导项：**集成前批量重放、集成后只重放受影响闭包**（见 §2）。

### 1.5 大型证明库的并行贡献与集成实践（外部参照）

【惯例/已证实；来源：并行研究子代理简报 + 我的检索】
- **mathlib（Lean 4）**：fork-and-PR + **bors 合并机器人**——只在 CI 对最新 master 通过后合并，且**批量合并**队列中的 PR，保证 master 常绿，这正是一百多人并行贡献而不反复冲突重建的机制（https://leanprover-community.github.io/contribute/how-to-contribute.html ；bors 工作流 https://github.com/leanprover-community/mathlib4/blob/master/.github/workflows/bors.yml）。**olean 内容寻址缓存**：`lake exe cache get/put` 从 Azure 下载/上传预编译产物，CI 从 master 预热缓存，每个 PR 从"已编译 master"起步（https://github.com/leanprover-community/mathlib4/blob/master/Cache/README.md）；`lake build -j` 只重编 import 闭包变化的模块。**工具链升级隔离**：新 Lean nightly 先在 `mathlib4-nightly-testing` 分支测试，"adaptations" PR 修好后再 bump（https://github.com/leanprover-community/mathlib4/commit/5e3de160241c384193f474cd07c55650f5011df6）。**大规模重构**：(a) 一次性 sed/Python 全树改名（mathlib3 #911 `is_group_hom.mul`→`map_mul`；https://github.com/leanprover-community/mathlib/pull/911）；(b) **deprecate-don't-delete**：旧名保留为 deprecated 别名，下游证明继续编译、逐步迁移；(c) **Lean 3→4 移植**：mathport 自动翻译 + 每文件 `#align` 保留旧名 + `declarations_diff` lint 机械校验"声明无丢失"（https://github.com/leanprover-community/mathlib4/commit/9389bd048052b76eb24639c5b69935977a84ba8d）；(d) **库拆分**：mathlib→Batteries，用大批 "adaptations" PR 消化（https://github.com/leanprover-community/mathlib4/commit/f1a7d67cb3c8018c6fc967b544f6fe82d50122b5）。
- **Coq/Rocq**：**user-overlays 机制 = 教科书式"依赖前沿"**——Coq 核心改动必须在所有注册下游项目（stdpp、math-comp、VST…）的 overlay 分支上重验通过才合并（https://github.com/lthms/coq/blob/master/dev/ci/user-overlays/README.md）；**增量检查** `.vo`/`.vos`（跳过证明）/`.vok`（稍后并行查证）＋ `coqdep` 依赖图 + `make -j`/dune 并行（https://github.com/rocq-prover/rocq/pull/8642 ；https://discourse.rocq-prover.org/t/parallel-checking-within-a-file-with-vok/643/1）；**stdlib 重组**：RFC 083"Boost stdlib development"规划把 stdlib 拆成独立可分发包、独立维护者、更快节奏（https://github.com/rocq-prover/rfcs/blob/main/text/083-boost-stdlib-dev/text.md），配套目录迁移（rocq#19530）与 Coq→Rocq 更名（rocq#19310）。
- **Isabelle AFP**：每个 entry 是独立 session（ROOT 声明），`isabelle build -d afp -g AFP` 沿 session 依赖图构建，`-j N` 并行 + **session heap 镜像缓存**——只重建变更闭包；Mira 测试板（build farm）持续全量验证整个 archive（https://isa-afp.org/ ；Isabelle System manual: https://isabelle.in.tum.de/website-Isabelle2025-RC4/dist/Isabelle2025-RC4/doc/system.pdf）。提交走编辑+外部评审流程，必须用当前 Isabelle 版本构建通过。
- **Mizar MML**：几十年数千文章由委员会 curation，每次 Mizar 版本发布**整库重验**（http://www.mirror.mizar-jp.org/library/submit.html）；**Flyspeck**：模块化 + 按依赖序可重放的检查链。
- **对 Acorn 的四条映射**：(1) bors 批量合并 → Suzumio 集成队列（staging + 批量 rebase + 闭包 strict）；(2) 内容寻址缓存 → `manifest.json` 的 blake3 哈希已具备，缺"按闭包跳过"的调度；(3) deprecate-don't-delete → Acorn 重构的名称稳定性协议（stub/facade 保留旧名）；(4) overlay/闭包重验 → `check --strict` 的闭包选择器（acorn-tools §23 已规划）。

---

## 2. Acorn/Suzumio 并行形式化流水线建议

### 2.1 现状与瓶颈（基于本地事实）

- **Acorn**：`verify`（ML 引导证明搜索 + 写证书）与 `check --strict`（0 搜索重放已提交证书）是两种操作；证书按模块存于 `build/<module>.jsonl`（旧快照布局；0.2.0 起为 `src/certs/<module>.jsonl`，每行 `{"goal":…,"proof":[…]}`，证明步骤以 `lib(<module>).<name>` 引用跨模块声明）；manifest（`build/manifest.json`，模块 → blake3 哈希，`PROJECT_FORMAT_VERSION=24`）只收录 build 状态良好的模块；模块名 = 文件路径（`src/list/list_base.ac` → `list.list_base`）；跨模块引用靠显式 `from X import Y`，loader 生成依赖列表；`export --proof-deps --elaborated` 可导出模块级 imports 与逐定理证明依赖。
- **acornlib**：约 312 个 `.ac` 源文件（本工作区存档快照 78 个），模块构成依赖 DAG。
- **Suzumio**：YAML 声明多智能体；SQLite 为项目事实来源（projects/agents/messages/signals/activations/events/tool_calls）；信号驱动非抢占调度（P0 打断、P1 工具边界、P2/P3 排队）；Docker 一次性激活；`/workspace`（可变）+ `/artifacts/<agent>`（不可变交接）；nudge/监控规则。
- **已知瓶颈**（团队文档 + 上轮战役）：(a) 大量激活进入审计/阻断；(b) 手工"重放"证书到合并树占主导成本；(c) 并行 `verify` 会竞争 `build/manifest.json`（必须串行写）；(d) 大 proof prelude 让每个 worker 尝试都先重验数百行；(e) 53 次小提交 × 每次全库 strict 的成本。
- **2026-06 战役实录**（`acornlib-20260609-progress.md`，Acorn 0.2.0）：8 个智能体（6 formalizer + pm + scout + verifier），按"数学领域家族（domain family）"分车道，每个家族一个 git 分支，verifier 审查后打包成 staging PR；最终产出 46 个 accepted refs、45 个 domain 分支、`.ac` 源码 `+15155/-139`、证书 jsonl `+4109/-392`、237 个变更路径；全库 strict 回放 `90511/90511 OK`、`0 searches`。**数字印证**：(i) 源码 churn（~15k 行）远小于证书+集成工作量；(ii) "证书生成命令必须在同一 worktree 串行"被再次验证；(iii) read-only 审计快照（real 分析相关 5 个）被明确排除在 accepted 之外——审计型激活的产出占比可观。【惯例/已证实（本工作区记录）】

### 2.2 设计原则

1. **模块即工作单元，manifest 哈希即缓存键**：【惯例/已证实（manifest 机制已存在）+ 推测（调度化）】一个模块（一个 `.ac` 文件）是原子工作单元；`blake3(src)` 变化 ⇒ 该模块及其依赖闭包需重验；不变 ⇒ 证书与 manifest 条目原样复用。叠加证书按名解析的设计，**只要名字稳定，跨 rebase/重构的证书可整体复用**。
2. **依赖前沿（dependency frontier）调度**：【推测，源自 mathlib/AFP 的分层构建实践】只允许智能体在"依赖已稳定"的模块上开工；同一时刻可并行工作的模块集合 = DAG 中"全部依赖已锁定"的层。
3. **验证分层**：`verify`（搜索，可并行读但串行写 build/）→ 单模块 `check --strict`（门禁）→ 依赖闭包 `check --strict`（集成时）→ 全库 `check --strict`（CI，只读并行）。
4. **一次只改一个模块的写权限**：避免两个 agent 同时改同一 `.ac`（Suzumio 已有"PM 分配 + owner"惯例，升级为强制规则：文件级锁/注册表）。
5. **批量集成，而非逐条提交**：把"周 53 次提交"的集成成本摊薄为"每批 5–10 个模块一次 rebase + 一次闭包 strict"。

### 2.3 流水线（阶段图）

```
目标选择(PM/人类, Top100/1000+ 清单)
   → scout 盘点缺口(现有 API 地图, 缺口陈述, 建议模块位置)
   → 分片(按依赖 DAG 分层; 每片 = 1 模块 或 1 引理族; 目标注册表去重)
   → 并行工作(每 agent 1 片, 私有 /workspace, 基于已锁定上游快照)
       每个语句/引理: verify → 单模块 check --strict(门禁) → 提交证书+manifest 到自己的分支
   → 交接(artifact 目录: README + candidate .ac + verify.log + strict.log)
   → 集成队列(单一 integration agent/脚本): rebase 到 staging, 串行 verify(防 manifest 竞争),
        闭包 check --strict, lint, 生成 review-sized PR 批
   → 人类/librarian 评审 → CI 全库 check --strict(只读并行) → 上游合并
```

### 2.4 分片与 DAG 分层

- 用 `export --full` 或 loader 的 imports 信息构建模块 DAG，做拓扑分层（叶子在前）。【推测】初始可并行度 = 第一层叶子模块数；每完成一层，释放下一层。
- 片大小建议：单个模块（<2000 行 `.ac`，与团队 review-sized 规则一致）；超大模块（如 real/、list/ 的巨型文件）在重构器就绪前按"引理族"横向切分（同一模块内的命名前缀子集），重构器就绪后纵向拆文件（§3）。
- **目标注册表（goal registry）**：【推测，来自 LeanAgent 知识库与 Suzumio SQLite 能力】在 SQLite 中维护"已被声称/已证/已放弃"的陈述指纹（规范化后的 goal 字符串哈希——证书 jsonl 里就有 `goal` 字段），智能体开工前查重，杜绝两人证明同一个引理（AGENTS.md 已发生过 duplicate constant 事故）。

### 2.5 集成与缓存

- **staging 分支 + 批处理**：所有新模块先进 `staging/` 分支；集成脚本按 DAG 顺序串行执行 `verify`（写证书）+ 更新 manifest；**绝不允许并行写 build/ 的命令**（团队规则，保持）。
- **2026-06 已验证的集成形态**【惯例/已证实（本工作区记录）】：46 个 accepted domain refs 不逐条开 PR，而是从 `upstream/master` 的干净分支**有序 cherry-pick** 成 3 个宽领域 stacked PR（#1175 核心基础设施 → #1176 代数/线性 → #1177 其余域）；重叠文件（如 `src/fin.ac`、`src/lie_algebra.ac` 被多个 domain 触碰）用"有序 cherry-pick + 重生成证书"处理；每个 PR 先 focused verify/strict/lint/扫描，再全库 `check --strict`（`90511/90511 OK, 0 searches`）后才声明可复现。**这套流程应固化为 Suzumio 的"集成契约"**。
- **缓存命中即跳过**：集成时对每个模块比较 `blake3(src)` 与 manifest：未变 ⇒ 跳过（证书、manifest 条目原样）；变了 ⇒ 只重验该模块 + 其后继闭包中引用它的模块。**这直接把"重放成本"从"全库每次"降到"闭包每次"**。【推测，但机制（manifest 哈希 + 依赖图）已存在】
- **CI**：GitHub Actions 上跑只读 `check --strict -j 8`（并行读安全，因为不写 manifest）；对 PR 批生成复现记录（commit、binary 路径、命令、totals——团队模板已有）。
- **避免 prelude 重搜**：【惯例/已证实（AGENTS.md 教训）】大 proof prelude 应在集成时缓存为"已证模块"，worker 引用其 `lib(...)` 名字而不是复制源码重证；`verify` 会命中证书缓存。

### 2.6 智能体交接与去重（Suzumio 落地）

- **2026-06 战役的调度模板可直接复用**（`acornlib-suzumio-workflow/acorn-formalization.yaml`，533 行）：8 智能体（6 formalizer + pm + scout + verifier）；scout-directed（scout 从库状态/公开里程碑挑选方向）；formalizer 按"数学领域家族"车道开发，每车道一个 git 分支；verifier 负责复验 + 打包（复验证据：focused verify/strict/lint/证书解析/重复声明扫描/diff 检查）；anti-stall 策略（formalizer 等 verifier 可以，等另一个 formalizer 不行——交叉依赖立即转派独立后备工作）；nudge 调优（noEffectNudge P2/30s 起、failedNudge P2/60s 起 ×4、quietAgentMonitor 10min、allQuietNudge 3min）。**这套模板是并行流水线的现成底座，缺的只是"模块级缓存与闭包调度"这一层**。【惯例/已证实（本工作区记录）】
- **ATLAS（Meta）是"Suzumio + Acorn"目标形态的公开先例**【惯例/已证实（论文/仓库）】：数千智能体 + 依赖感知任务调度 + 协作版本控制 + 形式化验证工具，26 本教科书 → 45,000+ 条 Lean 声明（https://arxiv.org/abs/2605.29955 ；https://github.com/facebookresearch/atlas-lean）。对照 Suzumio：Suzumio 已有 SQLite 任务状态/信号调度/artifact 交接，**缺的是"以模块依赖图驱动的调度与缓存"与"写时冲突检测"**（后者可参考 STORM，https://arxiv.org/abs/2605.20563）。【惯例/已证实（机制存在）＋ 推测（差距判断）】
- 复用 Suzumio 信号语义：P2 用于"该片完成/受阻"的继续信号；P3 例行任务；P0 仅用于"冲突/需要销毁性操作/安全"（已有定义）。
- **交接协议**（团队已有 artifact 约定，强化为机器可读）：每个模块完成时在 `/artifacts/<agent>/<module>.result.json` 写 `{module, files, verify_cmd, verify_totals, strict_cmd, strict_totals, deps_used, blockers}`；集成脚本直接消费该 JSON。
- **去重信号**：目标注册表更新时向 PM 发信号；两个 agent 撞同一模块时 P0/P1 通知 owner 变更。
- **失败保留**：失败尝试的已验证子引理进入 artifact（团队规则已有）。

### 2.7 成本控制

- 度量三项成本并记账（SQLite 已有 activations/tool_calls 审计）：(1) 搜索成本（verify 的 CPU/时间）；(2) 重放成本（check --strict）；(3) 集成成本（rebase/merge）。**两周战役的教训是 (3) 主导**，因此先优化集成路径。外部证据一致：Lean 侧实测重放/elaboration 占并行搜索 wall time >99%（https://arxiv.org/abs/2605.25556）；ATLAS 约 4M token / 千条声明是库级成本的粗略锚点（https://arxiv.org/abs/2605.29955）；Erdős 开放问题 agent 每条"几百美元"（https://arxiv.org/abs/2605.22763）。【惯例/已证实（外部）；占比为推测】
- 给 formalizer 明确停机条件（团队已有：30–60 分钟同类错误即上报），减少无产出激活。
- 用 `select`/`verify --print-proof` 定位失败，而不是反复整块重试（团队已有）。

### 2.8 风险与缓解

| 风险 | 缓解 |
|---|---|
| manifest/证书竞争 | 写操作全串行；只读 check 并行；集成脚本单点执行 |
| 依赖闭包爆炸（大模块被引用广） | 分片粒度尽量小；重构器拆分大模块（§3） |
| 智能体重复劳动 | 目标注册表 + 文件锁 + PM 分配 |
| strict replay 不稳（printer/type-arg bug） | 每个变更模块先过单模块 strict；已知 workaround（named helper 包装）入 lessons |
| 上游 rebase 带来的证书失效 | 每次 rebase 后只重放受影响闭包；PR 复现记录随 rebase 更新 |

### 2.9 预期收益（推测性估算）

【推测，基于战役公开数字的粗略推断，非实测】
- 2026-06 战役：~2 周、8 智能体、46 accepted refs、源码 +15k 行、证书 +4.1k 行、最终 3 个 stacked PR。假设瓶颈分配为：证明搜索/编写 50%、verifier 复验与打包 30%、审计/阻断/等待 20%，则：
  - 模块级缓存 + 闭包重验（P0/P1）：把"每次全库 strict"降为"闭包 strict"，预计可削减 verifier 复验/打包时间的大部分（30% 总量中的 60–80%）。
  - 目标注册表去重（P1）：削减重复引理证明（审计/阻断中的一部分）。
  - 依赖前沿调度（P1）：把"6 车道并发受交叉依赖限制"升级为"可并行层数 = 每层模块数"，对宽 DAG 的 wall-clock 改善显著；对窄 DAG（如依赖链）收益有限——此时应转向"模块内并行"（`verify --jobs`、单目标搜索）。
- **量化口径建议**：以"每个 accepted 模块的（搜索 CPU 时间 + 重放 CPU 时间 + 集成人工/激活数）"为度量单元，先建立基线再优化。



## 3. `.ac` AST 重构器架构

### 3.1 动机与证书耦合分析

**为什么要做**：acornlib 目前 ~312 个文件扁平堆放、模块粒度参差；分片/并行化需要"拆分大文件、合并小文件、重命名、移动声明"而不破坏既有证书。

**证书耦合事实**（已核实本地源码，`acorn/src/certificate.rs` 与 `kernel/concrete_proof.rs` 的明确设计文档）：

1. **证书 = goal 字符串 + 证明步骤字符串**（`Certificate{goal: String, proof: Option<Vec<String>>}`），按行存于 `build/<module>.jsonl`。字符串中引用常量**按名字**（跨模块为 `lib(<module>).<name>`，如 `lib(add_comm_semigroup).AddCommSemigroup`；模块内名字常以未限定形式出现，如 `sum`、`partial`）。
2. **检查时按名解析**：`Certificate`(名字) → `ConcreteProof`(数字 ID) → Checker；名字解析发生在该边界，用**当前代码库的 bindings**。因此内部数字 ID 重排不影响证书。
3. **官方设计目标明确写为"对重构稳健"（Robustness to Refactoring）**：
   - *Renaming*：某定理被改名，**不使用它的证书仍然有效**；
   - *Reordering*：常量重排（内部 ID 变化）不影响证书；
   - *Adding/removing definitions*：无关的增删不使证书失效。
4. **证书只存 claims，不存完整证明结构**：checker 自己决定"每个 claim 如何验证"。因此 claim 的 justification 变化（例如某个引理被改名、证明方式改变）**不会**破坏证书——只要该 claim 在当前上下文中仍可证。只有"claim 本身变得不可证"或"引用的名字无法解析"才会失败。
5. **模块 hash**（manifest.json：module → blake3，仅收录 build 状态良好的模块）只随源文本变化；下游模块证书是否失效只取决于"下游 claim 是否引用了被改变的名字/语义"，与 hash 本身无关。

**由此得到的直接影响**：
- **纯格式/空白/注释/语句重排**：名字与声明集合不变 ⇒ 证书按名回放，设计上应有效（需一个最小实验确认 printer 差异与 `--update-version` 场景）。【惯例/已证实（设计文档）】
- **重命名声明**：只有**引用旧名的证书 claims** 失效；失效范围 = 依赖闭包内实际引用该名的模块，通常远小于全库。
- **移动声明到另一模块**：证书字符串中**未限定名**通过引用模块的 `from <module> import <name>` 解析；因此**"移动声明 + 更新所有引用模块的 import 语句"可以保持既有证书字符串原样有效**（名字仍解析到同一常量）。唯一例外是证书字符串中**限定形式 `lib(<旧模块>).<name>`**（多见于类型类名出现在 elaborated 类型注解中），需在证书文件中做文本改写（同名常量、新模块路径）。
- **拆/并文件**：声明集合不变时，把声明连同其证书行迁移到新模块 jsonl 即可（goal 字符串匹配 statement），引用方 import 更新后证书保持有效。

这是 Acorn 与 Lean/Coq 的关键差异：**Acorn 证书是"语义 claim + 按名解析"，不是 tactic 脚本**（tactic 脚本对改名/重排高度敏感），因此 Acorn 的重构器可以做到"大部分重构不重搜、只重放"。【惯例/已证实（设计文档）＋ 推测（对迁移细节的推断，需验证）】

**已有前置规划**（本工作区 `acorn-tools.md`，1361 行提案）：团队已规划 39 个 `acorn-tools` 子命令（机器可读 JSON 输出，面向智能体），其中与本重构器直接重叠/互补的包括：§1 AST Parser、§4 Formatter、§10 Import and Dependency Explorer、§11 Public API Diff、§18 Certificate Replay Checker、§19/20 Manifest Analyzer/Normalizer、§23 Downstream Strict-Check Selector（即"按依赖图挑选下游 strict 检查"——本报告 §3.5 影响分析的现成接口）、§28 Acorn LSP、§36 Library Map Generator、§39 Handoff Theorem Inventory；提案还给出 Recommended Build Order（parse/decls → index/search → proof-patterns → verify-lane/downstream-checks → manifest/cert 工具 → duplicate/helper/scope → goal/type/resolve → handoff/api-diff）。**本报告的 AST 重构器应作为该工具族的新增成员（`acorn-tools refactor`）实现，并复用其既有构建顺序与 JSON 约定**。【惯例/已证实（提案文档存在）】

### 3.2 总体架构

```
┌─ 输入: src/**/*.ac, build/manifest.json, build/**/*.jsonl
│
├─ 1. 解析层  (复用 acorn/src/syntax: token.rs, expression.rs, statement/*)
│     TokenStream → Statement 列表(每个 Statement 带 first_token/last_token 源码区间)
│     保留注释/doc comment(parser 已将 DocComment 作为语句节点保留)
│
├─ 2. 语义索引层 (复用 loader + export --proof-deps --elaborated)
│     声明表: name → (module, kind, span)
│     引用图: 声明 → 其引用的其他声明(证明依赖, 模块限定名)
│     模块图: import 边(module → dep modules)
│
├─ 3. 变换层 (新写, 纯 AST 变换)
│     Rename / SplitFile / MergeFiles / MoveDecl / Reorder / Reformat
│     每条变换输出: 新源码(经 pretty 打印) + 受影响声明/模块集合
│
├─ 4. 打印层 (复用 pretty crate; 可做"最小 diff"打印: 只在需要处重排)
│
├─ 5. 影响分析层
│     输入变换集合 → 计算"需重验模块闭包" + "需更新 import 的模块"
│
└─ 6. 验证与提交层
      dry-run diff → 按 DAG 顺序串行 verify(只重验闭包) → 闭包 check --strict
      → 更新 manifest → 提交
```

### 3.3 可复用组件清单（本地核实）

| 组件 | 位置 | 用途 |
|---|---|---|
| 词法/语法解析器 | `acorn/src/syntax/{token,expression,statement}*` | 生成带 span 的 Statement AST（`Statement{first_token,last_token,statement: StatementInfo}`） |
| 语句类型 | `syntax/statement/ast.rs`：Let/Define/Theorem/Claim/Type/Structure/Inductive/Import/Attributes/Numerals/Match/Typeclass/Instance/Destructuring/DocComment 等 | 变换的操纵对象 |
| pretty 打印 | `pretty` crate（`::pretty::{DocAllocator, DocBuilder, Pretty}`，PRINT_WIDTH=60） | 打印重建源码 |
| 模块加载/依赖 | `loader/`（module_loader.rs、parsed_module.rs） | 模块依赖解析、content_hash |
| 导出/影响分析 | `exporter.rs`（`export --proof-deps --elaborated --output-dir`） | 逐定理证明依赖（模块限定名）、模块 imports |
| 缓存键 | `manifest.rs`（module → blake3、PROJECT_FORMAT_VERSION） | 内容寻址缓存 |
| 验证 CLI | `verify`/`check --strict`/`lint`/`select` | 门禁与调试 |

### 3.4 变换分类与证书影响矩阵

| 变换 | 对证书的影响 | 需重验的模块 | 说明 |
|---|---|---|---|
| **Reformat**（空白/换行/注释/`///` 措辞） | 无（名字不变）【惯例/已证实：设计文档】 | 仅自身（manifest hash 更新） | 先做最小实验确认"注释变化不破坏回放" |
| **Reorder**（同模块内语句重排） | 无（声明集合与名字不变；证书按名不按 ID）【惯例/已证实】 | 仅自身 | 注意：属性块/`numerals`/instance 与声明顺序敏感，需 lint+strict 兜底 |
| **SplitFile**（模块 M 拆成 M、M.part1…；声明按引用图切分） | 声明与名字不变；**证书行随声明迁移到新模块 jsonl；引用方 import 更新后未限定名仍解析** | 新/旧模块 + 引用被移动声明的下游闭包（大部分只需 `check --strict` 重放，不需重搜） | 迁移后对引用闭包做 strict；限定名出现处做证书文本改写 |
| **MergeFiles**（M1、M2 合并进 M） | 同 SplitFile 反向 | 合并后模块 + 引用方闭包 | — |
| **RenameDecl**（改名声明） | 引用旧名的证书 claims 失效（按名解析失败）；**不引用它的证书仍有效** | 本模块 + 引用闭包（通常很小） | 也可选择"证书字符串改写旧名→新名"以保留证书（同名常量）【推测】 |
| **MoveDecl**（声明移到另一模块） | 证书中未限定名经 import 解析；**更新 import 后证书原样有效**；限定名 `lib(旧)` 需改写 | 目标/源模块 + 引用闭包 | 首选方案：move + import 修复 + 证书文本改写；避免重搜 |
| **RenameModule**（改文件路径/模块名） | 所有 `lib(旧名)` 引用失效 | 引用闭包 | 除非用"别名/stub 模块"保留旧名（见下） |
| **AddDecl**（新增声明，不动旧的） | 无 | 无（新模块/新增声明走正常 verify） | 最安全，鼓励 |

**关键设计：名称稳定性协议**【推测，建议】：
1. **新增优先**：能新增就不改名；新声明放自然位置。
2. **拆文件时保留"模块身份"**：`src/real/real_base.ac`（模块 `real.real_base`）拆成 `real.real_base` + `real.real_pow` 等新模块时，**不要**把声明从 `real_base` 移到新模块；而是新文件只承载"新声明"；老声明留在原地。这样下游对 `lib(real.real_base).X` 的引用与证书全部保留。
3. **移动声明时用 stub 转发**：如果必须把 `X` 从模块 A 移到 B，可在 A 中保留 `let X = B.X`（若 Acorn 支持别名/重导出——需验证；或生成 `theorem/define` 包装）以保持 `lib(A).X` 解析成功。【推测：需实验确认 Acorn 是否允许跨模块别名转发；若不允许，则把"MoveDecl"降级为"CopyDecl + 引导下游迁移"的两步法】
4. **模块重命名提供兼容层**：若改名不可避免，旧模块名保留一个薄 facade（只 re-export/别名），新库逐渐迁移；manifest 中两模块并存，直到引用旧名的证书自然消亡。

### 3.5 影响分析（依赖闭包计算）

- 输入：变换集合 T（每条标注 affected declarations）。
- 步骤：
  1. 从 `export --proof-deps`/loader 得到"声明 → 引用它的声明"反向索引与模块 imports。
  2. 对每个受影响声明 d，收集"在证明或语句中引用 d 的声明"的模块集合 R(d)。
  3. 需重验模块集合 = ⋃ R(d) ∪ 变换直接改动的模块；按模块 DAG 拓扑排序后**从前往后**串行 `verify` + 单模块 strict（写操作串行，遵守 manifest 竞争规则）。
  4. 无引用变化的下游模块：manifest 条目不变、证书不变，直接跳过（缓存命中）。
- 工具化：把上述逻辑做成 `acorn refactor plan --transform=...` 的一个子命令或独立 CLI；也可以先写成脚本消费 `export --full` 的输出。
- 附加要求（M2/M3 实现细节）【推测】：移动/拆分声明时，需要"证书行 ↔ 声明"的归属映射——按归一化 goal 匹配（`docs/normalization.md` 的 (clause, var_map) 往返契约保证了 goal 字符串可稳定匹配 statement），把对应 jsonl 行迁移到新模块；该映射可在 elaborate 阶段计算。

### 3.6 安全机制

- **dry-run/预览**：任何变换先输出 `git diff` 级别的预览 + "将重验的模块闭包"清单，人工/CI 确认。
- **分阶段提交**：重构 PR 与功能 PR 分离；重构批自身按"格式化 → 拆分 → 改名"分层，每层一个 review-sized PR。
- **门禁**：每个重构批必须通过 闭包 `check --strict`；全库 strict 至少跑一次（只读并行可负担）。
- **回归保护**：重构批不改变任何 statement 语义（同一 AST 的文本表示变化），用"重验闭包前后的 manifest diff"作为自动断言：闭包外模块 hash 必须不变。
- **回滚**：重构器是纯文本/纯 AST 变换 + git，天然可回滚。

### 3.7 实现分期

- **M1（基础）**：`acorn reformat <module>` —— 解析 → pretty 打印 → 与原文 diff；验证"纯格式化不破坏证书回放"。同时交付 `split-file`（按声明集合切分，无改名）。风险最小，收益立即可见（把 312 个扁平文件按目录/命名整理）。
- **M2（改名/引用修复）**：`rename-decl <old> <new>` + `move-decl`：自动更新本模块内引用 + 生成 import 修复补丁；输出重验闭包清单。门禁 = 闭包 strict。
- **M3（合并/模块级）**：`merge-modules`、`rename-module`（带兼容 stub 策略）；自动 import 修复 + 影响闭包调度。
- **M4（集成到 Suzumio）**：把重构器暴露为 Suzumio toolpack（`acorn.refactor`），让 librarian/PM 在平台内发起重构任务，结果自动走闭包验证 + PR 批。

### 3.8 外部参照：其他证明助手的重构工具链（并行子代理简报）

【惯例/已证实；来源：AST 工具链研究子代理简报】
- **Coq/Rocq**：**SerAPI**（机器可读序列化协议，`sertop` JSON/S-expr）开发已停止，**被 coq-lsp/rocq-lsp 取代**（rocq-lsp 提供 documentSymbol/hover/definition，但**没有 rename 重构**，references 依赖 `.glob` 文件且"often incomplete"）；**增量编译 `.vo/.vos/.vok`** 是"先只重查陈述、稍后并行查证证明"的机制；`coqdep` 计算模块依赖图来确定重编译闭包；RefacCert 提供了"证明重构且保持 proof term 等价"的认证式重构先例。参考：https://github.com/rocq-archive/coq-serapi ；https://github.com/rocq-community/rocq-lsp ；https://github.com/rocq-prover/rocq/pull/8642
- **Lean 4**：theorem **默认 opaque**；proof term 按名引用常量 ⇒ 改名后"类型/证明项提及旧名"的所有后续声明必须重 elaboration，但**该定理自身的证明体文本不变**；**生成名**（`T.match_1`、`T._proof_1`、`T.rec`、投影、`[simp]` 等名字键控属性）必须同步迁移——这是脚本式改名（sed/find-replace + 重建 import 闭包）的主要陷阱；**文件移动在 Lean/Isabelle 很便宜**（声明名不含文件/模块路径，只改 import），在 **Coq 很贵**（逻辑名 = 模块路径）；mathlib 的 `#align` 映射 2024 年已移除，改名现在必须更新所有引用。参考：https://leanprover-community.github.io/lean4-metaprogramming-book/ ；https://github.com/leanprover-community/mathlib4/commit/465f26fde59aa31d051ef0b6db1fb34476802b64
- **Isabelle**：**PIDE 文档模型**对编辑做增量重查（只重查受影响区间）；`isabelle build` 按 session 依赖图 + heap 镜像缓存只重建受影响闭包；`isabelle update` 用于脚本化系统更新。参考：https://www21.in.tum.de/~wenzelm/papers/itp-pide.pdf ；https://isabelle.in.tum.de/website-Isabelle2025-RC4/dist/Isabelle2025-RC4/doc/system.pdf
- **通用工具**：**rowan（rust-analyzer 的无损红绿具体语法树）**是 Rust 重构器的规范蓝本——带 trivia（空白/注释）的 lossless CST + 增量重解析；ghc-exactprint 用"AST 标注精确源码位置 + 无损重印"解决注释保留；tree-sitter 语法（tree-sitter-lean、tree-sitter-rocq）与 ast-grep/Topiary 展示了 CST 编辑模式，但证明助手语法（notation、自定义 elaborator）超出 tree-sitter 覆盖，**elaborator 才是"token 解析到哪个名字"的最终事实来源**。参考：https://docs.rs/crate/rowan/0.12.1 ；https://github.com/rust-lang/rust-analyzer/blob/master/docs/dev/syntax.md
- **对 Acorn 重构器的四条借鉴**：(1) **注释保留是难点**——Acorn parser 把 DocComment 作为语句节点保留，但普通注释是 token；建议采用"token 区间（first/last_token）重印"或 rowan 式 trivia 方案，先做实验确认纯注释/空白变化不破坏证书回放；(2) **最小重验集 = 依赖闭包 ∩ 名字引用索引**（Coq `.glob`、Lean import 图同理）——与 §3.5 设计一致；(3) **Acorn 的移动成本介于 Lean 与 Coq 之间**：限定名 `lib(module).name` 如 Coq 受模块路径影响，但证书中未限定名经 import 解析 ⇒ 改 import + 证书文本改写即可保留证书（§3.4）；(4) 生成名/属性/instance 必须随声明迁移（Acorn 的 `attributes`/`instance`/`numerals` 块与 Lean 的 `[simp]` 属性同属名字键控状态）。【惯例/已证实（外部）＋ 推测（对 Acorn 的映射）】

---

## 4. 优先级行动清单

| 优先级 | 行动 | 理由 | 依赖 |
|---|---|---|---|
| **P0** | 把"单模块 `check --strict` 门禁 + manifest 缓存键 + 串行写 build/"固化为 Suzumio 工具与 CI 的强制路径 | 两周战役最大成本是重放与集成；这是唯一事实来源 | 无（机制已存在） |
| **P0** | 交付 AST 重构器 M1（reformat + split-file，不改名） | 解锁文件级分片；为并行化提供细粒度工作单元；风险最低 | 复用 syntax/ + pretty |
| **P1** | 模块 DAG 分层 + 依赖前沿调度 + 目标注册表（goal 指纹去重） | 让并行度与 DAG 解耦，消除重复劳动 | export --full 数据 |
| **P1** | 集成队列：staging 分支 + 批量 rebase + 闭包 strict + review-sized PR 批 | 把"53 次提交"摊薄成"5–10 批" | P0 第一项 |
| **P1** | 验证"纯格式化/注释变化不破坏证书回放"的最小实验 | 决定 M1 与名称稳定性协议的前提 | 本地 acorn binary |
| **P2** | 重构器 M2/M3（rename/move/merge/module rename + 自动 import 修复 + 闭包重验调度） | 大规模整理库结构（312 文件 → 规范目录） | M1 + 影响分析层 |
| **P2** | 证明搜索下探：把"多 agent 并行"与"verify --jobs N / 单目标搜索"对齐，探索证书状态缓存复用（对应 Lean 的 state snapshotting） | 提升单个模块的搜索吞吐 | acorn 内部 |
| **P2** | 失败/审计成本记账（SQLite 已有 activations/tool_calls）→ 月度复盘 | 让"审计/阻断"成本可量化、可优化 | 无 |

---

## 5. 主要参考资料

**AI 形式化系统**：
- AlphaProof/AlphaGeometry（Nature 2025）：https://www.nature.com/articles/s41586-025-09833-y ；研究页：https://research.google/pubs/olympiad-level-formal-mathematical-reasoning-with-reinforcement-learning/
- DeepSeek-Prover-V2：https://arxiv.org/abs/2504.21801 ；V1.5（MCTS/truncate-and-resume）：https://arxiv.org/abs/2408.08152 ；V1：https://huggingface.co/deepseek-ai/DeepSeek-Prover-V1
- InternLM2.5-StepProver：https://arxiv.org/abs/2410.15700
- Goedel-Prover：https://arxiv.org/abs/2502.07640 ；站点：https://goedel-lm.github.io/
- Llemma：https://arxiv.org/abs/2310.10631
- LeanDojo：https://arxiv.org/abs/2306.15626 ；Lean Copilot：https://arxiv.org/abs/2404.12534
- Draft, Sketch, and Prove：https://arxiv.org/abs/2210.12283
- Hilbert（Apple，miniF2F 99.2% / PutnamBench 70%）：https://arxiv.org/abs/2509.22819 ；https://machinelearning.apple.com/research/hilbert
- LeanAgent（155 定理 / 23 仓库）：https://arxiv.org/abs/2410.06209 ；https://leandojo.org/leanagent.html
- Lean-STaR：https://arxiv.org/abs/2407.10040 ；OProver（OProofs 数据）：https://arxiv.org/abs/2605.17283 ；Seed-Prover：https://arxiv.org/abs/2507.23726
- ECP（Enumerate–Conjecture–Prove，裁判式可接受性检查）：https://arxiv.org/abs/2505.18492
- **ATLAS / AutoformBot（Meta，数千智能体库级形式化）**：https://arxiv.org/abs/2605.29955 ；https://github.com/facebookresearch/atlas-lean
- BFS-Prover-V2：https://github.com/ByteDance-Seed/BFS-Prover-V2
- Prover-Verifier Games：https://arxiv.org/abs/2407.13692
- Autoformalization 综述：https://arxiv.org/abs/2505.23486
- 证明状态快照（elaboration 占 >99% wall time）：https://arxiv.org/abs/2605.25556
- 依赖感知评审（Lean Atlas / Lean Compass）：https://arxiv.org/abs/2604.16347 ；写时冲突检测（STORM）：https://arxiv.org/abs/2605.20563 ；HITL（FormalScience）：https://arxiv.org/abs/2604.23002 ；Erdős 开放问题 agent 成本：https://arxiv.org/abs/2605.22763 ；Tao 的 Lean+Claude Code 实验：https://mathstodon.xyz/@tao/114531073456744061

**基准**：
- miniF2F：https://arxiv.org/abs/2109.00110 ；PutnamBench：https://arxiv.org/abs/2407.11214 ；ProofNet：https://arxiv.org/abs/2302.12433 ；MSC-180：https://arxiv.org/abs/2512.18256
- FrontierMath 与 o3 复测争议：https://techcrunch.com/2025/04/20/openais-o3-ai-model-scores-lower-on-a-benchmark-than-the-company-initially-implied/

**并行库开发**：
- mathlib 贡献指南：https://leanprover-community.github.io/contribute/how-to-contribute.html ；工作流文档（bors/CI）：https://github.com/leanprover-community/mathlib4/blob/master/docs/workflows.md ；olean 缓存（`lake exe cache`）：https://github.com/leanprover-community/mathlib4/blob/master/Cache/README.md ；bors 工作流：https://github.com/leanprover-community/mathlib4/blob/master/.github/workflows/bors.yml ；mathport（Lean3→4）：https://reservoir.lean-lang.org/@leanprover-community/mathport
- Coq/Rocq 下游 overlay（依赖前沿重验）：https://github.com/lthms/coq/blob/master/dev/ci/user-overlays/README.md ；增量检查 `.vo/.vos/.vok`：https://github.com/rocq-prover/rocq/pull/8642 与 https://discourse.rocq-prover.org/t/parallel-checking-within-a-file-with-vok/643/1 ；并行证明处理手册：https://rocq-prover.org/doc/v8.20/refman/addendum/parallel-proof-processing.html ；stdlib 开发加速 RFC 083：https://github.com/rocq-prover/rfcs/blob/main/text/083-boost-stdlib-dev/text.md ；stdlib 目录迁移：https://github.com/rocq-prover/rocq/pull/19530
- Isabelle AFP：https://isa-afp.org/ ；Isabelle System manual（session/并行构建）：https://isabelle.in.tum.de/website-Isabelle2025-RC4/dist/Isabelle2025-RC4/doc/system.pdf ；PIDE：https://www21.in.tum.de/~wenzelm/papers/itp-pide.pdf
- Mizar MML 提交流程：http://www.mirror.mizar-jp.org/library/submit.html ；Flyspeck：https://arxiv.org/abs/1501.02155

**AST/重构工具**：
- SerAPI（已被 rocq-lsp 取代）：https://github.com/rocq-archive/coq-serapi ；opam：https://opam.ocaml.org/packages/coq-serapi/
- rocq-lsp（原 coq-lsp，无 rename 重构）：https://github.com/rocq-community/rocq-lsp ；协议支持表：https://raw.githubusercontent.com/rocq-community/rocq-lsp/main/etc/doc/PROTOCOL.md
- Coq 增量编译 `.vo/.vos/.vok`：https://github.com/rocq-prover/rocq/pull/8642 ；RefacCert（证明重构）：https://gitlab.univ-nantes.fr/cohen-j/RefacCert/-/releases/
- Lean 4 元编程书（elaboration）：https://leanprover-community.github.io/lean4-metaprogramming-book/ ；Lean 语言参考（Elaboration and Compilation）：https://lean-lang.org/doc/reference/latest/Elaboration-and-Compilation/ ；mathlib4 移除 `#align`：https://github.com/leanprover-community/mathlib4/commit/465f26fde59aa31d051ef0b6db1fb34476802b64
- Isabelle PIDE：https://www21.in.tum.de/~wenzelm/papers/itp-pide.pdf ；Isabelle/jEdit（文档模型）：https://arxiv.org/abs/1207.3441
- tree-sitter-lean：https://github.com/wvhulle/tree-sitter-lean ；https://github.com/BoltonBailey/tree-sitter-lean ；tree-sitter-rocq：https://github.com/lamg/tree-sitter-rocq ；ast-grep：https://ast-grep.github.io/ ；Topiary：https://topiary.tweag.io/
- rowan（rust-analyzer 无损 CST）：https://docs.rs/crate/rowan/0.12.1 ；rust-analyzer 语法设计文档：https://github.com/rust-lang/rust-analyzer/blob/master/docs/dev/syntax.md ；ghc-exactprint（注释保留重印）：https://www.stackage.org/lts-19.32/package/ghc-exactprint-0.6.4
- QED at Large（形式化软件工程综述）：https://dl.acm.org/doi/10.1561/2500000045

**本地事实来源**：`/data/acorn_venv/acorn/src/`（syntax/、loader/、manifest.rs、exporter.rs、certificate.rs、kernel/concrete_proof.rs）、`/data/acorn_venv/acorn-tools.md`（39 工具提案）、`/data/acorn_venv/doc/multiagent-formalization-team-guide-2026-05-31.md`、`/data/acorn_venv/suzumio/`（README、docs/architecture.md、docs/concepts.md）、`/data/acorn_venv/acornlib-suzumio-workflow/acorn-formalization.yaml`、`/data/acorn_venv/acornlib-20260609-progress.md`、`/data/acorn_venv/archived/acornlib/`（manifest.json、build/*.jsonl 样例）。

---

*备注：本报告由主研究智能体基于本地源码/工作区文档核查 + 定向 web 检索 + 3 份并行研究子代理简报（并行库开发 / AST 工具链 / 智能体平台与成本）综合而成；第 4 份子代理（AI 系统图景）简报未在时限内交付，其范围已由主智能体自身的检索覆盖。所有事实均已在正文标注来源。*
