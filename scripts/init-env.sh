#!/usr/bin/env bash
# Create .env from .env.example with every internal secret generated. Usage: ./scripts/init-env.sh [OPENAI_API_KEY]
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then echo ".env already exists; remove it first to regenerate" >&2; exit 1; fi
rnd() { python3 -c "import secrets;print(secrets.token_urlsafe($1))"; }
hex() { python3 -c "import secrets;print(secrets.token_hex($1))"; }
kek=$(python3 -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())")
key="${1:-${OPENAI_API_KEY:-}}"
mode=litellm; [ -n "$key" ] || mode=fake
sed -e "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=${key:-sk-...}|" \
    -e "s|^ARCHTWIN_LLM_MODE=.*|ARCHTWIN_LLM_MODE=${mode}|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(rnd 18)|" \
    -e "s|^ARCHTWIN_APP_DB_PASSWORD=.*|ARCHTWIN_APP_DB_PASSWORD=$(rnd 18)|" \
    -e "s|^KEYCLOAK_ADMIN_PASSWORD=.*|KEYCLOAK_ADMIN_PASSWORD=$(rnd 12)|" \
    -e "s|^ARCHTWIN_KEK=.*|ARCHTWIN_KEK=${kek}|" \
    -e "s|^LITELLM_MASTER_KEY=.*|LITELLM_MASTER_KEY=sk-at-$(rnd 24)|" \
    -e "s|^LANGFUSE_PUBLIC_KEY=.*|LANGFUSE_PUBLIC_KEY=pk-lf-$(hex 16)|" \
    -e "s|^LANGFUSE_SECRET_KEY=.*|LANGFUSE_SECRET_KEY=sk-lf-$(hex 16)|" \
    -e "s|^LANGFUSE_NEXTAUTH_SECRET=.*|LANGFUSE_NEXTAUTH_SECRET=$(rnd 32)|" \
    -e "s|^LANGFUSE_SALT=.*|LANGFUSE_SALT=$(rnd 32)|" \
    -e "s|^LANGFUSE_ENCRYPTION_KEY=.*|LANGFUSE_ENCRYPTION_KEY=$(hex 32)|" \
    -e "s|^LANGFUSE_ADMIN_PASSWORD=.*|LANGFUSE_ADMIN_PASSWORD=$(rnd 12)|" \
    -e "s|^CLICKHOUSE_PASSWORD=.*|CLICKHOUSE_PASSWORD=$(rnd 18)|" \
    -e "s|^VALKEY_PASSWORD=.*|VALKEY_PASSWORD=$(rnd 18)|" \
    -e "s|^SEAWEED_ACCESS_KEY=.*|SEAWEED_ACCESS_KEY=$(hex 10)|" \
    -e "s|^SEAWEED_SECRET_KEY=.*|SEAWEED_SECRET_KEY=$(rnd 24)|" \
    .env.example > .env
chmod 600 .env
echo "✔ .env created (LLM mode: ${mode}). Login at http://localhost:3200 as admin/admin (also alice, bob, vera / archtwin)"
