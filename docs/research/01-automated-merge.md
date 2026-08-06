# Acorn 分支自动合并与证书重放自动化：现状调研报告

> 调研日期：2026-08-05 ｜ 面向对象：Acorn 证明助手（acornlib）多代理分支合并流程
> 说明：本报告所有外部 URL 均来自实际检索结果（web_search），未凭空构造。每项结论标注为【已确立实践】/【研究原型】/【推测性】——"已确立实践"指主流系统/社区在生产中使用；"研究原型"指有可运行工具或论文但非默认实践；"推测性"指只有想法/类比、无成熟工具。

---

## 0. 执行摘要

1. **结论先行：Acorn 的架构（per-claim 证书 + blake3 模块 manifest + 只读重放的 `check --strict`）在业内已经是"最好形状"之一**——按语句粒度重放证书的能力目前只有 Metamath 具备；Lean/Coq/Isabelle 的重放粒度都比 Acorn 粗。因此"合并后只重证受影响模块"这条路在架构上是通的，缺的是**工具化**而非**可行性**。
2. **Git 层面没有任何现成的"证书合并"解决方案**，也没有任何主流证明库提交证书类构建产物（mathlib 的 olean、Coq 的 .vo、Isabelle 的 heap 都不进 git）。Acorn 提交证书 + manifest 的模式在业内是罕见的。但 Git 生态有成熟模板可抄：**为 `manifest.json` 写一个 per-key 3-way JSON merge driver（.gitattributes 自定义 merge driver，属已确立实践）**，把"每个分支都在 manifest 上冲突"降级为"只有同模块 hash 变化才冲突"。
3. **"验证优先的合并"（verify-then-merge）是业界的标准答案**：mathlib 历史上用 bors（从 Mergify 切换），现在用 GitHub merge queue，原则是"永远只合并经 CI 验证过的**合并结果本身**"。Acorn 需要的是同款编排：staging 合并 → 定向重证 → 全库 `check --strict` → 通过才落地。
4. **AST 级重构可以保住证书有效性，前提是证书按"声明身份"（名字）而非文件位置键控**——这是 Lean `move-decls` 能工作的原因（声明名不随文件变化）。Acorn 的 JSONL 证书若满足该前提，则拆分/合并文件、跨模块移动声明都是可自动化的，且 `check --strict` 重放是比主流 codemod 的测试**更强的正确性 oracle**。
5. **现实预期**：以本地数据为参照（46 个已接受分支中 36 个 merge-tree 干净、57 个冲突/需手动；已打包 PR 的冲突绝大多数是 manifest-only 或证书 churn），**纯机械合并（源合并 + manifest 定制 driver + 冲突标记检测 + 定向重证）可让大部分（估计 60–80%）合并接近全自动**；剩余 20–40% 涉及同模块修改、语义冲突、上游 API 变更导致的重证失败，需要人工/agent 介入。任何情况下**合并结果的验证门不可省略**——这是底线，不是优化项。

---

## 1. 现状全景：Git 层的合并自动化

### 1.1 问题的本质：为什么 3-way 行级合并不够

Git 默认的 3-way 合并只理解"哪一侧改了哪些行"，无法理解：

- 证书 `.jsonl` 中两个**不同行**可能在语义上冲突（同一 claim id/定理名下两条证明 hash 不同的记录）；
- `build/manifest.json` 是**单一 JSON 对象**，任何两个都新增模块的分支必然在同一文件上冲突，即使改的是不相交的 key；
- 两个证书文件的并集可能包含重复/矛盾的记录，只有重放/重证才能发现。

因此现状分四类策略：(a) 让 Git 机械地合并（union/外部 driver）；(b) 语义感知合并（JSON/结构化合并）；(c) 让合并结果被验证（合并队列、rerere）；(d) 干脆不提交派生产物（缓存 + 再生成）。

### 1.2 自定义 merge driver（.gitattributes）——最直接可抄的模式

