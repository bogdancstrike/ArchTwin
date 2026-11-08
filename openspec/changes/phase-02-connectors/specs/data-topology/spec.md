# Database and messaging topology discovery

## ADDED Requirements

### Requirement: Database family
**Requirement ID:** `AT-DATA_TOPOLOGY-001`

The system MUST support PostgreSQL, MySQL, MongoDB, Elasticsearch/OpenSearch, Neo4j and Qdrant metadata discovery where permitted, without default access to application records.

#### Scenario: Minimal metadata
- **GIVEN** a project connects PostgreSQL with catalog privileges
- **WHEN** scan executes
- **THEN** schemas/tables/relations are discovered without reading customer rows

#### Scenario: Row access refused
- **GIVEN** the database principal can read table rows
- **WHEN** the scanner runs
- **THEN** only catalog queries are issued and the excess privilege is reported

### Requirement: Messaging systems
**Requirement ID:** `AT-DATA_TOPOLOGY-002`

The system MUST discover Kafka topics, consumer groups, schemas, producers and consumers from available metadata and code evidence.

#### Scenario: Uncertain producer
- **GIVEN** a topic exists but no producer can be identified
- **WHEN** graph builds
- **THEN** producer remains unknown instead of fabricated

#### Scenario: No payload reads
- **GIVEN** a Kafka connector has consume permissions
- **WHEN** discovery runs
- **THEN** no message payloads are fetched; only topic, partition, group and schema metadata are stored

### Requirement: Sensitive metadata
**Requirement ID:** `AT-DATA_TOPOLOGY-003`

Connector mapping MUST classify credentials, PII columns and sensitive infrastructure details for redaction before search/LLM contexts.

#### Scenario: Unprivileged viewer
- **GIVEN** schema includes secret-valued metadata
- **WHEN** viewer opens the catalog
- **THEN** restricted fields are masked

#### Scenario: Masked in AI context
- **GIVEN** a column is classified as PII
- **WHEN** it is included in an AI evidence pack
- **THEN** only its masked name and classification are sent, never sample values
