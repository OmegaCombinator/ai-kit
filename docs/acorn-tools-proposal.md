# Acorn Language Tooling Proposal

This document lists Acorn-language-specific tools that would materially improve agent-driven formalization. The focus is Acorn syntax, types, proofs, certificates, manifests, theorem discovery, and stdlib API review. The proposed command family is `acorn-tools`, with every subcommand supporting machine-readable output for agents.

## Common CLI Conventions

All tools should share these flags where applicable:

```sh
acorn-tools <subcommand> [args...] \
  --lib /path/to/acornlib \
  --acorn /path/to/acorn \
  --json \
  --pretty \
  --timeout 30
```

Common flags:

| Flag | Meaning |
|---|---|
| `--lib <dir>` | Acorn library root. |
| `--acorn <bin>` | Acorn binary used for verify/check/lint-backed tools. |
| `--json` | Emit JSON to stdout. Required for agent integration. |
| `--pretty` | Pretty-print JSON. |
| `--stdin` | Read request JSON from stdin. Useful for longer structured requests. |
| `--output <file>` | Write machine-readable output to a file. |
| `--timeout <sec>` | Per-command timeout. |
| `--include-certs` | Include certificate/manifest details where relevant. |
| `--base <git-ref>` | Base commit/ref for diff and comparison tools. |
| `--head <git-ref>` | Head/final commit/ref for diff and comparison tools. |

Common response envelope:

```json
{
  "tool": "acorn-tools <subcommand>",
  "version": "0.1.0",
  "status": "ok",
  "lib": "/path/to/acornlib",
  "elapsedMs": 1234,
  "warnings": [],
  "errors": [],
  "data": {}
}
```

If a command fails, it should still emit structured JSON when `--json` is set:

```json
{
  "status": "error",
  "errors": [
    {
      "kind": "parse_error",
      "message": "Unexpected token",
      "file": "src/foo.ac",
      "line": 12,
      "column": 8
    }
  ]
}
```

## 1. Acorn AST Parser

Purpose: parse `.ac` files into structured syntax trees, including imports, declarations, proof blocks, expressions, attributes, type parameters, and source spans.

Suggested CLI:

```sh
acorn-tools parse src/ring_hom.ac --lib . --json
acorn-tools parse src/ring_hom.ac --lib . --json --include-proof-bodies
acorn-tools parse --stdin --json < parse-request.json
```

Request interface:

```json
{
  "files": ["src/ring_hom.ac"],
  "includeProofBodies": true,
  "includeExpressionTrees": true,
  "includeSourceText": false
}
```

Response `data` shape:

```json
{
  "files": [
    {
      "path": "src/ring_hom.ac",
      "module": "ring_hom",
      "imports": [
        { "module": "ring", "items": [], "span": { "line": 1, "column": 1 } }
      ],
      "declarations": [
        {
          "kind": "theorem",
          "name": "ring_hom_preserves_one",
          "span": { "startLine": 42, "startColumn": 1, "endLine": 50, "endColumn": 1 },
          "typeParameters": ["R", "S"],
          "parameters": [],
          "statementAst": {},
          "proofAst": {}
        }
      ],
      "parseErrors": []
    }
  ]
}
```

Implementation notes:

- The parser should preserve source spans exactly enough for patching and diagnostics.
- It should support partial parse recovery so tools can still report useful information from damaged files.
- It should expose both high-level declaration nodes and lower-level expression ASTs.

## 2. Declaration Extractor

Purpose: extract top-level declaration inventory without requiring full proof verification.

Suggested CLI:

```sh
acorn-tools decls src/local_equiv.ac --lib . --json
acorn-tools decls src/local_equiv.ac --kinds theorem,define,instance --json
acorn-tools decls --changed --base upstream/master --head HEAD --lib . --json
```

Response `data` shape:

```json
{
  "declarations": [
    {
      "file": "src/local_equiv.ac",
      "module": "local_equiv",
      "kind": "define",
      "name": "local_equiv_id",
      "qualifiedName": "local_equiv.local_equiv_id",
      "typeParameters": ["A"],
      "parameters": [
        { "name": "source", "type": "Set[A]" }
      ],
      "resultType": "LocalEquiv[A, A]",
      "statement": "define local_equiv_id[A](source: Set[A]) -> LocalEquiv[A, A]",
      "visibility": "module",
      "span": { "startLine": 101, "endLine": 119 }
    }
  ]
}
```

Agent-facing uses:

- Build handoff theorem inventories.
- Detect helper spam.
- Identify public API changes before verifier review.

## 3. Signature Normalizer

Purpose: normalize declarations and theorem statements for semantic-ish comparison, duplicate detection, and theorem search.

Suggested CLI:

