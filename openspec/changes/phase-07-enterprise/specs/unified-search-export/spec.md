# Unified search, discovery and portability

## ADDED Requirements

### Requirement: Scoped search
**Requirement ID:** `AT-UNIFIED_SEARCH_EXPORT-001`

Search MUST index approved architecture entities, docs, ADRs, tasks, drift and evidence with tenant and project filters applied before retrieval and ranking.

#### Scenario: Search isolation
- **GIVEN** word appears only in inaccessible project
- **WHEN** user searches globally
- **THEN** no result or count exposes the other project

#### Scenario: Index ACL lag
- **GIVEN** a permission change has not reached the search index
- **WHEN** a search runs
- **THEN** results are re-checked against current authorization before returning

### Requirement: Portable formats
**Requirement ID:** `AT-UNIFIED_SEARCH_EXPORT-002`

Exports MUST include canonical graph JSON, Structurizr DSL, Mermaid, Markdown, versioned ADRs and traceable bundle manifests where format supports the data.

#### Scenario: Roundtrip
- **GIVEN** an export is re-imported to a clean project
- **WHEN** integrity is checked
- **THEN** IDs and core relationships can be mapped without loss of required semantics

#### Scenario: Unsupported semantics
- **GIVEN** a graph feature cannot be represented in Mermaid
- **WHEN** export runs
- **THEN** the export lists what was dropped

### Requirement: APIs and events
**Requirement ID:** `AT-UNIFIED_SEARCH_EXPORT-003`

Public read APIs and selected webhooks MUST have OpenAPI schemas, stable resource IDs, rate limits and signed outgoing event delivery.

#### Scenario: Webhook retry
- **GIVEN** consumer returns an error
- **WHEN** delivery retries
- **THEN** idempotency key permits safe processing

#### Scenario: Invalid signature on outgoing event
- **GIVEN** a consumer verifies an outgoing webhook with the wrong secret
- **WHEN** verification runs
- **THEN** it fails, proving the signature covers the payload
