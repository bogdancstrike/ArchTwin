# Runtime infrastructure inventory

## ADDED Requirements

### Requirement: Supported runtimes
**Requirement ID:** `AT-RUNTIME_DISCOVERY-001`

The platform MUST discover runtime topology from Kubernetes and Docker Swarm in v1; future cloud inventory adapters are optional feature flags.

#### Scenario: K8s services
- **GIVEN** a read-only cluster connector is healthy
- **WHEN** a scan runs
- **THEN** deployments, services, ingresses and workload ownership are inventoried by environment

#### Scenario: Namespace outside scope
- **GIVEN** the connector is limited to namespaces a and b
- **WHEN** workloads exist in namespace c
- **THEN** no namespace c objects are stored

### Requirement: Runtime evidence
**Requirement ID:** `AT-RUNTIME_DISCOVERY-002`

Observations MUST carry cluster, namespace, environment, resource UID, resourceVersion, observation time and connector scope.

#### Scenario: Resource recreation
- **GIVEN** a Deployment is deleted and recreated with the same name
- **WHEN** a scan detects it
- **THEN** identity distinguishes the old UID from the new one

#### Scenario: Watch resync
- **GIVEN** a watch stream returns resourceVersion too old
- **WHEN** the watcher restarts
- **THEN** a relist reconciles state without duplicate or lost workloads

### Requirement: Source protection
**Requirement ID:** `AT-RUNTIME_DISCOVERY-003`

Runtime discovery MUST be read-only with scoped credentials and never require cluster-admin.

#### Scenario: Credential privilege
- **GIVEN** a connector has list/watch permissions only
- **WHEN** discovery executes
- **THEN** no rollout or write operation is attempted

#### Scenario: Cluster-admin credential rejected
- **GIVEN** a kubeconfig bound to cluster-admin is supplied
- **WHEN** the connector test runs
- **THEN** the connector reports excessive privilege and organization policy can refuse activation
