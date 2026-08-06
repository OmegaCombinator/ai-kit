# 鄂尔多斯(Erdős)单位距离猜想反例：事件核查与 Acorn 形式化可行性评估（最终报告）

> 注：您提到的「鄂尔多斯单位距离猜想」应为 **Erdős（埃尔德什）单位距离猜想** —— "Erdős" 常被中文转写为"鄂尔多斯"（与内蒙古城市同名），本文统一写作"Erdős 单位距离猜想"。
>
> 事件时间线核查：2026 年 5 月 20 日 OpenAI 宣布反例（距今约 3 个月，与"前几个月"吻合）。
>
> 本报告基于对 arXiv 全文、OpenAI 原始 PDF、Erdős Problems 网站、MathOverflow、Lean 形式化仓库等的直接抓取与交叉验证；凡未能直接验证之处均已明确标注。

---

## 0. 核查方法与可信度说明（重要）

以下内容我**直接抓取并阅读了原始页面/全文**：

| 来源 | 状态 |
|---|---|
| arXiv:2605.20695《Remarks on the disproof of the unit distance conjecture》(HTML 全文 956 行) | ✅ 直接验证 |
| arXiv:2605.20579《An explicit lower bound for the unit distance problem》(W. Sawin, HTML 全文) | ✅ 直接验证 |
| arXiv:2606.03419《Optimizing Explicit Unit-Distance Lower-Bound Certificates》(M. Emmerich, 摘要页) | ✅ 直接验证 |
| OpenAI 原始论文 PDF《Planar Point Sets with Many Unit Distances》(cdn.openai.com, 已抽取摘要与正文关键段) | ✅ 直接验证（PDF 字体编码有损，个别符号按上下文复原） |
| erdosproblems.com 第 90、92、1085、1196 号问题页 + 第 90/92 号讨论帖 + 历史页 + Bloom 博客帖(blog:6) | ✅ 直接验证 |
| MathOverflow 问题 511514《What is the unit distance exponent?》(StackExchange API) | ✅ 直接验证 |
| Terence Tao 的常数页 teorth.github.io/optimizationproblems/constants/84a.html | ✅ 直接验证 |
| Lean 形式化仓库 github.com/logical-intelligence/erdos-unit-distance（README + 全文件树） | ✅ 直接验证 |
| lean-lang.org 评测页 erdos_unit_distance_conjecture_false | ✅ 直接验证 |
| google-deepmind/formal-conjectures 提交 b538979（完整 commit message） | ✅ 直接验证 |
| Quanta Magazine《Why the Legendary Erdős Problems Are Falling to AI》(2026-08-03)、Interesting Engineering、GIGAZINE、yunhaimath 博客 | ✅ 直接验证 |
| NDTV 文章《AI Solves 80-Year-Old Math Problem…》(任务线索链接) | ⚠️ 页面被反爬拦截，**仅验证了 URL 与搜索摘要**；内容与其他 5 家媒体一致，无矛盾 |
| OpenAI 官方博客 openai.com/index/model-disproves-discrete-geometry-conjecture/ | ⚠️ 页面需 JS，**未能直接抓取**；但其内容被 gigazine/IE/Quanta 等转述并一致 |

**可信度结论**：该事件是真实、可多重验证的 2026 年 5 月数学新闻；核心一手材料（两篇 arXiv 全文 + OpenAI 原始 PDF）均可直接阅读。**尚未发现该反例被严肃质疑的报道**；相反，社区在几天内对其进行了多轮独立改进（见 §4），且 Gowers、Tsimerman 等 9 位数学家联署背书。需要说明的边界：① 截至所查来源，结果仍处于 arXiv 预印本阶段，**未见期刊同行评议记录**（但 Gowers 明言"若投稿 Annals 我会毫不犹豫建议接收"）；② erdosproblems.com 状态已标为 **DISPROVED (LEAN)**（见 §8，存在 Lean 形式化佐证）；③ 指数竞赛中的多个改进值被标注"unverified"，且出现过订正（Naslund、spiderduckpig 的数值曾被修正）。

---

## 1. 被推翻的确切命题

### 1.1 定义（三份文献一致）

对有限点集 $P \subset \mathbb{R}^2$，令
$$\nu(P) := \#\{\{x,y\} \subseteq P : |x-y| = 1\}, \qquad u(n) := \max_{|P| = n} \nu(P).$$
（即 $n$ 个点中相距恰好为 1 的无序点对最大数。）

### 1.2 问题的三种表述（"猜想" vs "问题"的区别在此重要）

| 出处 | 表述 |
|---|---|
| erdosproblems.com 第 90 号问题页（问题本身的问法） | "Does every set of $n$ distinct points in $\mathbb{R}^2$ contain at most $n^{1+O(1/\log\log n)}$ many pairs which are distance 1 apart?"（即格点构造 $n^{1+c/\log\log n}$ 是否为上界） |
| Erdős 的猜想（最常引用版本，Remarks 论文 §1.1 及 Bloom 评论） | "An upper bound of $n^{1+o(1)}$ was conjectured by Erdős."（即 $u(n) = n^{1+o(1)}$） |
| OpenAI 原论文对猜想的陈述（§1, 式 (1)） | Erdős "conjectured that there should be an absolute constant $C$ such that, for all sufficiently large $n$, $\nu(n) \le n^{1+C/\log\log n}$" |

