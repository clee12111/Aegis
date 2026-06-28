#!/usr/bin/env bash
# harness_preflight.sh — Blocks experiment launch unless all invariants hold.
set -euo pipefail

BB_DIR="${BB_DIR:-/home/ppeng/bountybench}"
EXPECTED_IMAGE_ID="sha256:600c21fcd37ab927705818b34ff481ee4a234061982ab5dea89ec5b23e72ac77"
MIN_DISK_GB=20
DEEPSEEK_URL="${OPENAI_BASE_URL:-https://api.deepseek.com}"
DEEPSEEK_KEY="${OPENAI_API_KEY:-}"

PASS=0
FAIL=0
WARN=0

pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  WARN: $1"; WARN=$((WARN + 1)); }

echo "============================================================"
echo "HARNESS PREFLIGHT — $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "============================================================"

echo ""
echo "--- 1. Disk space (>= ${MIN_DISK_GB} GB free) ---"
free_kb=$(df / --output=avail | tail -1 | tr -d ' ')
free_gb=$((free_kb / 1024 / 1024))
if [ "$free_gb" -ge "$MIN_DISK_GB" ]; then
    pass "Disk: ${free_gb} GB free"
else
    fail "Disk: only ${free_gb} GB free (need ${MIN_DISK_GB})"
fi

echo ""
echo "--- 2. No leaked containers ---"
kali_count=$(docker ps --filter "name=kali_env" -q 2>/dev/null | wc -l)
if [ "$kali_count" -eq 0 ]; then
    pass "No leaked Kali containers"
else
    fail "${kali_count} leaked Kali containers running"
fi

echo ""
echo "--- 3. Docker network shared_net ---"
if docker network inspect shared_net &>/dev/null; then
    pass "shared_net exists"
else
    echo "  Creating shared_net..."
    docker network create shared_net &>/dev/null && pass "shared_net created" || fail "Cannot create shared_net"
fi

