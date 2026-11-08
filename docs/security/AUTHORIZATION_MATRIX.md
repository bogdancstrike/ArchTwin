# Role/action decision matrix (proposed default — refined by Cerbos)
| Action / Resource | Project owner | Architect | Tech lead | Reviewer | Viewer | Security admin |
|---|---:|---:|---:|---:|---:|---:|
| View own project / allowed environment | Y | Y | Y | Y | Y | Audit-scope only |
| Edit draft diagram/docs | Y | Y | Project policy | Comment | N | N |
| Publish baseline | Y | Y with independent approval | N | N | N | N |
| Accept architecture ADR | Y with second reviewer | Y with second reviewer | N | Review | N | N |
| Configure project connectors | Y | Scoped | N | N | N | Review scopes |
| Read connector secrets | N (redacted) | N | N | N | N | N (rotation only) |
| Enable external issue write-back | Y + policy approval | N | N | N | N | Security review |
| Grant cross-project federation | Y + counterpart | N | N | N | N | Audit/restrict |
| Change security kill switch | Org security admin only | N | N | N | N | Y |
| Read project audit | Scoped | Scoped | Scoped | Limited | N | Policy-scoped |

Every row is additionally constrained by org, project, environment, classification, feature flag and data residency. Neither roles nor this table alone grant cross-project access.
