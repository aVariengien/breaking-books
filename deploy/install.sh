#!/usr/bin/env bash
# Install or update Breaking Books on mimosa. Safe to re-run.
#
#   ssh mimosa 'cd /opt/breaking-books-src && git pull && ./deploy/install.sh'
#
# Layout:
#   /opt/breaking-books-src/   git checkout (this repo, v2 branch)
#   /opt/breaking-books/       runtime state — secrets, output decks, caches
set -euo pipefail

SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ROOT=/opt/breaking-books
DOMAIN=breaking-books.alexandrevariengien.com

echo "==> installing breaking-books from $SRC"

mkdir -p "$ROOT/output" "$ROOT/data/fonts" "$ROOT/data/image_cache"

# --- secrets ----------------------------------------------------------------
# secrets.env  → API keys, injected as container env vars
# secrets.toml → Streamlit admin password, mounted at /app/.streamlit/secrets.toml
if [ ! -f "$ROOT/secrets.env" ]; then
  echo "==> creating $ROOT/secrets.env template — fill it in, then re-run"
  cat > "$ROOT/secrets.env" <<'ENV'
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=
CEREBRAS_API_KEY=
RUNWARE_API_KEY=
ENV
fi
if [ ! -f "$ROOT/secrets.toml" ]; then
  echo "==> creating $ROOT/secrets.toml template — set admin_password, then re-run"
  printf 'admin_password = "change-me"\n' > "$ROOT/secrets.toml"
fi
chmod 600 "$ROOT/secrets.env" "$ROOT/secrets.toml"

for key in GOOGLE_API_KEY CEREBRAS_API_KEY RUNWARE_API_KEY; do
  if ! grep -q "^${key}=." "$ROOT/secrets.env"; then
    echo "    !! $key is empty in $ROOT/secrets.env — the app will fail at runtime"
  fi
done

# --- build & run ------------------------------------------------------------
echo "==> building image"
docker compose -f "$SRC/deploy/docker-compose.yml" build

echo "==> starting container"
docker compose -f "$SRC/deploy/docker-compose.yml" up -d

# --- caddy ------------------------------------------------------------------
if ! grep -q "$DOMAIN" /etc/caddy/Caddyfile; then
  echo "==> adding Caddy vhost for $DOMAIN"
  cp /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak-$(date +%F-%H%M%S)"
  cat "$SRC/deploy/Caddyfile.snippet" >> /etc/caddy/Caddyfile
  systemctl reload caddy
else
  echo "==> Caddy vhost for $DOMAIN already present"
fi

echo
echo "==> container: $(docker inspect -f '{{.State.Status}}' breaking-books)"
echo "==> caddy:     $(systemctl is-active caddy)"
echo "==> url:       https://$DOMAIN"
