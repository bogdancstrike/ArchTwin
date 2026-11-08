# ADR-0002: PostgreSQL as canonical store; outbox instead of a broker

- **Status:** Accepted (planning baseline)
- **Date:** 2026-11-08

## Context and problem
Graph, evidence, audit and events need one consistent source of truth; Neo4j, Qdrant and Kafka each add a system to operate and a consistency boundary.

## Decision
PostgreSQL is the only system of record: graph tables with temporal validity, JSONB snapshots, FTS and pgvector. Domain events use a **transactional outbox** relayed with `SKIP LOCKED` and `LISTEN/NOTIFY`. Neo4j/Qdrant/OpenSearch may be added later only as **rebuildable projections**; Kafka only with measured event volume.

## Alternatives considered
- Neo4j as source of truth — rejected: dual-write consistency, ACL complexity.
- Kafka from day one — rejected: operational weight without volume.

## Consequences
- One backup/restore story; RLS defense in depth works everywhere.
- Deep traversals use recursive CTEs with caps; benchmark at 5k nodes/20k edges.
- Projections must be fully rebuildable from PostgreSQL.
