#!/bin/bash
set -euo pipefail
cd /home/ppeng/bountybench

pkill -9 -f 'lane_runner|lane_system_|workflows.runner' 2>/dev/null || true
sleep 2
docker rm -f $(docker ps -q) 2>/dev/null || true
rm -rf /tmp/lane_*.py /tmp/lane_*.json /tmp/lane_*.log /tmp/lane_runner_docker_sem 2>/dev/null || true
rm -f /tmp/experiment_checkpoint.json 2>/dev/null || true
find bountytasks -name "tmp_*" -type d -exec rm -rf {} + 2>/dev/null || true

for sys in langchain mlflow gradio bentoml vllm; do
    cb="bountytasks/$sys/codebase"
    if [ -d "$cb" ]; then
        (cd "$cb" && rm -f .git/index.lock .git/HEAD.lock 2>/dev/null; branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|.*/||'); git checkout --force "${branch:-main}" 2>/dev/null; git branch -D dev 2>/dev/null; git clean -fdx 2>/dev/null; git reflog expire --expire=now --all 2>/dev/null) || true
    fi
done

for sys in mlflow gradio; do
    (cd "bountytasks/$sys" && docker compose down --remove-orphans 2>/dev/null) || true
done

echo "=== Pre-baked images ==="
docker images bountyagent-langchain:latest --format '{{.Repository}}:{{.Tag}} {{.Size}}'
docker images bountyagent-vllm:latest --format '{{.Repository}}:{{.Tag}} {{.Size}}'

source .env
export OPENAI_API_KEY OPENAI_BASE_URL DEEPSEEK_API_KEY

echo ""
echo "=== LAUNCHING OVERNIGHT EXPERIMENT ==="
echo "Time: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

nohup python3 scripts/lane_runner.py --experiment > /tmp/overnight_experiment.log 2>&1 &
echo "PID=$!"
echo "Log: /tmp/overnight_experiment.log"
sleep 10
head -60 /tmp/overnight_experiment.log
