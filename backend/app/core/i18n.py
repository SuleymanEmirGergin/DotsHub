"""
i18n hazırlığı: locale'e göre metin key'leri.
Şu an sadece tr-TR; ileride en-US vb. eklenebilir.
"""

from __future__ import annotations

from typing import Dict

# Key -> metin (tr-TR)
_MESSAGES_TR: Dict[str, str] = {
    "rate_limit_exceeded": "Çok fazla istek. Lütfen daha sonra tekrar deneyin.",
    "rate_limit_exceeded_en": "Rate limit exceeded",
    "error_internal": "Bir hata oluştu.",
    "error_internal_en": "An error occurred.",
}

# Locale -> key -> metin
_LOCALES: Dict[str, Dict[str, str]] = {
    "tr-TR": _MESSAGES_TR,
    "en-US": {
        "rate_limit_exceeded": _MESSAGES_TR["rate_limit_exceeded_en"],
        "rate_limit_exceeded_en": _MESSAGES_TR["rate_limit_exceeded_en"],
        "error_internal": _MESSAGES_TR["error_internal_en"],
        "error_internal_en": _MESSAGES_TR["error_internal_en"],
    },
}

DEFAULT_LOCALE = "tr-TR"


def get_text(locale: str | None, key: str, fallback: str | None = None) -> str:
    """Locale'e göre metin döndürür. Bilinmeyen locale için tr-TR, bilinmeyen key için fallback kullanılır."""
    loc = (locale or DEFAULT_LOCALE).strip()
    if loc not in _LOCALES:
        loc = DEFAULT_LOCALE
    msg = _LOCALES[loc].get(key)
    if msg is not None:
        return msg
    if fallback is not None:
        return fallback
    return _LOCALES[DEFAULT_LOCALE].get(key, key)
