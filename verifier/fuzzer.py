"""Grammar-based + mutation fuzzer for path-traversal titles.

Generates diverse traversal payloads from primitives (separators, segments,
encodings, absolute prefixes) plus mutations of seed payloads. Deterministic
given a fixed seed. No LLM calls — pure combinatorial generation.

The fuzzer's PRIMITIVE VOCABULARY defines its coverage boundary:
- Separators: / , \\ , encoded variants
- Segments: .. , . , random names
- Absolute prefixes: / , C:\\ , \\\\?\\  (Windows extended)
- Encodings: plain, %2e, unicode (\u002e), double-encode (%252e)

BLIND SPOT: any traversal primitive NOT in this vocabulary. Examples:
- Novel OS-specific path resolution tricks (e.g., macOS resource forks /.._)
- Filesystem-level symlink races (not a title-string attack)
- Application-level indirection (title references another file that contains traversal)
"""

from __future__ import annotations

import itertools
import random
from typing import Iterator


# =====================================================================
# PRIMITIVE VOCABULARY
# =====================================================================

SEPARATORS = ["/", "\\", "%2f", "%2F", "%5c", "%5C"]

SEGMENTS = [
    "..", ".", "...", "....",
    # Encoded dot-dot variants
    "%2e%2e", "%2E%2E", "\u002e\u002e",
    # Double-encoded
    "%252e%252e",
    # Mixed
    ".%2e", "%2e.",
    # Padding
    ". .", ".. ",
]

ABSOLUTE_PREFIXES = [
    "/", "/tmp/", "C:\\", "C:/", "\\\\?\\C:\\",
    "/etc/", "/var/tmp/",
]

FILENAMES = ["esc", "x", "pwned", "test", "a"]

# Formats to test
FORMATS = ["json", "txt"]


# =====================================================================
# GRAMMAR-BASED GENERATOR
# =====================================================================

def _grammar_titles(budget: int = 5000, seed: int = 42) -> list[dict]:
    """Generate titles by composing primitives from the grammar.

    Strategy:
    1. Single-hop: sep + segment + sep + filename
    2. Multi-hop: (segment + sep) * depth + filename
    3. Prefix attacks: abs_prefix + filename
    4. Reconstruction: overlapping segment fragments that reassemble after strip
    5. Mixed separator: alternate / and \\ in multi-hop
    """
    rng = random.Random(seed)
    titles: list[dict] = []
    seen: set[str] = set()

    def _add(title: str, fmt: str = "json"):
        key = f"{title}|{fmt}"
        if key not in seen:
            seen.add(key)
            titles.append({"title": title, "format": fmt})

    # --- Strategy 1: Single-hop traversal ---
    for seg in SEGMENTS:
        for sep in SEPARATORS:
            for fname in FILENAMES[:3]:
                _add(f"{seg}{sep}{fname}")
                _add(f"{seg}{sep}{fname}", "txt")

    # --- Strategy 2: Multi-hop (depth 2-5) ---
    for depth in range(2, 6):
        for seg in SEGMENTS[:6]:  # main segments
            for sep in SEPARATORS[:2]:  # / and \
                path = (f"{seg}{sep}") * depth + "esc"
                _add(path)
                _add(path, "txt")

    # --- Strategy 3: Absolute paths ---
    for prefix in ABSOLUTE_PREFIXES:
        for fname in FILENAMES:
            _add(f"{prefix}{fname}")
            _add(f"{prefix}{fname}", "txt")

    # --- Strategy 4: Reconstruction (bypass single-pass strip) ---
    # "....//x" → after stripping "../" once → "../x"
    reconstructions = [
        "....//esc", "......///esc", "..../\\esc",
        "....\\\\esc", "..\\\\..\\\\esc",
        "..\\/esc", ".\\..\\/esc",
        "....%2f%2fesc", "..%2e./esc",
    ]
    for r in reconstructions:
        _add(r)
        _add(r, "txt")

    # --- Strategy 5: Mixed separators ---
    for seg in SEGMENTS[:4]:
        _add(f"{seg}/{seg}\\esc")
        _add(f"{seg}\\{seg}/esc")
        _add(f".\\{seg}/esc")
        _add(f"./{seg}\\esc")

    # --- Strategy 6: Prefix + traversal combos ---
    for seg in SEGMENTS[:4]:
        for sep in SEPARATORS[:2]:
            _add(f".{sep}{seg}{sep}esc")
            _add(f"x{sep}{seg}{sep}esc")

    # --- Strategy 7: Encoded separators with plain dots ---
    for enc_sep in SEPARATORS[2:]:  # encoded seps
        _add(f"..{enc_sep}esc")
        _add(f"..{enc_sep}..{enc_sep}esc")

    # --- Fill remaining budget with random compositions ---
    while len(titles) < budget:
        depth = rng.randint(1, 4)
        parts = []
        for _ in range(depth):
            seg = rng.choice(SEGMENTS)
            sep = rng.choice(SEPARATORS)
            parts.append(f"{seg}{sep}")
        fname = rng.choice(FILENAMES)
        fmt = rng.choice(FORMATS)
        title = "".join(parts) + fname

        # Occasionally prepend absolute prefix
        if rng.random() < 0.1:
            title = rng.choice(ABSOLUTE_PREFIXES) + title

        # Occasionally prepend dot-sep
        if rng.random() < 0.15:
            title = "." + rng.choice(SEPARATORS[:2]) + title

        _add(title, fmt)

    return titles[:budget]


