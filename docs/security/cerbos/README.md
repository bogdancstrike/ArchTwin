# Cerbos policy integration

`project.yaml` is an **illustrative** Cerbos resource policy for basic project actions, not sufficient as the sole production policy. Implement separate policies for environments, diagrams, documents, connector secrets, architecture sources, issue sync, drift and cross-project grants. Use an integration test matrix for owner, architect, reviewer, viewer and denied users. Do not use project role alone for sensitive evidence; include classification and federation constraints.

Example principal:
`{id: "user-123", roles: ["architect"], attr: {org_id: "org-A", project_ids: ["project-A"], classification_ceiling: "internal"}}`

Example resource:
`{kind: "project", id: "project-A", attr: {org_id: "org-A", project_id: "project-A", classification: "internal"}}`

Never trust client-supplied principal role or resource attributes. Resource attributes are loaded server-side from canonical records. For collection search use a verified PlanResources adapter, and test every AST operator. Keep query-plan and CheckResources behavior consistent in multi-tenant property tests.
