"""Validate the fuzzing verifier against the enumerated baseline.

Answers:
1. Which gamed patches does the enumerated V (classes A-D only) MISS?
2. Does the fuzzer CATCH those missed patches — and how many inputs to find escape?
3. Recovered recall: fuzzer vs enumerated on the full gamed set.

Run: python -m verifier.run_fuzz_validation
  or: python verifier/run_fuzz_validation.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verifier.traversal import _PATCHES, _V_EXPLOITS, _L_EXPLOITS, _run_in_sandbox
from verifier.fuzzer import generate_fuzz_corpus


def _enumerated_catches(patch_id: str, patch_data: dict) -> bool:
    """Does the enumerated V set (V1-V5, classes A-D) catch this patch?"""
    for eid, edata in _V_EXPLOITS.items():
        if _run_in_sandbox(edata["title"], edata["format"], patch_data["sanitize"]):
            return True
    return False


def _labeling_says_gamed(patch_id: str, patch_data: dict) -> bool:
    """Does the full L set (with E/F/G classes) flag this patch as gamed?"""
    for eid, edata in _L_EXPLOITS.items():
        if _run_in_sandbox(edata["title"], edata["format"], patch_data["sanitize"]):
            return True
    return False


def _fuzz_first_escape(patch_data: dict, corpus: dict[str, dict]) -> tuple[bool, int, str | None]:
    """Run fuzz corpus against a patch. Returns (caught, inputs_tried, first_escaping_title)."""
    for i, (fid, fdata) in enumerate(corpus.items(), 1):
        if _run_in_sandbox(fdata["title"], fdata["format"], patch_data["sanitize"]):
            return True, i, fdata["title"]
    return False, len(corpus), None


def main():
    print("=" * 70)
    print("FUZZING VERIFIER VALIDATION")
    print("=" * 70)

    # Step 1: Identify gamed patches (using full L set as ground truth)
    gamed_patches = {}
    genuine_patches = {}
    for pid, pdata in _PATCHES.items():
        if _labeling_says_gamed(pid, pdata):
            gamed_patches[pid] = pdata
        else:
            genuine_patches[pid] = pdata

    print(f"\nGround truth (L-set labels): {len(genuine_patches)} genuine, {len(gamed_patches)} gamed")

    # Step 2: Which gamed patches does enumerated V MISS?
    print(f"\n--- Enumerated V (classes A-D only) vs gamed patches ---")
    enum_caught = {}
    enum_missed = {}
    for pid, pdata in gamed_patches.items():
        if _enumerated_catches(pid, pdata):
            enum_caught[pid] = pdata
        else:
            enum_missed[pid] = pdata

    print(f"  Caught: {len(enum_caught)} / {len(gamed_patches)}")
    print(f"  Missed: {len(enum_missed)} / {len(gamed_patches)}")
    enum_recall = len(enum_caught) / len(gamed_patches) if gamed_patches else 0
    print(f"  Recall: {enum_recall:.1%}")

    if enum_missed:
        print(f"\n  Missed patches (leak only through non-V classes):")
        for pid, pdata in enum_missed.items():
            print(f"    {pid}: {pdata['rationale']}")

    # Step 3: Generate fuzz corpus
    print(f"\n--- Generating fuzz corpus ---")
    t0 = time.time()
    corpus = generate_fuzz_corpus()
    gen_time = time.time() - t0
    print(f"  Generated {len(corpus)} unique inputs in {gen_time:.2f}s")

    # Step 4: Fuzzer vs the MISSED patches
    print(f"\n--- Fuzzer vs enumerated-missed patches ---")
    fuzz_catches_missed = {}
    for pid, pdata in enum_missed.items():
        caught, n_tried, first_title = _fuzz_first_escape(pdata, corpus)
        status = "CAUGHT" if caught else "MISSED"
        fuzz_catches_missed[pid] = {"caught": caught, "inputs": n_tried, "title": first_title}
        title_display = repr(first_title)[:50] if first_title else "N/A"
        print(f"  {pid} ({pdata['rationale'][:40]}): {status} at input #{n_tried} — {title_display}")

    n_recovered = sum(1 for v in fuzz_catches_missed.values() if v["caught"])
    print(f"\n  Recovered: {n_recovered} / {len(enum_missed)} previously-missed patches")

    # Step 5: Fuzzer vs ALL gamed patches (full recall)
    print(f"\n--- Fuzzer vs ALL gamed patches ---")
    t0 = time.time()
    fuzz_all_results = {}
    for pid, pdata in gamed_patches.items():
        caught, n_tried, first_title = _fuzz_first_escape(pdata, corpus)
        fuzz_all_results[pid] = {"caught": caught, "inputs": n_tried, "title": first_title}

    fuzz_time = time.time() - t0
    fuzz_caught_count = sum(1 for v in fuzz_all_results.values() if v["caught"])
    fuzz_recall = fuzz_caught_count / len(gamed_patches) if gamed_patches else 0

    print(f"  Caught: {fuzz_caught_count} / {len(gamed_patches)}")
    print(f"  Recall: {fuzz_recall:.1%}")
    print(f"  Time: {fuzz_time:.2f}s")

    fuzz_missed = {pid: v for pid, v in fuzz_all_results.items() if not v["caught"]}
    if fuzz_missed:
        print(f"\n  Still missed by fuzzer:")
        for pid in fuzz_missed:
            print(f"    {pid}: {gamed_patches[pid]['rationale']}")

    # Step 6: False positives — does fuzzer flag any genuine patches?
    print(f"\n--- Fuzzer vs genuine patches (false positive check) ---")
    t0 = time.time()
    fps = []
    for pid, pdata in genuine_patches.items():
        caught, n_tried, first_title = _fuzz_first_escape(pdata, corpus)
        if caught:
            fps.append((pid, first_title))

    fp_time = time.time() - t0
    print(f"  False positives: {len(fps)} / {len(genuine_patches)}")
    print(f"  Time: {fp_time:.2f}s")
    if fps:
        for pid, title in fps:
            print(f"    FP: {pid} escaped by {repr(title)[:50]}")

    # Summary
    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Enumerated V recall:  {enum_recall:.1%} ({len(enum_caught)}/{len(gamed_patches)})")
    print(f"  Fuzzing V recall:     {fuzz_recall:.1%} ({fuzz_caught_count}/{len(gamed_patches)})")
    print(f"  Delta:                +{fuzz_recall - enum_recall:.1%}")
    print(f"  Previously missed:    {len(enum_missed)} patches")
    print(f"  Recovered by fuzzer:  {n_recovered}/{len(enum_missed)}")
    print(f"  Corpus size:          {len(corpus)} inputs")
    print(f"  False positives:      {len(fps)}")
    print(f"")
    print(f"  BLIND SPOT BOUNDARY: The fuzzer's primitive vocabulary.")
    print(f"  Coverage depends on: separators ({len(set(s for s in ['/', chr(92), '%2f', '%2F', '%5c', '%5C']))} variants),")
    print(f"  segments ({len(set(['..', '.', '...', '....', '%2e%2e', '%2E%2E']))+ 5} variants),")
    print(f"  absolute prefixes ({len(set(['/tmp/', 'C:'+chr(92), 'C:/', '/etc/']))+ 3} variants).")
    print(f"  If a traversal primitive is ABSENT from this vocabulary,")
    print(f"  the fuzzer cannot generate it. Examples of uncovered primitives:")
    print(f"    - OS-specific resource fork paths (macOS /.._namedfork)")
    print(f"    - Filesystem junction/symlink races (not title-string attacks)")
    print(f"    - Null-byte injection (\\x00) for C-based path resolvers")
    print(f"    - Novel Unicode normalization attacks (NFKC folding)")
    print(f"    - Application-level path indirection (title references a config)")

    # Save results
    out_dir = Path(__file__).resolve().parent.parent / "results"
    out_dir.mkdir(exist_ok=True)
    results = {
        "enumerated_recall": enum_recall,
        "fuzz_recall": fuzz_recall,
        "delta": fuzz_recall - enum_recall,
        "corpus_size": len(corpus),
        "enum_missed_patches": list(enum_missed.keys()),
        "fuzz_catches_missed": fuzz_catches_missed,
        "fuzz_all_results": {k: {"caught": v["caught"], "inputs": v["inputs"]} for k, v in fuzz_all_results.items()},
        "false_positives": [pid for pid, _ in fps],
        "genuine_count": len(genuine_patches),
        "gamed_count": len(gamed_patches),
    }
    with open(out_dir / "fuzz_validation_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n  Results saved to results/fuzz_validation_results.json")


if __name__ == "__main__":
    main()
