# src/statdata/formats.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .fetch import FetchResult


@dataclass(frozen=True)
class SeriesPoint:
    period: str          # stringa così com’è (es. "2018-Q1")
    value: float | None


@dataclass(frozen=True)
class SeriesDump:
    dataset: str
    series_key: str
    points: list[SeriesPoint]
    meta: dict[str, Any]


def to_raw_bytes(res: FetchResult) -> bytes:
    if res.raw is not None:
        return res.raw
    # Se abbiamo message ma non raw, lasciamo che l’utente usi res.message direttamente
    raise ValueError("Questo FetchResult non contiene raw bytes (parse=True). Usa res.message oppure fetch(parse=False).")


def to_minimal_series_dump(res: FetchResult) -> SeriesDump:
    """
    Estrae una singola serie (quella richiesta) come lista (period, value).
    Non fa normalizzazione: prende tempo e valore come sono.
    """
    if res.message is None:
        raise ValueError("FetchResult.message è None. Esegui fetch_data(..., parse=True).")

    msg = res.message

    # Struttura tipica: msg.data[0].series è dict {SeriesKey: Series}
    data = getattr(msg, "data", None)
    if not data:
        return SeriesDump(res.dataset, res.series_key, [], {"note": "No data in message"})

    ds = data[0]
    series_map = getattr(ds, "series", None) or {}
    if not series_map:
        return SeriesDump(res.dataset, res.series_key, [], {"note": "No series in dataset"})

    # prendi la prima (dovrebbe essercene una sola se la key era completa)
    first_key = next(iter(series_map.keys()))
    ser = series_map[first_key]

    obs = getattr(ser, "obs", None) or {}
    # obs: dict {time_key: Observation}
    points: list[SeriesPoint] = []
    for t_key, ob in obs.items():
        # t_key spesso è tipo 0,1,2... oppure un oggetto tempo; proviamo str()
        period = str(t_key)
        val = getattr(ob, "value", None)
        try:
            val = float(val) if val is not None else None
        except Exception:
            val = None
        points.append(SeriesPoint(period=period, value=val))

    meta = {
        "series_count": len(series_map),
        "obs_count": len(points),
    }
    return SeriesDump(dataset=res.dataset, series_key=res.series_key, points=points, meta=meta)
