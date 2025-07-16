def truncate_words(text: str, max_words: int, ellipsis: str = "…") -> str:
    """Devuelve *text* limitado a *max_words* palabras.

    - Si el texto tiene *max_words* palabras o menos, se devuelve intacto.
    - Si excede el límite, se devuelven las primeras *max_words* palabras
      seguidas del *ellipsis* (por defecto «…»).

    Args:
        text: Cadena de entrada.
        max_words: Número máximo de palabras a conservar.
        ellipsis: Cadena a añadir cuando el texto ha sido truncado.

    Returns:
        Texto truncado.
    """
    if max_words <= 0:
        return ""

    words = text.split()
    if len(words) <= max_words:
        return text

    return " ".join(words[:max_words]) + ellipsis
