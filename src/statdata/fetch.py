# src/statdata/fetch.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from .client import get_client
from .query import BuiltQuery
from .sources import get_source


@dataclass(frozen=True)
class FetchResult:
    dataset: str
    series_key: str
    params: dict[str, Any]
    raw: bytes | None          # raw SDMX-ML / SDMX-JSON
    message: Any | None        # oggetto python-sdmx (se parse riuscito)
    content_type: str | None


def fetch_data(bq: BuiltQuery, source_id: str, *, parse: bool = True) -> FetchResult:
    """
    Scarica dati SDMX per dataset+series_key.
    - parse=True: prova a parsare in oggetto sdmx (message)
    - parse=False: ritorna solo raw bytes
    """
    c = get_client(source_id)

    # sdmx1: c.data(resource_id, key=..., params=...)
    # Qui usiamo l'interfaccia alto livello; se fallisce, fallback raw.
    if parse:
        try:
            msg = c.data(bq.dataset, key=bq.series_key, params=bq.params)
            return FetchResult(
                dataset=bq.dataset,
                series_key=bq.series_key,
                params=bq.params,
                raw=None,
                message=msg,
                content_type=None,
            )
        except Exception:
            # fallback raw sotto
            pass

    # Fallback raw: costruisci URL SDMX REST a mano usando base_url (se disponibile)
    src = get_source(source_id)
    base_url = getattr(src, "base_url", None)
    if not base_url:
        raise RuntimeError("base_url non disponibile per questa source; abilitalo in sources.py per raw fetch.")

    # standard SDMX 2.1: /data/{flowRef}/{key}
    url = base_url.rstrip("/") + f"/data/{bq.dataset}/{bq.series_key}"

    r = requests.get(url, params=bq.params, timeout=60)
    r.raise_for_status()

    return FetchResult(
        dataset=bq.dataset,
        series_key=bq.series_key,
        params=bq.params,
        raw=r.content,
        message=None,
        content_type=r.headers.get("Content-Type"),
    )
