You must answer **only** using the relational paths below.

Question: {question}

Retrieved path information (ordered by reliability ascending):
{paths}   <!-- each as: <v_i> --(e_i:desc)--> <v_{i+1}> ... -->

Instructions:
- Use only edges/nodes from the paths.
- Prefer information near the end (highest reliability).
- If missing evidence, say "INSUFFICIENT EVIDENCE".

Return:
1) Final answer (≤150 tokens)
2) Short chain of reasoning mapped to path IDs.