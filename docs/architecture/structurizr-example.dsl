workspace "ArchTwin Example" "Reference C4 export; derived from canonical graph" {
  model {
    architect = person "Solution Architect" "Reviews architecture and drift"
    archtwin = softwareSystem "ArchTwin" "Living architecture workspace" {
      web = container "Web Studio" "C4 diagrams, ADRs, project review" "React / Vite"
      api = container "API" "Scoped architecture model & query" "FastAPI / asyncio"
      worker = container "Discovery Workers" "Connector ingestion / drift" "Python"
      db = container "Architecture Store" "Canonical evidence and versions" "PostgreSQL"
    }
    git = softwareSystem "GitHub/GitLab" "Code events and metadata"
    architect -> web "Designs and reviews"
    web -> api "Calls" "HTTPS/JSON"
    api -> db "Queries/mutates" "SQL"
    worker -> db "Persists observations" "SQL"
    git -> worker "Notifies" "Webhooks"
  }
  views {
    systemContext archtwin "Context" { include *; autoLayout lr }
    container archtwin "Containers" { include *; autoLayout lr }
    styles {
      element "Person" { shape person }
    }
  }
}