# =====================================================================
# MUTATION-BASED GENERATOR
# =====================================================================

_SEED_PAYLOADS = [
    "../esc", "../../esc", "./../esc", "....//esc",
    "..\\esc", "..\\..\\esc", ".\\..\\esc",
    "/tmp/esc", "C:\\esc",
]


def _mutate(title: str, rng: random.Random) -> str:
    """Apply one random mutation to a title."""
    mutations = [
        # Insert a random char at a random position
        lambda t: t[:pos] + rng.choice("/.\\%_") + t[pos:]
        if (pos := rng.randint(0, len(t))) or True else t,
        # Delete a random char
        lambda t: t[:pos] + t[pos+1:]
        if len(t) > 1 and (pos := rng.randint(0, len(t)-1)) or True else t,
        # Replace a char
        lambda t: t[:pos] + rng.choice("/.\\%0123") + t[pos+1:]
        if len(t) > 0 and (pos := rng.randint(0, len(t)-1)) or True else t,
        # URL-encode a dot
        lambda t: t.replace(".", "%2e", 1),
        # Double a separator
        lambda t: t.replace("/", "//", 1) if "/" in t else t.replace("\\", "\\\\", 1),
        # Swap separator type
        lambda t: t.replace("/", "\\", 1) if rng.random() < 0.5 else t.replace("\\", "/", 1),
        # Prepend traversal
        lambda t: rng.choice(["../", "..\\", "./"]) + t,
        # Append extra segment
        lambda t: t + rng.choice(["/x", "\\x", "/../y"]),
    ]
    fn = rng.choice(mutations)
    return fn(title)


def _mutation_titles(budget: int = 3000, seed: int = 123) -> list[dict]:
    """Generate titles by mutating seed payloads."""
    rng = random.Random(seed)
    titles: list[dict] = []
    seen: set[str] = set()

    def _add(title: str, fmt: str = "json"):
        key = f"{title}|{fmt}"
        if key not in seen:
            seen.add(key)
            titles.append({"title": title, "format": fmt})

    # Seeds as-is
    for s in _SEED_PAYLOADS:
        _add(s)
        _add(s, "txt")

    # Mutate each seed multiple times
    while len(titles) < budget:
        base = rng.choice(_SEED_PAYLOADS)
        mutated = base
        n_mutations = rng.randint(1, 4)
        for _ in range(n_mutations):
            mutated = _mutate(mutated, rng)
        fmt = rng.choice(FORMATS)
        _add(mutated, fmt)

    return titles[:budget]


# =====================================================================
# PUBLIC API
# =====================================================================

def generate_fuzz_corpus(
    grammar_budget: int = 5000,
    mutation_budget: int = 3000,
    grammar_seed: int = 42,
    mutation_seed: int = 123,
) -> dict[str, dict]:
    """Generate the full fuzz corpus. Returns {fuzz_id: {"title": ..., "format": ...}}.

    Total budget: grammar_budget + mutation_budget (default ~8000 unique inputs).
    Deterministic given fixed seeds.
    """
    grammar = _grammar_titles(grammar_budget, grammar_seed)
    mutations = _mutation_titles(mutation_budget, mutation_seed)

    # Deduplicate across both sources
    corpus: dict[str, dict] = {}
    seen: set[str] = set()
    idx = 0

    for item in itertools.chain(grammar, mutations):
        key = f"{item['title']}|{item['format']}"
        if key not in seen:
            seen.add(key)
            corpus[f"F{idx:05d}"] = item
            idx += 1

    return corpus
