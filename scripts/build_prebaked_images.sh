#!/bin/bash
# Build pre-baked Kali images with system-level deps pre-installed.
# Each image runs the EXACT install_command from metadata.json at build time,
# minus the editable pip install (which needs the mounted codebase at runtime).
# This is byte-identical to what each run would produce — same versions, same paths.

set -euo pipefail

BB_DIR="${BB_DIR:-/home/ppeng/bountybench}"
BASE_IMAGE="cybench/bountyagent:latest"

echo "=== Building pre-baked Kali images ==="
echo "Base image: $BASE_IMAGE"
echo ""

# --- langchain: compile Python 3.9.6 from source (the ~300s cost) ---
# The full install_command from metadata.json:
#   cd libs/langchain && pip install -e . && cd - && \
#   wget Python-3.9.6.tgz && tar xzf && ./configure --enable-optimizations && \
#   make -j$(nproc) && make altinstall && ln -s ...
# Split: Python compilation goes in the image; pip install -e stays at runtime.
echo "--- langchain: pre-baking Python 3.9.6 ---"
cat > /tmp/Dockerfile.langchain << 'DEOF'
FROM cybench/bountyagent:latest
RUN wget -q https://www.python.org/ftp/python/3.9.6/Python-3.9.6.tgz && \
    tar xzf Python-3.9.6.tgz && \
    cd Python-3.9.6 && \
    ./configure --enable-optimizations --prefix=/opt/python/python3.9.6 && \
    make -j$(nproc) && \
    make altinstall && \
    ln -s /opt/python/python3.9.6/bin/python3.9 /usr/local/bin/python3.9.6 && \
    cd .. && \
    rm -rf Python-3.9.6.tgz Python-3.9.6
DEOF
docker build -f /tmp/Dockerfile.langchain -t bountyagent-langchain:latest /tmp/ 2>&1 | tail -5
echo "langchain image built: $(docker images bountyagent-langchain:latest --format '{{.Size}}')"
echo ""

# --- vllm: apt packages + non-editable pip deps ---
# The full install_command from metadata.json:
#   export SETUPTOOLS_SCM_PRETEND_VERSION=0.6.2 && export VLLM_TARGET_DEVICE=empty && \
#   apt-get update && apt-get install -y git build-essential cmake netcat-openbsd && \
#   pip install -e . && pip install pytest msgpack-numpy pytest-asyncio xformers==0.0.27.post2
# Split: apt packages + non-editable pip packages go in the image; pip install -e stays at runtime.
echo "--- vllm: pre-baking apt + pip deps ---"
cat > /tmp/Dockerfile.vllm << 'DEOF'
FROM cybench/bountyagent:latest
RUN apt-get update && \
    apt-get install -y git build-essential cmake netcat-openbsd && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
RUN pip install pytest msgpack-numpy pytest-asyncio "xformers==0.0.27.post2"
DEOF
docker build -f /tmp/Dockerfile.vllm -t bountyagent-vllm:latest /tmp/ 2>&1 | tail -5
echo "vllm image built: $(docker images bountyagent-vllm:latest --format '{{.Size}}')"
echo ""

echo "=== Pre-baked images ready ==="
docker images | grep bountyagent
