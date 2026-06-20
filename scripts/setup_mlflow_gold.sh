#!/usr/bin/env bash
# Generate gamed patch files for MLflow bounty_1 (CVE-2024-1558).
#
# Run on the GCP VM AFTER bountytasks submodule is checked out.
# Creates bountytasks/mlflow/gold_patches/ with two gamed handlers.py variants.
#
# Usage:
#   cd ~/Aegis
#   bash scripts/setup_mlflow_gold.sh [/path/to/bountytasks]

set -euo pipefail

BOUNTYTASKS="${1:-${AEGIS_BOUNTYTASKS:-$HOME/Aegis/bountybench/bountytasks}}"

exec python3 "$(dirname "$0")/setup_mlflow_gold.py" "$BOUNTYTASKS"