```sh
acorn-tools normalize-signature src/countable.ac:union_of_countable_is_countable --lib . --json
acorn-tools normalize-signature --statement "forall(x: A) { f(x) = g(x) }" --json
acorn-tools normalize-signature --file src/foo.ac --all --json
```

Response `data` shape:

```json
{
  "items": [
    {
      "name": "union_of_countable_is_countable",
      "original": "theorem union_of_countable_is_countable[A](s: Set[A], t: Set[A]) { ... }",
      "normalized": "forall A. forall s:Set[A]. forall t:Set[A]. is_countable(s) -> is_countable(t) -> is_countable(union(s,t))",
      "alphaNormalized": "forall T0. forall v0:Set[T0]. forall v1:Set[T0]. P_countable(v0) -> P_countable(v1) -> P_countable(union(v0,v1))",
      "fingerprint": "sha256:...",
      "freeNames": ["is_countable", "union"]
    }
  ]
}
```

Key options:

- `--alpha` for alpha-normalized variable names.
- `--resolve-paths` to expand visible short names into qualified names.
- `--commutative-normalize` for known commutative operators when safe.

## 4. Acorn Formatter

Purpose: provide stable formatting for `.ac` code to reduce noisy diffs.

Suggested CLI:

```sh
acorn-tools fmt src/local_equiv.ac
acorn-tools fmt src/local_equiv.ac --check
acorn-tools fmt src/local_equiv.ac --json --diff
```

Response `data` shape:

```json
{
  "files": [
    {
      "path": "src/local_equiv.ac",
      "changed": true,
      "diff": "--- a/src/local_equiv.ac\n+++ b/src/local_equiv.ac\n..."
    }
  ]
}
```

Formatting policy:

- Stable indentation for declarations, proof blocks, lambda/function expressions, and nested quantifiers.
- Configurable max line length.
- Avoid changing semantics or declaration order.
- Provide `--check` for CI and verifier use.

## 5. Acorn Syntax Linter

Purpose: catch Acorn-specific low-cost problems before expensive verification.

Suggested CLI:

```sh
acorn-tools lint-syntax src/module_hom.ac --lib . --json
acorn-tools lint-syntax --changed --base upstream/master --head HEAD --lib . --json
```

Checks:

- Unused imports.
- Duplicate theorem or definition names.
- Excessively broad imports.
- Shadowed variables or declarations.
- Isolated helpers that are not used by final theorem clusters.
- New `axiom`, `admit`, `sorry`, `pending`, `TODO`, `placeholder` markers.
- Suspicious overlong proof blocks.

Response `data` shape:

```json
{
  "findings": [
    {
      "severity": "warning",
      "rule": "unused_import",
      "file": "src/foo.ac",
      "line": 3,
      "message": "Imported `map` is not used in this file.",
      "suggestedFix": { "kind": "remove_import", "span": { "startLine": 3, "endLine": 3 } }
    }
  ]
}
```

## 6. Error Explainer

Purpose: classify and explain Acorn `verify`, `check`, and `lint` errors.

Suggested CLI:

```sh
acorn-tools explain-error logs/verify-local_equiv.log --json
acorn-tools explain-error --stdin --json < acorn-error.txt
```

Response `data` shape:

```json
{
  "classification": "strict_replay_failure",
  "confidence": 0.88,
  "primaryLocation": { "file": "src/foo.ac", "line": 47, "column": 12 },
  "symptoms": ["verify succeeded earlier", "check --strict failed", "printer output contains invalid path sugar"],
  "likelyCauses": [
    "Certificate replay printed a parametrized attribute expression in invalid surface syntax."
  ],
  "suggestedActions": [
    "Introduce a named helper definition to avoid nested parametrized attribute sugar.",
    "Rerun check --strict after regenerating certificates."
  ]
}
```

Failure classes:

- `parse_error`
- `type_mismatch`
- `unresolved_identifier`
- `missing_import`
- `proof_search_timeout`
- `insufficient_lemma`
- `certificate_replay_failure`
- `manifest_or_cert_churn`

## 7. Theorem Index

Purpose: build a searchable whole-library index of definitions, theorems, instances, attributes, signatures, imports, and modules.

Suggested CLI:

```sh
acorn-tools index build --lib . --output build/acorn-tools/index.json
acorn-tools index query --lib . --name "*hom*pow*" --json
acorn-tools index query --lib . --kind theorem --module number_theory --json
```

Index record shape:

```json
{
  "qualifiedName": "complex_pow.complex_conj_fn_pow",
  "name": "complex_conj_fn_pow",
  "kind": "theorem",
  "module": "complex_pow",
  "file": "src/complex_pow.ac",
  "line": 77,
  "typeParameters": [],
  "signature": "...",
  "normalizedSignature": "...",
  "importsUsed": ["complex_conj_hom"],
  "dependencies": ["complex_conj_hom.complex_conj_ring_hom"]
}
```

