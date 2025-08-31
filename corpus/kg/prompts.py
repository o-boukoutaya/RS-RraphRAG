# corpus/kg/prompts.py
from __future__ import annotations

GENERIC_INSTRUCTIONS_FR = """Tu es un extracteur d'information pour construire un Knowledge Graph.
RÈGLES:
- NE PAS HALLUCINER : extrais uniquement ce qui est explicitement présent dans le texte (ne rate aucune information (entité, relation, ... tout lien)).
- Conserve les libellés tels qu'ils apparaissent (pas de paraphrase sémantique).
- Normalise les nombres (ex: "1 200 000" -> 1200000).
- Si une info est absente, omets-la.
- Langue de sortie: JSON strict, sans texte additionnel.

SCHÉMA DE SORTIE (JSON strict):
{
  "entities": [
    { "type": "<Type>", "name": "<Nom exact>", "props": { "<clé>": "<valeur>", ... } }
  ],
  "relations": [
    {
      "type": "<RELATION_TYPE_UPPERCASE>",
      "source": { "type": "<Type>", "name": "<Nom exact>" },
      "target": { "type": "<Type>", "name": "<Nom exact>" },
      "props": { "<clé>": "<valeur>", ... },
      "confidence": 0.0
    }
  ]
}
"""

IMMOBILIER_HINT_FR = """DOMAINE: immobilier
Exemples d'entités: Project, UnitType, Unit, City, Place, Developer, Amenity, Price.
Exemples de relations: LOCATED_IN, DEVELOPS, OFFERS, HAS_AMENITY, PRICE_FROM, NEAR."""

def build_extraction_prompt(text: str, domain_hint: str = "immobilier") -> str:
    base = GENERIC_INSTRUCTIONS_FR
    if (domain_hint or "").strip().lower() in {"immobilier", "immo", "real-estate"}:
        base = base + "\n" + IMMOBILIER_HINT_FR
    example = (
        'EXEMPLE DE SORTIE MINIMALE:\n'
        '{\n'
        '  "entities": [ {"type":"Document","name":"Brochure","props":{}} ],\n'
        '  "relations": []\n'
        '}\n'
    )
    return f"{base}\n{example}\nTEXTE:\n\"\"\"\n{text}\n\"\"\"\n\nRéponds UNIQUEMENT par le JSON, sans backticks."