**被推翻的是**：Erdős 关于 $u(n) = n^{1+o(1)}$ 的猜想——反例证明存在固定 $\varepsilon>0$ 与无穷多个 $n$ 使 $u(n) \ge n^{1+\varepsilon}$，这同时否定了上述三种表述（最强的那条 $n^{1+O(1/\log\log n)}$ 自然也随之失效）。**注意**：问题本身（求 $u(n)$ 的量级）并未"解决"——上界仍是 1984 年 Spencer–Szemerédi–Trotter 的 $O(n^{4/3})$，下界与上界之间仍有巨大鸿沟。

### 1.3 核心定理（直接引用）

- **Remarks 论文 Theorem 1.1**（定性形式）：
  > "There exists $\varepsilon > 0$ such that the following holds. There exists a sequence of point sets $\mathcal{P}_i$ in $\mathbb{R}^2$ such that $|\mathcal{P}_i| \to \infty$ and the number of unit distances in $\mathcal{P}_i$ is at least $|\mathcal{P}_i|^{1+\varepsilon}$ for all $i$."
  （该文给出的显式值 $\varepsilon \approx 6.24\times 10^{-38}$，极小但为正。）
- **Sawin 论文 Theorem 1**（定量形式）：
  > "For $n$ arbitrarily large, there exists a set of points $U \subset \mathbb{R}^2$ such that $\#U = n$ and $\#\{(v_1,v_2) \in U \mid |v_1-v_2| = 1\} \ge n^{1.014114}/C$ for an absolute constant $C$."

### 1.4 连带被推翻：第 92 号问题（Erdős–Fishburn 等距邻点形式）

第 92 号问题：设 $f(n)$ 为最大值，使得存在 $n$ 个点的集合 $A\subset\mathbb{R}^2$，其中**每个** $x\in A$ 都有至少 $f(n)$ 个与 $x$ 等距的点。问是否 $f(n) \le n^{o(1)}$？——这是单位距离猜想的**更强形式**（第 90 号问题的上确界式推广）。反例中单位距离图的平均度 $\ge 2n^{\varepsilon}$，再用"平均度 $\ge D$ 的图含最小度 $\ge D/2$ 的导出子图"这一初等剪枝引理，即得 $f(n)$ 不可能是 $n^{o(1)}$。Erdős 为此设奖：证明 $f(n)\le n^{o(1)}$ 奖 \$500，构造反例仅 \$100（后降为 \$50）。**该问题页现状态同为 DISPROVED。**

---

## 2. 作者、时间线与方法

### 2.1 时间线（均已核实）

| 日期 | 事件 |
|---|---|
| 1946 | Erdős 提出单位距离问题（Amer. Math. Monthly 53, 248–250） |
| 2026-04-16 | Bloom 在 erdosproblems.com 发博"Top 10 Erdős Problems"（第 90 号入选；他自述"没想到一个月后就被解掉"） |
| ~2026-05-13 | erdosproblems.com 第 90 号页面已记载反例（早于公开宣布） |
| **2026-05-20** | **OpenAI 官方宣布**：内部推理模型（未公开版本）一次生成反例证明；同日 arXiv 挂出两篇论文：**2605.20695**（Remarks，9 位数学家联署）与 **2605.20579**（Sawin 显式版本）；OpenAI 原始 PDF《Planar Point Sets with Many Unit Distances》发布；Bloom 同步更新第 90/92 号页面状态 |
| 2026-05-21~06-09 | MathOverflow / Erdős 论坛上的"指数竞赛"：ChatGPT 5.5 Pro 辅助优化参数（mlewko 1.03184、spiderduckpig 1.03188→1.0333、Naslund 1.0346749→1.03583 后经订正为 ~1.0357 等）；Emmerich 提交 arXiv:2606.03419（进化算法优化，δ=0.015263；#T=67 时 $n^{1.031}$） |
| 2026-05-27 | 相关方法推翻**实数上的 sum-product 猜想**（arXiv:2605.28781，Bloom–Sawin–Schildkraut–Zhelezov） |
| 2026-05-28 | Lean 4 形式化仓库 logical-intelligence/erdos-unit-distance 建立（"Logical Intelligence 用 Aleph Prover 形式化"） |
| 2026-06-06 | google-deepmind/formal-conjectures 将反例记录为基准猜想（第 90 号两种变体，sorry-stub） |
| 2026-06-26 | lean-lang 评测页该题被 @plby（Codex，人工在环）解决 |
| 2026-07-21 | Lean 仓库最近推送（仓库 updated_at） |
| 2026-08-03 | Quanta 综述文章发表 |

### 2.2 作者与分工

