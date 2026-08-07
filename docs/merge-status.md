# 上游吸收完成 ✅（2026-08-07）

## 结果

`OmegaCombinator/acornlib-omega` main: `a9186ce1..74687ddb`（merge upstream/master f32b0ac9）

- **101653/101653 OK**（verify），`check --strict` **0 searches**（3m19s @ -j8）
- 比 fork 原版多 ~2500 个目标（上游新增定理/简化吸收）
- fork 独有内容完整保留；上游简化（proof-local 删除）吸收
- erdos396.ac（6 月战役移植）暂缓：其证明引用合并前的 list/nat API，
  保存在 `translate/erdos396-pending/` 待适配

## 工具链成果（全部实测）

1. **manifest/jsonl merge driver**：证书按 goal 键三方合并（修复 delete-side bug）
2. **union_sources.py**：接口文件声明级并集（fork 源码保序 + 上游独有声明追加；
   修复 attributes 复数、instance 同名、多行参数截断三个 bug）
3. **fix_certs.py**：按"源码来源"恢复对应侧完整证书（union 会丢目标）
4. **merge_repair.sh / unblock_merge.py**：收敛循环
5. **acorn 0.2.6 `--save-partial`**（增量搜索补丁，patches/0001）：
   搜索失败时保存已证目标证书，下次续搜——实测 3624 goals 的模块，
   清空证书后第一轮存 11/15 行，第二轮只搜缺失 4 个

## 关键教训

- 证书必须整库用同一版本生成（0.2.4/0.2.6 格式不同）
- 接口文件的正确合并 = fork 完整源码 + 上游独有声明追加（不是单侧）
- 上游独有接口声明若依赖 fork 没有的上游 API → 保留 fork 接口、排除该上游模块
- 全库 strict 门 3m19s 使"每批一次全库门"完全可负担

## 下一步

src/ 重组（org_map.json 已备好，535 模块领域映射）→ move_module.py 逐批移动。

## src/ 重组进度（2026-08-07 晚）

已提交 6 批（全部全库 strict 101653/101653 OK）：
1. probability（9b04ea73）
2. complex + category（1361a3df）
3. graph（39e0bd69）
4. logic（91c57a95）
5. data/arithmetic+nat+int+fin（d244f37b）
6. data/basic+list+finite+cardinal（8c638568 + bfd512cf）——944+ 文件改写
7. algebra/group+monoid+basic（9d596902）

**deferred**：
- algebra/ring/field/module/lie + 散件：移动破坏 real_field 的 `∈` sugar
  strict-replay（`Ideal.zero` 移动后 trace 不匹配，5 goals 无法重放/重搜）——
  已回退 7b。教训：**模块移动可能改变 sugar 的 elaborate 结构，破坏既有证书
  trace**；需要"每模块移动前先查 strict-replay 稳定性"的机制
- 目标在已有包内的根模块（geometry/number_theory/order/polynomial/
  combinatorics/crypto 等 50 个）：移入会变 package-private，需接口再导出机制

## 工具链新增

- reorg_batch.py：org_map 驱动批量移动（包守卫、缩进 import、点/斜杠修正）
- union_sources.py：接口声明级并集（attributes 复数/instance 同名/多行参数修复）
