#!/bin/sh
# Start the analysis API on loopback, then the workspace in front of it.
#
# The API is never published outside the container. A reviewer reaches the
# workspace; the workspace reaches the API over localhost. That way a
# misconfigured port mapping cannot expose the ledger endpoints directly.
set -eu

python -m caguard.cli serve \
    --host 127.0.0.1 \
    --port 8000 \
    --store "${CAGUARD_STORE:-/data/review.db}" \
    --model "${CAGUARD_MODEL:-none}" &
api_pid=$!

# If the API dies, the container should stop rather than serve a broken UI.
trap 'kill "$api_pid" 2>/dev/null || true' INT TERM

printf 'waiting for the analysis engine'
i=0
while [ "$i" -lt 30 ]; do
    if python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=1)" 2>/dev/null; then
        printf ' ready\n'
        break
    fi
    printf '.'
    i=$((i + 1))
    sleep 1
done

exec node web/server.js