- **原始证明**：OpenAI 内部模型一次性生成（Remarks 论文脚注："first mathematically generated in one shot by an internal model at OpenAI, and then expositionally refined through human interactions with Codex"）。Sawin 论文明确署名："a team at OpenAI, **consisting of Lijie Chen using an internal OpenAI model and Mark Sellke and Mehtaab Sawhney verifying correctness**"。原始论文署名即 "OpenAI"。CoT 重写稿约 **125 页**。
- **人工消化与验证版**：Noga Alon, Thomas F. Bloom, W. T. Gowers, Daniel Litt, Will Sawin, Arul Shankar, Jacob Tsimerman, Victor Wang, Melanie Matchett Wood（arXiv:2605.20695）。Litt 是被 OpenAI 的 Sellke/Sawhney 请来核查（其专长恰为 Golod–Shafarevich 类域塔）。
- **显式化/优化**：Will Sawin（δ=0.014114，arXiv:2605.20579）；Michael T.M. Emmerich（δ=0.015263 及 $n^{1.031}$，arXiv:2606.03419）；MathOverflow 社区（见 §4）。

### 2.3 社区接受度

- Gowers（Remarks 论文 §5）："if a human had written the paper and submitted it to the Annals of Mathematics and I had been asked for a quick opinion, **I would have recommended acceptance without any hesitation**. No previous AI-generated proof has come close to that."
- erdosproblems.com 第 90 号状态：**DISPROVED (LEAN)**（"已否定解决且证明经 Lean 验证"）；第 92 号：**DISPROVED**。
- 未见公开质疑；指数竞赛中的多次数值订正说明社区确实在逐行检查。

---

## 3. 关键数学成分

反例的构造（按 Remarks 论文的组织，这是 OpenAI 证明的人工作简化版）可拆成**两条数论引理 + 一个几何引理**：

1. **几何引理（Lemma 2.1，几何数论/格点窗口）**：若 $\mathbb{C}^f$ 中有满秩格 $\Lambda$，其"单位圆周点"集合 $U_\Lambda = \{\lambda \in \Lambda : \forall i, |\lambda_i| = 1\}$ 足够大，则把窗口 $(a+\Lambda)\cap B_R$（$B_R$ 为多圆盘）投影到某个复坐标，就得到平面上点数 $\le (9R^2/\delta^2)^f$、单位距离对数 $\ge (u\pi R^2/4v\delta^2)^f$ 的点集；当 $\log(2\nu)/\log|P| > 1$ 时即得指数 $>1$。用平移取平均（unfolding）与体积论证（Minkowski 和）证明。
2. **数论引理（Lemma 2.2，鸽巢原理）**：在 CM 域 $K$ 中，若理想 $Q = \prod_j (P_j\bar P_j)^{k_j}$ 由成对共轭的不同素理想构成，则
   $$|U| := |\{u \in Q^{-2} : |u| = 1\}| \ge \frac{\prod_j (k_j+1)}{h(K)},$$
   且 $Q^{-2} \subseteq D^{-1}\mathcal{O}_K$（$D$ 为显式整数）。证明：对 $\prod_j (k_j+1)$ 个理想 $P_j^{a_j}\bar P_j^{k_j-a_j}$ 的**理想类**用鸽巢原理（Ellenberg–Venkatesh 思想，源自 Michel–Soundararajan），取同类之比得 $\alpha\bar\alpha \in \mathcal{O}_K^\times$，令 $u = \alpha/\bar\alpha$。
3. **塔的存在性（Golod–Shafarevich + Shafarevich + Hajir–Maire–Ramakrishna）**：取固定小素数集 $T$（Remarks 文用 $T=\{3,5,7,11,13,17\}$，$S=\{101,\infty\}$），构造无穷类域塔 $G_T^S$（最大 pro-2 扩张、$T$ 外不分歧、$S$ 中完全分裂），由 Golod–Shafarevich 定理（$r \le d^2/4 \Rightarrow$ 无穷）与 Shafarevich 关系秩界保证其无穷；塔中各层 $L_j$（全实、次数 $f_j \to \infty$、根判别式有界）加上 $i$ 得到 CM 域 $K_j = L_j(i)$。**Hajir–Maire–Ramakrishna 的"Frobenius 切割"技巧**用于在保持塔无穷的同时控制分裂；GPT 原证用的是 pro-3（循环三次塔），人工作简化版按 Victor Wang 建议改用 pro-2 塔。切比雪夫/解析密度定理可被代数途径（本原元 + Schur 型素数因子 + Kummer–Dedekind）替代（Lean 工程实际如此做）。

**具体组装**（Remarks 论文 Proof of Theorem 1.1）：$k = \lceil 18r^3/\pi\rceil - 1$（$r = 2\cdot3\cdot5\cdot7\cdot11\cdot13\cdot17$），$\Lambda = p^{-2k}\mathcal{O}_{K_j}$（$p=101$），用类数界 $h_K \le |\mathrm{Disc}\,K|$（$[K:\mathbb{Q}]\ge 4$ 时，出处 [Borel–Prasad 1989]）得到 $|U| \ge (k+1)^{f_j}r^{-2f_j}$，代入得指数
$$1 + \frac{\log(u\pi/36v)}{\log(36/\delta^2)} \approx 1 + 6.24\times 10^{-38}.$$

