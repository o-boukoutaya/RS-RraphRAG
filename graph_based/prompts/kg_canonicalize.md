# KG Canonicalize (chunk → entities & relations)

- Return **exactly one** JSON object, and nothing else (no prose, no code fences).
- **Do not hallucinate** relations. Only assert if explicitly or strongly implied.
- Entity descriptions ≤ 40 words. Confidence `conf` ∈ [0,1].
- Canonicalize names (casefold, trim punctuation), deduplicate via `aliases`.

SCHEMA (return exactly ONE JSON object, nothing else):
{
  "entities": [
    {
      "name": "string",          // canonical label
      "type": "string",          // coarse-grained type (e.g., person, org, product, location, date, metric, other)
      "aliases": ["string", ...],
      "desc": "short description",
      "conf": 0.0
    }
  ],
  "relations": [
    {
      "src": "string",           // entity name as above (canonical)
      "pred": "string",          // relation verb/noun in snake_case (e.g., "founded_by", "located_in")
      "dst": "string",           // entity name as above (canonical)
      "conf": 0.0
    }
  ]
}

CONTEXT:
- series: {{series}}
- chunk_id: {{cid}}

CHUNK:
{{chunk_text}}

CONSTRAINTS:
- Prefer entity types among: person | organization | product | location | date | metric | other.
- Use deterministic ordering:
  - entities sorted by `name` (asc),
  - relations sorted by (`src`, `pred`, `dst`) (asc/lexicographic).
- If no entity or relation is supported by the text, return:
  { "entities": [], "relations": [] }
