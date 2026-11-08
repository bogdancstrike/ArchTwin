# ADR-0004: Keycloak for identity, Cerbos for authorization, explicit federation

- **Status:** Accepted (planning baseline)
- **Date:** 2026-11-08

## Context and problem
Regulated customers need standard SSO, fine-grained policy-as-code, and provable project isolation, including in search, caches and AI context.

## Decision
Keycloak (OIDC + PKCE) authenticates; memberships and role bindings live in PostgreSQL; **Cerbos** decides every read and write (`CheckResources`) and filters lists (`PlanResources` via the official SQLAlchemy adapter; unknown operators ⇒ deny). PostgreSQL RLS with `SET LOCAL` is defense in depth. Cross-project access needs a bilateral, scoped, expiring **federation grant**.

## Alternatives considered
- Homegrown RBAC — rejected: hard to audit and test.
- OPA/OpenFGA — viable; Cerbos chosen for resource/action fit, query plans and Horizon reuse.

## Consequences
- Policies are versioned and unit-tested in CI.
- PDP outage fails closed.
- Federation adds an approval workflow but prevents implicit sharing.
