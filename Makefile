.PHONY: init-env up down logs ps reset test test-integration test-e2e test-ui test-all lint policy-test migrate-check spec-validate
COMPOSE ?= docker compose
API := cd apps/api && uv run

init-env:          ; ./scripts/init-env.sh $(OPENAI_API_KEY)
up:                ; $(COMPOSE) up -d --build
down:              ; $(COMPOSE) --profile "*" down
logs:              ; $(COMPOSE) logs -f --tail=200 api worker
ps:                ; $(COMPOSE) ps
reset:             ; $(COMPOSE) --profile "*" down -v   # deletes ALL data
lint:              ; $(API) ruff check archtwin tests && cd ../web && npx tsc -b
test:              ; $(API) pytest -q                    # unit (no services needed)
test-integration:  ; $(API) pytest -q -m integration tests/integration   # needs `make up` (PostgreSQL)
test-e2e:          ; $(API) pytest -q -m e2e tests/e2e   # needs the full stack
test-ui:           ; cd apps/web && npx playwright test
test-all: test test-integration test-e2e test-ui
policy-test:       ; docker run --rm -v "$$PWD/deploy/cerbos/policies":/policies ghcr.io/cerbos/cerbos:0.39.0 compile /policies
spec-validate:     ; npx -y @fission-ai/openspec@latest validate --all --strict
migrate-check:     ; $(COMPOSE) run --rm migrate sh -c "alembic upgrade head && alembic downgrade base && alembic upgrade head"