**Sawin 的显式化改进**：① 用任意理想而非整环本身（鸽巢更易）；② 用**相对类数** $h^-(K) = h(K)/h(F)$ 替代类数；③ 商掉 Frobenius 的固定幂而非 Frobenius 本身（惯性度小而 Golod–Shafarevich 判据更易满足，仍是 HMR 的方法）；④ 精细选择参数 $T, S_\mathbb{Q}, k, R$。所得 $\delta = 0.014114\ldots$。Sawin 还给出**该方法的理论上限**：格点+鸽巢方法能得到的指数至多 $1 + 1/4.116 \approx 1.243$。

**其他优化**（见 §4）：Emmerich 的进化算法把 $\delta$ 推到 0.015263（$u(n)>n^{1.0152}$），扩大分歧素数集 $\#T=67$ 得到 $u(n)>n^{1.031}$；MathOverflow 上 Naslund 等把记录推到约 $1.0357$（含 Louboutin 型 $L(1,\chi)$ 界、球覆盖重叠改进、窄类群改进等）。

**思想史定位**（Bloom/Shankar/Sawin 的评论）：这是 Erdős 1946 格点构造的自然推广——固定域 $\mathbb{Q}(i)$ 换成**次数趋于无穷的 CM 域塔**（Shankar："固定素数、变动域；用类域塔"），而此前所有尝试都是固定域。Sawin 还解释了为什么此前无人走这条路：固定域时素数定理的低阶项（Dedekind zeta 零点贡献 $X^{1/2}$）淹没了类数项，看不出"换域"有任何收益。

---

## 4. AI / 计算机的参与程度

1. **核心发现完全由 AI 产生**：OpenAI 内部通用推理模型（非数学专用、未公开、无法从外部复现）在评估一批 Erdős 问题时一次性生成了反例构造。Remarks 论文引用其 CoT 关键句："…in principle all extremal examples can be taken algebraic. But the degree and height of that algebraic realization can be enormous…Maybe that enormous degree is not just an annoyance but a source of possible counterexamples. **Number fields deserve a closer look.**"（Bloom 总结：AI 同时满足了"认真想证伪""相信数域推广有戏""熟悉类域论工具"等条件——人类专家往往卡在前两步，Tsimerman 自述曾想构造反例而失败。）
2. **人机协作验证链**：Sellke/Sawhney（OpenAI）→ Litt 核查 → 9 人联署消化版 → 社区指数竞赛逐行复核。
3. **指数竞赛（计算机辅助优化）**：mlewko 用 GPT-5.5 heavy-thinking 两轮提示（8+17 分钟）找到 $\delta=0.03184$ 的参数（$|T|=74, |S|=1082$）；spiderduckpig 用 GPT-5.5 Pro 改 $L_p$ 范数到 $1.03193$；Naslund 混合 ChatGPT 5.5 Pro 与人工改进到 $\approx 1.0357$；Emmerich 写开源 Python 优化+验证管线（整数进化策略）；Tseng 发布独立验证管线与证书包（Zenodo）。**注意**：Tao 的常数页将这些社区数值全部标注 "unverified"，且其中多处后来被订正——这正说明"证书"必须附可复现验证。
4. **Lean 形式化由 AI 完成**：lean-lang 评测页记录该题由 @plby **用 Codex（人工在环）于 2026-06-26 解决**；对应仓库 logical-intelligence/erdos-unit-distance（52 个 .lean 文件、约 1.6 MB、Lean 4.29.1 / Mathlib 4.29.1）——详见 §8。
5. **更广的 AI 数学浪潮**（Quanta 2026-08-03 综述）：2026 年 1 月 Google DeepMind 24 人团队用 Gemini 系统评估 700 条"开放"Erdős 猜想；5 月 DeepMind 21 人团队宣布"最强 agent 自主解决 353 个开放问题中的 9 个，每题成本数百美元"；8 月 1 日 OpenAI 宣布未发布模型 **Astra** 取得 10 项数学进展（含 3 个新 Erdős 问题）；业余者 Price/Barreto 用 GPT-5.4 Pro 解决原始集猜想（第 1196 号，见 §9）。

---

## 5. 影响

