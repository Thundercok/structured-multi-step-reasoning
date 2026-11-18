#!/bin/zsh
set -eu
cd "$(dirname "$0")/../.."
export HF_HUB_OFFLINE=1 MLX_MAX_OPS_PER_BUFFER=10 MLX_MAX_MB_PER_BUFFER=512
R=audit/probe_adapters_20261118
for a in self human; do
  [[ -f $R/features_$a.npz ]] || .venv/bin/python -u $R/probe_adapters.py extract $a >> $R/extract_$a.log 2>&1
done
.venv/bin/python $R/probe_adapters.py fit > $R/fit.log 2>&1
echo done
