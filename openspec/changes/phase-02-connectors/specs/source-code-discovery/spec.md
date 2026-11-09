# Source repository and code architecture extraction

## ADDED Requirements

### Requirement: Repo scanning
**Requirement ID:** `AT-SOURCE_CODE_DISCOVERY-001`

The system MUST integrate GitHub and GitLab, read selected refs and commits, discover languages, manifests, dependency edges, APIs, Dockerfiles and code-owned teams.

#### Scenario: Read-only Git
- **GIVEN** a GitHub installation has contents read
- **WHEN** a scan executes
- **THEN** no repository commits or branches are modified

#### Scenario: Unselected ref ignored
- **GIVEN** only the main branch is selected
- **WHEN** a push to a feature branch arrives
- **THEN** no architecture inventory change is recorded for the feature branch

### Requirement: Static analysis evidence
**Requirement ID:** `AT-SOURCE_CODE_DISCOVERY-002`

Discovered endpoints, Kafka topics, database clients and other dependencies MUST have path, commit, parser type and line-range evidence.

#### Scenario: Generated inference
- **GIVEN** an inferred API dependency is unsupported by code
- **WHEN** a diagram is generated
- **THEN** it is explicitly marked inferred and not promoted to observed

#### Scenario: Parser crash isolation
- **GIVEN** the Java analyzer crashes on one file
- **WHEN** the scan continues
- **THEN** other files are processed and the failed file is reported with the parser version as incomplete coverage

### Requirement: Change tracking
**Requirement ID:** `AT-SOURCE_CODE_DISCOVERY-003`

When webhooks are enabled, push/PR/MR events MUST trigger incremental extraction and produce source changes keyed to commit SHA; without webhooks, polling MUST provide the same result within the polling interval.

#### Scenario: Changed route
- **GIVEN** a merged commit changes a controller endpoint
- **WHEN** the hook is delivered
- **THEN** the architectural API inventory is updated and change is linked to the commit

#### Scenario: Duplicate push events
- **GIVEN** the same push webhook is delivered twice
- **WHEN** both deliveries are processed
- **THEN** one extraction runs and one change record exists for the commit

### Requirement: Local directories
**Requirement ID:** `AT-SOURCE_CODE_DISCOVERY-004`

The system MUST accept local directories mounted read-only under an operator-configured source root as datasources: one repository (any ref), a folder of repositories (one system each) or a docs/architecture folder (`content=docs`).

#### Scenario: Folder of repositories
- **GIVEN** a directory that holds several Git repositories and is not itself a repository
- **WHEN** a scan executes
- **THEN** each repository is scanned at its HEAD as its own software system and the revision lists every repository commit

#### Scenario: Documentation folder
- **GIVEN** a folder scanned with `content=docs`
- **WHEN** the scan executes
- **THEN** its documents, ADRs and diagram sources are ingested and no runtime containers are derived from it

### Requirement: Local directory confinement
**Requirement ID:** `AT-SOURCE_CODE_DISCOVERY-005`

Directories outside the source roots, including through symbolic links, MUST be refused; the folder picker MUST return folder names only and only to users allowed to create connectors.

#### Scenario: Path outside the source roots
- **GIVEN** a path outside the mounted source roots, or a symbolic link pointing outside them
- **WHEN** a user tests, scans or browses it
- **THEN** the request is refused and nothing is read

#### Scenario: Viewer cannot browse
- **GIVEN** a project viewer
- **WHEN** they open the folder picker
- **THEN** the request is denied by policy
