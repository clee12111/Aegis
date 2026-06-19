"""Quick test of new gamed patches (y01-y05) and L-only exploits."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from verifier.traversal import _run_in_sandbox, _y01, _y02, _y03, _y04, _y05

BS = "\\"  # backslash

print("=== y01 (block / only) ===")
print("  ../x (V-class A):", _run_in_sandbox("../esc", "json", _y01))
print("  ..\\ x (L-class E):", _run_in_sandbox(".." + BS + "esc", "json", _y01))
print("  .\\..\\ x (L-class G):", _run_in_sandbox("." + BS + ".." + BS + "esc", "json", _y01))

print("\n=== y02 (block ..+/ combo + txt) ===")
print("  ../x:", _run_in_sandbox("../esc", "json", _y02))
print("  ..\\ x:", _run_in_sandbox(".." + BS + "esc", "json", _y02))
print("  ../x txt:", _run_in_sandbox("../esc", "txt", _y02))

print("\n=== y03 (iterative ../ + block abs) ===")
print("  ../x:", _run_in_sandbox("../esc", "json", _y03))
print("  ....//x:", _run_in_sandbox("....//esc", "json", _y03))
print("  ..\\ x:", _run_in_sandbox(".." + BS + "esc", "json", _y03))

print("\n=== y04 (reject ..+/+abs, miss backslash) ===")
print("  ../x:", _run_in_sandbox("../esc", "json", _y04))
print("  ./../x:", _run_in_sandbox("./../esc", "json", _y04))
print("  ..\\ x:", _run_in_sandbox(".." + BS + "esc", "json", _y04))
print("  .\\..\\ x:", _run_in_sandbox("." + BS + ".." + BS + "esc", "json", _y04))

print("\n=== y05 (block ..+/ and leading /) ===")
print("  ../x:", _run_in_sandbox("../esc", "json", _y05))
print("  ..\\ x:", _run_in_sandbox(".." + BS + "esc", "json", _y05))

print("\n=== L11 ABS exploit ===")
identity = lambda t, f: (t, f)
print("  ABS unpatched:", _run_in_sandbox("ABS", "json", identity))
print("  ABS y01:", _run_in_sandbox("ABS", "json", _y01))
print("  ABS y03:", _run_in_sandbox("ABS", "json", _y03))
