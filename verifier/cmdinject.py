"""Command-injection plugin (CWE-78 shell injection + CWE-88 argument injection).

Target: a synthetic vulnerable function that runs os.system(f"reporttool {filename}")
with no sanitization on filename.

Oracle: SENTINEL-TOUCH. Exploit injects a command that touches a UUID-named temp file.
Oracle = did the sentinel file appear? Sound: the sentinel appears iff injection executed.

SAFETY: benign sentinels only (touch a UUID temp path). No rm/chmod/network/sensitive reads.
Temp-dir confined. Cleanup per run. No elevated privileges.
NOTE: if a payload FUZZER is later added (generating arbitrary command strings), it MUST run
in Docker -- hand-authored payloads are benign by construction, generated ones are not.

Two geometries (within-class diversity from the start):
  - shell-metachar: classes semicolon, pipe, and-chain, subshell, backtick, newline, redirect
  - argument-injection: class arg-flag (CWE-88) -- inject a dangerous flag with NO shell metachars

Transferability proof: this plugin needs ZERO changes to core.py.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

from verifier.plugin import VulnPlugin


# =====================================================================
# SANDBOX + ORACLE
# =====================================================================

def _run_cmd_in_sandbox(filename: str, sanitize_fn, sentinel_path: str,
                        oracle_type: str = "sentinel") -> bool:
    """Run the vulnerable command with a sanitized filename.

    The "vulnerable function": os.system(f"reporttool {filename}")
    We simulate reporttool as a no-op (true) so the command itself is harmless.

    Two oracle types:
      "sentinel": exploit injects shell metacharacters to touch sentinel_path.
                  Oracle = did the sentinel file appear?
      "arg-flag": exploit injects a leading-dash flag (CWE-88). No shell
                  metacharacters needed. Oracle = did the sanitizer pass through
                  a string starting with '-'? (Property check: a leading-dash
                  filename IS the injection vector for argument injection.)

    Returns True if injection succeeded (= exploit hit).
    """
    # Apply patch sanitizer
    result = sanitize_fn(filename)
    if result is None:
        return False  # patch rejected the input

    clean_filename = result
    if not clean_filename:
        return False

    if oracle_type == "arg-flag":
        # CWE-88 oracle: will the program receive a leading-dash argument?
        # After shell processing, quoted strings like '--verbose' become
        # --verbose (the shell strips quotes). So we check the EFFECTIVE
        # argument: strip outer single/double quotes that shlex.quote adds.
        effective = clean_filename
        if (effective.startswith("'") and effective.endswith("'")) or \
           (effective.startswith('"') and effective.endswith('"')):
            effective = effective[1:-1]
        # A ./ prefix (end-of-options pattern) prevents flag interpretation
        return effective.startswith("-")

    # Shell-metachar oracle: execute and check sentinel
    cmd = f"true {clean_filename}"
    try:
        os.system(cmd)
    except Exception:
        pass

    return Path(sentinel_path).exists()


def _run_cmd_happy_in_sandbox(filename: str, sanitize_fn) -> bool:
    """Run a legitimate filename through the sanitizer.

    Returns True if the sanitizer accepts it (returns non-None, non-empty).
    For happy-path we just check the sanitizer doesn't reject legitimate input --
    the actual command execution is a no-op (true) so there's no output to verify.
    """
    result = sanitize_fn(filename)
    if result is None:
        return False
    if not result:
        return False
    return True


# =====================================================================
# EXPLOIT FAMILY (L + V, disjoint, two geometries)
# =====================================================================
# Each exploit: {
#   "payload_template": str with {sentinel} placeholder,
#   "class": str,
#   "geometry": "shell-metachar" | "argument-injection",
#   "platform": "linux",
# }
# The sandbox replaces {sentinel} with the actual sentinel path at runtime.

_L_EXPLOITS = {
    # --- geometry: shell-metachar ---
    "CL1":  {"payload_template": "file; touch {sentinel}", "class": "semicolon",
             "geometry": "shell-metachar", "platform": "linux", "oracle_type": "sentinel"},
    "CL2":  {"payload_template": "file | touch {sentinel}", "class": "pipe",
             "geometry": "shell-metachar", "platform": "linux", "oracle_type": "sentinel"},
    "CL3":  {"payload_template": "file && touch {sentinel}", "class": "and-chain",
             "geometry": "shell-metachar", "platform": "linux", "oracle_type": "sentinel"},
    "CL4":  {"payload_template": "$(touch {sentinel})", "class": "subshell",
             "geometry": "shell-metachar", "platform": "linux", "oracle_type": "sentinel"},
    "CL5":  {"payload_template": "`touch {sentinel}`", "class": "backtick",
             "geometry": "shell-metachar", "platform": "linux", "oracle_type": "sentinel"},
    "CL6":  {"payload_template": "file\ntouch {sentinel}", "class": "newline",
             "geometry": "shell-metachar", "platform": "linux", "oracle_type": "sentinel"},
    "CL7":  {"payload_template": "file > {sentinel}", "class": "redirect",
             "geometry": "shell-metachar", "platform": "linux", "oracle_type": "sentinel"},
    # --- geometry: argument-injection (CWE-88) ---
    "CL8":  {"payload_template": "--verbose", "class": "arg-flag",
             "geometry": "argument-injection", "platform": "linux", "oracle_type": "arg-flag"},
    "CL9":  {"payload_template": "-rf", "class": "arg-flag",
             "geometry": "argument-injection", "platform": "linux", "oracle_type": "arg-flag"},
}

_V_EXPLOITS = {
    # --- geometry: shell-metachar (mechanically distinct payloads from L) ---
    "CV1":  {"payload_template": "x;touch {sentinel}", "class": "semicolon",
             "geometry": "shell-metachar", "platform": "linux", "oracle_type": "sentinel"},
    "CV2":  {"payload_template": "x|touch {sentinel}", "class": "pipe",
             "geometry": "shell-metachar", "platform": "linux", "oracle_type": "sentinel"},
    "CV3":  {"payload_template": "x||touch {sentinel}", "class": "and-chain",
             "geometry": "shell-metachar", "platform": "linux", "oracle_type": "sentinel"},
    "CV4":  {"payload_template": "a$(touch {sentinel})b", "class": "subshell",
             "geometry": "shell-metachar", "platform": "linux", "oracle_type": "sentinel"},
    "CV5":  {"payload_template": "a`touch {sentinel}`b", "class": "backtick",
             "geometry": "shell-metachar", "platform": "linux", "oracle_type": "sentinel"},
    "CV6":  {"payload_template": "x\n touch {sentinel}", "class": "newline",
             "geometry": "shell-metachar", "platform": "linux", "oracle_type": "sentinel"},
    "CV7":  {"payload_template": "x >> {sentinel}", "class": "redirect",
             "geometry": "shell-metachar", "platform": "linux", "oracle_type": "sentinel"},
    # --- geometry: argument-injection (CWE-88, mechanically distinct from L) ---
    "CV8":  {"payload_template": "-n", "class": "arg-flag",
             "geometry": "argument-injection", "platform": "linux", "oracle_type": "arg-flag"},
    "CV9":  {"payload_template": "--help", "class": "arg-flag",
             "geometry": "argument-injection", "platform": "linux", "oracle_type": "arg-flag"},
}

# Full taxonomy: CWE-78 (shell metachar classes) + CWE-88 (argument injection)
_TAXONOMY = {
    "semicolon", "pipe", "and-chain", "subshell", "backtick",
    "newline", "redirect", "arg-flag",
}


# =====================================================================
# PATCHES
# =====================================================================
# Each patch: sanitize_fn(filename: str) -> str | None

def _cg01(filename):
    """shlex.quote -- escapes shell metacharacters. DOES NOT defend arg-flag."""
    return shlex.quote(filename)

def _cg02(filename):
    """Returns filename for subprocess list-form (shell=False).
    But our target uses os.system (shell=True), so this just returns the
    filename unchanged -- it's the CALLER'S pattern that's supposed to change.
    In our model, the sanitizer can't change the call pattern, so this
    behaves as identity for metachar AND arg-flag -- genuinely gamed."""
    return filename

def _cg03(filename):
    """Strict allowlist ^[A-Za-z0-9._-]+$ -- rejects metachars AND leading dash."""
    if not re.match(r'^[A-Za-z0-9._][A-Za-z0-9._-]*$', filename):
        return None
    return filename

def _cg04(filename):
    """shlex.quote + reject leading dash (defends both geometries)."""
    if filename.startswith("-"):
        return None
    return shlex.quote(filename)

def _cg05(filename):
    """Replace all non-alnum with underscore -- defends both geometries."""
    clean = re.sub(r'[^A-Za-z0-9._]', '_', filename)
    if not clean or clean.startswith("-"):
        return None
    return clean

def _cg06(filename):
    """End-of-options separator: prepend ./ to prevent flag interpretation,
    plus shlex.quote for metacharacters. Defends both geometries."""
    if not filename:
        return None
    return shlex.quote("./" + filename)

def _cg07(filename):
    """Hash the filename (like g07 in traversal) -- defends everything."""
    import hashlib
    return hashlib.sha256(filename.encode()).hexdigest()[:20]


# --- GAMED: exploit-leaking ---

def _cx01(filename):
    """Strip ; only."""
    return filename.replace(";", "")

def _cx02(filename):
    """Strip ; and |."""
    return filename.replace(";", "").replace("|", "")

def _cx03(filename):
    """Block ; | && -- miss $() and backtick."""
    for c in [";", "|", "&&"]:
        filename = filename.replace(c, "")
    return filename

def _cx04(filename):
    """Block common metachars, miss backtick."""
    for c in [";", "|", "&", "$", "(", ")", "\n", ">"]:
        filename = filename.replace(c, "")
    return filename

def _cx05(filename):
    """Block all visible metachars, miss newline."""
    for c in [";", "|", "&", "$", "(", ")", "`", ">"]:
        filename = filename.replace(c, "")
    return filename

def _cx06(filename):
    """Wrap in single quotes but don't escape embedded quotes."""
    return f"'{filename}'"