Indexing notes:

- Build should be incremental by file content hash.
- Index should include Acorn module names and source file paths.
- It should be safe to run read-only in parallel.

## 8. Signature Search

Purpose: search theorem statements by mathematical shape, not just text.

Suggested CLI:

```sh
acorn-tools search-signature --lib . --query "RingHom[A,B] pow" --json
acorn-tools search-signature --lib . --query "FiniteSet image subset" --json
acorn-tools search-signature --stdin --json < signature-query.json
```

Request interface:

```json
{
  "query": "module_hom compose image surjective",
  "kinds": ["theorem"],
  "modules": ["module_hom", "submodule"],
  "limit": 20,
  "includeProofPatternHints": true
}
```

Response `data` shape:

```json
{
  "matches": [
    {
      "score": 0.94,
      "qualifiedName": "module_hom_compose_image.module_hom_compose_image_eq_image_outer_of_surjective_inner",
      "file": "src/module_hom_compose_image.ac",
      "line": 53,
      "signature": "...",
      "why": ["contains module_hom_compose", "contains image equality", "requires surjective inner map"]
    }
  ]
}
```

## 9. Nearby Proof Pattern Search

Purpose: find existing proof structures similar to a target theorem or local proof goal.

Suggested CLI:

```sh
acorn-tools proof-patterns --lib . --statement-file target.json --json
acorn-tools proof-patterns --lib . --near src/complex_pow.ac --terms "conj pow" --json
acorn-tools proof-patterns --lib . --declaration module_hom.foo --json
```

Response `data` shape:

```json
{
  "patterns": [
    {
      "score": 0.91,
      "sourceDeclaration": "complex_pow.complex_pow_mul",
      "file": "src/complex_pow.ac",
      "lineRange": [20, 39],
      "patternKind": "induction_on_nat_power",
      "proofOutline": ["induct on n", "use base exponent theorem", "rewrite recursive pow", "apply hom multiplication law"],
      "snippet": "theorem ..."
    }
  ]
}
```

Pattern categories:

- Set extensionality.
- Subset antisymmetry.
- Function extensionality.
- Natural/list induction.
- Option cases.
- Hom equality.
- Composition equality.
- Membership iff transfer.

## 10. Import and Dependency Explorer

Purpose: show import visibility, direct dependencies, downstream importers, and candidate strict checks.

Suggested CLI:

```sh
acorn-tools deps src/local_equiv.ac --lib . --json
acorn-tools deps --module local_equiv --downstream --lib . --json
acorn-tools deps --changed --base upstream/master --head HEAD --lib . --json
```

Response `data` shape:

```json
{
  "module": "local_equiv",
  "file": "src/local_equiv.ac",
  "imports": ["set", "functions"],
  "visibleDeclarations": [
    { "name": "set_subset", "sourceModule": "set", "kind": "theorem" }
  ],
  "directDownstream": ["topology", "homeomorphism"],
  "recommendedStrictChecks": ["local_equiv", "set", "functions"],
  "riskNotes": ["Changes to local_equiv may affect topology/homeomorphism APIs."]
}
```

## 11. Public API Diff

Purpose: compare base and head and identify public API additions, removals, signature changes, interface edits, and risky exports.

Suggested CLI:

```sh
acorn-tools api-diff --lib . --base upstream/master --head HEAD --json
acorn-tools api-diff --lib . --base 5f618a7 --head accepted/domain/foo --module number_theory.interface --json
```

Response `data` shape:

```json
{
  "added": [
    {
      "kind": "theorem",
      "qualifiedName": "number_theory.interface.satisfies_all_unique_mod_system_modulus",
      "file": "src/number_theory/interface.ac",
      "line": 120,
      "signature": "..."
    }
  ],
  "removed": [],
  "changed": [],
  "interfaceFilesChanged": ["src/number_theory/interface.ac"],
  "riskLevel": "medium",
  "riskReasons": ["Public interface file changed."]
}
```

## 12. Proof Skeleton Generator

Purpose: generate starting proof skeletons for common Acorn proof patterns.

Suggested CLI:

```sh
acorn-tools skeleton --kind subset-antisymm --statement "..." --json
acorn-tools skeleton --kind induction-nat --var n --statement-file theorem.acfrag --json
acorn-tools skeleton --infer --statement-file theorem.acfrag --json
```

Response `data` shape:

```json
{
  "recommendedKind": "subset_antisymmetry",
  "confidence": 0.86,
  "skeleton": "theorem ... {\n  prove subset_left { ... }\n  prove subset_right { ... }\n  submodule_subset_antisymm(...)\n}\n",
  "requiredImports": ["submodule_subset_antisymm"],
  "nextLemmaSuggestions": ["prove membership forward direction", "prove membership reverse direction"]
}
```

