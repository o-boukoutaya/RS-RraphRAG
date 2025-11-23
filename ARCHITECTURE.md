# Architecture GraphRAG (backend)

- `adapters/` : couches techniques
  - `db/neo4j.py` : accès Neo4j (sessions, contraintes, requêtes)
  - `llm/`       : wrappers LLMs et embedders
  - `storage/`   : stockage de fichiers (local, MinIO, ...)
  - `vector/`    : abstraction vector store (WIP)

- `app/` : cœur application et HTTP
  - `core/config.py`    : chargement settings/env → Settings
  - `core/resources.py` : services métier (Corpus, Graph, Retrieval)
  - `observability/`    : état global + SSE + pipeline tracing
  - `main.py`           : création FastAPI et wiring
  - `mcp.py`            : serveur MCP (tools)

- `corpus/` : ingestion et pré-traitement de documents
- `graph_based/` : logique de construction du graphe
- `pipelines/steps/` : pipelines métiers (import, build, rag)
- `routes/` : API HTTP (utilisent les services de `app/core/resources.py`)
- `config/` : configuration YAML (runtime + pipelines)
- `tools/` : scripts CLI (exécution pipelines hors HTTP)
