#!/usr/bin/env bash
set -euo pipefail

# FIFO watchdog:
# - Detects missing required containers in openclaw-fifo-job-system
# - Detects stale SQLite processing rows (older than threshold)
# - Auto-creates a deduplicated GitHub issue when anomalies are found

REPO="${REPO:-ZennAI-Japan/openclaw-mission-control}"
FIFO_PROJECT_DIR="${FIFO_PROJECT_DIR:-$HOME/.openclaw/workspace/projects/openclaw-fifo-job-system}"
DASHBOARD_FILE="${DASHBOARD_FILE:-$HOME/.openclaw/workspace/FIFO_QUEUE.md}"
STALE_MINUTES="${STALE_MINUTES:-30}"

required_services=(redis worker scheduler queue-sync)

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found" >&2
  exit 1
fi
if ! command -v gh >/dev/null 2>&1; then
  echo "gh not found" >&2
  exit 1
fi

collect_missing_services() {
  local running_services_raw
  running_services_raw="$(docker compose -f "$FIFO_PROJECT_DIR/docker-compose.yml" ps --services --status running 2>/dev/null || true)"

  local running_services=()
  while IFS= read -r svc; do
    [[ -z "$svc" ]] && continue
    running_services+=("$svc")
  done <<EOF
$running_services_raw
EOF

  local missing_services=()
  for req in "${required_services[@]}"; do
    local found=0
    for svc in "${running_services[@]}"; do
      if [[ "$svc" == "$req" ]]; then
        found=1
        break
      fi
    done
    if [[ "$found" -eq 0 ]]; then
      missing_services+=("$req")
    fi
  done

  if [[ ${#missing_services[@]} -gt 0 ]]; then
    (IFS=,; echo "${missing_services[*]}")
  else
    echo ""
  fi
}

missing_csv="$(collect_missing_services)"
if [[ -n "$missing_csv" ]]; then
  sleep 8
  missing_csv="$(collect_missing_services)"
fi
if [[ -z "$missing_csv" ]]; then
  missing_csv="none"
fi

incomplete_json="$(docker compose -f "$FIFO_PROJECT_DIR/docker-compose.yml" run --rm -v "$DASHBOARD_FILE:/workspace/FIFO_QUEUE.md" worker python list_incomplete.py --db /data/tasks.db --dashboard /workspace/FIFO_QUEUE.md 2>/dev/null || true)"

if [[ -z "$incomplete_json" ]]; then
  incomplete_json='{"sqlite_incomplete":[],"dashboard_incomplete":[],"sqlite_incomplete_count":0,"dashboard_incomplete_count":0,"error":"list_incomplete failed"}'
fi

analysis_json="$(python3 - <<'PY' "$incomplete_json" "$STALE_MINUTES"
import json, sys
from datetime import datetime, timezone, timedelta

raw = sys.argv[1]
stale_minutes = int(sys.argv[2])
now = datetime.now(timezone.utc)

try:
    data = json.loads(raw)
except Exception:
    print(json.dumps({"stale_processing_count": 0, "stale_task_ids": [], "parse_error": True}))
    raise SystemExit(0)

stale_ids = []
for t in data.get("sqlite_incomplete", []):
    if t.get("status") != "processing":
        continue
    updated = t.get("updated_at")
    if not updated:
        continue
    try:
        dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
    except Exception:
        continue
    if now - dt >= timedelta(minutes=stale_minutes):
        stale_ids.append(t.get("task_id", "unknown"))

print(json.dumps({
    "stale_processing_count": len(stale_ids),
    "stale_task_ids": stale_ids,
    "sqlite_incomplete_count": data.get("sqlite_incomplete_count", 0),
    "dashboard_incomplete_count": data.get("dashboard_incomplete_count", 0),
}, ensure_ascii=False))
PY
)"

stale_count="$(python3 - <<'PY' "$analysis_json"
import json,sys
print(json.loads(sys.argv[1]).get('stale_processing_count',0))
PY
)"
stale_ids_csv="$(python3 - <<'PY' "$analysis_json"
import json,sys
print(','.join(json.loads(sys.argv[1]).get('stale_task_ids',[])) or 'none')
PY
)"
if [[ "$missing_csv" == "none" && "$stale_count" == "0" ]]; then
  echo "fifo_watchdog: healthy"
  exit 0
fi

fingerprint="fifo-watchdog|missing=${missing_csv}|stale=${stale_ids_csv}"
title="bug(fifo-watchdog): 異常検知 ${fingerprint}"

existing="$(gh issue list --repo "$REPO" --state open --search "$fingerprint in:title" --json number --jq '.[0].number // empty')"
if [[ -n "$existing" ]]; then
  echo "fifo_watchdog: existing issue #$existing"
  exit 0
fi

body_template=$(cat <<'EOF'
## 自動検知（FIFO watchdog）

- fingerprint: `__FINGERPRINT__`
- missing services: `__MISSING__`
- stale processing count: `__STALE_COUNT__`
- stale task ids: `__STALE_IDS__`
- stale threshold minutes: `__STALE_MINUTES__`

## list_incomplete snapshot
```json
__INCOMPLETE_JSON__
```

## analysis snapshot
```json
__ANALYSIS_JSON__
```

## 推奨アクション
1. `docker compose -f __COMPOSE_FILE__ up -d --build`
2. `list_incomplete.py` で再確認
3. 再発する場合は worker の再claim/retry ロジック点検
EOF
)

body="${body_template//__FINGERPRINT__/$fingerprint}"
body="${body//__MISSING__/$missing_csv}"
body="${body//__STALE_COUNT__/$stale_count}"
body="${body//__STALE_IDS__/$stale_ids_csv}"
body="${body//__STALE_MINUTES__/$STALE_MINUTES}"
body="${body//__INCOMPLETE_JSON__/$incomplete_json}"
body="${body//__ANALYSIS_JSON__/$analysis_json}"
body="${body//__COMPOSE_FILE__/$FIFO_PROJECT_DIR\/docker-compose.yml}"

gh issue create --repo "$REPO" --title "$title" --label bug --body "$body" >/dev/null

echo "fifo_watchdog: issue created"
