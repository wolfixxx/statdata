# src/statdata/formats.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .fetch import FetchResult


def _gen_quarters(start: str, end: str) -> list[str]:
    sy, sq = start.split("-Q")
    ey, eq = end.split("-Q")
    sy, sq, ey, eq = int(sy), int(sq), int(ey), int(eq)

    out = []
    y, q = sy, sq
    while (y < ey) or (y == ey and q <= eq):
        out.append(f"{y}-Q{q}")
        q += 1
        if q == 5:
            q = 1
            y += 1
    return out


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
    if res.message is None:
        raise ValueError("FetchResult.message è None. Esegui fetch_data(..., parse=True).")

    msg = res.message
    data = getattr(msg, "data", None)
    if not data:
        return SeriesDump(res.dataset, res.series_key, [], {"note": "No data in message"})

    ds = data[0]
    series_map = getattr(ds, "series", None) or {}
    if not series_map:
        return SeriesDump(res.dataset, res.series_key, [], {"note": "No series in dataset"})

    first_key = next(iter(series_map.keys()))
    ser = series_map[first_key]

    # Prendi osservazioni in modo robusto (sdmx1 varia)
    obs = None
    for attr in ("obs", "observations"):
        if hasattr(ser, attr):
            obs = getattr(ser, attr)
            break
    if obs is None and hasattr(ds, "obs"):
        obs = getattr(ds, "obs")

    if not obs:
        return SeriesDump(
            res.dataset,
            res.series_key,
            [],
            {"series_count": len(series_map), "obs_count": 0, "note": "No observations found"},
        )

    # Se l'indice del tempo è numerico, prova a risalire alle etichette tempo dal dataset
    time_labels = None
    start = res.params.get("startPeriod")
    end = res.params.get("endPeriod")

    # mapping per serie trimestrali
    if start and end and res.series_key.startswith("Q."):
        time_labels = _gen_quarters(start, end)
    
    

    points: list[SeriesPoint] = []

    if isinstance(obs, dict):
        items = obs.items()
    elif isinstance(obs, list):
        items = enumerate(obs)
    else:
        # fallback: prova a iterare
        try:
            items = list(obs.items())  # type: ignore[attr-defined]
        except Exception:
            items = []

    for t_key, ob in items:
        # t_key può essere int oppure stringa tipo "0"
        period = str(t_key)
        idx = None
        if isinstance(t_key, int):
            idx = t_key
        elif isinstance(t_key, str) and t_key.isdigit():
            idx = int(t_key)

        if idx is not None and isinstance(time_labels, list) and 0 <= idx < len(time_labels):
            period = str(time_labels[idx])

        val = getattr(ob, "value", None)
        try:
            val = float(val) if val is not None else None
        except Exception:
            val = None

        points.append(SeriesPoint(period=period, value=val))

    meta = {"series_count": len(series_map), "obs_count": len(points)}
    return SeriesDump(dataset=res.dataset, series_key=res.series_key, points=points, meta=meta)
