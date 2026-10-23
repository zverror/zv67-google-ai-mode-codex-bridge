#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
data_dir="${ZV67_DATA_DIR:-$HOME/Library/Application Support/ZV67}"
port="${ZV67_PORT:-18080}"
plist="$HOME/Library/LaunchAgents/com.zv67.gateway.plist"

echo "ZV67 install"
echo "  project:  $project_root"
echo "  data:     $data_dir"
echo "  port:     $port"

for tool in python3 uv npm; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "missing required tool: $tool" >&2
    exit 1
  fi
done

mkdir -p "$data_dir/logs"
chmod 700 "$data_dir"

cd "$project_root/backend"
if [[ ! -x .venv/bin/python ]]; then
  uv venv .venv
fi
uv pip install --python .venv/bin/python -e '.[dev]'

cd "$project_root/frontend"
npm install --no-audit --no-fund
npm run build

python3 - "$project_root" "$data_dir" "$port" "$plist" <<'PY'
import pathlib
import sys

root, data_dir, port, plist = sys.argv[1:5]
template = pathlib.Path(root, "packaging", "macos", "com.zv67.gateway.plist.template")
text = template.read_text(encoding="utf-8")
text = text.replace("__ROOT__", root).replace("__DATA_DIR__", data_dir).replace("__PORT__", port)
target = pathlib.Path(plist).expanduser()
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(text, encoding="utf-8")
PY

launchctl bootout "gui/$(id -u)/com.zv67.gateway" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$plist"
launchctl kickstart -k "gui/$(id -u)/com.zv67.gateway"

for _ in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:${port}/health" >/dev/null 2>&1; then
    echo "ZV67 is running: http://127.0.0.1:${port}/admin/"
    exit 0
  fi
  sleep 1
done

echo "service did not become healthy; see $data_dir/logs/zv67.err.log" >&2
exit 1

