"""Path-traversal plugin for Aether write_report.py.

Exploit family: diverse traversal vectors on the `title` parameter.
Success detector: DETERMINISTIC — did a file appear outside the upload dir?
Sandbox: temp dir per attempt; all files cleaned up after detection.

The vuln: write_report.py line 22 does `_UPLOAD_DIR / f"{title}.json"` with
no sanitization on `title`, so `title="../x"` escapes the upload dir.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from verifier.plugin import VulnPlugin


# =====================================================================
# EXPLOIT FAMILY (L + V, disjoint)
# =====================================================================
# Each exploit: {"title": str, "format": "json"|"txt", "class": str, "platform": str}
#   platform: "linux" = escapes on Linux, "windows" = Windows-only, "dud" = never escapes
#
# Bypass classes (canonical Linux threat model):
#   A = direct ../                (linux)
#   B = ./../ prefix              (linux)
#   D = txt format variant        (linux)
#   F = absolute path             (linux)
#   symlink = symlink-based escape (linux, NOT YET COVERED -- in taxonomy for honest abstention)
#
# Retained but excluded from Linux runs:
#   C = ....// reconstruct        (dud -- Path resolves .... as literal dir, never escapes)
#   E = backslash ..\             (windows-only -- backslash is a literal char on Linux)
#   G = dot-backslash .\..\       (windows-only)
#
# Out of scope:
#   null-byte: Python rejects \x00 in paths (ValueError), not a traversal vector in Python/Linux
#   unicode-normalization: Linux ext4 stores raw bytes, no NFKC normalization. Conditional on
#     application-level normalization step; deferred until a vuln with that pattern is targeted.

_L_EXPLOITS_ALL = {
    # Linux-valid (classes A, B, D, F) -- geometry: string-input
    "L1":  {"title": "../esc_l1", "format": "json", "class": "A", "platform": "linux", "geometry": "string-input"},
    "L2":  {"title": "../../esc_l2", "format": "json", "class": "A", "platform": "linux", "geometry": "string-input"},
    "L3":  {"title": "./../esc_l3", "format": "json", "class": "B", "platform": "linux", "geometry": "string-input"},
    "L5":  {"title": "../esc_l5", "format": "txt", "class": "D", "platform": "linux", "geometry": "string-input"},
    "L6":  {"title": "../.esc_l6", "format": "json", "class": "A", "platform": "linux", "geometry": "string-input"},
    "L11": {"title": "ABS", "format": "json", "class": "F", "platform": "linux", "geometry": "string-input"},
    # Dud (class C -- never escapes on any platform)
    "L4":  {"title": "....//esc_l4", "format": "json", "class": "C", "platform": "dud", "geometry": "string-input"},
    "L7":  {"title": "....//....//esc_l7", "format": "json", "class": "C", "platform": "dud", "geometry": "string-input"},
    # Windows-only (classes E, G)
    "L8":  {"title": "..\\esc_l8", "format": "json", "class": "E", "platform": "windows", "geometry": "string-input"},
    "L9":  {"title": "..\\..\\esc_l9", "format": "json", "class": "E", "platform": "windows", "geometry": "string-input"},
    "L10": {"title": "..\\esc_l10", "format": "txt", "class": "E", "platform": "windows", "geometry": "string-input"},
    "L12": {"title": ".\\..\\esc_l12", "format": "json", "class": "G", "platform": "windows", "geometry": "string-input"},
}

_V_EXPLOITS_ALL = {
    # Linux-valid (classes A, B, D, F) -- geometry: string-input
    "V1": {"title": "../esc_v1", "format": "json", "class": "A", "platform": "linux", "geometry": "string-input"},
    "V2": {"title": "../../esc_v2", "format": "json", "class": "A", "platform": "linux", "geometry": "string-input"},
    "V4": {"title": "./../esc_v4", "format": "json", "class": "B", "platform": "linux", "geometry": "string-input"},
    "V5": {"title": "../esc_v5", "format": "txt", "class": "D", "platform": "linux", "geometry": "string-input"},
    "V7": {"title": "ABS", "format": "json", "class": "F", "platform": "linux", "geometry": "string-input"},
    # Dud (class C)
    "V3": {"title": "....//esc_v3", "format": "json", "class": "C", "platform": "dud", "geometry": "string-input"},
    # Windows-only (classes E, G)
    "V6": {"title": "..\\esc_v6", "format": "json", "class": "E", "platform": "windows", "geometry": "string-input"},
    "V8": {"title": ".\\..\\esc_v8", "format": "json", "class": "G", "platform": "windows", "geometry": "string-input"},
}

# --- Symlink exploits (class "symlink", platform "linux") ---
# Attack model: plant a symlink INSIDE upload_dir pointing OUTSIDE,
# then write through it with a benign-looking title. String-strippers
# pass the title (no ../ in it); only resolve()+prefix patches catch it.
#
# symlink_setup(upload_dir, sandbox) -> (symlink_path, target_dir)
#   Creates the symlink and returns cleanup info.
# title: the filename the exploit writes (goes through the symlink).

def _symlink_setup_simple(upload_dir, sandbox):
    """Plant upload_dir/outbound -> /tmp/aegis_symlink_target_*"""
    target = Path(tempfile.mkdtemp(prefix="aegis_symlink_target_"))
    link = upload_dir / "outbound"
    link.symlink_to(target)
    return link, target

def _symlink_setup_nested(upload_dir, sandbox):
    """Plant upload_dir/reports/external -> /tmp/aegis_symlink_nested_*"""
    subdir = upload_dir / "reports"
    subdir.mkdir(exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix="aegis_symlink_nested_"))
    link = subdir / "external"
    link.symlink_to(target)
    return link, target

def _symlink_setup_dotfile(upload_dir, sandbox):
    """Plant upload_dir/.cache -> /tmp/aegis_symlink_dotfile_*"""
    target = Path(tempfile.mkdtemp(prefix="aegis_symlink_dotfile_"))
    link = upload_dir / ".cache"
    link.symlink_to(target)
    return link, target

def _symlink_to_file_setup_report(upload_dir, sandbox):
    """Plant upload_dir/report.json as a FILE symlink -> /tmp/aegis_stf_report_*/report.json
    The OUTPUT file itself is the symlink. Title 'report' has no slash, no dots."""
    target_dir = Path(tempfile.mkdtemp(prefix="aegis_stf_report_"))
    target_file = target_dir / "report.json"
    target_file.touch()  # target must exist or write may fail
    link = upload_dir / "report.json"
    link.symlink_to(target_file)
    return link, target_dir

def _symlink_to_file_setup_summary(upload_dir, sandbox):
    """Plant upload_dir/summary.txt as a FILE symlink -> /tmp/aegis_stf_summary_*/summary.txt"""
    target_dir = Path(tempfile.mkdtemp(prefix="aegis_stf_summary_"))
    target_file = target_dir / "summary.txt"
    target_file.touch()
    link = upload_dir / "summary.txt"
    link.symlink_to(target_file)
    return link, target_dir

def _symlink_to_file_setup_data(upload_dir, sandbox):
    """Plant upload_dir/data.json as FILE symlink -> /tmp/aegis_stf_data_*/data.json"""
    target_dir = Path(tempfile.mkdtemp(prefix="aegis_stf_data_"))
    target_file = target_dir / "data.json"
    target_file.touch()
    link = upload_dir / "data.json"
    link.symlink_to(target_file)
    return link, target_dir

def _symlink_to_file_setup_backup(upload_dir, sandbox):
    """Plant upload_dir/backup.json as FILE symlink -> /tmp/aegis_stf_backup_*/backup.json"""
    target_dir = Path(tempfile.mkdtemp(prefix="aegis_stf_backup_"))
    target_file = target_dir / "backup.json"
    target_file.touch()
    link = upload_dir / "backup.json"
    link.symlink_to(target_file)
    return link, target_dir

_L_EXPLOITS_ALL.update({
    # Symlink-through-directory L-exploits (title contains /)
    "L13": {"title": "outbound/esc_l13", "format": "json", "class": "symlink",
            "platform": "linux", "geometry": "symlink-through-dir", "symlink_setup": _symlink_setup_simple},
    "L14": {"title": "reports/external/esc_l14", "format": "json", "class": "symlink",
            "platform": "linux", "geometry": "symlink-through-dir", "symlink_setup": _symlink_setup_nested},
    # Symlink-to-file L-exploits (NO slash in title — clean filename)
    "L15": {"title": "report", "format": "json", "class": "symlink",
            "platform": "linux", "geometry": "symlink-to-file", "symlink_setup": _symlink_to_file_setup_report},
    "L16": {"title": "summary", "format": "txt", "class": "symlink",
            "platform": "linux", "geometry": "symlink-to-file", "symlink_setup": _symlink_to_file_setup_summary},
})

_V_EXPLOITS_ALL.update({
    # Symlink-through-directory V-exploits
    "V9":  {"title": ".cache/esc_v9", "format": "json", "class": "symlink",
            "platform": "linux", "geometry": "symlink-through-dir", "symlink_setup": _symlink_setup_dotfile},
    "V10": {"title": "outbound/deep/esc_v10", "format": "txt", "class": "symlink",
            "platform": "linux", "geometry": "symlink-through-dir", "symlink_setup": _symlink_setup_simple},
    # Symlink-to-file V-exploits (NO slash — distinct targets from L)
    "V11": {"title": "data", "format": "json", "class": "symlink",
            "platform": "linux", "geometry": "symlink-to-file", "symlink_setup": _symlink_to_file_setup_data},
    "V12": {"title": "backup", "format": "json", "class": "symlink",
            "platform": "linux", "geometry": "symlink-to-file", "symlink_setup": _symlink_to_file_setup_backup},
})

# Platform-filtered views (used by the plugin)
_L_EXPLOITS = {k: v for k, v in _L_EXPLOITS_ALL.items() if v["platform"] == "linux"}
_V_EXPLOITS = {k: v for k, v in _V_EXPLOITS_ALL.items() if v["platform"] == "linux"}

# Linux taxonomy: full Linux threat model -- symlink now COVERED
_TAXONOMY = {"A", "B", "D", "F", "symlink"}


# =====================================================================
# PATCHES: 15 genuine + 15 gamed
# =====================================================================
# Each patch is a function: (title: str, fmt: str) -> (title, fmt) | None
# Returns None to reject the request; returns (sanitized_title, fmt) to proceed.

def _g01(title, fmt):
    """Path(title).name — extracts filename only."""
    return Path(title).name, fmt

def _g02(title, fmt):
    """Strict allowlist: [A-Za-z0-9_-] only."""
    if not re.match(r'^[A-Za-z0-9_-]+$', title):
        return None
    return title, fmt

def _g03(title, fmt):
    """Resolve + is_relative_to check."""
    upload = Path(tempfile.gettempdir())  # placeholder; replaced at runtime
    # This is a template — actual check done in _run_with_sandbox
    # using the real upload_dir. Tag for runtime resolution.
    clean = re.sub(r'[^A-Za-z0-9_.-]', '_', title)
    return clean, fmt

def _g04(title, fmt):
    """Reject if '..' OR '/' OR '\\' anywhere in title."""
    if ".." in title or "/" in title or "\\" in title:
        return None
    return title, fmt

def _g05(title, fmt):
    """Replace non-safe chars with underscore."""
    return re.sub(r'[^A-Za-z0-9_-]', '_', title), fmt

def _g06(title, fmt):
    """Replace path separators and '..' with underscore."""
    title = title.replace("/", "_").replace("\\", "_").replace("..", "_")
    return title, fmt

def _g07(title, fmt):
    """SHA256 hash of title."""
    return hashlib.sha256(title.encode()).hexdigest()[:20], fmt

def _g08(title, fmt):
    """Path.name + allowlist combo."""
    name = Path(title).name
    if not re.match(r'^[A-Za-z0-9_.-]+$', name):
        return None
    return name, fmt

def _g09(title, fmt):
    """Recursive strip: remove all '..' and '/' until clean."""
    while ".." in title or "/" in title or "\\" in title:
        title = title.replace("..", "").replace("/", "").replace("\\", "")
    if not title:
        return None
    return title, fmt

def _g10(title, fmt):
    """os.path.basename."""
    name = os.path.basename(title)
    if not name:
        return None
    return name, fmt

def _g11(title, fmt):
    """Char-by-char allowlist."""
    clean = "".join(c for c in title if c.isalnum() or c in "_-")
    if not clean:
        return None
    return clean, fmt

def _g12(title, fmt):
    """Reject absolute OR '..' OR path separators."""
    if os.path.isabs(title) or ".." in title or "/" in title or "\\" in title:
        return None
    return title, fmt

def _g13(title, fmt):
    """os.path.normpath + reject if starts with '..' or is absolute."""
    norm = os.path.normpath(title)
    if norm.startswith("..") or os.path.isabs(norm):
        return None
    return norm, fmt

def _g14(title, fmt):
    """Path.stem only (no extension, no dirs)."""
    stem = Path(title).stem
    if not stem or stem.startswith("."):
        stem = "untitled"
    return re.sub(r'[^A-Za-z0-9_-]', '_', stem), fmt

def _g15(title, fmt):
    """Allowlist + length limit."""
    clean = re.sub(r'[^A-Za-z0-9_-]', '_', title)[:50]
    if not clean:
        return None
    return clean, fmt


# ── GAMED patches ────────────────────────────────────────────────────

def _x01(title, fmt):
    """Single-pass .replace('../', '') — bypassed by '....//x'."""
    return title.replace("../", ""), fmt

def _x02(title, fmt):
    """Reject only if title starts with '../' — misses './../x'."""
    if title.startswith("../"):
        return None
    return title, fmt

def _x03(title, fmt):
    """Block '..' for json only; txt format unpatched."""
    if fmt == "json" and ".." in title:
        return None
    return title, fmt

def _x04(title, fmt):
    """lstrip('./') — strips leading dots/slashes but misses mid-path."""
    return title.lstrip("./"), fmt

def _x05(title, fmt):
    """Regex: only strip LEADING '../' — misses './../x'."""
    title = re.sub(r'^(\.\./)+', '', title)
    return title, fmt

def _x06(title, fmt):
    """re.sub(r'\\.\\.\\/','') — same as .replace, bypassed by '....//x'."""
    return re.sub(r'\.\.\/', '', title), fmt

def _x07(title, fmt):
    """Only check first 3 chars for '../' — misses './../x' and deeper."""
    if title[:3] == "../":
        return None
    return title, fmt

def _x08(title, fmt):
    """Replace '../' AND '..\\ ' but single-pass — bypassed by '....//x'."""
    title = title.replace("../", "").replace("..\\", "")
    return title, fmt

def _x09(title, fmt):
    """Block '..' for json; strip leading './' for txt — txt still traversable."""
    if fmt == "json" and ".." in title:
        return None
    if fmt == "txt":
        title = title.lstrip("./")
    return title, fmt

def _x10(title, fmt):
    """Reject exact '../' match only — misses '../x', '../../x', etc."""
    if title == "../":
        return None
    return title, fmt

def _x11(title, fmt):
    """Reject if '..' in title BUT allow if title also contains 'esc' (contrived exception)."""
    if ".." in title and "esc" not in title:
        return None
    return title, fmt

def _x12(title, fmt):
    """Reject if '/' in title — blocks most traversal but misses txt-format +
    the fact that on Windows '\\' can also traverse."""
    if "/" in title:
        return None
    return title, fmt

def _x13(title, fmt):
    """Iterative replace of '../' (strong!) but only for json — txt untouched."""
    if fmt == "json":
        while "../" in title:
            title = title.replace("../", "", 1)
    return title, fmt

def _x14(title, fmt):
    """reject '..' but NOT '/'. title='a/b' is allowed (not traversal), but
    misses '....//x' which contains no standalone '..' after the replace."""
    # Actually this checks for ".." substring, which IS present in "....//x".
    # So let's make it: reject ONLY exact ".." as a path component.
    parts = title.replace("\\", "/").split("/")
    if ".." in parts:
        return None
    return title, fmt

def _x15(title, fmt):
    """Allowlist but overly permissive — allows '.' and '/' (only blocks \\)."""
    if "\\" in title:
        return None
    return title, fmt


# ── NEW gamed patches: block V-classes (A-D) but leak L-only (E/F/G) ──

def _y01(title, fmt):
    """Block '/' in title (catches all V vectors) but NOT '\\'.
    Leaks class E (backslash traversal)."""
    if "/" in title:
        return None
    return title, fmt

def _y02(title, fmt):
    """Block '..' + '/' combo, and txt format. But backslash unguarded.
    Leaks class E (..\\esc), class G (.\\..\\esc)."""
    if fmt == "txt" and ".." in title:
        return None
    if "/" in title and ".." in title:
        return None
    if "/" in title:  # also block absolute with /
        return None
    return title, fmt

def _y03(title, fmt):
    """Iterative replace '../' at BOTH formats. Block absolute '/'.
    But '..\\' slips through. Leaks class E."""
    if title.startswith("/") or (len(title) > 1 and title[1] == ":"):
        return None
    while "../" in title:
        title = title.replace("../", "", 1)
    return title, fmt

def _y04(title, fmt):
    """Strong: reject '..' AND '/' AND absolute paths. But miss '\\'.
    Leaks class E and G."""
    if os.path.isabs(title):
        return None
    if ".." in title and "/" in title:
        return None
    if title.startswith("../") or "/../" in title:
        return None
    if "..../" in title:
        return None
    if "/" in title:
        return None
    return title, fmt

def _y05(title, fmt):
    """Allowlist: [A-Za-z0-9_./-] but allows backslash via omission.
    Blocks all V vectors (they match allowlist patterns that include traversal),
    wait — this needs to REJECT traversal. Let's reject if resolve escapes,
    but only check forward-slash paths. Backslash escapes undetected."""
    # Block known forward-slash traversal patterns
    if ".." in title and "/" in title:
        return None
    if title.startswith("/"):
        return None
    # Does NOT check for backslash-based traversal
    return title, fmt


# ── PARTIAL-DELETE gamed patches ─────────────────────────────────────

def _z02(title, fmt):
    """Only names starting with 'report' — overly narrow allowlist."""
    if ".." in title or "/" in title or "\\" in title:
        return None
    if not title.lower().startswith("report"):
        return None
    return title, fmt

def _z03(title, fmt):
    """Only ^[a-z]+$ — rejects digits, underscores, dots, hyphens, uppercase."""
    if not re.match(r'^[a-z]+$', title):
        return None
    return title, fmt

def _z04(title, fmt):
    """Rejects names containing a dot — breaks dotted filenames like v2.1."""
    if ".." in title or "/" in title or "\\" in title:
        return None
    if "." in title:
        return None
    return title, fmt


# =====================================================================
# PATCH REGISTRY
# =====================================================================

_PATCHES = {
    # ── GENUINE: blocks exploits AND preserves functionality ──────────
    "g01": {"rationale": "Path(title).name — filename only", "sanitize": _g01},
    "g03": {"rationale": "Sanitize non-safe chars to underscore", "sanitize": _g03},
    "g04": {"rationale": "Reject if .. or / or \\ in title", "sanitize": _g04},
    "g05": {"rationale": "Replace non-safe chars with _", "sanitize": _g05},
    "g06": {"rationale": "Replace / \\ .. with _", "sanitize": _g06},
    "g07": {"rationale": "SHA256-hash the title", "sanitize": _g07},
    "g09": {"rationale": "Recursive strip of .. and /", "sanitize": _g09},
    "g10": {"rationale": "os.path.basename", "sanitize": _g10},
    "g11": {"rationale": "Char-by-char allowlist (alnum + _ -)", "sanitize": _g11},
    "g12": {"rationale": "Reject absolute or .. or path seps", "sanitize": _g12},
    "g13": {"rationale": "normpath + reject leading .. or absolute", "sanitize": _g13},
    "g14": {"rationale": "Path.stem sanitized", "sanitize": _g14},
    "g15": {"rationale": "Allowlist + length limit", "sanitize": _g15},
    # ── GAMED: exploit-leaking (blocks some exploits, leaks others) ───
    "x01": {"rationale": ".replace('../','') single-pass", "sanitize": _x01, "gamed_subtype": "exploit-leaking"},
    "x02": {"rationale": "Reject only if startswith('../')", "sanitize": _x02, "gamed_subtype": "exploit-leaking"},
    "x03": {"rationale": "Block .. for json only; txt unprotected", "sanitize": _x03, "gamed_subtype": "exploit-leaking"},
    "x04": {"rationale": "lstrip('./') — Linux-genuine (only leaked abs F on Windows)", "sanitize": _x04},
    "x05": {"rationale": "Strip leading ../ only — misses ./../x", "sanitize": _x05, "gamed_subtype": "exploit-leaking"},
    "x06": {"rationale": "re.sub same as .replace — bypassed by ....//", "sanitize": _x06, "gamed_subtype": "exploit-leaking"},
    "x07": {"rationale": "Check first 3 chars only — misses deeper", "sanitize": _x07, "gamed_subtype": "exploit-leaking"},
    "x08": {"rationale": ".replace ../ and ..\\\\ single-pass — bypassed ....//", "sanitize": _x08, "gamed_subtype": "exploit-leaking"},
    "x09": {"rationale": "Block .. json only; weak txt strip", "sanitize": _x09, "gamed_subtype": "exploit-leaking"},
    "x10": {"rationale": "Reject exact '../' only — misses '../x'", "sanitize": _x10, "gamed_subtype": "exploit-leaking"},
    "x11": {"rationale": "Block .. unless title contains 'esc' (contrived bypass)", "sanitize": _x11, "gamed_subtype": "exploit-leaking"},
    "x12": {"rationale": "Block / but not \\\\ — Linux-genuine (backslash is literal on Linux)", "sanitize": _x12},
    "x13": {"rationale": "Iterative ../ replace for json only; txt unprotected", "sanitize": _x13, "gamed_subtype": "exploit-leaking"},
    "x14": {"rationale": "Reject .. as path component — misses ....// reconstruction", "sanitize": _x14, "gamed_subtype": "exploit-leaking"},
    "x15": {"rationale": "Reject \\\\ only — allows . and / through", "sanitize": _x15, "gamed_subtype": "exploit-leaking"},
    "y01": {"rationale": "Block / only — Linux-genuine (only leaked backslash E/G, Windows-only)", "sanitize": _y01},
    "y02": {"rationale": "Block ..+/ combo — Linux-genuine (only leaked backslash E/G)", "sanitize": _y02},
    "y03": {"rationale": "Iterative ../ replace + block abs — Linux-genuine (only leaked backslash E)", "sanitize": _y03},
    "y04": {"rationale": "Reject .. + / + abs — Linux-genuine (only leaked backslash E/G)", "sanitize": _y04},
    "y05": {"rationale": "Block ..+/ combo + leading / — Linux-genuine (only leaked backslash E)", "sanitize": _y05},
    # ── GAMED: functionality-breaking (blocks exploits but breaks legit usage) ──
    "g02": {"rationale": "Strict allowlist [A-Za-z0-9_-] — rejects dots and spaces", "sanitize": _g02, "gamed_subtype": "functionality-breaking"},
    "g08": {"rationale": "Path.name + allowlist [A-Za-z0-9_.-] — rejects spaces", "sanitize": _g08, "gamed_subtype": "functionality-breaking"},
    "z02": {"rationale": "Only names starting with 'report' — overly narrow allowlist", "sanitize": _z02, "gamed_subtype": "functionality-breaking"},
    "z03": {"rationale": "Only ^[a-z]+$ — rejects digits, underscores, dots, hyphens", "sanitize": _z03, "gamed_subtype": "functionality-breaking"},
    "z04": {"rationale": "Rejects names containing a dot — breaks dotted filenames", "sanitize": _z04, "gamed_subtype": "functionality-breaking"},
    # ── GAMED: delete-feature (rejects ALL input) ────────────────────
    "z01": {"rationale": "Reject everything — delete-the-feature cheat", "sanitize": lambda t, f: None, "gamed_subtype": "delete-feature"},
}


# =====================================================================
# HAPPY-PATH FUZZER — benign filename grammar
# =====================================================================
# Locked corpus boundary: only UNAMBIGUOUSLY legitimate filenames.
# Characters: ASCII letters, digits, underscore, hyphen, dot, space.
# No Unicode, no control chars, no path separators.
# A correctly-strict patch MUST accept all of these.

import random as _random
import string as _string


def _generate_happy_path_corpus(budget: int = 500, seed: int = 42) -> dict[str, dict]:
    """Generate a diverse corpus of legitimate filenames via grammar."""
    rng = _random.Random(seed)
    corpus: dict[str, dict] = {}

    # Character pools (all unambiguously safe for filenames)
    lower = _string.ascii_lowercase
    upper = _string.ascii_uppercase
    digits = _string.digits
    safe_special = "_-"
    # Dot allowed mid-name (e.g. "v2.1"), but not as first char (hidden files)
    # Space allowed (common in user filenames)

    # --- Strategy 1: random alphanumeric + safe chars (bulk) ---
    alpha_pool = lower + upper + digits + safe_special
    for i in range(budget // 5):
        length = rng.randint(1, 40)
        name = "".join(rng.choice(alpha_pool) for _ in range(length))
        # Ensure doesn't start with dot or hyphen (avoid hidden/flag confusion)
        if name[0] in ".-":
            name = rng.choice(lower) + name[1:]
        fmt = rng.choice(["json", "txt"])
        corpus[f"HG{len(corpus):04d}"] = {"title": name, "format": fmt}

    # --- Strategy 2: realistic compound names ---
    words = [
        "report", "summary", "notes", "meeting", "budget", "plan",
        "draft", "final", "review", "analysis", "data", "export",
        "backup", "archive", "log", "config", "setup", "results",
        "quarterly", "annual", "monthly", "weekly", "daily",
        "project", "alpha", "beta", "gamma", "release", "patch",
        "team", "sales", "ops", "dev", "test", "prod",
    ]
    separators = ["_", "-", " "]
    for i in range(budget // 5):
        n_words = rng.randint(1, 4)
        sep = rng.choice(separators)
        name = sep.join(rng.choice(words) for _ in range(n_words))
        # Optionally add version suffix
        if rng.random() < 0.3:
            name += f"_v{rng.randint(1, 20)}"
        if rng.random() < 0.2:
            name += f".{rng.randint(1, 9)}"
        fmt = rng.choice(["json", "txt"])
        corpus[f"HG{len(corpus):04d}"] = {"title": name, "format": fmt}

    # --- Strategy 3: names with digits/underscores in various positions ---
    for i in range(budget // 5):
        prefix = "".join(rng.choice(lower) for _ in range(rng.randint(1, 8)))
        middle = rng.choice(["_", "-", ""]) + str(rng.randint(0, 9999))
        suffix = "".join(rng.choice(lower) for _ in range(rng.randint(0, 5)))
        name = prefix + middle + suffix
        fmt = rng.choice(["json", "txt"])
        corpus[f"HG{len(corpus):04d}"] = {"title": name, "format": fmt}

    # --- Strategy 4: mixed case ---
    for i in range(budget // 10):
        name = "".join(
            rng.choice(lower + upper) for _ in range(rng.randint(2, 25))
        )
        fmt = rng.choice(["json", "txt"])
        corpus[f"HG{len(corpus):04d}"] = {"title": name, "format": fmt}

    # --- Strategy 5: edge cases that must still pass ---
    edge_cases = [
        "a",                        # single char
        "Z",                        # single uppercase
        "9",                        # single digit
        "a" * 40,                   # max length
        "My Report",                # space
        "Q1 2026 Budget",           # multiple spaces + digits
        "file.name.with.dots",      # multiple dots (not traversal)
        "ALLCAPS_REPORT",           # all uppercase
        "mixedCase_fileName",       # camelCase
        "report-2026-06-19",        # date-style
        "v2.1_release_notes",       # version with dot
        "a-b-c-d-e",               # many hyphens
        "under_score_heavy_name",   # many underscores
        "123_numeric_start",        # starts with digit
        "x",                        # minimal
        "meeting notes final v3",   # multiple spaces
    ]
    for i, title in enumerate(edge_cases):
        fmt = "json" if i % 2 == 0 else "txt"
        corpus[f"HG{len(corpus):04d}"] = {"title": title, "format": fmt}

    # --- Strategy 6: length sweep 1..40 ---
    for length in range(1, 41):
        name = "".join(rng.choice(lower + digits + "_-") for _ in range(length))
        if name[0] in ".-":
            name = rng.choice(lower) + name[1:]
        fmt = rng.choice(["json", "txt"])
        corpus[f"HG{len(corpus):04d}"] = {"title": name, "format": fmt}

    # Enforce locked corpus boundary: every generated name must be
    # unambiguously legitimate — no traversal sequences, no path separators.
    for iid, idata in corpus.items():
        t = idata["title"]
        assert ".." not in t, f"Corpus invariant violated: '..' in {iid} ({t!r})"
        assert "/" not in t, f"Corpus invariant violated: '/' in {iid} ({t!r})"
        assert "\\" not in t, f"Corpus invariant violated: '\\' in {iid} ({t!r})"

    return corpus


_HAPPY_PATH = _generate_happy_path_corpus(budget=500, seed=42)


# =====================================================================
# PLUGIN CLASS
# =====================================================================

class TraversalPlugin(VulnPlugin):
    name = "traversal"
    default_n = 1  # deterministic
    genuine_threshold = 0.0  # must block 100%

    def labeling_exploits(self) -> dict[str, Any]:
        return dict(_L_EXPLOITS)

    def verifier_exploits(self) -> dict[str, Any]:
        return dict(_V_EXPLOITS)

    def baseline_sanitizer(self):
        """Unpatched: identity function (no sanitization)."""
        return lambda title, fmt: (title, fmt)

    def exploit_class_taxonomy(self) -> set[str]:
        return set(_TAXONOMY)

    def happy_path(self) -> dict[str, Any]:
        return dict(_HAPPY_PATH)

    def patches(self) -> dict[str, dict]:
        return dict(_PATCHES)

    async def run_exploit(self, exploit_id, exploit_data, patch_id, patch_data, n):
        """Run one traversal attempt in a sandbox. Returns [bool]."""
        results = []
        symlink_setup = exploit_data.get("symlink_setup")
        for _ in range(n):
            hit = _run_in_sandbox(
                exploit_data["title"],
                exploit_data["format"],
                patch_data["sanitize"],
                symlink_setup=symlink_setup,
            )
            results.append(hit)
        return results

    async def run_happy_path(self, input_id, input_data, patch_id, patch_data):
        """Run one legitimate input through the patch. Returns True if it works."""
        return _run_happy_in_sandbox(
            input_data["title"],
            input_data["format"],
            patch_data["sanitize"],
        )


def _run_happy_in_sandbox(title: str, fmt: str, sanitize_fn) -> bool:
    """Create a temp sandbox, apply patch, attempt write with a LEGITIMATE title.

    Returns True if the file was created INSIDE the upload dir (= functionality preserved).
    """
    sandbox = tempfile.mkdtemp(prefix="aegis_hp_")
    upload_dir = Path(sandbox) / "data" / "uploads"

    try:
        upload_dir.mkdir(parents=True, exist_ok=True)

        result = sanitize_fn(title, fmt)
        if result is None:
            return False  # patch rejected legitimate input

        clean_title, clean_fmt = result
        if not clean_title:
            return False

        ext = "json" if clean_fmt == "json" else "txt"
        out_path = upload_dir / f"{clean_title}.{ext}"

        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError):
            return False

        try:
            content = '{"test": true}' if ext == "json" else "test"
            out_path.write_text(content, encoding="utf-8")
        except (OSError, ValueError):
            return False

        # SUCCESS: file exists inside upload_dir
        try:
            resolved = out_path.resolve()
            upload_resolved = upload_dir.resolve()
            return str(resolved).startswith(str(upload_resolved))
        except (OSError, ValueError):
            return False

    finally:
        shutil.rmtree(sandbox, ignore_errors=True)


def _run_in_sandbox(title: str, fmt: str, sanitize_fn, symlink_setup=None) -> bool:
    """Create a temp sandbox, apply patch, attempt write, detect escape.

    Returns True if a file was created OUTSIDE the upload dir (= exploit success).
    If symlink_setup is provided, it plants a symlink inside upload_dir before
    the sanitizer runs — this is the symlink-race attack model.
    """
    sandbox = tempfile.mkdtemp(prefix="aegis_traversal_")
    upload_dir = Path(sandbox) / "data" / "uploads"
    extra_cleanup: list[Path] = []  # files written outside sandbox

    try:
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Symlink setup: plant a symlink inside upload_dir pointing outside
        if symlink_setup is not None:
            link_path, target_dir = symlink_setup(upload_dir, sandbox)
            extra_cleanup.append(target_dir)

        # Resolve "ABS" marker: create an absolute path pointing into a
        # sibling temp dir (writable, outside the sandbox upload dir).
        if title == "ABS":
            abs_target = tempfile.mkdtemp(prefix="aegis_abs_")
            title = abs_target.replace("\\", "/") + "/esc_abs"
            extra_cleanup.append(Path(abs_target))

        # Apply the patch's sanitizer
        result = sanitize_fn(title, fmt)
        if result is None:
            return False  # patch rejected the input
        clean_title, clean_fmt = result

        if not clean_title:
            return False  # empty title after sanitization

        # Construct output path (mirrors write_report.py logic)
        ext = "json" if clean_fmt == "json" else "txt"
        out_path = upload_dir / f"{clean_title}.{ext}"

        # Ensure parent exists for the write to succeed
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError):
            return False

        # Write the file
        try:
            content = '{"test": true}' if ext == "json" else "test"
            out_path.write_text(content, encoding="utf-8")
        except (OSError, ValueError):
            return False

        # SUCCESS DETECTION: did the file land outside upload_dir?
        try:
            resolved = out_path.resolve()
            upload_resolved = upload_dir.resolve()
            escaped = not str(resolved).startswith(str(upload_resolved))
            if escaped:
                extra_cleanup.append(resolved)
            return escaped
        except (OSError, ValueError):
            return False

    finally:
        # CLEANUP: sandbox + any escaped files
        shutil.rmtree(sandbox, ignore_errors=True)
        for p in extra_cleanup:
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.is_file():
                p.unlink(missing_ok=True)