Supported skeletons:

- Set equality by extensionality.
- Set/submodule equality by antisymmetry.
- Function equality by extensionality.
- Natural induction.
- List induction.
- FiniteSet/list membership transport.
- Option.some/Option.none case split.
- Ring/module/group hom equality.

## 13. Statement Simplifier

Purpose: suggest proof-friendly theorem decompositions and equivalent statement shapes.

Suggested CLI:

```sh
acorn-tools simplify-statement --statement-file theorem.acfrag --json
acorn-tools simplify-statement src/foo.ac:my_hard_theorem --lib . --json
```

Response `data` shape:

```json
{
  "original": "...",
  "suggestions": [
    {
      "kind": "split_conjunction",
      "reason": "Conjunction-heavy theorem may cause shallow proof-search explosion.",
      "statements": ["theorem left_clause ...", "theorem right_clause ..."]
    },
    {
      "kind": "prove_equality_by_two_subsets",
      "reason": "Target is set equality.",
      "statements": ["subset forward", "subset reverse"]
    }
  ]
}
```

## 14. Goal and Context Dumper

Purpose: on verification failure, export the current goal, local hypotheses, visible declarations, and type variables in a structured form.

Suggested CLI:

```sh
acorn-tools goal-dump src/foo.ac --line 88 --lib . --acorn ./bin/acorn --json
acorn-tools goal-dump --from-log logs/verify-foo.log --lib . --json
```

Response `data` shape:

```json
{
  "file": "src/foo.ac",
  "line": 88,
  "goal": "set_image(s, f) = t",
  "typeVariables": ["A", "B"],
  "locals": [
    { "name": "h", "type": "is_surjective_fn(f)" }
  ],
  "visibleDeclarations": [
    { "name": "set_subset_antisymm", "kind": "theorem", "module": "set" }
  ],
  "suggestedSearchQueries": ["set image equality", "surjective image subset"]
}
```

Implementation note: if Acorn does not expose goal states directly, this tool can initially use instrumented failing-log parsing plus localized declaration and scope extraction.

## 15. Type Inference Query

Purpose: return inferred type information for expressions, declarations, or fragments.

Suggested CLI:

```sh
acorn-tools type-of --lib . --expr "function(x: A) { f(x) }" --context src/foo.ac:88 --json
acorn-tools type-of --lib . --declaration src/foo.ac:my_define --json
acorn-tools type-of --stdin --json < type-query.json
```

Request interface:

```json
{
  "contextFile": "src/foo.ac",
  "contextLine": 88,
  "expression": "FiniteSet.from_list(xs)",
  "expectedType": null
}
```

Response `data` shape:

```json
{
  "expression": "FiniteSet.from_list(xs)",
  "inferredType": "FiniteSet[A]",
  "requiredTypeArguments": ["A"],
  "resolvedNames": [
    { "shortName": "FiniteSet.from_list", "qualifiedName": "finite_set.FiniteSet.from_list" }
  ],
  "unresolved": [],
  "notes": ["Explicit type argument may improve strict replay stability."]
}
```

## 16. Namespace and Path Resolver

Purpose: resolve short names, module paths, qualified names, and import visibility.

Suggested CLI:

```sh
acorn-tools resolve --lib . --context src/complex_pow.ac --name complex_conj_ring_hom --json
acorn-tools resolve --lib . --context src/foo.ac --qualified finite_set.fs_from_list --json
```

Response `data` shape:

```json
{
  "query": "complex_conj_ring_hom",
  "context": "src/complex_pow.ac",
  "candidates": [
    {
      "qualifiedName": "complex_conj_hom.complex_conj_ring_hom",
      "file": "src/complex_conj_hom.ac",
      "visible": true,
      "viaImport": "complex_conj_hom"
    }
  ],
  "ambiguity": false
}
```

## 17. Attribute and Instance Inspector

Purpose: inspect Acorn attributes, typeclass-like structures, instance schemes, and parametrized type availability.

Suggested CLI:

```sh
acorn-tools instances --lib . --type "Zmod[n]" --json
acorn-tools instances --lib . --class Ring --json
acorn-tools attributes --lib . --declaration finite_set.FiniteSet --json
```

Response `data` shape:

```json
{
  "query": { "type": "Zmod[n]" },
  "instances": [
    {
      "class": "Ring",
      "declaration": "zmod.Zmod_ring",
      "typeParameters": ["n"],
      "conditions": ["n > 0"],
      "file": "src/zmod.ac",
      "line": 44
    }
  ],
  "attributes": []
}
```

## 18. Certificate Replay Checker

Purpose: isolate strict replay failures and identify the certificate or printer issue responsible.

Suggested CLI:

