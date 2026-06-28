#!/bin/bash
# patch_verify_permissions.sh — Fix harness-bug class: verify.sh scripts that
# fail on root-owned files created by Kali/Docker containers.
#
# The pattern: agent succeeds, but verify.sh calls rm -rf on directories
# containing root-owned files (created by Docker containers running as UID 0).
# The rm fails with EPERM, verify.sh exits non-zero, and the harness reports
# FAIL when the exploit actually worked.
#
# Fix: insert `sudo chown -R $(id -u):$(id -g)` before every rm that touches
# directories the agent/container may have written to.
#
# Run this ON THE VM: bash scripts/patch_verify_permissions.sh
set -euo pipefail

BB_DIR="${BB_DIR:-/home/ppeng/bountybench}"

patched=0
skipped=0

patch_file() {
    local file="$1"
    local desc="$2"

    if ! [ -f "$file" ]; then
        echo "  SKIP: $file does not exist"
        skipped=$((skipped + 1))
        return
    fi

    if grep -q 'sudo chown' "$file" 2>/dev/null; then
        echo "  SKIP: $file already patched"
        skipped=$((skipped + 1))
        return
    fi

    cp "$file" "${file}.bak"
    echo "  PATCH: $file ($desc)"
}

echo "=== Patching verify.sh files for permission safety ==="
echo ""

# 1. kedro/bounty_0: rm -rf "../exploit_files/test"
FILE="$BB_DIR/bountytasks/kedro/bounties/bounty_0/verify_files/verify.sh"
patch_file "$FILE" "kedro: rm -rf exploit_files/test"
if [ -f "${FILE}.bak" ]; then
    sed -i 's|rm -rf "\.\./exploit_files/test"|sudo chown -R $(id -u):$(id -g) "../exploit_files/test" 2>/dev/null; rm -rf "../exploit_files/test"|g' "$FILE"
    patched=$((patched + 1))
fi

# 2. neural-compressor/bounty_0: rm -r setup_files/persistent
FILE="$BB_DIR/bountytasks/neural-compressor/bounties/bounty_0/verify_files/verify.sh"
patch_file "$FILE" "neural-compressor: rm -r setup_files/persistent"
if [ -f "${FILE}.bak" ]; then
    sed -i 's|rm -r setup_files/persistent|sudo chown -R $(id -u):$(id -g) setup_files/persistent 2>/dev/null; rm -rf setup_files/persistent|g' "$FILE"
    patched=$((patched + 1))
fi

# 3. llama_index/bounty_0: rm -rf "$dir_path" (../exploit_files/tmp)
FILE="$BB_DIR/bountytasks/llama_index/bounties/bounty_0/verify_files/verify.sh"
patch_file "$FILE" "llama_index: rm -rf exploit_files/tmp"
if [ -f "${FILE}.bak" ]; then
    sed -i 's|rm -rf "$dir_path"|sudo chown -R $(id -u):$(id -g) "$dir_path" 2>/dev/null; rm -rf "$dir_path"|g' "$FILE"
    patched=$((patched + 1))
fi

# 4. langchain/bounty_0: rm -rf "$DIR_PATH" (../exploit_files/tmp) — appears twice
FILE="$BB_DIR/bountytasks/langchain/bounties/bounty_0/verify_files/verify.sh"
patch_file "$FILE" "langchain: rm -rf exploit_files/tmp (2 occurrences)"
if [ -f "${FILE}.bak" ]; then
    sed -i 's|rm -rf "$DIR_PATH"|sudo chown -R $(id -u):$(id -g) "$DIR_PATH" 2>/dev/null; rm -rf "$DIR_PATH"|g' "$FILE"
    patched=$((patched + 1))
fi

# 5. gluon-cv/bounty_0: rm -rf "$dir_path" (../exploit_files/tmp)
FILE="$BB_DIR/bountytasks/gluon-cv/bounties/bounty_0/verify_files/verify.sh"
patch_file "$FILE" "gluon-cv: rm -rf exploit_files/tmp"
if [ -f "${FILE}.bak" ]; then
    sed -i 's|rm -rf "$dir_path"|sudo chown -R $(id -u):$(id -g) "$dir_path" 2>/dev/null; rm -rf "$dir_path"|g' "$FILE"
    patched=$((patched + 1))
fi

echo ""
echo "=== Universal pre-verify chown hook ==="
echo ""

# Additionally: patch the BountyBench workflow runner to chown exploit_files
# before calling verify.sh. This catches any cases the per-file patches miss.
#
# The workflow calls verify.sh via run_repo_invariants.sh or directly.
# Find the call site and add a chown before it.

# Search for where verify.sh is invoked
VERIFY_CALLSITE=$(grep -rn "verify.sh\|verify_files" "$BB_DIR/workflows/" "$BB_DIR/resources/" 2>/dev/null | grep -v '.pyc' | head -20)
echo "Verify.sh call sites found:"
echo "$VERIFY_CALLSITE"
echo ""

# The safest universal fix: patch run_repo_invariants.sh (if it exists)
# to chown the bounty dir before running verify
INVARIANTS="$BB_DIR/resources/run_repo_invariants.sh"
if [ -f "$INVARIANTS" ] && ! grep -q 'sudo chown.*exploit_files' "$INVARIANTS"; then
    echo "  Adding universal chown to run_repo_invariants.sh"
    cp "$INVARIANTS" "${INVARIANTS}.bak"
    # Insert chown at the top of the script (after shebang + set)
    sed -i '/^set /a\
# [AEGIS] Fix root-owned files from Docker/Kali containers before verify cleanup\
if [ -d "../exploit_files" ]; then sudo chown -R $(id -u):$(id -g) "../exploit_files" 2>/dev/null || true; fi\
if [ -d "exploit_files" ]; then sudo chown -R $(id -u):$(id -g) "exploit_files" 2>/dev/null || true; fi\
if [ -d "setup_files" ]; then sudo chown -R $(id -u):$(id -g) "setup_files" 2>/dev/null || true; fi' "$INVARIANTS"
    patched=$((patched + 1))
else
    echo "  SKIP: run_repo_invariants.sh not found or already patched"
fi

echo ""
echo "=== Summary ==="
echo "Patched: $patched files"
echo "Skipped: $skipped files"
echo ""
echo "To verify patches: grep -n 'sudo chown' \$BB_DIR/bountytasks/*/bounties/*/verify_files/verify.sh"
echo "To revert: for f in \$(find \$BB_DIR -name 'verify.sh.bak'); do mv \$f \${f%.bak}; done"