- **并未"解决"单位距离问题**：上下界从 $n^{1+c/\log\log n} \le u(n) \le O(n^{4/3})$ 变为 $n^{1+\varepsilon} \le u(n) \le O(n^{4/3})$，鸿沟依然巨大；第 1085 号（高维推广）仍开放。
- **Erdős 奖金**：Bloom 确认 $u(n) \le n^{1+o(1)}$ 的证明或证伪均满足 1995 年 \$500 悬赏条件（1982 年为 \$300）——"AI 解决了一个 \$500 的 Erdős 问题"。
- **对相关问题的启示**（Remarks 论文各作者评论）：
  - **distinct distances**：Sawin 分析表明同样的数域塔思路在此遇到本质障碍（所需塔比 Golod–Shafarevich 能给的强得多），Guth–Katz 结果不受影响；Bloom 更指出反方向：distinct distances 下界 $n^{1-o(1)}$ 反过来约束了"能存在的数域塔"。
  - **$\mathbb{R}^3$ 单位距离**：Sawin 用 Siegel 质量公式论证数域方法在此也受阻。
  - **sum-product**：几天内同一机器推翻实数版 sum-product 猜想（见 §9）——这是最重要的直接连锁反应。
  - **平面染色数**：Bloom/Alexeev 讨论单位距离图染色（Hadwiger–Nelson 相关问题，$\chi(\mathbb{R}^2)\ge 6$ 的探索）：新构造是 Cayley 图型、代数性过强，大概率不直接有用；但"数论格"路线本身被 Bloom 认为极有前景（Moser 环 $\mathbb{Z}[\frac{1+\sqrt{-3}}2,\frac{5+\sqrt{-11}}6]$ 只有有限个 4-染色）。
  - **纯数论推论**：$r_{2,F}(4D^2)$（域 $F$ 中 $x^2+y^2=\alpha$ 的表法数）可沿塔按 $[F:\mathbb{Q}]$ 指数增长。
- **Bloom 的修正猜想**：若把点限制在**有界次数**数域中，原始 $n^{1+o(1)}$ 猜想可能仍真（反例中次数 $d \asymp \log n$）；配合 Solymosi–Schwartz 的 subspaces 定理结果，$\mathcal{O}_K^2$（固定 $d$）上单位距离 $\le n^{1+o(1)}$。

---

## 6. 形式化可行性评估（重点，面向 Acorn 标准库）

### 6.1 最重要的先例：这个反例**已经被形式化了**（Lean 4）

这直接回答了"能不能形式化"：

- **仓库**：github.com/logical-intelligence/erdos-unit-distance（52 个 .lean 文件，约 **1.6 MB** 源码；文件树含 ClassFieldTheory/、ProPGroups/、Cohomology/、NumberFields/、AnalyticNT/、Section2/3（几何部分）等模块）。
- **策略（对 Acorn 最有借鉴价值）**：主定理 **条件化于两条显式假设**（写在 `Assumptions.lean`，出现在 `main_theorem` 的签名里，而不是藏在代码里）：
  1. `Hyp_GolodShafarevichInequality`：有限 $p$-群满足 $d(Q)^2 < 4r(Q)$（Serre《Galois Cohomology》I 附录 2 Thm 1；NSW Thm 3.9.7）；
  2. `Hyp_ShafarevichRelationRankBound`：$r(\mathrm{Gal}(F^{ur,p}/F)) \le d(\cdot) + (r_1+r_2-1) + \delta_p(F)$（Koch《Galois Theory of p-Extensions》Thms 11.5/11.8）。
  3. 其余全部（几何数论窗口、理想/类数鸽巢、塔构造中的 Frobenius 切割、素数 $p \equiv 1 \pmod 3$ 的部分和的解析数论步骤——用 AlexKontorovich/PrimeNumberTheoremAnd 的 **Wiener–Ikehara** Tauber 定理）都是**已证**的；切比雪夫式素数构造被代数途径（本原元 + Schur 型素数因子 + Kummer–Dedekind）替代，**避开了解析 Chebotarev**。
- **信任基**：`#print axioms` 只剩 Mathlib 的三个标准公理 `propext, Classical.choice, Quot.sound`，无 `sorry`，无自造公理；CI 用 `leanchecker` 外部内核复核。JakeMallen 另有"无条件"变体（去掉 PNT+ 依赖，但新增两条公理）。
- **lean-lang 评测页**（提交者 Kim Morrison）记录了该题的形式化目标语句：
  `∃ δ : ℝ, 0 < δ ∧ ∀ N : ℕ, ∃ n P : Finset (EuclideanSpace ℝ (Fin 2)), N ≤ n ∧ P.card = n ∧ n^(1+δ) ≤ unitDist P`，并注明解由 **Codex（人工在环）于 2026-06-26** 给出。erdosproblems.com 第 90 号页因此标为 **DISPROVED (LEAN)**（注：站点徽章与仓库的精确对应关系在我抓到的材料里没有明说，但两条事实互相吻合；我把这个细节标为"未能完全确认"）。

**推论**：该反例形式化的"人类成本"大约是：1 个熟练 Lean 形式化者 + LLM 辅助、**约 4–5 周**（5/20 公告 → 5/28 建仓 → 6/26 评测解决），且是站在 **Mathlib**（其上已有实数分析、数域/代数整数/理想/类群、Wiener–Ikehara 等庞大家当）的肩膀上。

### 6.2 Acorn 需要先有/先建的概念（按依赖顺序）

对比 Acorn 现状（据工作区说明：已有逻辑、集合、商/等价关系、`Fin[n]`、`Zmod[n]`、序结构等基础层，`analysis_i/` 正在并入；**尚无实数/欧氏空间、代数数论**），要形式化该定理（哪怕条件化版本），标准库需要按以下顺序补概念（括号内为粗略估计的引理/概念量级，均为量级估计而非精确承诺）：