echo ""
echo "--- 4. Git safe.directory for task codebases ---"
safe_dirs=$(git config --global --get-all safe.directory 2>/dev/null || true)
missing=0
for dir in "$BB_DIR"/bountytasks/*/codebase; do
    if [ -d "$dir" ]; then
        fullpath=$(readlink -f "$dir")
        if echo "$safe_dirs" | grep -qF "$fullpath"; then
            :
        else
            missing=$((missing + 1))
        fi
    fi
done
if [ "$missing" -eq 0 ]; then
    pass "All task codebases in safe.directory"
else
    fail "${missing} task codebases NOT in safe.directory"
fi

echo ""
echo "--- 5. Agent image ---"
image_arch=$(docker inspect cybench/bountyagent:latest --format '{{.Architecture}}' 2>/dev/null || echo "MISSING")
image_id=$(docker inspect cybench/bountyagent:latest --format '{{.Id}}' 2>/dev/null || echo "MISSING")
if [ "$image_arch" = "amd64" ]; then
    pass "Agent image architecture: amd64"
else
    fail "Agent image architecture: ${image_arch} (expected amd64)"
fi
if [ "$image_id" = "$EXPECTED_IMAGE_ID" ]; then
    pass "Agent image ID matches expected"
else
    warn "Agent image ID differs: ${image_id:0:30}..."
fi

echo ""
echo "--- 6. Pull override disabled ---"
if grep -q "images.pull" "$BB_DIR/resources/kali_env_resource.py" 2>/dev/null; then
    fail "images.pull() is still active"
else
    pass "Pull override disabled"
fi

echo ""
echo "--- 7. Debug print removed ---"
if grep -q "MAKE_REQUEST_DEBUG" "$BB_DIR/resources/model_resource/model_provider.py" 2>/dev/null; then
    warn "Debug print still present"
else
    pass "No debug print in model_provider.py"
fi

echo ""
echo "--- 8. DeepSeek API endpoint ---"
if [ -z "$DEEPSEEK_KEY" ]; then
    fail "OPENAI_API_KEY not set"
else
    response=$(curl -s -w "\n%{http_code}" -X POST "${DEEPSEEK_URL}/chat/completions" \
        -H "Authorization: Bearer ${DEEPSEEK_KEY}" \
        -H "Content-Type: application/json" \
        -d '{"model":"deepseek-chat","messages":[{"role":"user","content":"hi"}],"max_tokens":1}' \
        --max-time 15 2>/dev/null || echo -e "\n000")
    http_code=$(echo "$response" | tail -1)
    if [ "$http_code" = "200" ]; then
        pass "DeepSeek endpoint responds (HTTP 200)"
    else
        fail "DeepSeek endpoint returned HTTP ${http_code}"
    fi
fi

echo ""
echo "--- 9. Harness patches intact ---"
cd "$BB_DIR"
mod_count=$(git diff --name-only 2>/dev/null | wc -l)
if [ "$mod_count" -ge 8 ]; then
    pass "Harness patches present (${mod_count} modified files)"
else
    fail "Only ${mod_count} modified files (expected ~9)"
fi

echo ""
echo "--- 10. Preflight script integrity ---"
# Compare this script's checksum against the repo copy (if accessible)
REPO_PREFLIGHT="${REPO_PREFLIGHT_PATH:-}"
if [ -n "$REPO_PREFLIGHT" ] && [ -f "$REPO_PREFLIGHT" ]; then
    vm_hash=$(sha256sum "$BB_DIR/harness_preflight.sh" 2>/dev/null | cut -c1-16)
    repo_hash=$(sha256sum "$REPO_PREFLIGHT" 2>/dev/null | cut -c1-16)
    if [ "$vm_hash" = "$repo_hash" ]; then
        pass "Preflight script matches repo copy"
    else
        warn "Preflight script differs from repo (vm=${vm_hash} repo=${repo_hash})"
    fi
else
    # Fallback: check against embedded hash (updated at deploy time)
    EXPECTED_PREFLIGHT_HASH="${EXPECTED_PREFLIGHT_HASH:-skip}"
    if [ "$EXPECTED_PREFLIGHT_HASH" = "skip" ]; then
        pass "Preflight script integrity (no reference hash set)"
    else
        vm_hash=$(sha256sum "$BB_DIR/harness_preflight.sh" 2>/dev/null | cut -c1-16)
        if [ "$vm_hash" = "$EXPECTED_PREFLIGHT_HASH" ]; then
            pass "Preflight script matches expected hash"
        else
            warn "Preflight script hash mismatch (vm=${vm_hash} expected=${EXPECTED_PREFLIGHT_HASH})"
        fi
    fi
fi

echo ""
echo "--- 11. Clean tmp state ---"
tmp_count=$(find "$BB_DIR/bountytasks" -name "tmp_*" -type d 2>/dev/null | wc -l)
if [ "$tmp_count" -eq 0 ]; then
    pass "No leftover tmp_* directories"
else
    warn "${tmp_count} leftover tmp_* directories"
fi

echo ""
echo "============================================================"
echo "ENVIRONMENT FINGERPRINT"
echo "============================================================"
fp_image_id="$image_id"
fp_patch_hash=$(cd "$BB_DIR" && git diff 2>/dev/null | sha256sum | cut -c1-16)
fp_subtask_hash=$(cd "$BB_DIR/bountytasks" && git diff 2>/dev/null | sha256sum | cut -c1-16)
fp_container_list=$(docker ps --format '{{.Names}}' 2>/dev/null | sort | sha256sum | cut -c1-16)
fp_disk_gb="$free_gb"
fp_timestamp=$(date -u '+%Y-%m-%dT%H:%M:%SZ')

fingerprint="${fp_image_id:7:12}|${fp_patch_hash}|${fp_subtask_hash}|${fp_container_list}|${fp_disk_gb}GB|${fp_timestamp}"
echo "  $fingerprint"
echo ""
echo "  Components:"
echo "    image_id:       ${fp_image_id:0:30}..."
echo "    patch_hash:     ${fp_patch_hash}"
echo "    subtask_hash:   ${fp_subtask_hash}"
echo "    container_hash: ${fp_container_list}"
echo "    free_disk:      ${fp_disk_gb} GB"
echo "    timestamp:      ${fp_timestamp}"

echo ""
echo "============================================================"
total=$((PASS + FAIL + WARN))
echo "RESULT: ${PASS} pass, ${FAIL} fail, ${WARN} warn (${total} checks)"
if [ "$FAIL" -gt 0 ]; then
    echo "VERDICT: BLOCKED — fix ${FAIL} failure(s) before running experiment"
    echo "============================================================"
    exit 1
else
    if [ "$WARN" -gt 0 ]; then
        echo "VERDICT: PROCEED WITH CAUTION — ${WARN} warning(s)"
    else
        echo "VERDICT: ALL CLEAR"
    fi
    echo "============================================================"
    exit 0
fi
