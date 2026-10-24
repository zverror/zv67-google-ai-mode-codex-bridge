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

if [[ "$(uname -s)" != Darwin ]]; then
  echo "This installer requires macOS (launchd). See docs/INSTALL.md." >&2
  exit 1
fi

for tool in uv node npm curl launchctl lsof; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "missing required tool: $tool" >&2
    exit 1
  fi
done

if ! node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit((major === 20 && minor >= 19) || (major === 22 && minor >= 12) || major > 22 ? 0 : 1)'; then
  echo "Node.js 20.19+ or 22.12+ is required; Node.js 24 is recommended." >&2
  exit 1
fi

if [[ ! "$port" =~ ^[0-9]+$ ]] || (( 10#$port < 1 || 10#$port > 65535 )); then
  echo "ZV67_PORT must be an integer between 1 and 65535." >&2
  exit 1
fi

service_pid="$(launchctl print "gui/$(id -u)/com.zv67.gateway" 2>/dev/null | awk '$1 == "pid" && $2 == "=" {print $3; exit}' || true)"
listeners="$(lsof -nP -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
for listener in $listeners; do
  if [[ -z "$service_pid" || "$listener" != "$service_pid" ]]; then
    echo "Port $port belongs to another process (PID $listener). Choose another ZV67_PORT." >&2
    exit 1
  fi
done

mkdir -p "$data_dir/logs"
chmod 700 "$data_dir"

cd "$project_root/backend"
if [[ ! -x .venv/bin/python ]]; then
  uv venv --python 3.12 .venv
fi
if ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
  echo "backend/.venv requires Python 3.12+. Recreate it with uv venv --python 3.12 backend/.venv." >&2
  exit 1
fi
uv pip install --python .venv/bin/python -e '.[dev]'

cd "$project_root/frontend"
npm ci --no-audit --no-fund
npm run build

"$project_root/backend/.venv/bin/python" - "$project_root" "$data_dir" "$port" "$plist" <<'PY'
import pathlib
import plistlib
import os
import sys

root, data_dir, port, plist = sys.argv[1:5]
template = pathlib.Path(root, "packaging", "macos", "com.zv67.gateway.plist.template")
values = {"__ROOT__": root, "__DATA_DIR__": data_dir, "__PORT__": port}


def substitute(value):
    if isinstance(value, str):
        for placeholder, replacement in values.items():
            value = value.replace(placeholder, replacement)
        return value
    if isinstance(value, list):
        return [substitute(item) for item in value]
    if isinstance(value, dict):
        return {key: substitute(item) for key, item in value.items()}
    return value


configuration = substitute(plistlib.loads(template.read_bytes()))
target = pathlib.Path(plist).expanduser()
target.parent.mkdir(parents=True, exist_ok=True)
previous_env = {}
if target.exists():
    previous_env = plistlib.loads(target.read_bytes()).get("EnvironmentVariables", {})
api_key = os.environ.get("ZV67_API_KEY", previous_env.get("ZV67_API_KEY", ""))
if api_key.strip():
    configuration["EnvironmentVariables"]["ZV67_API_KEY"] = api_key.strip()
target.touch(mode=0o600, exist_ok=True)
target.chmod(0o600)
with target.open("wb") as stream:
    plistlib.dump(configuration, stream, sort_keys=False)
PY

launchctl bootout "gui/$(id -u)/com.zv67.gateway" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$plist"
launchctl kickstart -k "gui/$(id -u)/com.zv67.gateway"

for _ in $(seq 1 30); do
  if curl --max-time 3 -fsS "http://127.0.0.1:${port}/health" |
    "$project_root/backend/.venv/bin/python" -c 'import json, sys; h=json.load(sys.stdin); sys.exit(0 if h.get("service") == "zv67" and h.get("status") == "ok" else 1)' >/dev/null 2>&1; then
    echo "ZV67 is running: http://127.0.0.1:${port}/admin/"
    exit 0
  fi
  sleep 1
done

echo "service did not become healthy; see $data_dir/logs/zv67.err.log" >&2
exit 1