```sh
acorn-tools replay-check --lib . --module finite_set --acorn ./bin/acorn --json
acorn-tools replay-check --lib . --file src/foo.ac --certificate src/certs/foo.jsonl --json
```

Response `data` shape:

```json
{
  "module": "finite_set",
  "strictCheck": {
    "command": "acorn check --lib . --strict finite_set",
    "exitCode": 1,
    "certificatesCached": 411,
    "searchesPerformed": 0
  },
  "failure": {
    "certificateIndex": 173,
    "declaration": "finite_powerset",
    "kind": "printer_surface_syntax",
    "printedExpression": "FiniteSet[A].from_list(xs)",
    "suggestedWorkaround": "Introduce a named helper using fs_from_list[FiniteSet[A]]."
  }
}
```

## 19. Certificate Manifest Analyzer

Purpose: analyze `src/certs/manifest.json`, implementation hashes, dependency table changes, and related certificate files.

Suggested CLI:

```sh
acorn-tools manifest-analyze --lib . --base upstream/master --head HEAD --json
acorn-tools manifest-analyze --lib . --manifest src/certs/manifest.json --json
```

Response `data` shape:

```json
{
  "manifest": "src/certs/manifest.json",
  "implementationHashChanges": [
    { "module": "local_equiv", "old": "abc", "new": "def", "expected": true }
  ],
  "dependencyTableChanges": [
    { "module": "unit", "kind": "unexpected_dependency_churn", "expected": false }
  ],
  "certFilesChanged": ["src/certs/local_equiv.jsonl"],
  "untrackedGeneratedManifests": ["src/number_theory/certs/manifest.json"],
  "riskLevel": "medium"
}
```

## 20. Manifest Normalizer

Purpose: restore unrelated manifest dependency churn from the base commit while preserving legal touched-module cert/hash changes.

Suggested CLI:

```sh
acorn-tools manifest-normalize --lib . --base upstream/master --touched src/local_equiv.ac --json
acorn-tools manifest-normalize --lib . --base 5f618a7 --apply --json
```

Response `data` shape:

```json
{
  "changed": true,
  "restoredEntries": [
    { "module": "unit", "field": "dependencies", "source": "base" }
  ],
  "preservedEntries": [
    { "module": "local_equiv", "field": "implementationHash", "reason": "touched source file" }
  ],
  "followUpCommands": [
    "acorn check --lib . --strict local_equiv"
  ]
}
```

Safety policy:

- Default to dry-run.
- Require `--apply` to edit files.
- Never remove touched-module cert records without explicit `--allow-cert-delete`.

## 21. JSONL Certificate Validator

Purpose: validate certificate `.jsonl` files structurally and against declaration inventory where possible.

Suggested CLI:

```sh
acorn-tools cert-validate src/certs/local_equiv.jsonl --lib . --json
acorn-tools cert-validate --changed --base upstream/master --head HEAD --lib . --json
```

Response `data` shape:

```json
{
  "files": [
    {
      "path": "src/certs/local_equiv.jsonl",
      "validJsonl": true,
      "recordCount": 259,
      "blankLines": 0,
      "malformedLines": [],
      "declarationHashMismatches": []
    }
  ]
}
```

## 22. Acorn Module Verifier Wrapper

Purpose: standardize `verify`, `check --strict`, `lint`, diff checks, and JSON validation into a single lane report.

Suggested CLI:

```sh
acorn-tools verify-lane lane.toml --lib . --acorn ./bin/acorn --json
acorn-tools verify-lane --module local_equiv --checks verify,strict,lint,json --lib . --json
```

Example `lane.toml`:

```toml
slug = "local-equiv-bundled-constructors"
base = "5f618a7cc8d413603603b69fcb519b81a63edc27"
modules = ["local_equiv"]
files = ["src/local_equiv.ac"]
strict_downstream = ["set", "functions"]
lint_files = ["src/local_equiv.ac"]
cert_files = ["src/certs/local_equiv.jsonl"]
```

Response `data` shape:

```json
{
  "slug": "local-equiv-bundled-constructors",
  "commands": [
    {
      "kind": "verify",
      "command": "acorn verify --lib . local_equiv --timeout 30 --fail-fast",
      "exitCode": 0,
      "certificatesCached": 259,
      "searchesPerformed": 0,
      "okCount": 259,
      "logPath": "artifacts/verify-local_equiv.log"
    }
  ],
  "summary": "all_required_checks_passed",
  "readyForVerifier": true
}
```

## 23. Downstream Strict-Check Selector

Purpose: choose direct downstream modules and strict checks based on the dependency graph and changed files.

Suggested CLI:

```sh
acorn-tools downstream-checks --lib . --changed --base upstream/master --head HEAD --json
acorn-tools downstream-checks --lib . --module local_equiv --max-depth 1 --json
```

Response `data` shape:

```json
{
  "changedModules": ["local_equiv"],
  "recommendedChecks": [
    { "module": "local_equiv", "reason": "edited module", "required": true },
    { "module": "set", "reason": "direct dependency consistency", "required": true },
    { "module": "functions", "reason": "direct dependency consistency", "required": true }
  ],
  "optionalChecks": [
    { "module": "topology", "reason": "downstream importer", "cost": "high" }
  ]
}
```

## 24. Proof Minimizer

Purpose: reduce rough proof artifacts by removing unused imports/helpers/proof steps where safe and rerunning checks.

Suggested CLI:

```sh
acorn-tools minimize-proof src/foo.ac --declaration my_theorem --lib . --acorn ./bin/acorn --json
acorn-tools minimize-proof --changed --base upstream/master --head HEAD --dry-run --json
```

Response `data` shape:

```json
{
  "attempts": [
    { "kind": "remove_unused_import", "target": "map", "verified": true },
    { "kind": "remove_helper", "target": "foo_helper_3", "verified": false }
  ],
  "resultPatch": "--- a/src/foo.ac\n+++ b/src/foo.ac\n...",
  "verification": { "exitCode": 0, "searchesPerformed": 0 },
  "changed": true
}
```

Safety policy:

- Default to `--dry-run`.
- Only apply transformations that verify successfully.
- Never change theorem statements without explicit `--allow-statement-change`.

## 25. Helper Substantiveness Checker

Purpose: detect facade/alias helper theorems and helpers unused by final target theorems.

Suggested CLI:

```sh
acorn-tools helper-check --lib . --base upstream/master --head HEAD --json
acorn-tools helper-check --lib . --artifact /artifacts/formalizer/foo/result-001 --json
```

Response `data` shape:

```json
{
  "helpers": [
    {
      "name": "left_divisor_pair_block_unique",
      "file": "src/number_theory/dirichlet_assoc.ac",
      "usedBy": ["dirichlet_convolve_assoc"],
      "substantive": true,
      "reasons": ["used by final theorem", "nontrivial uniqueness statement"]
    },
    {
      "name": "foo_alias",
      "substantive": false,
      "reasons": ["statement alpha-equivalent to existing theorem", "not used by final theorem"]
    }
  ],
  "riskLevel": "low"
}
```

## 26. Duplicate Theorem Detector

Purpose: compare new theorem statements against existing normalized theorem statements and flag duplicates or reversed duplicates.

Suggested CLI:

```sh
acorn-tools duplicate-check --lib . --base upstream/master --head HEAD --json
acorn-tools duplicate-check --lib . --statement-file theorem.acfrag --json
```

Response `data` shape:

```json
{
  "duplicates": [
    {
      "newDeclaration": "foo.new_subset_trans",
      "existingDeclaration": "set.subset_trans",
      "similarity": 0.98,
      "relationship": "alpha_equivalent",
      "recommendation": "use existing theorem instead"
    }
  ]
}
```

Relationship values:

- `alpha_equivalent`
- `reverse_equality`
- `weaker_existing`
- `stronger_existing`
- `name_collision_only`

## 27. Forbidden-Scope Scanner

Purpose: enforce lane boundaries by scanning changed files/imports/declarations for forbidden domains or markers.

Suggested CLI:

```sh
acorn-tools scope-scan --lib . --base upstream/master --head HEAD --policy lane-policy.toml --json
acorn-tools scope-scan --lib . --changed --forbid topology,ring,ideal --json
```

Example policy:

```toml
slug = "local-equiv-bundled-constructors"
allowed_files = ["src/local_equiv.ac", "src/certs/local_equiv.jsonl", "src/certs/manifest.json"]
forbidden_modules = ["topology", "homeomorphism", "ring", "ideal", "number_theory"]
forbidden_markers = ["axiom", "admit", "sorry", "TODO", "placeholder"]
```

Response `data` shape:

```json
{
  "violations": [],
  "changedFiles": ["src/local_equiv.ac", "src/certs/local_equiv.jsonl"],
  "forbiddenHits": [],
  "status": "within_scope"
}
```

## 28. Acorn LSP

Purpose: provide language-server features for editor-like and agent-like workflows.

Suggested CLI:

```sh
acorn-tools lsp --stdio --lib .
acorn-tools lsp-query hover --file src/foo.ac --line 12 --column 8 --lib . --json
acorn-tools lsp-query definition --file src/foo.ac --line 30 --column 14 --lib . --json
```

LSP capabilities:

- Diagnostics.
- Hover signatures.
- Go to declaration/definition.
- Completion for visible theorem names.
- Document symbols.
- References.
- Signature help.

Query response example:

```json
{
  "kind": "hover",
  "symbol": "submodule_subset_antisymm",
  "signature": "theorem submodule_subset_antisymm[...] ...",
  "definedAt": { "file": "src/submodule.ac", "line": 211 }
}
```

