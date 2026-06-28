#!/bin/bash
# Launch diagnostic sweep: decontaminated baseline for failure classification.
#
# Steps:
# 1. Patch vulnerable verify.sh files (harness-bug fix)
# 2. Clean state
# 3. Run 24 tasks (22 non-Docker + 2 Docker), bare, 1 attempt, detect+exploit
#
# Run ON THE VM:
#   cd /home/ppeng/bountybench
#   bash /path/to/Aegis/scripts/launch_diagnostic.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BB_DIR="/home/ppeng/bountybench"

cd "$BB_DIR"

# 1. Patch verify.sh harness bugs
echo "=== Step 1: Patch verify.sh permissions ==="
bash "$SCRIPT_DIR/patch_verify_permissions.sh"
echo ""

# 2. Clean state
echo "=== Step 2: Clean state ==="
pkill -9 -f 'lane_runner|lane_system_|workflows.runner' 2>/dev/null || true
sleep 2
docker rm -f $(docker ps -q) 2>/dev/null || true
rm -rf /tmp/lane_*.py /tmp/lane_*.json /tmp/lane_*.log /tmp/lane_runner_docker_sem 2>/dev/null || true
rm -f /tmp/experiment_checkpoint.json 2>/dev/null || true

# Fix ownership globally
sudo chown -R $(id -u):$(id -g) bountytasks/ 2>/dev/null || true

# Reset codebases for systems we'll use
for sys in astropy bentoml curl django gluon-cv gpt_academic gunicorn imaginairy kedro langchain llama_index neural-compressor open-webui paddle parse-url scikit-learn setuptools undici vllm yaml zipp composio agentscope; do
    cb="bountytasks/$sys/codebase"
    if [ -d "$cb" ]; then
        (cd "$cb" && \
         rm -f .git/index.lock .git/HEAD.lock 2>/dev/null; \
         branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|.*/||') ; \
         git checkout --force "${branch:-main}" 2>/dev/null; \
         git branch -D dev 2>/dev/null; \
         git clean -fdx 2>/dev/null; \
         git reflog expire --expire=now --all 2>/dev/null) || true
    fi
done

# Docker cleanup for composio and agentscope
for sys in composio agentscope; do
    (cd "bountytasks/$sys" && docker compose down --remove-orphans 2>/dev/null) || true
done

# Clean tmp dirs
find bountytasks -name "tmp_*" -type d -exec rm -rf {} + 2>/dev/null || true

echo "State clean."
echo ""

# 3. Source env and launch
source .env
export OPENAI_API_KEY OPENAI_BASE_URL DEEPSEEK_API_KEY

echo "=== Step 3: Launch diagnostic sweep ==="
echo "Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Tasks: 24 (22 non-Docker + 2 Docker)"
echo "Arms: bare@15"
echo "Phases: detect, exploit"
echo "Attempts: 1"
echo ""

nohup python3 scripts/lane_runner.py --experiment > /tmp/diagnostic_sweep.log 2>&1 &
echo "PID=$!"
echo "Log: /tmp/diagnostic_sweep.log"
echo ""
sleep 10
head -60 /tmp/diagnostic_sweep.log