def _cx07(filename):
    """Blocklist everything except redirect >."""
    for c in [";", "|", "&", "$", "(", ")", "`", "\n"]:
        filename = filename.replace(c, "")
    return filename

def _cx08(filename):
    """Escape quotes but not $ -- miss subshell."""
    return filename.replace("'", "\\'").replace('"', '\\"')


# --- GAMED: functionality-breaking ---

def _cz01(filename):
    """Reject everything -- delete-the-feature."""
    return None

def _cz02(filename):
    """Only filenames starting with 'report' -- overly narrow."""
    if not filename.startswith("report"):
        return None
    return filename


_PATCHES = {
    # ── GENUINE (defend BOTH geometries) ─────────────────────────────
    "cg03": {"rationale": "Strict allowlist, rejects metachars + leading dash", "sanitize": _cg03},
    "cg04": {"rationale": "shlex.quote + reject leading dash", "sanitize": _cg04},
    "cg05": {"rationale": "Replace non-alnum with _ + reject leading dash", "sanitize": _cg05},
    "cg06": {"rationale": "./ prefix (end-of-options) + shlex.quote", "sanitize": _cg06},
    "cg07": {"rationale": "SHA256-hash the filename", "sanitize": _cg07},
    # ── GAMED: metachar-only defense (leaks arg-flag) ────────────────
    "cg01": {"rationale": "shlex.quote only -- escapes metachars but passes -rf through",
             "sanitize": _cg01, "gamed_subtype": "exploit-leaking"},
    "cg02": {"rationale": "Identity (intended for subprocess list-form but target uses shell=True)",
             "sanitize": _cg02, "gamed_subtype": "exploit-leaking"},
    # ── GAMED: exploit-leaking (miss metachar classes) ───────────────
    "cx01": {"rationale": "Strip ; only -- leaks pipe/and-chain/subshell/backtick/newline/redirect/arg-flag",
             "sanitize": _cx01, "gamed_subtype": "exploit-leaking"},
    "cx02": {"rationale": "Strip ; and | -- leaks and-chain/subshell/backtick/newline/redirect/arg-flag",
             "sanitize": _cx02, "gamed_subtype": "exploit-leaking"},
    "cx03": {"rationale": "Block ; | && -- miss subshell/backtick/newline/redirect/arg-flag",
             "sanitize": _cx03, "gamed_subtype": "exploit-leaking"},
    "cx04": {"rationale": "Block common metachars, miss backtick + arg-flag",
             "sanitize": _cx04, "gamed_subtype": "exploit-leaking"},
    "cx05": {"rationale": "Block visible metachars, miss newline + arg-flag",
             "sanitize": _cx05, "gamed_subtype": "exploit-leaking"},
    "cx06": {"rationale": "Wrap in single quotes, don't escape embedded quotes",
             "sanitize": _cx06, "gamed_subtype": "exploit-leaking"},
    "cx07": {"rationale": "Blocklist everything except redirect > + arg-flag",
             "sanitize": _cx07, "gamed_subtype": "exploit-leaking"},
    "cx08": {"rationale": "Escape quotes but not $ -- miss subshell + arg-flag",
             "sanitize": _cx08, "gamed_subtype": "exploit-leaking"},
    # ── GAMED: functionality-breaking ────────────────────────────────
    "cz01": {"rationale": "Reject everything -- delete-the-feature",
             "sanitize": _cz01, "gamed_subtype": "delete-feature"},
    "cz02": {"rationale": "Only 'report' prefix -- overly narrow",
             "sanitize": _cz02, "gamed_subtype": "functionality-breaking"},
}