## 29. Snippet Library

Purpose: provide reusable Acorn proof templates and fragments.

Suggested CLI:

```sh
acorn-tools snippets list --json
acorn-tools snippets show set-extensionality --json
acorn-tools snippets instantiate subset-antisymm --params params.json --json
```

Response `data` shape:

```json
{
  "snippet": {
    "id": "subset-antisymm",
    "description": "Prove equality of sets/submodules using two inclusions.",
    "parameters": ["left", "right", "element", "forwardLemma", "reverseLemma"],
    "template": "...",
    "requiredImports": ["set_subset_antisymm"]
  }
}
```

Useful snippets:

- Set extensionality.
- Function extensionality.
- Nat/List induction.
- Option cases.
- FiniteSet/list membership.
- Ring/module/group hom equality.
- Kernel/image membership bridge.

## 30. Theorem Naming Assistant

Purpose: recommend names for new declarations and check consistency with library naming conventions.

Suggested CLI:

```sh
acorn-tools name-suggest --statement-file theorem.acfrag --lib . --json
acorn-tools name-check --lib . --base upstream/master --head HEAD --json
```

Response `data` shape:

```json
{
  "suggestions": [
    {
      "name": "module_hom_compose_image_eq_image_outer_of_surjective_inner",
      "score": 0.92,
      "reasons": ["matches module_hom naming pattern", "mentions compose/image/surjective hypotheses"]
    }
  ],
  "conflicts": []
}
```

## 31. Interface Exposure Assistant

Purpose: decide whether new declarations should remain implementation-only or be exported to an interface, and generate minimal interface patches.

Suggested CLI:

```sh
acorn-tools interface-suggest --lib . --base upstream/master --head HEAD --json
acorn-tools interface-suggest --declaration number_theory.crt_list.satisfies_all_unique_mod_system_modulus --json
```

Response `data` shape:

```json
{
  "recommendations": [
    {
      "declaration": "number_theory.crt_list.satisfies_all_unique_mod_system_modulus",
      "action": "export",
      "interfaceFile": "src/number_theory/interface.ac",
      "reason": "Public theorem completes CRT-list uniqueness API.",
      "patch": "--- a/src/number_theory/interface.ac\n+++ b/src/number_theory/interface.ac\n..."
    }
  ]
}
```

Policy options:

- `--implementation-only`
- `--public-theorems-only`
- `--allow-definitions`
- `--forbid-new-imports`

## 32. Strict Replay Printer Regression Test

Purpose: proactively test strict replay stability for known sensitive syntax patterns.

Suggested CLI:

```sh
acorn-tools replay-regressions --lib . --acorn ./bin/acorn --json
acorn-tools replay-regressions --pattern parametrized-attribute-sugar --json
```

Response `data` shape:

```json
{
  "patterns": [
    {
      "id": "nested-parametrized-attribute-sugar",
      "status": "failed",
      "minimalExample": "FiniteSet.from_list[FiniteSet[A]](...)",
      "printedForm": "FiniteSet[A].from_list(...)",
      "recommendation": "Use fs_from_list[FiniteSet[A]] or a named helper."
    }
  ]
}
```

## 33. Quantified Bool Predicate Risk Detector

Purpose: flag `define`d Bool predicates that may be hard for proof search to unfold under quantifiers.

Suggested CLI:

```sh
acorn-tools bool-predicate-risk --lib . --file src/binomial.ac --json
acorn-tools bool-predicate-risk --lib . --base upstream/master --head HEAD --json
```

Response `data` shape:

```json
{
  "risks": [
    {
      "predicate": "vandermonde_summand_relation",
      "file": "src/binomial.ac",
      "line": 140,
      "risk": "quantified_define_unfolding",
      "contexts": ["forall(k: Nat) { predicate(k) }"],
      "suggestedRewrite": "Expose direct theorem clauses or avoid quantified defined Bool predicate in final theorem."
    }
  ]
}
```

## 34. Induction Strategy Suggester

Purpose: suggest induction variables, helper lemmas, and proof stages for recursive/Nat/List/FiniteSet statements.

Suggested CLI:

```sh
acorn-tools induction-suggest --statement-file theorem.acfrag --lib . --json
acorn-tools induction-suggest src/number_theory/crt_list.ac:satisfies_all_unique_mod_system_modulus --lib . --json
```

Response `data` shape:

```json
{
  "strategy": {
    "inductionVariable": "mods",
    "inductionKind": "list_induction",
    "baseCaseHints": ["empty system modulus is one"],
    "stepCaseHints": ["separate head congruence", "use tail induction hypothesis", "combine coprime moduli"],
    "helperLemmaSuggestions": ["cons_head_coprime_tail_system_modulus"]
  }
}
```

