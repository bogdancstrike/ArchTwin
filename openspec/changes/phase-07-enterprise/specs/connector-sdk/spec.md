# Extension SDK and connector marketplace model

## ADDED Requirements

### Requirement: Versioned SDK
**Requirement ID:** `AT-CONNECTOR_SDK-001`

A documented Python connector SDK MUST define manifests, capabilities, auth, discovery, normalization, watermark sync, testing and compatibility negotiation.

#### Scenario: External adapter
- **GIVEN** developer implements the documented protocol
- **WHEN** conformance tests run
- **THEN** adapter is accepted only after passing contracts

#### Scenario: Incompatible SDK version
- **GIVEN** an adapter declares an unsupported SDK major version
- **WHEN** it is loaded
- **THEN** activation is refused with a compatibility error

### Requirement: Supply-chain safety
**Requirement ID:** `AT-CONNECTOR_SDK-002`

Third-party adapters MUST have signatures or trust review, sandboxed workers, declared outbound/network permissions and optional organization allowlists.

#### Scenario: Unsigned plugin
- **GIVEN** organization requires signed plugins
- **WHEN** administrator uploads unsigned adapter
- **THEN** activation is refused

#### Scenario: Undeclared egress
- **GIVEN** a plugin connects to a host not in its manifest
- **WHEN** the sandbox enforces egress
- **THEN** the connection is blocked and the plugin is flagged

### Requirement: Isolation and limits
**Requirement ID:** `AT-CONNECTOR_SDK-003`

A connector error MUST be contained to its job/project, with quotas, circuit breakers, timeouts and dead-letter visibility.

#### Scenario: Bad connector
- **GIVEN** plugin enters an infinite retry
- **WHEN** scheduler detects budget exceeded
- **THEN** job is quarantined without destabilizing other projects

#### Scenario: Dead-letter visibility
- **GIVEN** a job is quarantined
- **WHEN** an operator opens the connector page
- **THEN** the dead-lettered job, last error and retry option are visible
