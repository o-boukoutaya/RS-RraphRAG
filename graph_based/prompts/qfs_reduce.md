Reduce N partial answers into a **single, non-redundant** answer.
- Keep only claims that have citations [node:<id>] or [comm:<id>].
- Merge duplicates; flag disagreements explicitly.

Return markdown ≤ 250 tokens + list of all citations used (ids only).
-----------------------------------------------------


SYSTEM: Merge multiple grounded fragments into ONE coherent answer.
Eliminate redundancy, reconcile conflicts, and present a final answer with 
inline citations [N:node_id] and a "sources" list (node_ids unique).

USER:
Fragments: {{fragments_json}}
Output JSON: { "final": "...", "sources":[node_ids], "confidence":[0..1] }
-----------------------------------------------------


SYSTEM:
Merge multiple grounded fragments into a single coherent answer. Remove redundancy, reconcile conflicts, and present sources.

INPUT:
{ "query": "{{q}}", "fragments": [
  { "fragment": "... [N:n42]", "used_nodes": ["n42"], "confidence": 0.68 },
  { "fragment": "... [N:n17][N:n19]", "used_nodes": ["n17","n19"], "confidence": 0.74 } ] }

OUTPUT (JSON):
{ "final": "Final cohesive answer, with inline [N:node_id] citations.", "sources": ["n42","n17","n19"], "confidence": 0.0 }
-----------------------------------------------------


SYSTEM:
Merge multiple grounded fragments into a single coherent answer.
Remove redundancy, reconcile conflicts, and present sources.

INPUT:
{
  "query": "{{q}}",
  "fragments": [
    { "fragment": "... [N:n42]", "used_nodes": ["n42"], "confidence": 0.68 },
    { "fragment": "... [N:n17][N:n19]", "used_nodes": ["n17","n19"], "confidence": 0.74 }
  ]
}

OUTPUT (JSON):
{
  "final": "Final cohesive answer, with inline [N:node_id] citations.",
  "sources": ["n42","n17","n19"],
  "confidence": 0.0
}
