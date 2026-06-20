"""Linux recon: run on the GCP VM to survey exploit behavior on Linux."""
import platform
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from verifier.traversal import (
    _V_EXPLOITS, _L_EXPLOITS, _TAXONOMY, _PATCHES,
    _run_in_sandbox,
)

print(f"Platform: {platform.system()}")
assert platform.system() == "Linux", "This script must run on Linux"

identity = lambda t, f: (t, f)

# --- 2. Exploit behavior on Linux ---
print("\n=== EXPLOIT BEHAVIOR ON LINUX (unpatched baseline) ===")
header = f"{'ID':<5} {'Class':<6} {'Payload':<35} Escaped"
print(header)
print("-" * len(header))

linux_results = {}
for eid in sorted(list(_L_EXPLOITS.keys()) + list(_V_EXPLOITS.keys())):
    edata = _L_EXPLOITS.get(eid) or _V_EXPLOITS.get(eid)
    hit = _run_in_sandbox(edata["title"], edata["format"], identity)
    cls = edata["class"]
    linux_results[eid] = {"class": cls, "escaped": hit}
    print(f"{eid:<5} {cls:<6} {edata['title']!r:<35} {hit}")

# --- 3. Which classes are Linux-valid ---
print("\n=== LINUX-VALID CLASSES ===")
classes_that_escape = set()
classes_that_dont = set()
for eid, info in linux_results.items():
    if info["escaped"]:
        classes_that_escape.add(info["class"])
    else:
        classes_that_dont.add(info["class"])

# A class is linux-valid if ANY exploit of that class escapes
for cls in sorted(_TAXONOMY):
    valid = cls in classes_that_escape
    print(f"  Class {cls}: {'LINUX-VALID' if valid else 'WINDOWS-ONLY'}")

# --- 4. Gold-set labels under Linux ---
print("\n=== GOLD-SET LABELS UNDER LINUX ===")
# Collect linux-valid exploits (from both L and V)
linux_valid_exploits = {}
for eid in sorted(list(_L_EXPLOITS.keys()) + list(_V_EXPLOITS.keys())):
    edata = _L_EXPLOITS.get(eid) or _V_EXPLOITS.get(eid)
    if linux_results[eid]["escaped"]:
        linux_valid_exploits[eid] = edata

print(f"Linux-valid exploits: {sorted(linux_valid_exploits.keys())}")
print()

header2 = f"{'PID':<5} {'Any Linux escape':<18} {'Escaping exploits'}"
print(header2)
print("-" * 70)

former_fns = {"x04", "x09", "x12", "x14", "y01", "y02", "y03", "y04", "y05"}

for pid in sorted(_PATCHES.keys()):
    pdata = _PATCHES[pid]
    escaping = []
    for eid, edata in linux_valid_exploits.items():
        hit = _run_in_sandbox(edata["title"], edata["format"], pdata["sanitize"])
        if hit:
            escaping.append(f"{eid}({edata['class']})")
    any_escape = len(escaping) > 0
    marker = " <-- former-FN" if pid in former_fns else ""
    print(f"{pid:<5} {str(any_escape):<18} {', '.join(escaping) if escaping else 'none'}{marker}")
