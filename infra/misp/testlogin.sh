#!/bin/bash
# Smoke-test the MISP web login (CSRF token + session cookie flow).
#
# Credentials come from the environment only — never hardcode them here.
# Usage (from infra/misp/, loading the gitignored .env.misp):
#   set -a; . ./.env.misp; set +a; ./testlogin.sh
# Or export MISP_ADMIN_EMAIL / MISP_ADMIN_PASSWORD manually before running.
# Optional: MISP_URL (default https://localhost; from the host use
# https://<GMKTEC_IP>:8443).
set -euo pipefail

MISP_URL="${MISP_URL:-https://localhost}"
ADMIN_EMAIL="${MISP_ADMIN_EMAIL:?MISP_ADMIN_EMAIL must be set (see infra/misp/.env.misp.template)}"
ADMIN_PASSWORD="${MISP_ADMIN_PASSWORD:?MISP_ADMIN_PASSWORD must be set (see infra/misp/.env.misp.template)}"

JAR=$(mktemp)
OUT=$(mktemp)
trap 'rm -f "$JAR" "$OUT"' EXIT

# Get login page and extract CSRF token + cookie
RESPONSE=$(curl -sk -c "$JAR" "$MISP_URL/users/login")
TOKEN=$(echo "$RESPONSE" | grep -o 'data\[_Token\]\[key\]" value="[^"]*"' | grep -o 'value="[^"]*"' | cut -d'"' -f2)
FIELDS=$(echo "$RESPONSE" | grep -o 'data\[_Token\]\[fields\]" value="[^"]*"' | grep -o 'value="[^"]*"' | cut -d'"' -f2)

echo "Token: $TOKEN"
echo "Fields: $FIELDS"

# Submit login with same cookie jar. Password is fed via stdin so it does not
# appear in the process list.
RESULT=$(printf '%s' "$ADMIN_PASSWORD" | curl -sk -c "$JAR" -b "$JAR" -X POST "$MISP_URL/users/login" \
  -d "_method=POST" \
  --data-urlencode "data[_Token][key]=$TOKEN" \
  --data-urlencode "data[User][email]=$ADMIN_EMAIL" \
  --data-urlencode "data[User][password]@-" \
  --data-urlencode "data[_Token][fields]=$FIELDS" \
  -d "data[_Token][unlocked]=" \
  -w "\nHTTP:%{http_code}" -L -o "$OUT" 2>&1)

echo "Result: $RESULT"
echo "Page title: $(grep -o '<title>[^<]*</title>' "$OUT" || true)"
