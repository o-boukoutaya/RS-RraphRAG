# Entity Linking (EntGPT-P style, multiple-choice with NONE)

TASK: Given a MENTION and CANDIDATE entities (same series), pick the single best match or
"NONE" if no candidate refers to the same real-world entity. Be conservative.

RETURN FORMAT (single JSON object only):
{ "winner": "<entity_id_or_NONE>", "confidence": 0.0 }

MENTION:
name: {{name}}
type_hint: {{type_hint}}
context: {{context}}   # optional short description (if any)

CANDIDATES:  # up to K entries
[
  { "id": "{{cand_id}}", "name": "{{cand_name}}",
    "type": "{{cand_type}}", "desc": "{{cand_desc}}" },
  ...
]

Rules:
- Prefer exact coreference, not topical relatedness.
- If in doubt, return winner="NONE".
- Confidence in [0,1].