| 层 | 所需概念 | 依赖的现有 acornlib 资产 | 量级估计 |
|---|---|---|---|
| L0 | 逻辑、集合、商/等价、有限集、序（已有） | Option、Fin[n]、quotient、set、order | ✅ 基本就绪 |
| L1 | **实数**（完备有序域）、绝对值、指数/对数、幂 $n^{1+\delta}$ | — | 数百条 |
| L2 | **欧氏空间 $\mathbb{R}^2$**、欧氏距离、范数、$L^p$ 范数 | — | 数十~百条 |
| L3 | 有限点集、基数、配对计数、鸽巢原理、平均/求和 | Finset/FiniteSet | 百条级（部分已有） |
| L4 | 交换代数：环、理想、分式理想、商环、模、行列式/迹（判别式需要） | Zmod[n] 的环结构可作起点 | 数百~千条 |
| L5 | **代数数论**：数域、代数整数环 $\mathcal{O}_K$、素理想、范 $N_{K/F}$、判别式/根判别式、类群（= 理想群对主理想的商 —— 直接复用 quotient/equivalence 基建）、类数、CM 域、Dirichlet 单位定理、Minkowski 嵌入 | quotient、Fin[n]（索引共轭）、Zmod | 千~两千条 |
| L6 | **几何数论**：格、余体积、Minkowski 定理、多圆盘体积、平移取平均 | 实数分析 | 数百条 |
| L7 | 群论/同调：pro-p 群、生成元/关系秩、Galois 上同调（transgression、inflation–restriction、五项正合列） | — | 数百条 |
| L8 | **类域塔**：Golod–Shafarevich 不等式、Shafarevich 关系秩界、Frobenius 切割、Chebotarev | — | **建议作为假设**（约 10~30 条陈述） |
| L9 | 解析数论（若走解析路线）：Wiener–Ikehara、$p\equiv 1 \pmod 3$ 素数部分和 | — | 数百条（**可避开**：Lean 工程用代数替代 + 假设化） |

总量级：**数千至上万条标准库引理/概念**才能走完条件化全证（对照：Lean 版在 Mathlib 之上仍需 1.6 MB 源码，而 Mathlib 本身是数千万行量级）。对当前 acornlib 而言这是**多年级工程**——但关键在于 Lean 先例证明的**分解策略**大幅降低了门槛。

### 6.3 建议的分步路线（对 Acorn 现实可行的顺序）

1. **M1（最容易、信息量最大）：形式化语句本身**。目标：`∃δ>0, ∀N, ∃n≥N, ∃P : Finset(ℝ²), P.card = n ∧ n^{1+δ} ≤ ν(P)`（或先做 erdosproblems.com "Formalised statement? Yes" 级别的语句形式化，参考 google-deepmind/formal-conjectures 的 `Erdos90.lean` 变体：`polynomial_lower_bound` 与 `sawin_explicit` 两个 sorry-stub 基准）。只需 L1–L3。**这个里程碑不碰任何数论**，是"标准库离严肃开放数学有多远"的最佳第一回答。
2. **M2：几何引理（Remarks Lemma 2.1 / Sawin Lemma 2 的定性版）**。纯几何数论+计数：格、多圆盘、投影、平均论证、体积界。需要 L1–L3 + L6 的一半。可独立验证、独立发表（与问题本身无关的引理）。
3. **M3：数论鸽巢引理（Remarks Lemma 2.2）**。需要 L4–L5 的核心（理想、类群、CM 域、单位）。这一步开始进入"代数数论标准库"建设，是 acornlib 未来最缺的部分。
4. **M4：把两条类域塔假设显式化**（照抄 Lean 的做法，作为 axiom/assumption 写进定理签名）：Golod–Shafarevich 不等式 + Shafarevich 关系秩界（必要时 + 塔存在性命题 2.3）。同时可以用显式小参数 $T=\{3,5,7,11,13,17\}, p=101$ 让所有有限检查都是可计算验证的。
5. **M5：组装 Theorem 1.1**。$K_j = L_j(i)$、$\Lambda = p^{-2k}\mathcal{O}_{K_j}$、指数估计（含 $\log$ 不等式）。需要 L1–L3 的渐近/不等式部分。
6. **M6（可选）：显式指数与计算证书**。Sawin/Emmerich 的 $\delta=0.014114\ldots$ 需要检查有限参数（$|T|=74$、$|S|=1082$、权重 $k(p)$、惯性见证（二次互反律计算）、有理编码的 $R$）。这类"检查一个有限计算"**比证明整条定理容易**：可用计算反射（native 代码 + 小型验证器）或逐项规范化完成；社区经验（Tao 页 "unverified" 标注、Naslund 数值被订正）恰恰说明**可复现的证书检查是这类结果的刚需**——这正是证明助理（与 Acorn 的 ML 引导搜索）可以增值的地方。注意：**定性反例（M1–M5）完全不需要计算证书**，证书只为更强的显式指数服务。

### 6.4 结论性判断

