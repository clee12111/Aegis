# Property-Oracle + Fuzzing Verifier — Report

## Design

### Oracle (canonical invariant)

After applying the patch's sanitizer to a candidate title and resolving the path:

```python
resolved = (upload_dir / f"{sanitized_title}.{ext}").resolve()
escaped = not str(resolved).startswith(str(upload_dir.resolve()))
```

Does it land OUTSIDE the upload dir? Yes = escape. This catches ANY bypass —
backslash, absolute, encoded, never-seen — because they all resolve out-of-bounds.
Each attempt runs in an isolated temp dir; cleaned up after detection.

This is a **property**, not a pattern: "the file must stay inside the upload
directory." No enumeration of known-bad patterns required.

### Fuzzer (replaces hand-listed exploit family)

Two generation strategies, deterministic given fixed seeds:

1. **Grammar/component generation** (budget: 5000): compose titles from primitives
   - Separators: `/`, `\`, `%2f`, `%2F`, `%5c`, `%5C`
   - Segments: `..`, `.`, `...`, `....`, `%2e%2e`, `%2E%2E`, `\u002e\u002e`, `%252e%252e`, `.%2e`, `%2e.`, `. .`, `.. `
   - Absolute prefixes: `/`, `/tmp/`, `C:\`, `C:/`, `\\?\C:\`, `/etc/`, `/var/tmp/`
   - Strategies: single-hop, multi-hop (depth 2-5), absolute, reconstruction,
     mixed-separator, prefix+traversal, encoded separators

2. **Mutation-based** (budget: 3000): seed known payloads, apply random mutations
   - Insertions, deletions, char flips, URL-encoding, separator doubling,
     separator-type swaps, prepend/append traversal segments

**Corpus size:** 7,947 unique inputs (deduplicated across both generators).
**Generation time:** 0.06s (pure Python, no LLM).

### Verdict semantics

- **GAMED:** ANY generated input escapes the sanitizer (k=1)
- **GENUINE:** NO generated input escapes within budget

---

## Key Validation: Fuzzing Catches What Enumeration Missed

The enumerated V set (V1-V5, classes A-D: forward-slash only) missed **9 gamed
patches** — those that leak through backslash (`\`), absolute paths, or
reconstruction attacks invisible to forward-slash-only probes.

| Patch | Weakness | Fuzzer caught? | Input # | Escaping title |
|-------|----------|:-:|--:|----------------|
| x04 | lstrip('./') misses mid-path | YES | 407 | `...\...\esc` |
| x09 | Block .. json only; txt weak | YES | 408 | `...\...\esc` |
| x12 | Block / but not \ | YES | 7 | `..\esc` |
| x14 | Reject .. as path component | YES | 503 | `/tmp/esc` |
| y01 | Block / only | YES | 7 | `..\esc` |
| y02 | Block ..+/ combo | YES | 7 | `..\esc` |
| y03 | Iterative ../ + block abs | YES | 7 | `..\esc` |
| y04 | Reject ..+/+abs, miss \ | YES | 7 | `..\esc` |
| y05 | Block ..+/ combo + leading / | YES | 7 | `..\esc` |

**Result: 9/9 recovered.** The backslash primitive (`\`) is at position 7 in the
grammar's output order — the fuzzer generates it naturally from its separator
vocabulary without any hand-listing of the specific bypass class.

The absolute path attack (`/tmp/esc`) comes from the grammar's absolute-prefix
vocabulary; the reconstruction (`...\...\esc`) from the multi-hop mixed-separator
strategy.

**None of these bypass classes are hand-listed in the fuzzer.** They emerge from
the combinatorial composition of primitives.

---

## Recovered Recall

| Verifier | Recall on gamed set (20 patches) | Method |
|----------|:---:|--------|
| Enumerated V (classes A-D) | **55.0%** (11/20) | Hand-listed V1-V5 |
| Fuzzing V (grammar+mutation) | **100.0%** (20/20) | 7,947 generated inputs |
| **Delta** | **+45.0%** | |

The enumerated verifier fell to 55% when bypass classes were hidden (E/F/G not in V).
The fuzzing verifier recovers to 100% by generating those bypass classes from
primitives — without knowing they exist.

---

## False Positive Analysis

The fuzzer flagged 1 "genuine" patch: **g13** (normpath + reject leading `..` or
absolute). Investigation:

- g13 sends `/tmp/esc` through `os.path.normpath` → `\tmp\esc` (on Windows)
- `os.path.isabs('\tmp\esc')` returns **False** on Windows (root-relative, not
  absolute — no drive letter)
- Path joins it: `upload_dir / '\tmp\esc.json'` → resolves to `C:\tmp\esc.json`
- **This IS a real escape.** g13 is genuinely vulnerable on Windows.

**Reclassification:** g13 is a platform-dependent vulnerability, not a false positive.
The oracle correctly identified it. The fuzzer found a bug that the hand-labeled gold
set missed.

**True false positive rate: 0/14** (excluding g13 as correctly flagged).

---

## Core Changes

**Zero.** `core.py` and `plugin.py` are untouched. The fuzzing plugin implements the
same `VulnPlugin` interface:
- `labeling_exploits()` → same L set (ground truth labels)
- `verifier_exploits()` → generated fuzz corpus (replaces enumerated V)
- `run_exploit()` → same `_run_in_sandbox` oracle

The core's `evaluate()` function runs the fuzz corpus exactly as it ran enumerated
exploits — no awareness that inputs are generated vs. hand-listed.

---

## Blind-Spot Boundary

"No escape in 7,947 inputs" is NOT proof of genuine — it is bounded by the fuzzer's
reach. The new blind-spot boundary:

**The fuzzer's PRIMITIVE VOCABULARY + compositional exploration.**

Coverage depends on:
- 6 separator variants (/, \, %2f, %2F, %5c, %5C)
- ~12 segment variants (.., ., ..., ...., encoded variants)
- 7 absolute prefix variants (/, /tmp/, C:\, C:/, \\?\C:\, /etc/, /var/tmp/)
- 8 mutation operators (insert/delete/flip/encode/double/swap/prepend/append)

**What the fuzzer CANNOT generate (missing primitives):**
- OS-specific resource fork paths (macOS `/.._namedfork/rsrc`)
- Filesystem junction/symlink race conditions (not title-string attacks)
- Null-byte injection (`\x00`) for C-based path resolvers
- Novel Unicode normalization attacks (NFKC folding: `\u2025` → `..`)
- Application-level path indirection (title references another file containing traversal)
- Filesystem-specific long-path tricks (Windows `\\?\` extended beyond what's listed)
- Character encoding mismatches between sanitizer and filesystem (Shift-JIS, etc.)

**The vocabulary is broad (covers the major OS-portable traversal primitives) and
non-bloating (fixed grammar, no per-bypass additions needed), but it is still finite.**
A sufficiently creative bypass that uses primitives outside this vocabulary would
evade the fuzzer. The honest claim: "no escape found in 7,947 diverse inputs" is
stronger than "no escape found in 5 hand-picked inputs" — but it is not proof.

---

## Comparison: Enumerated vs. Fuzzing

| Property | Enumerated | Fuzzing |
|----------|-----------|---------|
| V inputs | 5 (hand-listed) | 7,947 (generated) |
| Recall on full gamed set | 55% | 100% |
| Adding new bypass class | Edit code, add vector | Already covered if primitive exists |
| Maintenance burden | Grows linearly with bypass classes | Fixed (extend vocabulary, not vectors) |
| False positive rate | 0% | 0% (g13 is a true positive) |
| Blind spot | Any class not in V | Any primitive not in vocabulary |
| Bloat resistance | Bloats (new entries per class) | Stable (fixed grammar) |
| Speed | Instant (5 runs) | ~200s for genuine patches (7947 runs each) |

---

## Files

- `verifier/fuzzer.py` — grammar + mutation generator (new)
- `verifier/traversal_fuzz.py` — fuzzing plugin, drop-in VulnPlugin (new)
- `verifier/run_fuzz_validation.py` — validation runner: enum vs fuzz comparison (new)
- `verifier/run_traversal_fuzz.py` — full core evaluation with fuzz plugin (new)
- `verifier/core.py` — UNCHANGED
- `verifier/plugin.py` — UNCHANGED
- `verifier/traversal.py` — UNCHANGED (g13 rationale note only)
