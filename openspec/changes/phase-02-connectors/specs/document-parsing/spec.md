# Document and diagram import processing

## ADDED Requirements

### Requirement: Docling ingestion
**Requirement ID:** `AT-DOCUMENT_PARSING-001`

The platform MUST use Docling for supported PDFs, Word, presentation and document formats with parser-specific fallbacks and source metadata.

#### Scenario: PDF ingestion
- **GIVEN** an authorized user uploads an architecture PDF
- **WHEN** parsing completes
- **THEN** pages, tables and extracted sections are available with page provenance

#### Scenario: Unsupported format
- **GIVEN** a user uploads a format Docling cannot parse and no fallback exists
- **WHEN** processing runs
- **THEN** the document is stored as unparsed with a clear status and is excluded from evidence

### Requirement: File security
**Requirement ID:** `AT-DOCUMENT_PARSING-002`

Uploads MUST enforce size/type limits, malware scanning, decompression limits, tenant-isolated storage and asynchronous processing.

#### Scenario: Malicious upload
- **GIVEN** a file fails malware validation
- **WHEN** processing starts
- **THEN** the file is quarantined and never enters the AI retrieval index

#### Scenario: Decompression bomb
- **GIVEN** an archive expands beyond the configured limit
- **WHEN** parsing starts
- **THEN** the worker aborts within its resource budget and marks the file rejected

### Requirement: Document associations
**Requirement ID:** `AT-DOCUMENT_PARSING-003`

Documents MUST be project-owned, versioned, tagged and linkable to elements, ADRs, tasks and architecture snapshots.

#### Scenario: Revision
- **GIVEN** a new design document version is uploaded
- **WHEN** architect compares versions
- **THEN** old references remain available by immutable version

#### Scenario: Cross-project link refused
- **GIVEN** a document belongs to project A
- **WHEN** a user links it to an element in project B without a grant
- **THEN** the link is rejected