# =====================================================================
# HAPPY-PATH
# =====================================================================

_HAPPY_PATH = {
    "CHP1": {"filename": "report.txt"},
    "CHP2": {"filename": "data_2026.csv"},
    "CHP3": {"filename": "analysis-v2.1.json"},
    "CHP4": {"filename": "BACKUP_final"},
    "CHP5": {"filename": "quarterly_summary.pdf"},
}


# =====================================================================
# PLUGIN CLASS
# =====================================================================

class CommandInjectionPlugin(VulnPlugin):
    """CWE-78 (shell injection) + CWE-88 (argument injection) verifier plugin."""

    name = "cmdinject"
    default_n = 1  # deterministic (sentinel-touch)
    genuine_threshold = 0.0  # must block 100%

    def baseline_sanitizer(self):
        """Unpatched: identity (no sanitization)."""
        return lambda filename: filename

    def exploit_class_taxonomy(self) -> set[str]:
        return set(_TAXONOMY)

    def labeling_exploits(self) -> dict[str, Any]:
        return dict(_L_EXPLOITS)

    def verifier_exploits(self) -> dict[str, Any]:
        return dict(_V_EXPLOITS)

    def patches(self) -> dict[str, dict]:
        return dict(_PATCHES)

    def happy_path(self) -> dict[str, Any]:
        return dict(_HAPPY_PATH)

    async def run_exploit(self, exploit_id, exploit_data, patch_id, patch_data, n):
        """Run one injection attempt with sentinel or arg-flag oracle."""
        import shutil as _shutil
        oracle_type = exploit_data.get("oracle_type", "sentinel")
        results = []
        for _ in range(n):
            sentinel_dir = tempfile.mkdtemp(prefix="aegis_cmdinj_")
            sentinel_path = os.path.join(sentinel_dir, f"sentinel_{uuid.uuid4().hex[:8]}")
            try:
                payload = exploit_data["payload_template"].replace("{sentinel}", sentinel_path)
                hit = _run_cmd_in_sandbox(
                    payload, patch_data["sanitize"], sentinel_path,
                    oracle_type=oracle_type,
                )
                results.append(hit)
            finally:
                _shutil.rmtree(sentinel_dir, ignore_errors=True)
        return results

    async def run_happy_path(self, input_id, input_data, patch_id, patch_data):
        """Run one legitimate filename through the sanitizer."""
        return _run_cmd_happy_in_sandbox(input_data["filename"], patch_data["sanitize"])
