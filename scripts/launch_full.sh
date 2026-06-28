#!/bin/bash
set -x
pkill -9 -f "lane_runner|workflows.runner" 2>/dev/null || true
sleep 2
docker ps -q | xargs -r docker rm -f 2>/dev/null || true
rm -rf /tmp/lane_*.py /tmp/lane_*.json /tmp/lane_*.log /tmp/lane_runner_docker_sem /tmp/experiment_checkpoint.json 2>/dev/null || true
find /home/ppeng/bountybench/bountytasks -name "tmp_*" -type d -exec rm -rf {} + 2>/dev/null || true

cd /home/ppeng/bountybench

for cb in bountytasks/*/codebase; do
    if [ -d "$cb/.git" ] || [ -f "$cb/.git" ]; then
        (cd "$cb" && rm -f .git/index.lock .git/HEAD.lock 2>/dev/null && \
         branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|.*/||') && \
         git checkout --force "${branch:-main}" 2>/dev/null && \
         git branch -D dev 2>/dev/null && \
         git clean -fdx 2>/dev/null) || true
    fi
done

for sys in mlflow gradio lunary LibreChat InvokeAI agentscope composio fastapi node pytorch-lightning; do
    if [ -d "bountytasks/$sys" ]; then
        (cd "bountytasks/$sys" && docker compose down --remove-orphans 2>/dev/null) || true
    fi
done

source .env
export OPENAI_API_KEY OPENAI_BASE_URL DEEPSEEK_API_KEY

echo "=== LAUNCHING FULL BENCHMARK ==="
date -u "+%Y-%m-%d %H:%M:%S UTC"
nohup python3 scripts/lane_runner.py --experiment > /tmp/full_benchmark.log 2>&1 &
echo "PID=$!"
sleep 12
head -60 /tmp/full_benchmark.log
