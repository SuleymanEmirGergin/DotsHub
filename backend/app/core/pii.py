"""
PII maskeleme: loglarda hassas alanları kısalt veya maskele.
"""

from __future__ import annotations

from typing import Optional


def mask_for_log(value: Optional[str], field_name: str = "value") -> str:
    """
    Log satırlarında kullanılmak üzere PII değerini maskele.
    - Boş/None -> "(empty)"
    - device_id / x-device-id: ilk 4 + "****" (en fazla 8 karakter göster)
    - email: yerel kısım ilk 2 + *** + @ + domain ilk 2 + ***
    - Diğer: son 4 karakter hariç *** (en fazla 8 karakter)
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return "(empty)"
    s = value.strip()
    if not s:
        return "(empty)"
    fl = field_name.lower()
    if "device" in fl or "device_id" in fl:
        if len(s) <= 8:
            return "****"
        return s[:4] + "****"
    if "email" in fl:
        if "@" not in s:
            return s[:2] + "***" if len(s) > 2 else "***"
        local, _, domain = s.partition("@")
        local_m = (local[:2] + "***") if len(local) > 2 else "***"
        domain_m = (domain[:2] + "***") if len(domain) > 2 else "***"
        return f"{local_m}@{domain_m}"
    if len(s) <= 4:
        return "****"
    return "***" + s[-4:] if len(s) > 8 else "****"
