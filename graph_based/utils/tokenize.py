import re


def approx_token_count(text: str, ratio: float = 1.33) -> int:
    """
    Approximation simple (pas de tiktoken) : nb_mots * ratio.
    Suffisant pour des budgets et garde-fous.
    """
    if not text:
        return 0
    return int(len(text.split()) * ratio) + 1

def count_tokens(text: str, *, model_hint: str = "llama3") -> int:
    """Compteur approximatif de tokens pour le budgetage QFS/PathRAG."""
    from app.core.resources import get_settings
    match get_settings().provider.default:
        case "gemini":
            return approx_token_count(text, ratio=2)  # ~2 chars/token
        case "openai":
            return approx_token_count(text, ratio=1.33)  # ~4 chars/token
        case "azure":
            return approx_token_count(text, ratio=1.33)  # ~4 chars/token
    return approx_token_count(text, ratio=1.5)  # fallback

def fit(text: str, *, max_tokens: int = 2048) -> str:
    """Tronque un texte pour qu'il tienne dans max_tokens (approx)."""
    if not text or max_tokens <= 0: return ""
    approx = approx_token_count(text)
    if approx <= max_tokens: return text

    # Tronquer en coupant les phrases (garde-fou)
    sentences = re.split(r'(?<=[.!?]) +', text)
    fitted = ""
    for sent in sentences:
        if approx_token_count(fitted + " " + sent) > max_tokens:
            break
        fitted += (" " if fitted else "") + sent
    if not fitted:  # si une phrase est trop longue, tronquer brutalement
        avg_char_per_token = 4  # approximation
        safe = int(max_tokens * avg_char_per_token * 0.9)
        fitted = text[:safe]
    return fitted