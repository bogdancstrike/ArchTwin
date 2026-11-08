# Living architecture documentation

## ADDED Requirements

### Requirement: Documentation types
**Requirement ID:** `AT-DOCUMENTATION_ENGINE-001`

The system MUST generate versioned system descriptions, C4 narratives, interface catalogs, deployment runbooks, dependencies, data flows and architecture summaries from permitted facts.

#### Scenario: Docs regeneration
- **GIVEN** the Kafka topic contract changes
- **WHEN** the doc is regenerated
- **THEN** changed claims are shown as a reviewed diff

#### Scenario: Handwritten prose protected
- **GIVEN** a section was edited by hand
- **WHEN** regeneration runs
- **THEN** the section is not overwritten; a proposed diff is offered instead

### Requirement: Citations and ownership
**Requirement ID:** `AT-DOCUMENTATION_ENGINE-002`

Every machine-generated claim MUST reference relevant graph facts or source passages, and documents MUST have owners and review states.

#### Scenario: Unverifiable text
- **GIVEN** the LLM suggests a database not found in evidence
- **WHEN** a draft is generated
- **THEN** the sentence is clearly unverified and not published automatically

#### Scenario: Fully cited draft
- **GIVEN** every claim in a draft maps to evidence
- **WHEN** the citation coverage report runs
- **THEN** coverage is 100% and the draft can enter review

### Requirement: Export
**Requirement ID:** `AT-DOCUMENTATION_ENGINE-003`

Architecture documentation MUST export as Markdown, PDF/Docx through an isolated renderer, and optionally create reviewable Git PRs behind flags.

#### Scenario: Export permissions
- **GIVEN** a user exports a confidential architecture
- **WHEN** export runs
- **THEN** project permissions and redaction remain enforced

#### Scenario: Renderer isolation
- **GIVEN** a document contains a remote image URL
- **WHEN** PDF export runs
- **THEN** the isolated renderer does not fetch the URL