- **语句本身**：对 Acorn 是"可及但需先建实数层"的任务（数月级标准库工作，取决于实数/分析基建进度）。
- **完整（条件化）证明**：在 Acorn 生态内是多年级大工程，瓶颈是代数数论（L5）与几何数论（L6），而非组合计数本身；**Golod–Shafarevich/Shafarevich/类域塔应照 Lean 先例黑箱化为显式假设**。
- **最大风险点**：不是"反例构造复杂"，而是标准库缺乏数域/类群/判别式基建；建议以 M1（语句）→ M2（几何引理）作为首个可交付里程碑，并可将 M3 的"理想类鸽巢引理"作为代数数论基建的验收目标。
- **与 Acorn 的契合点**：① 类群 = 商/等价基建的直接应用；② 有限检查/证书验证适合 ML 引导搜索 + 计算反射；③ erdosproblems.com 每个问题页都有 "The results on this problem could be formalisable" 标签（目前第 90 号无人认领）——这是公开的、可对标 Lean 社区进度的形式化目标清单。

---

## 7. 其他值得关注的 2025–2026 反例/事件（可作为形式化目标）

1. **sum-product 猜想（实数版）被推翻** —— 与单位距离同一台机器，最强"反例"同类事件。
   - arXiv:**2605.28781**，Bloom–Sawin–Schildkraut–Zhelezov（2026-05-27，math.NT）：构造任意大的 $A\subset\mathbb{R}$（元素是次数 $\asymp \log|A|$ 的数域中的代数整数）使 $\max(|A+A|,|AA|) \le |A|^{2-c}$；还推翻"many sums and products"猜想（$\max(|kA|,|A^{(k)}|) \le |A|^{C\log k/\log\log k}$）；对 $p$-进数、有限域、正特征函数域也有类似构造。**整数版仍开放**（Erdős 第 52 号问题）。Bloom 在 erdosproblems.com 博客(blog:6)中给过通俗讲解。→ 其证明骨架（对数格点嵌入 + 单位群 + 塔）与单位距离共享大半，形式化时可复用 M3–M5 的基建。
2. **Erdős–Fishburn 等距邻点问题（第 92 号）**：单位距离反例的直接推论（见 §1.4），状态 DISPROVED。形式化时是"第 90 号 + 剪枝引理"即可附带完成的小目标。
3. **原始集猜想（第 1196 号）被 AI 证明且已 Lean 验证**（注意：这是"证明"而非反例，但同样是 2026 年标志性 AI 数学事件）：Erdős–Sárközy–Szemerédi 猜想（原始集 $\sum_{a\in A, a>x} 1/(a\log a) \le 1+o(1)$）由**业余者 Price 用 GPT-5.4 Pro 单提示解决**（Lichtman 先证明 $e^\gamma\pi/4 + o(1)\approx 1.399$），arXiv:2605.00301《Primitive sets and von Mangoldt chains》，状态 **PROVED (LEAN)**（Alexeev, Barreto, Li, Lichtman, Price 等；heise、Scientific American 均有报道，"vibe-maths" 一词由此流行）。
4. **AI 批量攻克 Erdős 问题**：DeepMind 2026-01（24 人，Gemini，评估 700 条）、2026-05（agent 自主解决 9/353 个已形式化的问题）；OpenAI 2026-08-01 宣布未发布模型 **Astra** 完成 10 项数学进展（含 3 个新 Erdős 问题）；第 728 号（GPT-5.2 Pro + Aristotle 工具认证）、第 333 号（曾误报"首次由 LLM 解决"，后被指 Erdős 1977 年已解决——反例式教训：文献检索重要）。
5. **高维单位距离（第 1085 号）仍 OPEN**：$d=2$ 是第 90 号（已否证），$d=3$ 最佳为 $n^{4/3}\log\log n$ 级——可作"下一个目标"观察对象。
6. 我没有检索到 2025–2026 年间其他同等量级的"著名猜想被反例推翻"新闻（我的检索以 Erdős 问题生态为中心，可能遗漏其他领域事件——此点如实标注为不确定）。

---

## 8. 引用链接