**机制**：`.gitattributes` 可按路径指定合并行为：`merge=union`（两边的行拼接）、`merge=ours`、或命名外部 driver（`merge=mydriver`，在 gitconfig 里配置 `[merge "mydriver"] driver="script %O %A %B"`，脚本须把结果写回 `%A`）。`git merge-file --union` 是 `merge=union` 的底层命令，可直接用于脚本（[git-merge-file 手册](https://git-scm.com/docs/git-merge-file/2.44.0.html)）。【已确立实践】

**生成文件/锁文件的真实先例**（acornlib 的 `manifest.json` 最像锁文件）：
- **package-lock-merge-driver**：npm 上发布的合并 `package-lock.json` 的 driver（[yarnpkg 页面](https://classic.yarnpkg.com/en/package/package-lock-merge-driver)；[dev.to 教程](https://dev.to/cloudx/resolving-git-conflicts-in-package-lockjson-using-a-merge-driver-2ipk)；[@gemini-testing/npm-merge-driver](https://www.npmjs.com/package/%40gemini-testing/npm-merge-driver?activeTab=readme)；[仓库采用案例](https://github.com/Nitya-003/InnerHue/issues/54)）。
- **rust-lang/cargo#2302** 明确记录了行级合并会生成"不对应任何一侧输入"的 Cargo.lock，**合并后必须重新校验/重新生成**——这正是 Acorn 证书的处境（[cargo issue](https://github.com/rust-lang/cargo/issues/2302)）。
- **changelog 用 `merge=union`**：OpenSearch（[PR #18474](https://github.com/opensearch-project/OpenSearch/pull/18474)）、bareos（[commit](https://github.com/bareos/bareos/commit/ce37e8493ef9a2259c1d0533d927ef98dd3794ae)）等——只适合 append-only 文本，不适合单一 JSON 对象。
- **PO 翻译文件 driver**（Weblate 分发 `git-merge-gettext-po`）：与 JSONL"每行一条记录"的结构最接近的先例（[issue](https://github.com/WeblateOrg/weblate/issues/10967)）。
- **其他**：Chromium 为 clang-reformat 引起的 churn 引入过 merge driver（[codereview](https://codereview.chromium.org/2348793003/)）；Cilium 用 driver 合并生成的 k8s manifests（[PR #43943](https://github.com/cilium/cilium/pull/43943)）；Unity Smart Merge（UnityYamlMerge）是商业级结构化 YAML 合并 driver（[讨论帖](https://discussions.unity.com/t/configuring-unityyamlmerge-for-git-the-correct-instructions/1661546/3)）。
- **`merge=ours`** 用于"永远不合并、之后重新生成"的编译产物（[案例](https://github.com/cgcardona/agentception/issues/699)）。

**形式化方法界的先例：没有。** 检索未发现任何 Lean/mathlib、Coq/Rocq、Isabelle 仓库使用自定义 merge driver。【对证明助手的应用：推测性，模式需从锁文件/PO 世界引入】

**关键坑（有据可查）**：
- driver **只在文件真正冲突时运行**，干净合并/fast-forward 不运行（[SO](https://stackoverflow.com/feeds/question/22577405)）；
- **`git merge-tree`（ort）不执行 merge driver**（[git 邮件列表 bug 报告](http://yhbt.net/lore/git/FR2P281MB231375E73789D6DD5F8BECF6BC552@FR2P281MB2313.DEUP281.PROD.OUTLOOK.COM/)）——不能用 merge-tree 预览 driver 输出；
- `merge=union` 是拼接不是合并，会产生重复行/语法非法文件（对 `manifest.json` 是硬错误）。

### 1.3 rerere / imerge / merge-tree

- **`git rerere`**：按冲突文本记录并自动复用你手工解决过的冲突（[文档](https://git-scm.com/docs/git-rerere/2.22.0)）。【已确立实践】但对高 churn 的证书文件，冲突文本漂移快，只能当便利设施。
- **`git imerge`**：把大合并拆成中间提交的逐对合并，可增量记录/恢复（[README](https://raw.githubusercontent.com/mhagger/git-imerge/master/README.md)）。【已确立实践，维护不活跃】它减小单步冲突规模，不减少冲突总数。
- **`git merge-tree --write-tree`**：不碰工作区做内存合并、报告冲突（[介绍](https://giddydev.hashnode.dev/catch-production-merge-conflicts-before-they-occur-with-git-merge-tree)）。【已确立实践】适合 CI 里做"哪些证书文件会冲突"的分诊；但如上所述它不会跑你的自定义 driver。

### 1.4 JSON / JSONL 3-way 合并工具

- **通用 JSON object merge driver**：`git-json-intellimerge`（[npm](https://www.npmjs.com/package/git-json-intellimerge)）、`@patdx/git-json-merge`（[JSR](https://jsr.io/@patdx/git-json-merge)）、`jsonmerge_git_merge_driver`（[GitHub](https://github.com/fcostin/jsonmerge_git_merge_driver)）、jq 版 DIY gist（[gist](https://gist.github.com/eduard-malakhov/81616a91ad978070c846a2e152d22298)）、`git-merge-packagejson`（[npm](https://www.npmjs.com/package/git-merge-packagejson)）。【研究原型】多为小包/演示级，**预算要自己写/维护**。
- **语义标准**：RFC 7396 JSON Merge Patch 定义了 JSON 对象递归合并语义（null 表示删除）（[RFC](https://www.rfc-editor.org/rfc/rfc7396.html)），很多 driver 实现的是它的 3-way 变体。【已确立实践（作为规范）】
- **JSONL（NDJSON）**：**没有专门的 3-way JSONL merge driver**。可借鉴的模式是 **beads** 的"冲突标记检测"：把 JSONL 里出现 `<<<<<<<` 当作错误条件显式处理（[commit](https://github.com/gastownhall/beads/commit/5e420e8ee04d55b1f36d42313eee5efaa94708ab)）——即不自动合并 JSONL，而是**检测到污染就大声失败**，作为 CI 门。【研究原型，但直接可迁移】
- **注意**：`json-merge`（max-mapper）名字有误导性——它做的是 NDJSON 流的两两合并，不是 3-way merge driver（[npm](https://www.npmjs.com/package/json-merge)）。

### 1.5 合并队列与"验证优先"合并（verify-then-merge）

- **GitHub merge queue**：把 PR 排队、创建临时集成分支、对**合并结果**跑 CI、通过后落地（[GitHub Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue)）。【已确立实践】
- **bors / bors-ng**：经典 "merge when green"：CI 跑在临时 merge commit 上，成功才 fast-forward 到 master，保证 master 永远是"其 PR 的已验证合并"（[bors-ng](https://github.com/bors-ng/bors-ng)）。【已确立实践】
- **mathlib 的先例（与 Acorn 最相关）**：mathlib3 从 Mergify 切到 bors（[PR #2322](https://github.com/butterthebuddha/mathlib/commit/0c74775e1d5e418e8d48bb249911de7cd3ec4c25)），mathlib4 继续用 bors（[bors.toml](https://github.com/101damnations/mathlib4/blob/master/bors.toml)、[PR #40763](https://github.com/leanprover-community/mathlib4/pull/40763)），社区已在讨论换到 GitHub 原生 merge queue（[Zulip 讨论](https://leanprover-community.github.io/archive/stream/287929-mathlib4/topic/Replace.20Bors.20with.20GitHub.20Merge.20Queue.html#478138640)）。【已确立实践】
- **自动合并且仅在检查通过时**：`pascalgn/automerge-action`（[marketplace](https://github.com/marketplace/actions/merge-pull-requests-automerge-action-supports-fast-forward)）、ghprmerge（[README](https://github.com/UnitVectorY-Labs/ghprmerge/blob/1b8f714e012fe79b8a5b56052acd2fdc399fb2a5/README.md)）、Dependabot 式"rebase 到最新 base 再跑检查直到绿"循环。【已确立实践】
- **mathlib 还刻意阻止"大 import 增长"的 PR 合并**——因为模块依赖图的增长直接决定增量重编译成本（[PR #38225](https://github.com/leanprover-community/mathlib4/pull/38225)）。这个策略直接对应 Acorn 的"依赖 fan-out 越大，合并时被失效的证书越多"。

### 1.6 语义合并工具

- **Plastic SCM SemanticMerge**：商业语义合并，按语言 parser 在 AST 层合并，支持外部 parser 扩展（[指南](https://docs-plasticscm.azurewebsites.net/semanticmerge/intro-guide/semanticmerge-intro-guide)；[external parsers](https://docs.plasticscm.com/semanticmerge/external-parsers/external-parsers-guide)）。【已确立实践（商业）】但绑死 Plastic/Unity 工具链，无 JSONL/证明语言 parser。
- **半结构化合并研究**：SSMerge（[PDF](https://www.se.cs.uni-saarland.de/projects/SSMerge/deploy/apel__ssm.pdf)）、"Semistructured Merge with Language-Specific Syntactic Separators"（[UFPE 2024/25](https://portal.cin.ufpe.br/2025/01/13/semistructured-merge-with-language-specific-syntactic-separators/)）、"Leveraging Structure in Software Merge"（[Seibt et al.](https://pauloborba.cin.ufpe.br/publication/2021leveraging_structure_in_software_merge__an_empirical_study/2021-Seibt-Leveraging%20Structure%20in%20Software%20Merge-%20An%20Empirical%20Study.pdf)）。【研究原型】JSONL 恰是"换行分隔的记录"这一半结构化格式，该文献是最接近的研究方向，但没有"合并证明证书"的专门研究或产品。

### 1.7 关键观察：主流证明库都不在 git 里合并派生产物

- **mathlib**：olean 不进 git，用 **`lake exe cache get`** 按 commit 取预编译缓存（[Cache/README.md](https://raw.githubusercontent.com/leanprover-community/mathlib4/master/Cache/README.md)；[lakefile.lean](https://raw.githubusercontent.com/leanprover-community/mathlib4/1645399c2674a15372cb0fc74b63d8550ac8fece/lakefile.lean)；[DeepWiki 核心基础设施](https://deepwiki.com/leanprover-community/mathlib4/2-core-infrastructure)）。源码 diff 只含 `.lean`，普通文本合并即可；缓存按 commit 重建。
- **Coq/Rocq**：`.vo` 是构建产物不进 git，stdlib 甚至移除了安装的 `.v` 源文件（[rocq#17159](https://github.com/rocq-prover/rocq/issues/17159)）。
- **Isabelle**：heap 是会话级产物；[系统手册](https://isabelle.in.tum.de/website-Isabelle2025-RC4/dist/Isabelle2025-RC4/doc/system.pdf)与社区讨论（[Zulip](http://isabelle.systems/zulip-archive/stream/336180-Archive-Mirror.3A-Isabelle-Users-Mailing-List/topic/.5Bisabelle.5D.20Questions.20about.20Isebelle.20session.20build.20process.html#294744639)）说明 heap 不进 git。
- **结论**：acornlib"提交证书 + manifest"的模式在主流生态中**没有同侪**。长期最优解是向 mathlib 模式靠拢（证书进内容寻址缓存、按源 hash 取用），短期则在"提交派生物 + 定制合并 + 验证门"的现有约束内做自动化。

---

## 2. 现状全景：证明助手的证书/重放/缓存

### 2.1 Lean 4 / mathlib

- **olean 与 lake 增量构建**：每个模块编译为 `.olean`（序列化的 kernel 已检查声明 + 导出的证明对象）；lake 维护导入依赖图，按**trace inputs（源 hash、toolchain、imports）**判断陈旧性，`lake build -j` 并行构建（[olean 是什么](https://proofassistants.stackexchange.com/questions/292/what-is-in-an-olean-file)；[lean4 #416 独立编译](https://github.com/leanprover/lean4/issues/416)；[lake trace inputs PR #7906](https://github.com/leanprover/lean4/pull/7906)；[DeepWiki 增量编译](https://deepwiki.com/leanprover/lean4/2.5-incremental-compilation)）。【已确立实践】
- **mathlib 的缓存与 CI**：master 上全库构建，olean 上传为 artifact cache，PR 用 `lake exe cache get` 取 base 再只构建增量（[Cache/README.md](https://raw.githubusercontent.com/leanprover-community/mathlib4/master/Cache/README.md)）；mathlib3 时代是 Azure cache + `fetch_olean_cache.sh`（[commit](https://github.com/leanprover-community/mathlib3/commit/5cd6eeb909663bb6e2aa41e5ddda95d9cb00ff9d)）；CI 按领域分片生成多个 workflow（[mk_build_yml.sh](https://github.com/leanprover-community/mathlib4/blob/e52667ea379842d2a4c0c8bee77bd341cbf0b10c/.github/workflows/mk_build_yml.sh)）。【已确立实践】
- **合并工作流**：bors staging → 全库 CI → 落地；更新依赖的 bump bot 持续开 "chore: update Mathlib dependencies" PR 并由 bors 合并（[示例](https://github.com/leanprover-community/mathlib4/pull/35225)）；阻止大 import 增长（[PR #38225](https://github.com/leanprover-community/mathlib4/pull/38225)）。【已确立实践】
- **lean4checker**：独立实现的、只重放 `.olean` 里导出证明对象的检查器，不重跑 elaborator/tactic——这是与 Acorn `check --strict`（0 searches）最接近的主流对等物（[README](https://github.com/lean4checker/blob/master/README.md)；[Reservoir](https://reservoir.lean-lang.org/@leanprover/lean4checker)；[PA.SE "如何重放 Lean 推导"](https://proofassistants.stackexchange.com/questions/5310/how-to-replay-a-derivation-in-lean)）。**关键反面数据点**：mathlib 曾把它接入 CI 并加 benchmark，后来在常规 CI 里**禁用了**（[build with toolchain #8669](https://github.com/leanprover-community/mathlib4/commit/16f64a1daa2da81b56dcff88eab90ee1559da06f)；[disable in regular CI #12968](https://github.com/leanprover-community/mathlib4/commit/62aac0f1f61add3f9c6d2b8e042bd3cd68c81e1c)）——教训：外部重放检查器要付出工具链同步维护成本，信号价值必须大于维护税。【已确立实践（工具存在且被下游使用），但常规 CI 里被停用】
- **证明无关性与稳定命名**：Lean kernel 中证明项被擦除（`Expr.eraseProofs`，[PR #10867](https://github.com/leanprover-community/mathlib4/pull/10867)），使 olean 小、重放快；mathlib 的定理命名规范让"重构定义但语句不变"时定理名稳定、下游不 churn（[mathlib3 命名规范](https://raw.githubusercontent.com/leanprover-community/mathlib3/34a0c8c5e57b3504d157a7b93069a189054e8b17/docs/contribute/naming.md)）。【已确立实践】

### 2.2 Coq / Rocq

- **.vo 与增量构建**：模块编译为 `.vo`；`coqdep` 计算模块依赖、`coq_makefile` 生成基于依赖的 Makefile（[coqdep 手册](https://manpages.debian.org/trixie/coq/coqdep.1.en.html)），dune 对 Coq 的支持持续演进（[dune coq_lib.mli](https://browse.dgit.debian.org/ocaml-dune.git/tree/src/dune_rules/coq/coq_lib.mli?id=d70f63c4bb1635eff856d32a8183fa96cf25d519)）。【已确立实践】
- **coqchk**：独立于交互式 prover 重查 `.vo` 一致性的检查器（[手册](https://man.archlinux.org/man/extra/rocq/coqchk.1.en.html)；[Coq 命令参考](https://rocq-prover.org/doc/V8.20.0/refman/practical-tools/coq-commands.html)）。**注意**：它共享主 prover 的 kernel 代码（并非真正独立实现）、维护滞后、从未被标准接入构建管线（[dune 里建 coqchk 规则的 open issue #16072](https://github.com/coq/coq/issues/16072)）。【已确立实践（工具存在）/ 研究原型（作为 CI 门）】
- **SerAPI / coq-lsp**：SerAPI 用 JSON 协议暴露 Coq 内部（项、环境序列化，[issue #119](https://github.com/rocq-archive/coq-serapi/issues/119)；[FAQ](https://github.com/ejgallego/coq-serapi/blob/v8.8/FAQ.md)）；coq-lsp/rocq-lsp 是增量语言服务器，**按声明**维护已检查状态（[README](https://ocaml.org/p/coq-lsp/0.2.2%2B8.20/doc/README.html)）。【已确立实践（IDE 用途）】
- **proof repair 研究线（Talia Ringer 等）**——"合并/重构后自动修证"的最大研究线，工作流形状与 Acorn 的"重放失败 → 只在失败处重搜"一致：
  - *QED at Large: A Survey of Engineering of Formally Verified Software*（Ringer, Palmskog, Sergey, Gligoric, Tatlock, FnT 2019/20；[ACM](https://dl.acm.org/doi/10.1561/2500000045)；[arXiv](https://arxiv.org/pdf/1905.07244v1)）
  - *Adapting Proof Automation to Adapt Proofs*（Ringer et al., CPP 2018；[ACM](https://dl.acm.org/doi/10.1145/3167094)）——"fast-forward：把旧证明脚本重放到第一个失败步再修补"
  - *Proof Repair*（Ringer 博士论文，UW 2021；[ResearchWorks](https://digital.lib.washington.edu/researchworks/items/cd72da84-0fed-47d7-9494-405a32b9d76c/full)）
  - *Proof Repair across Type Equivalences*（PLDI 2021；[ar5iv](https://ar5iv.labs.arxiv.org/html/2010.00774)；[rocq 论文页](https://staging.rocq-prover.org/papers/proof-repair-across-type-equivalences)；工具 [PUMPKIN-PATCH](https://github.com/uwplse/PUMPKIN-PATCH)）
  - *Mostly Automated Proof Repair for Verified Libraries*（PLDI 2023；[程序页](https://pldi23.sigplan.org/details/pldi-2023-pldi/2/Mostly-Automated-Proof-Repair-for-Verified-Libraries)）
  - *Baldur: Whole-Proof Generation and Repair with LLMs*（2023；[ar5iv](https://ar5iv.labs.arxiv.org/html/2303.04910)）
  - 实务总结：[Galois "Proof Repair and Code Generation"](https://www.galois.com/articles/proof-repair-and-code-generation)
  - 【研究原型】——整个方向是活跃研究，有可运行原型，不是主流 CI 实践。对 Acorn 的启示是**流程形状**（重放到第一个坏 claim 再局部重搜），不是要建类型等价修补机制。
- **coq-waterproof**：让证明脚本对目标小变化更鲁棒的教学型 tactics 库（[GitHub](https://github.com/proux01/coq-waterproof)）。【已确立实践（教育用途）】

### 2.3 Isabelle

- **会话/heap 缓存**：理论按 **session** 组织，每个 session 编译成 heap image（`.heaps`）；`isabelle build` 按会话粒度增量复用，`-j` 并行（[系统手册](https://isabelle.in.tum.de/website-Isabelle2025-RC4/dist/Isabelle2025-RC4/doc/system.pdf)；[DeepWiki: seL4 Isabelle 构建管理](https://deepwiki.com/seL4/isabelle/6.2-build-management)）。【已确立实践】
- **AFP testboard**：Archive of Formal Proofs 在每次变更时对**全库**（所有 AFP entry × Isabelle dev 版本）做回归构建，失败分诊给维护者（[提交页](https://isa-afp.org/submission/?id=2026-03-25_06-34-01_784)；[isabelle-dev 邮件](https://mailmanbroy.informatik.tu-muenchen.de/pipermail/isabelle-dev/2024-May/017894.html)；[Zulip: Total build failure in AFP](http://isabelle.systems/zulip-archive/stream/247542-Mirror.3A-Isabelle-Development-Mailing-List/topic/Total.20build.20failure.20in.20AFP.html)）。这是**组织模式**（持续回归 + 分诊），不是证书重放技术。【已确立实践】
- **sledgehammer**：用外部 ATP/SMT 解目标并回放构造 kernel 内证明——即"旧证明坏了，自动重新找证"的标准机制（[文档](https://isabelle.in.tum.de/website-Isabelle2013-1/dist/Isabelle2013-1/doc/sledgehammer.pdf)；[SMT 回放管线研究](https://par.nsf.gov/biblio/10679200)）。【已确立实践】

### 2.4 其他系统

- **Agda**：`.agdai` interface 文件缓存模块类型检查结果，按源/依赖失效（[文档](https://agda.readthedocs.io/en/v2.6.4.3/tools/interface-files.html)）；时间戳驱动、无内容寻址、有失效性能问题（[issue #2447](https://github.com/agda/agda/issues/2447)）。【已确立实践但较弱】
- **Metamath**：**最接近 Acorn 的设计**——每个定理以纯文本存完整自包含证明，`verify proof` 用微小验证器逐语句独立重查；纯文本证明天然可合并、可重放（[set.mm verifiers 文档](https://raw.githubusercontent.com/metamath/set.mm/develop/verifiers.md)；[CI 迁移讨论](https://www.mail-archive.com/metamath@googlegroups.com/msg02030.html)；[格式检查 PR 政策](https://www.mail-archive.com/metamath@googlegroups.com/msg02385.html)；压缩证明加载快约 50%（[mmj2 笔记](http://de.metamath.org/other/AsteroidMeta/mmj2ProofCompressionNotes)）；[提议自动检查 PR 的 bot](https://github.com/metamath/set.mm/issues/1851)）。【已确立实践】
- **HOL4/HOL Light**：LCF kernel 逐条检查并记录推理轨迹；HOL4 正往"可独立消费的流式 proof trace"演进（[commit](https://github.com/HOL-Theorem-Prover/HOL/commit/88d9a56abc8c661e19d670c8cc94e6b4809ef259)）。【脚本式重建：已确立实践；导出式证明轨迹：研究原型】
- **PVS**：`.prf` sidecar 存证明，理论变化后重新验证；NASA pvslib 提供 `prove-all` 全库回归脚本（[README](https://raw.githubusercontent.com/nasa/pvslib/master/README.md)）。【已确立实践】
- **内容寻址构建缓存**：Bazel remote cache（按 action/content hash 寻址、跨机器共享，[文档](https://bazel.googlesource.com/bazel/+show/41fe8762bbe3a084d2810716e01b4b06200fa0d1/site/docs/remote-caching.md)）、Nix（derivation 按输入内容 hash 键控，[intensional model 解读](https://raw.githubusercontent.com/fzakaria/fzakaria.com/d59f4be9b1459982bfff02c1de3ef60b67d8181e/_posts/2025-03-08-demystifying-nix-s-intensional-model.md)）。【一般构建：已确立实践；用于证明检查：研究原型/推测性】

### 2.5 增量检查粒度（声明级缓存）

- **按模块**：lean4checker 逐 `.olean` 重放；lake 只重建 trace 变化的模块。
- **按声明**：coq-lsp 在文档内按声明维护已检查状态；**unsorry**（Lean 去中心化 CI 提案）有 "Incremental Kernel Replay"（[ADR-033](https://raw.githubusercontent.com/agenticsnz/unsorry/main/docs/adrs/ADR-033-Incremental-Kernel-Replay.md)）、"Verify on Ingest"（[ADR-048](https://raw.githubusercontent.com/agenticsnz/unsorry/main/docs/adrs/ADR-048-Verify-On-Ingest.md)）、"Sharded Gate A Kernel Replay"（[ADR-063](https://raw.githubusercontent.com/agenticsnz/unsorry/main/docs/adrs/ADR-063-Sharded-Gate-A-Kernel-Replay.md)）等设计。【研究原型】
- **按语句**：Metamath 逐定理独立验证——**主流系统中唯一与 Acorn per-claim 证书同粒度**的系统。

---

## 3. 现状全景：AST 级重构（移动/拆分/合并声明）

### 3.1 Coq/Rocq

- **SerAPI**：JSON 协议暴露 Coq 全 API（解析/执行/查询/环境序列化），CoqGym 等工具的基础（[README v8.16](https://raw.githubusercontent.com/rocq-archive/coq-serapi/v8.16/README.md)；[opam](https://opam.ocaml.org/packages/coq-serapi/coq-serapi.8.20.0+0.20.0/)）。【已确立实践】但**没有**"把这条 vernac 移到另一个文件"的操作，只有构建块。
- **coq-lsp/rocq-lsp**：增量文档模型（Fleche），把文件解析成 vernac 命令树并增量检查（[README](https://ocaml.org/p/coq-lsp/0.2.2%2B8.20/doc/README.html)；[SerAPI 兼容说明](https://github.com/rocq-community/rocq-lsp/blob/e9d23e852b07db6016deac99e0d0822305b447dd/etc/SerAPI.md)）。【已确立实践（IDE）】
- **STM/vernac**：Coq 的 Structured Theory Document 把 `.v` 解析为命令序列（[Stm API](https://coq.inria.fr/doc/V8.18.0/api/coq-core/Stm/index.html#type-doc)）——理论上可写插件移动 `Vernac` 命令并重跑 STM，**但没人发布过这样的工具**。
- **MetaCoq/TemplateCoq**：把 Coq 项/环境整体反射为可操作的数据结构（[GitHub](https://github.com/rlepigre/metacoq)；[opam](https://rocq-prover.org/p/coq-metacoq-template/1.3.4%2B9.0)）。【框架：已确立实践；用它重构整个库：研究原型】
- **coqsplit.ml**：CUFP 2015 教程附带的单文件拆分脚本（[源码](https://raw.githubusercontent.com/arthuraa/cufp-2015-tutorial/74ba8778f57b9703ac8a372cfa8fc2a4621c80b7/coqsplit.ml)）——教程级、无维护。【研究原型】
- **coq-club 2023-10 "moving a definition to a different file" 讨论**：结论是**手动**做（[msg00036](https://sympa.inria.fr/sympa/arc/coq-club/2023-10/msg00036.html)）。【推测性（无工具）】
- **关键结构事实**：Coq 的全局名是 `DirPath.Ident`（模块路径限定），跨模块移动声明会改全局名、破坏引用（[libnames.ml](https://github.com/vbgl/coq/blob/6ef1332d6a227eb8ff959a40215dc7134b104ce6/library/libnames.ml)）；`Section`/`Context` 机制让"移出 section 的定理"改变其精化形式（[sections 手册](https://rocq-prover.org/doc/V8.13.2/refman/language/core/sections.html)）。命名空间稳定性仍在设计（[RFC #25](https://github.com/rocq-prover/rfcs/pull/25)）。

### 3.2 Lean 4

- **元编程 API**：`Lean.Parser` 解析、`Elab.Command` 精化、`addDecl`/`addAndCompile` 运行时加入声明——所有 Lean 工具（linter、`#eval`、move-decls）都建在这上面（[元编程书 Elaboration 章](https://leanprover-community.github.io/lean4-metaprogramming-book/main/07_elaboration.html)；[DeepWiki 命令与声明精化](https://deepwiki.com/leanprover/lean4/2.3.2-command-and-declaration-elaboration)）。【已确立实践】
- **REPL / Pantograph / PyPantograph**：机器到机器接口（[REPL on Reservoir](https://reservoir.lean-lang.org/@leanprover-community/REPL)；[PyPantograph](https://github.com/stanford-centaur/PyPantograph)；[Pantograph 论文](https://www.springerprofessional.de/pantograph-a-machine-to-machine-interaction-interface-for-advanc/50934388)）。【已确立实践（ML-for-ATP 圈）】是读/步进接口，不是库重写工具。
- **mathlib4 的 `move-decls` / `declarations_diff`——与 Acorn 需求最接近的现成先例**：比较两个分支的**声明集合**（原 `no_lost_declarations`，后改名 [commit 9389bd0](https://github.com/leanprover-community/mathlib4/commit/9389bd048052b76eb24639c5b69935977a84ba8d)），检测声明在文件间的移动/改名并生成最小 diff 的 move PR；已 CI 集成（[commit ab1a7fb](https://github.com/leanprover-community/mathlib4/commit/ab1a7fbd22a5daec848143888c480f92bf055621)；[PR #12935](https://github.com/leanprover-community/mathlib4/pull/12935/files)；[PR #15195](https://github.com/leanprover-community/mathlib4/pull/15195/files)；[后置 workflow 输出 Lean-aware diff](https://github.com/leanprover-community/mathlib4/pull/39888)）。【已确立实践】它能工作是因为 **Lean 声明名是 namespace 限定、不随文件变化**。
- **mathport**：机械化把整个 mathlib3 翻译到 Lean 4，用 `#align` 保留旧名别名（[README](https://github.com/avigad/mathport/blob/master/README.md)；[mathlib4 的 Mathport 说明](https://raw.githubusercontent.com/leanprover-community/mathlib4/b0c3952f590d4b2e301d2ffe13bb815856fff1e5/Mathlib/Mathport/README.md)）。【一次性迁移：已确立实践；持续维护：研究原型】
- **olean 不可原地编辑**：`.olean` 是二进制序列化环境（[module.cpp](https://github.com/leanprover/lean4/blob/ff37e5d512efcd3981290270a2fc3ecb100bbd0c/src/library/module.cpp)），只能改源重新编译——与 Acorn 可读 JSONL 证书形成对比：**Acorn 的证书格式在原则上比 Lean 的 .olean 更利于重构**。

### 3.3 Tree-sitter 与证明语言 parser

- tree-sitter-lean 有多个实现但**都是部分的**——Lean 语法由 elaborator 驱动，独立语法无法捕捉语义（[PA.SE 讨论](https://proofassistants.stackexchange.com/questions/5020/why-use-tree-sitter-lean-or-pypantograph-to-extract-lean-4-constructs-like-eval)；[wvhulle/tree-sitter-lean](https://github.com/wvhulle/tree-sitter-lean)）；tree-sitter-rocq 是个人项目（[lamg/tree-sitter-rocq](https://github.com/lamg/tree-sitter-rocq)）；Metamath/Isabelle 无维护中的 grammar。【研究原型】
- 结论：**做语义保持重写的正确基底是证明器自己的 parser/API**（SerAPI、Lean elaborator、STM/PIDE 文档模型），不是 tree-sitter。

### 3.4 主流语言的 codemod 基线

- jscodeshift（[介绍](https://www.sitepoint.com/getting-started-with-codemods/)）、ast-grep（[custom languages](https://github.com/codemod/ast-grep-custom-languages)）、semgrep（[规则语法](https://semgrep.dev/docs/writing-rules/rule-syntax)）、Coccinelle（Linux kernel 规模的语义补丁，[培训](https://lkml.iu.edu/hypermail/linux/kernel/2412.2/03127.html)；[APLAS 2007 论文](https://homes.cs.aau.dk/~rrh/pubs/aplas07.pdf)）。【各自语言内：已确立实践】**没有针对证明文件的同类工具**；对证明助手是【推测性】。

### 3.5 稳定命名/标签与重放友好实践

- **Lean**：声明名全局、namespace 限定、与文件无关——`move-decls` 安全的前提（[DeepWiki 环境与模块系统](https://deepwiki.com/leanprover/lean4/3.5-environment-and-module-system)）；`#align` 让旧名在改名/移植期继续可用；命名规范让名字可预测（[mathlib3 命名规范](https://raw.githubusercontent.com/leanprover-community/mathlib3/34a0c8c5e57b3504d157a7b93069a189054e8b17/docs/contribute/naming.md)）。改名仍是全局重写（[示例 PR](https://github.com/leanprover-community/mathlib4/pull/41654)）。
- **Coq**：全局名含模块路径 → 跨模块移动即改名（见 3.1）。**Metamath**：语句按 label 标识，证明引用 label 而非文本，重排语句免费，改名是机械的 label 重写；set.mm 有批量改名脚本（[PR #1466](https://github.com/metamath/set.mm/pull/1466)；[sqr→sqrt 批量改名](https://github.com/metamath/set.mm/commit/84a8a6a737e5b07f4c8286fc037e095eae98e892)）和拆分巨型 set.mm 的 open issue（[#3520](https://github.com/metamath/set.mm/issues/3520)）。
- **相关研究**：*Growing Mathlib*（Baanen et al., CICM 2025）研究大型数学库的维护机制（移动声明、改名、保持 CI 绿，[arXiv](https://arxiv-org.ezproxy.obspm.fr/html/2508.21593v2)）；*Proof-Refactor*（2026 arXiv）研究把生成的正式证明重构为模块化产物（[arXiv](https://arxiv-org.ezproxy.obspm.fr/html/2606.03743v1)）；*Lean Refactor / ImProver*（2026 arXiv）是 agentic 证明优化（[ar5iv](https://ar5iv.labs.arxiv.org/html/2605.20244)）。【研究原型】

### 3.6 对 Acorn 的核心结论

- **证书有效性能否被 AST 重构保持，取决于一个事实：证书按"声明身份"（名字）而非文件位置键控。** Lean 证明了强版本：名字与文件无关 → 同 namespace 内移动声明名字安全 → mathlib 用 `declarations_diff` 将其 CI 化。Acorn 证书在 `src/<module>/certs/<module>.jsonl`，需审计三点：(1) 键是否含模块路径（含 → 跨模块移动要重键/重证；不含 → 只搬条目 + 改 import）；(2) 证明是否按稳定名字引用声明；(3) 重放是否依赖任何文本性内容（位置、printer 输出、sugar）——Acorn 已有 strict-replay printer bug 先例（`FiniteSet.from_list[...]` 重放为非法表达式，见工作区 AGENTS.md Top 100 #52），所以"重构后重放仍成立"必须测试而非假设。
- **AST 级 merge/refactor 工具对 `.ac` 现实吗？** 现实，且有三个条件：(1) `.ac` 需要一个 checker 之外的可靠 parser（Rust crate 或 shell 出子进程）；(2) v1 操作集照抄 mathlib 已验证的操作：分支间声明集合 diff → 移动/拆分/合并声明（自动改 import/引用）→ 改名 → 重键证书 → `check --strict`；(3) 把重放当正确性 oracle。**独特优势**：主流 codemod 只能"希望"重写正确，Acorn 的 `check --strict`（0 searches）是机器可检查的保证——这使 AST 重构工具不仅现实，而且比主流等价物更安全。
- **清醒的边界**：没有任何工具自动合并证明库的**两个分支**——现有全部是单分支重构。Acorn 的现实目标是**合并助手**（声明集 diff + 提议移动/改名 + 重放验证 + 交给人工），不是黑盒自动合并。

---

## 4. Acorn 自动合并推荐架构

### 4.1 (a) 合并流水线设计（近中期落地）

```
                    ┌─────────────────────────────────────────────┐
                    │  每个候选分支（agent 分支 / 打包分支）        │
                    └──────────────────┬──────────────────────────┘
                                       ▼
  ① 源合并          git merge upstream/master（.ac 源，通常干净）
  ② 产物合并        manifest.json  ← 自定义 per-key 3-way JSON merge driver（.gitattributes）
                    证书 JSONL     ← 结构化 pre-pass（按 claim id 3-way）+ 冲突标记检测门
  ③ 影响面计算      loader 依赖 DAG + manifest hash → 受影响模块集合（依赖闭包）
  ④ 定向重证        仅受影响模块顺序 verify（写 manifest 必须串行！）
  ⑤ 全库门          check --strict -j N（只读，可并行），要求 0 searches
  ⑥ 落地            merge queue / bors 式：CI 跑在合并结果上，通过才 merge
```

各步骤要点：

1. **源合并**：保持现状（不同领域无符号冲突，已证明干净）。
2. **manifest.json 定制 driver**（最高杠杆，投入最小）：`manifest.json` 是扁平 module→blake3 对象；一个约 50 行的 jq/python driver 实现 **per-key 3-way**——仅一侧改则取该侧；两侧同改同值则取；两侧不同值则留冲突标记。这精确编码了工作区现有规则（"保留上游无关模块 churn，只加本分支自己的模块 hash"）。可参考模板：[jq gist](https://gist.github.com/eduard-malakhov/81616a91ad978070c846a2e152d22298)、[jsonmerge_git_merge_driver](https://github.com/fcostin/jsonmerge_git_merge_driver)、[git-json-intellimerge](https://www.npmjs.com/package/git-json-intellimerge)、[@patdx/git-json-merge](https://jsr.io/@patdx/git-json-merge)。机制本身【已确立实践】（自定义 driver 是标准做法）；现成 JSON driver 是【研究原型】——**预算自己写/维护**。
3. **证书 JSONL**：JSONL 是"换行分隔记录"的半结构化格式，无现成 3-way driver；两条路线：(i) 短期——把 `merge=union` 当作**机械预处理**，但必须配套"冲突标记检测门"（任何提交的 `.jsonl` 出现 `<<<<<<<` 即 CI 失败，参考 [beads 模式](https://github.com/gastownhall/beads/commit/5e420e8ee04d55b1f36d42313eee5efaa94708ab)）和"每次合并结果必须重证"的强制门；(ii) 中期——按 claim id 做 3-way 记录合并（键是 claim id，值 3-way），把"同 claim 双写"从静默重复变成显式冲突。
4. **影响面计算**：写一个小工具读 loader 依赖 DAG 与 `build/manifest.json`：从"两侧源文件集合差 + 上游 hash 变化"出发，沿依赖边传播，输出受影响模块集。这与 Lean lake 的 trace-input 失效、mathlib 为 olean cache 加的 `.hash` 文件（[commit 13fffe4](https://github.com/leanprover-community/mathlib4/commit/13fffe41bd106d1f489a5e036efd8c19f682aca3)）是同一机制——Acorn 的 blake3 manifest 已经是它的雏形。
5. **定向重证 + 全库门**：只对受影响模块 verify（**串行**，写 manifest 有竞态，工作区规则已强调）；然后全库 `check --strict -j N`（只读，可并行）作为硬门。mathlib 的教训：lean4checker 因维护成本被常规 CI 停用（[#12968](https://github.com/leanprover-community/mathlib4/commit/62aac0f1f61add3f9c6d2b8e042bd3cd68c81e1c)）——`check --strict` 门要廉价、稳定，否则会变成"CI 维护税"。
6. **验证优先落地**：用 GitHub merge queue 或 bors 风格（mathlib 先例：[从 Mergify 切 bors](https://github.com/butterthebuddha/mathlib/commit/0c74775e1d5e418e8d48bb249911de7cd3ec4c25)、[bors.toml](https://github.com/101damnations/mathlib4/blob/master/bors.toml)）——CI 跑在**合并结果**上，通过才落地。配套 rebase 循环（Dependabot/ghprmerge 模式），让 46 个分支持续贴近 master，每次合并的证书 churn 最小。

### 4.2 (b) 让证书更"合并友好"

1. **证书内嵌源 hash（内容寻址）**：在证书 JSONL 中记录"该 claim 所属模块的源 blake3 hash（或其依赖集合 hash）"。这样两个分支的证书即使文本不同，若源 hash 相同则**可证明未受影响**，合并时可直接取任意一侧而无需重证。这是把现有 `manifest.json` 的模块级 hash 下沉到声明级，把"文本冲突"转化为"可验证的无关性"。【推测性但工程上直接】
2. **按声明身份键控**：审计并固定证书键 = 声明身份（不含文件位置/行列/文本偏移）。若键含模块路径，定义"跨模块移动 = 改名 + 重键"的显式规则（Lean/Coq 均如此处理）。【已确立实践（名字身份）在 Acorn 上的应用：推测性，需先审计】
3. **压缩/最小化证书**：Metamath 压缩证明加载快约 50%（[mmj2 笔记](http://de.metamath.org/other/AsteroidMeta/mmj2ProofCompressionNotes)）；Acorn 证书重放成本正比于证明体积，压缩格式能直接加速全库门。Lean 式证明无关性/擦除（[Expr.eraseProofs](https://github.com/leanprover-community/mathlib4/pull/10867)）不直接迁移（Acorn 重放的是完整证明脚本，不是擦除后的内核项），但提示"证书尽量小"的价值。
4. **稳定命名规范**：mathlib 命名规范（[文档](https://raw.githubusercontent.com/leanprover-community/mathlib3/34a0c8c5e57b3504d157a7b93069a189054e8b17/docs/contribute/naming.md)）保证"语句不变 → 名字不变 → 下游不 churn"。Acorn 应把 claim 名绑定到语句结构（而非生成顺序/序号），否则上游改动会无谓地 churn 一堆无关 claim 名。【已确立实践（流程纪律）】
5. **依赖 fan-out 治理**：mathlib 明确阻止大 import 增长的 PR（[#38225](https://github.com/leanprover-community/mathlib4/pull/38225)）。Acorn 应在合并门中监控模块依赖扇出：被失效证书数量 = 受影响模块闭包大小，fan-out 增长要评审。**尽量少 import、模块粒度合理**能直接缩小每次合并的重证范围。

### 4.3 (c) 自动化比例的现实预期

参照本地数据：46 个已接受分支中 36 个 merge-tree 干净、57 个冲突/需手动（含已打包后不再干净适用的）；已打包 PR 的冲突绝大多数是 **manifest-only 冲突**（保留上游条目 + 加本分支条目）或**证书 churn 回滚**（无关模块的 verify 诱导漂移）。据此估算：

| 场景 | 占比（估计） | 自动化程度 | 需要什么 |
|---|---|---|---|
| 纯新增模块、manifest-only 冲突、无语义冲突 | **50–70%** | **全自动** | JSON driver + 冲突标记门 + 影响面工具 + 定向重证 + 全库门 |
| 同模块 modify/delete、需小幅适配（如 [#1145 topology_compact 加 wrapper](https://github.com/acornprover/acornlib/pull/1145)、[#1115 恢复被删文件](https://github.com/acornprover/acornlib/pull/1115)） | 20–35% | **半自动**（工具提议 diff + agent 确认/微调） | `declarations_diff` 式声明集合 diff（mathlib 蓝图：[#39888](https://github.com/leanprover-community/mathlib4/pull/39888)） |
| 语义冲突、上游 API 变更致重证失败、需重写证明 | **5–15%** | **人工/agent 介入** | 现有 review 流程 + 定向重搜（"重放到第一个坏 claim 再局部重搜"） |

**诚实声明**：这些比例是估计，不是实测。机械部分（源合并 + manifest driver + 冲突标记检测 + 影响面定向重证 + 全库门）"自动化"是已确立实践的组装；"自动修复语义冲突"在任何生态都不存在（proof repair 是研究原型，且其结论是修复是启发式的、最终保障仍是重查）。**任何合并结果都必须过验证门**——这不是可选项。

---

## 5. 风险与坑

1. **3-way 行级合并看不到语义冲突**：两个分支同 claim 不同证明 hash，行级合并要么文本冲突要么静默产生语义错误文件。唯一的解是 claim-id 级 JSON driver + 重放门，缺一不可。`merge=union` 对 `manifest.json` 是语法错误（拼接两个 JSON 文档）。
2. **并行写 manifest 竞态**：工作区规则已记录"并行 verify 会丢 manifest 条目"。合并流水线的重证阶段必须串行写 manifest，之后才允许并行只读 `check --strict`。
3. **strict-replay 的 printer/类型实参脆弱性**：`FiniteSet.from_list[FiniteSet[A]]` 重放为非法表达式的先例说明——证书重放依赖打印器的文本输出，AST 工具不能假设"文本往返 = 恒等"，每次工具操作后都要全库 `check --strict` 兜底。
4. **上游 churn 的失效风暴**：受影响集合 = 依赖闭包；模块 import 越多，上游一次改动失效的证书越多。需要 fan-out 监控 + 小粒度模块 + 稳定命名来压低。
5. **rerere/imerge 的局限**：rerere 按冲突文本精确匹配，高 churn 证书下命中率低；imerge 减小单步规模不减小总数。它们都解决不了"证书必须重证"这一根本约束。
6. **merge driver 的工程坑**：driver 只在冲突时运行、`git merge-tree` 不执行 driver（[lore 报告](http://yhbt.net/lore/git/FR2P281MB231375E73789D6DD5F8BECF6BC552@FR2P281MB2313.DEUP281.PROD.OUTLOOK.COM/)）、`.gitattributes` 自身会冲突、driver 必须对"干净合并"无副作用。测试策略：用一个合成分支矩阵跑 driver 的单元测试，不能依赖 merge-tree 预览。
7. **外部重放检查器的维护税**：lean4checker 被 mathlib 常规 CI 停用（[#12968](https://github.com/leanprover-community/mathlib4/commit/62aac0f1f61add3f9c6d2b8e042bd3cd68c81e1c)）、coqchk 从未接入标准构建（[#16072](https://github.com/coq/coq/issues/16072)）。`check --strict` 作为合并门要有预算维护，且要自问"检查器是否真独立于写证书的验证器"。
8. **证书格式约束**：若证书引用了文件位置、printer 输出或非规范 sugar，重构/合并会破坏重放。**先审计 JSONL 的键与内容，再动工具**。
9. **集中式 artifact cache 的信任面**：mathlib 模式（[`lake exe cache get`](https://raw.githubusercontent.com/leanprover-community/mathlib4/master/Cache/README.md)）取预编译产物会静默扩大信任面（除非每次重查）。Acorn 若走"证书移出 git 进缓存"，必须在重放门稳固之后再做，且缓存 key 必须含源 hash。
10. **LFS/Xet 不解决冲突**：只是搬字节，冲突的证书照样冲突（[LFS 教程](https://www.atlassian.com/git/tutorials/git-lfs)）。

---

## 6. 优先级行动清单

**立即（本周内，纯工具，低风险高回报）**
1. 写 `manifest.json` 自定义 merge driver（per-key 3-way，jq/python 约 50 行）+ `.gitattributes` 绑定；写单元测试矩阵（仅一侧改 / 两侧同改 / 两侧异改 → 冲突标记）。
2. 加 CI 冲突标记检测门：任何提交的 `.jsonl`/`manifest.json` 含 `<<<<<<<` 即失败（[beads 模式](https://github.com/gastownhall/beads/commit/5e420e8ee04d55b1f36d42313eee5efaa94708ab)）。
3. 写"影响面计算"工具：读 loader 依赖 DAG + `build/manifest.json`，输出受影响模块闭包（源差异 + 上游 hash 变化传播）。

**短期（1–2 个里程碑）**
4. 合并流水线脚本：源合并 → manifest driver → 冲突标记检测 → 受影响闭包定向 verify（串行写 manifest）→ 全库 `check --strict -j N`（并行只读）→ 报告。
5. 用 GitHub merge queue（或 bors 风格）把"验证合并结果本身"制度化；给 46 个分支做 rebase 循环保持贴近 master。
6. 审计证书 JSONL：键是否含模块路径？是否引用位置/printer 文本？据此决定"移动 = 重键"还是"移动 = 重证"的规则。**这一步决定 7 的形态**。
7. 证书内嵌源 blake3 hash（声明级内容寻址），使未变模块的合并"可证明无关"。

**中期（2–4 个里程碑）**
8. AST 级工具 v1：`.ac` parser（Rust crate 或子进程）→ 声明级 AST → 全局名字映射 → move/split/merge/rename（自动改 import/引用）→ 重键证书 → `check --strict` 门。蓝图是 mathlib4 的 [`declarations_diff`/`move-decls`](https://github.com/leanprover-community/mathlib4/commit/ab1a7fbd22a5daec848143888c480f92bf055621)（含 [reduced-diff CI 步骤](https://github.com/leanprover-community/mathlib4/commit/4d53cd6e4a2fabbc7fe50fcf261a1c7eb4b9509c) 与 [post-build diff 输出](https://github.com/leanprover-community/mathlib4/pull/39888)）。
9. 依赖 fan-out 监控 + 大 import 增长审查门（mathlib [PR #38225](https://github.com/leanprover-community/mathlib4/pull/38225) 模式）；压缩证书格式（Metamath 先例，[mmj2 笔记](http://de.metamath.org/other/AsteroidMeta/mmj2ProofCompressionNotes)）。

**长期（可选，视规模）**
10. 把证书移出 git，进内容寻址缓存（按源 hash 取用）——mathlib 模式（[Cache/README.md](https://raw.githubusercontent.com/leanprover-community/mathlib4/master/Cache/README.md)）。这使证书/manifest 冲突类**彻底消失**（分支只碰 `.ac` 源，而源已证明能干净合并）；需要缓存服务器 + 策略变更，故列为长期。
11. 跟进声明级增量重放研究（[unsorry ADR-033/048/063](https://raw.githubusercontent.com/agenticsnz/unsorry/main/docs/adrs/ADR-033-Incremental-Kernel-Replay.md) 等）与 proof repair 文献（[Ringer 系列](https://dl.acm.org/doi/10.1561/2500000045)）——作为信息输入，不承诺采用。

---

## 7. 附：关键先例速查表

| 需求 | 最相关先例 | 状态 | URL |
|---|---|---|---|
| manifest 类 JSON 合并 | 锁文件 merge driver 生态 | 已确立实践（机制） | [package-lock-merge-driver](https://classic.yarnpkg.com/en/package/package-lock-merge-driver)、[dev.to](https://dev.to/cloudx/resolving-git-conflicts-in-package-lockjson-using-a-merge-driver-2ipk) |
| JSONL 冲突检测 | beads conflict-marker detection | 研究原型 | [beads commit](https://github.com/gastownhall/beads/commit/5e420e8ee04d55b1f36d42313eee5efaa94708ab) |
| 验证优先合并 | mathlib bors / merge queue | 已确立实践 | [切 bors](https://github.com/butterthebuddha/mathlib/commit/0c74775e1d5e418e8d48bb249911de7cd3ec4c25)、[Zulip 讨论](https://leanprover-community.github.io/archive/stream/287929-mathlib4/topic/Replace.20Bors.20with.20GitHub.20Merge.20Queue.html#478138640) |
| 模块级 hash 缓存 | lake / mathlib olean cache | 已确立实践 | [Cache/README.md](https://raw.githubusercontent.com/leanprover-community/mathlib4/master/Cache/README.md)、[lean4 #7906](https://github.com/leanprover/lean4/pull/7906) |
| 只读重放检查器 | lean4checker（曾接入 mathlib CI 后被停用） | 已确立实践 + 反面教训 | [README](https://github.com/lean4checker/blob/master/README.md)、[停用 #12968](https://github.com/leanprover-community/mathlib4/commit/62aac0f1f61add3f9c6d2b8e042bd3cd68c81e1c) |
| 按语句重放 | Metamath `verify proof` | 已确立实践 | [set.mm verifiers](https://raw.githubusercontent.com/metamath/set.mm/develop/verifiers.md) |
| 合并/重构后修证 | Ringer 等 proof repair 研究线 | 研究原型 | [PLDI 2021](https://ar5iv.labs.arxiv.org/html/2010.00774)、[Galois 总结](https://www.galois.com/articles/proof-repair-and-code-generation) |
| 声明移动工具 | mathlib4 `move-decls`/`declarations_diff` | 已确立实践 | [ab1a7fb](https://github.com/leanprover-community/mathlib4/commit/ab1a7fbd22a5daec848143888c480f92bf055621)、[#39888](https://github.com/leanprover-community/mathlib4/pull/39888) |
| 程序化访问证明器 | SerAPI / Lean REPL / Pantograph | 已确立实践 | [SerAPI README](https://raw.githubusercontent.com/rocq-archive/coq-serapi/v8.16/README.md)、[PyPantograph](https://github.com/stanford-centaur/PyPantograph) |
| 全库回归 + 分诊 | AFP testboard | 已确立实践 | [isabelle-dev 邮件](https://mailmanbroy.informatik.tu-muenchen.de/pipermail/isabelle-dev/2024-May/017894.html) |

---

*报告完。所有引用的外部 URL 均来自本次调研的 web_search 结果；标【推测性】的条目均未发现可运行的现成实现。Acorn 侧的事实（证书布局、manifest 版本 23、`check --strict` 语义、26 个 micro-batch 手工重放、PR 冲突类型分布）来自工作区文档与 PR 追踪记录。*
