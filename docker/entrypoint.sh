#!/bin/bash
# Start the analysis API on loopback, then the workspace in front of it.
#
# The API is never published outside the container. A reviewer reaches the
# workspace; the workspace reaches the API over localhost. That way a
# misconfigured port mapping cannot expose the ledger endpoints directly.
#
# Both run as children of this script. If either exits, the other is stopped
# and the container exits with that status, so the platform restarts it —
# rather than leaving a workspace that answers with no engine behind it.
set -euo pipefail

python -m caguard.cli serve \
    --host 127.0.0.1 \
    --port 8000 \
    --store "${CAGUARD_STORE:-/data/review.db}" \
    --model "${CAGUARD_MODEL:-none}" &
api_pid=$!

stop() {
    kill "$api_pid" "${web_pid:-}" 2>/dev/null || true
}
trap 'stop; exit 143' INT TERM

printf 'waiting for the analysis engine'
for _ in $(seq 1 60); do
    if python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=1)" 2>/dev/null; then
        printf ' ready\n'
        break
    fi
    if ! kill -0 "$api_pid" 2>/dev/null; then
        printf '\nThe analysis engine stopped while starting. See the log above.\n' >&2
        wait "$api_pid" || exit $?
        exit 1
    fi
    printf '.'
    sleep 1
done

if ! python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=1)" 2>/dev/null; then
    printf '\nThe analysis engine did not become ready within 60 seconds.\n' >&2
    stop
    exit 1
fi

node web/server.js &
web_pid=$!

# Whichever stops first ends the container.
set +e
wait -n "$api_pid" "$web_pid"
status=$?
stop
exit "$status"