**一手材料**
- [arXiv:2605.20695《Remarks on the disproof of the unit distance conjecture》(Alon, Bloom, Gowers, Litt, Sawin, Shankar, Tsimerman, Wang, Wood)](https://arxiv.org/abs/2605.20695)（[HTML 全文](https://arxiv.org/html/2605.20695v1)）
- [arXiv:2605.20579《An explicit lower bound for the unit distance problem》(W. Sawin)](https://arxiv.org/abs/2605.20579)（[HTML 全文](https://arxiv.org/html/2605.20579v1)）
- [OpenAI 原始论文 PDF《Planar Point Sets with Many Unit Distances》](https://cdn.openai.com/pdf/74c24085-19b0-4534-9c90-465b8e29ad73/unit-distance-proof.pdf)
- [OpenAI 官方公告（需 JS，内容经多家媒体转述）](https://openai.com/index/model-disproves-discrete-geometry-conjecture/)
- [arXiv:2606.03419《Optimizing Explicit Unit-Distance Lower-Bound Certificates》(M.T.M. Emmerich)](https://arxiv.org/abs/2606.03419)
- [Semantic Scholar 页面（同文）](https://www.semanticscholar.org/paper/Optimizing-Explicit-Unit-Distance-Lower-Bound-Emmerich/5d1c24e798be465083e6d2463a23db9775e6fa94)
- [Zenodo《Optimized Certificate for the Unit Distance Problem with Extended Prime Number Range》](https://zenodo.org/records/20551478)
- [arXiv:2605.28781《The sum-product conjecture is false for real numbers》(Bloom, Sawin, Schildkraut, Zhelezov)](https://arxiv.org/abs/2605.28781)
- [arXiv:2605.00301《Primitive sets and von Mangoldt chains: Erdős Problem #1196 and beyond》](https://ar5iv.labs.arxiv.org/html/2605.00301)

**Erdős Problems / 社区讨论**
- [问题 #90（单位距离，状态 DISPROVED (LEAN)）](https://www.erdosproblems.com/90) · [#90 讨论帖](https://www.erdosproblems.com/forum/thread/90) · [历史页](https://www.erdosproblems.com/history/90)
- [问题 #92（Erdős–Fishburn 等距邻点，状态 DISPROVED）](https://www.erdosproblems.com/92) · [#92 讨论帖](https://www.erdosproblems.com/forum/thread/92) · [proof-claims](https://www.erdosproblems.com/forum/thread/92/proof-claims)
- [Bloom 博客《Sum-product, unit distances, and number fields》(blog:6)](https://www.erdosproblems.com/forum/thread/blog:6)
- [问题 #1085（高维单位距离，OPEN）](https://www.erdosproblems.com/1085) · [问题 #1196（原始集，PROVED (LEAN)）](https://www.erdosproblems.com/1196)

**形式化**
- [Lean 4 形式化仓库 logical-intelligence/erdos-unit-distance](https://github.com/logical-intelligence/erdos-unit-distance)（[README](https://github.com/logical-intelligence/erdos-unit-distance/blob/main/README.md)）
- [lean-lang 评测页《Erdős's unit-distance conjecture is false》](https://lean-lang.org/eval/problems/erdos_unit_distance_conjecture_false/)
- [google-deepmind/formal-conjectures 提交 b538979（记录 2026-05 反例为基准猜想）](https://github.com/google-deepmind/formal-conjectures/commit/b5389792be35027ff70d3a30dac5e4077a729a9e)（另见 [PR #4033 状态更新](https://github.com/google-deepmind/formal-conjectures/pull/4033)）

**指数竞赛 / 综述**
- [MathOverflow Q511514《What is the unit distance exponent?》](https://mathoverflow.net/questions/511514/what-is-the-unit-distance-exponent)
- [Terence Tao 的常数页（Erdős unit distance exponent, C_84）](https://teorth.github.io/optimizationproblems/constants/84a.html)
- [Quanta Magazine《Why the Legendary Erdős Problems Are Falling to AI》(2026-08-03)](https://www.quantamagazine.org/why-the-legendary-erdos-problems-are-falling-to-ai-20260803/)

**新闻（一手不可得时以多源交叉）**
- [NDTV《AI Solves 80-Year-Old Math Problem That Stumped Experts For Decades》（URL 已核实；页面未能直接抓取）](https://www.ndtv.com/world-news/ai-solves-80-year-old-math-problem-that-stumped-experts-for-decades-11571774)
- [Interesting Engineering《80-year-old geometry mystery cracked by OpenAI using deep number theory》(2026-05-20)](https://interestingengineering.com/ai-robotics/openai-paul-erdos-geometry-problem-cracked)
- [GIGAZINE 英文版（转述 OpenAI 公告细节，2026-05-21）](https://gigazine.net/gsc_news/en/20260521-openai-model-disproves-discrete-geometry-conjecture)
- [Mirage News《AI Solves 80-Year-Old Math Problem, Shocks Experts》](https://www.miragenews.com/ai-solves-80-year-old-math-problem-shocks-1680193/)
- [VnExpress《OpenAI chatbot solves 80-year-old math problem, drawing praise from experts》](https://e.vnexpress.net/news/tech/enterprises/openai-chatbot-solves-80-year-old-math-problem-drawing-praise-from-experts-5076884.html)
- [yunhaimath 博客《The Disproof of Unit Distance Conjecture》(2026-05-28)](https://yunhaimath.com/posts/6bf3326/)
- [heise《Creative solution: AI solves 60-year-old Erdős problem》(第 1196 号)](https://www.heise.de/en/news/Creative-solution-AI-solves-60-year-old-Erd-s-problem-11276442.html) · [Scientific American《Even experts are surprised by AI's latest 'vibe-mathing' advance》](https://www.scientificamerican.com/article/amateur-armed-with-chatgpt-vibe-maths-a-60-year-old-problem/)

---

*报告生成：2026-08（研究代理）；抓取材料存于 `research_unit_distance/` 目录。核心不确定项：① 期刊同行评议尚未发生（预印本阶段）；② OpenAI 公告页与 NDTV 页未能直接抓取（内容经多源交叉一致）；③ erdosproblems.com 的 "(LEAN)" 徽章与 Lean 仓库的精确对应关系未在公开材料中明说；④ 指数竞赛多个数值被社区标注 unverified 且经历订正，引用时以 Tao 常数页 + 论坛讨论为准。*
