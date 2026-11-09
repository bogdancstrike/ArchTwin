# Shop — ArchTwin reference fixture

A small, OTel-instrumented system used to develop and verify connectors against labelled ground truth
(`ground-truth.yaml`). It is a **separate Compose project** (`archtwin-fixtures`, containers `archtwin-fixture-*`) and is
never part of the application Compose file.

```
shop-loadgen ─http─▶ shop-web ─http─▶ shop-orders ─sql─▶ orders-db (PostgreSQL)
                         └────http──▶ shop-inventory ─sql─▶ inventory-db (MySQL)
shop-orders ─publishes─▶ Kafka topic orders.created (Avro schema in Schema Registry) ─▶ shop-billing (group billing)
every service ─OTLP─▶ otel-collector (servicegraph connector) ─▶ prometheus
```

| Make target | What it does |
|---|---|
| `make fixtures-up` | build and start the fixture (joins the `archtwin_app` network so read-only connectors can reach it) |
| `make fixtures-demo` | create the *Shop (reference fixture)* project with git, Docker, OTel, PostgreSQL, MySQL and Kafka connectors and scan them |
| `make fixtures-down` | stop and remove the fixture and its volumes |

Read-only credentials provisioned for ArchTwin: PostgreSQL `archtwin_catalog_ro` (CONNECT + USAGE) and MySQL
`archtwin_catalog_ro` (`REFERENCES` only — metadata visibility, no `SELECT`). Prometheus is published on
`127.0.0.1:9390` and the storefront on `127.0.0.1:8390` for manual poking.

Tests that use it: `apps/api/tests/unit/test_connectors_m1.py` (static recall against the ground truth, always) and
`apps/api/tests/e2e/test_fixture_connectors.py` (live, skipped when the fixture is down).
