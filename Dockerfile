# CA-Guard, self-hosted.
#
# Everything a firm needs on one machine: the analysis engine, the API and the
# review workspace. No account, no key, no outbound call.
#
# Two stages, because the browser interface needs Node to build and nothing to
# run. Shipping the Node toolchain in the final image would triple its size for
# no benefit.

# --- stage 1: build the workspace --------------------------------------------
FROM node:26-slim AS web

WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web/ ./
# The browser talks to the API on the same container.
ENV CAGUARD_API=http://127.0.0.1:8000
RUN npm run build


# --- stage 2: the application ------------------------------------------------
FROM python:3.13-slim AS app

# Node is needed to *run* the built Next.js server, but not to build it.
RUN apt-get update \
    && apt-get install --no-install-recommends -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Never run as root. A ledger is a client's most sensitive file.
RUN useradd --create-home --uid 10001 caguard
WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir . && rm -rf /root/.cache

COPY --from=web /build/.next/standalone ./web/
COPY --from=web /build/.next/static ./web/.next/static
COPY --from=web /build/public ./web/public
COPY docker/entrypoint.sh /usr/local/bin/caguard-entrypoint
RUN chmod +x /usr/local/bin/caguard-entrypoint

# Decisions live here. Mount a volume over it so they survive an upgrade.
RUN mkdir -p /data && chown -R caguard:caguard /data /app
VOLUME ["/data"]

USER caguard
ENV CAGUARD_STORE=/data/review.db \
    CAGUARD_MODEL=none \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# 3000 is the workspace. The API stays on loopback inside the container and is
# deliberately not published: only the interface is reachable.
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)" || exit 1

ENTRYPOINT ["caguard-entrypoint"]