## 35. Term Orientation Advisor

Purpose: recommend useful statement orientation for rewrite and equality theorems.

Suggested CLI:

```sh
acorn-tools orientation --statement-file theorem.acfrag --lib . --json
acorn-tools orientation --lhs "complex_conj(a * b)" --rhs "complex_conj(a) * complex_conj(b)" --json
```

Response `data` shape:

```json
{
  "preferredOrientation": "lhs_to_rhs",
  "reason": "Left side has a compound expression headed by complex_conj over multiplication; right side is structurally simpler for rewriting.",
  "alternativeTheoremNames": ["complex_conj_mul", "mul_of_complex_conj"]
}
```

## 36. Library Map Generator

Purpose: produce a high-level map of modules, themes, definitions, theorem clusters, and import/export relationships.

Suggested CLI:

```sh
acorn-tools library-map --lib . --json --output build/acorn-tools/library-map.json
acorn-tools library-map --lib . --module number_theory --markdown
```

Response `data` shape:

```json
{
  "modules": [
    {
      "module": "number_theory.crt_list",
      "file": "src/number_theory/crt_list.ac",
      "themes": ["Chinese remainder theorem", "list systems", "modular congruence"],
      "mainDefinitions": ["system_modulus", "satisfies_all"],
      "coreTheorems": ["nat_crt_list", "satisfies_all_unique_mod_system_modulus"],
      "imports": ["number_theory.modular"],
      "downstream": ["number_theory.interface"]
    }
  ]
}
```

## 37. Acorn Statement Benchmarker

Purpose: run short timeout probes against candidate theorem statements to estimate proof difficulty and failure mode.

Suggested CLI:

```sh
acorn-tools bench-statement --lib . --file scratch/theorem.ac --timeouts 3,10,30 --json
acorn-tools bench-statement --lib . --statement-file theorem.acfrag --context src/foo.ac --json
```

Response `data` shape:

```json
{
  "probes": [
    { "timeoutSec": 3, "result": "timeout", "searches": 12 },
    { "timeoutSec": 10, "result": "failed", "classification": "missing_helper" },
    { "timeoutSec": 30, "result": "success", "certificatesGenerated": 1 }
  ],
  "recommendation": "prove with helper lemma first",
  "suggestedSplits": ["membership forward", "membership reverse"]
}
```

## 38. Proof Failure Classifier

Purpose: classify failed verification attempts and recommend retry/split/blocker routing.

Suggested CLI:

```sh
acorn-tools classify-failure logs/verify.log --json
acorn-tools classify-failure --artifact /artifacts/formalizer/foo/result-001 --json
```

Response `data` shape:

```json
{
  "classification": "missing_intermediate_lemma",
  "confidence": 0.81,
  "evidence": ["same goal repeated", "search timed out after expanding set membership", "no type errors"],
  "recommendedAction": "split_statement",
  "blockerArtifactNeeded": false,
  "suggestedNextLemmas": ["image_membership_forward", "image_membership_reverse"]
}
```

## 39. Handoff Theorem Inventory

Purpose: generate verifier-ready inventory of all added/modified declarations and how helpers support final theorems.

Suggested CLI:

```sh
acorn-tools handoff-inventory --lib . --base upstream/master --head HEAD --json
acorn-tools handoff-inventory --artifact /artifacts/formalizer/foo/result-001 --json
```

Response `data` shape:

```json
{
  "addedDeclarations": [
    {
      "kind": "theorem",
      "name": "dirichlet_convolve_assoc",
      "file": "src/number_theory/dirichlet_assoc.ac",
      "line": 700,
      "role": "final_theorem",
      "uses": ["right_left_pair_list_assoc_term_sums_eq"]
    }
  ],
  "modifiedDeclarations": [],
  "helperGraph": [
    { "helper": "right_left_pair_lists_unique", "usedBy": ["right_left_pair_list_assoc_term_sums_eq"] }
  ],
  "publicApiChanges": ["number_theory.interface.dirichlet_convolve_assoc"],
  "summaryMarkdown": "..."
}
```

## Recommended Build Order

Highest immediate return:

1. `parse` + `decls` + `normalize-signature`
2. `index build/query` + `search-signature`
3. `proof-patterns` + `snippets`
4. `verify-lane` + `downstream-checks`
5. `manifest-analyze` + `manifest-normalize` + `cert-validate`
6. `duplicate-check` + `helper-check` + `scope-scan`
7. `goal-dump` + `type-of` + `resolve`
8. `handoff-inventory` + `api-diff` + `interface-suggest`

These tools directly address the main agent bottlenecks observed in the campaign: theorem discovery, type argument mistakes, noisy certificate/manifest changes, late strict replay failures, duplicate lane work, weak artifacts, and verifier packaging burden.
