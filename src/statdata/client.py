# src/statdata/client.py
from __future__ import annotations

from functools import lru_cache

import sdmx

from .sources import get_source


@lru_cache(maxsize=32)
def get_client(source_id: str) -> sdmx.Client:
    """
    Ritorna un sdmx.Client configurato per la fonte richiesta.
    Cache: evita di ricreare client identici.
    """
    src = get_source(source_id)
    # sdmx.Client accetta un "url" base del provider
    return sdmx.Client(src.sdmx_id, timeout=60)
