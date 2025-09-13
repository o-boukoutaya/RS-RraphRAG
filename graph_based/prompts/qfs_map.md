Given the question: {question}
and community summaries: {chunks}

Produce a partial answer (map step) with inline citations [node:<id>] / [comm:<id>].
100–150 tokens. Output markdown.
-------------------------------------------

SYSTEM: Given a query and ONE community summary, produce an answer fragment 
grounded ONLY in that community. Cite node_ids you used.

USER:
Query: {{q}}
CommunitySummary: {{summary}}
Output JSON: { "fragment": "...", "used_nodes":[ids], "confidence":[0..1] }
-------------------------------------------


SYSTEM:
Given a user query and ONE community summary, produce a grounded answer fragment. Cite node_ids. Do not use outside knowledge.

INPUT:
{ "query": "{{q}}", "community_summary": {{summary_json}} }

OUTPUT (JSON):
{ "fragment": "Short paragraph answering the query from this community only, with inline [N:node_id] citations.",
  "used_nodes": ["n1","n7"], "confidence": 0.0 }
-------------------------------------------


SYSTEM:
Given a user query and ONE community summary, produce a grounded answer fragment.
Cite node_ids. Do not use outside knowledge.

INPUT:
{
  "query": "{{q}}",
  "community_summary": {{summary_json}}
}

OUTPUT (JSON):
{
  "fragment": "Short paragraph answering the query from this community only, with inline [N:node_id] citations.",
  "used_nodes": ["n1","n7"],
  "confidence": 0.0
}
