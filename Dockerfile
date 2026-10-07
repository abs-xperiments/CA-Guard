# CA-Guard, self-hosted.
#
# Everything a firm needs on one machine: the analysis engine, the API and the
# review workspace. No account, no key, no outbound call.
#
# Three stages. The browser interface needs Node to build; the Python
# environment is resolved from uv.lock by uv; the final image carries only what
# runs — no uv, no compilers, no build caches.

# --- stage 1: build the workspace --------------------------------------------
FROM node:26-slim AS web

WORKDIR /build
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY web/ ./
# The browser talks to the API on the same container.
ENV CAGUARD_API=http://127.0.0.1:8000
RUN npm run build


# --- stage 2: the Python environment, exactly as locked -----------------------
FROM python:3.13-slim AS python-env

COPY --from=ghcr.io/astral-sh/uv:0.11.24 /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /src
# Dependencies first, from the lockfile alone, so they are cached across code
# changes. --frozen refuses to run if uv.lock and pyproject.toml disagree:
# the image gets exactly the versions the tests ran against.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src/ ./src/
RUN uv sync --frozen --no-dev --no-editable


# --- stage 3: the application ------------------------------------------------
FROM python:3.13-slim AS app

# The same Node the workspace was built with, rather than whatever version the
# distribution packages: Next.js 16 needs Node 20.9 or newer.
COPY --from=web /usr/local/bin/node /usr/local/bin/node
# The one shared library that binary needs and the slim image lacks.
RUN apt-get update \
    && apt-get install --no-install-recommends -y libatomic1 \
    && rm -rf /var/lib/apt/lists/* \
    && node --version

# Never run as root. A ledger is a client's most sensitive file.
RUN useradd --create-home --uid 10001 caguard

COPY --from=python-env /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app
COPY --from=web /build/.next/standalone ./web/
COPY --from=web /build/.next/static ./web/.next/static
COPY --from=web /build/public ./web/public
COPY docker/entrypoint.sh /usr/local/bin/caguard-entrypoint
RUN chmod 0755 /usr/local/bin/caguard-entrypoint

# Only /data is writable by the application: decisions and the stored
# originals. The code itself stays root-owned, so a compromised process cannot
# rewrite what it runs.
RUN mkdir -p /data && chown caguard:caguard /data
VOLUME ["/data"]

# No USER here: the entrypoint starts as root only to hand /data (which
# platforms mount root-owned) to the caguard user, then drops to it for good
# with every capability removed. Nothing in the application ever runs as root.
ENV CAGUARD_STORE=/data/review.db \
    CAGUARD_MODEL=none \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# 3000 is the workspace. The API stays on loopback inside the container and is
# deliberately not published: only the interface is reachable.
EXPOSE 3000

# Through the workspace, so a healthy result means both processes are serving.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import os,urllib.request;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"3000\")}/api/health',timeout=3)" || exit 1

ENTRYPOINT ["caguard-entrypoint"]
