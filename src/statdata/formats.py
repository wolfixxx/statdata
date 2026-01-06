# src/statdata/formats.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
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


def _gen_years(start: str, end: str) -> list[str]:
    sy = int(str(start)[:4])
    ey = int(str(end)[:4])
    return [str(y) for y in range(sy, ey + 1)]


def _gen_months(start: str, end: str) -> list[str]:
    # start/end: "YYYY-MM"
    sy, sm = start.split("-")
    ey, em = end.split("-")
    y, m = int(sy), int(sm)
    ey, em = int(ey), int(em)

    out = []
    while (y < ey) or (y == ey and m <= em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m == 13:
            m = 1
            y += 1
    return out

def _gen_days(start: str, end: str) -> list[str]:
    # start/end: YYYY-MM-DD
    d0 = datetime.fromisoformat(start)
    d1 = datetime.fromisoformat(end)

    out = []
    d = d0
    while d <= d1:
        out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
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

    # mapping per serie temporali
    if start and end:
        if res.series_key.startswith("D."):
            time_labels = _gen_days(start, end)
        elif res.series_key.startswith("Q."):
            time_labels = _gen_quarters(start, end)
        elif res.series_key.startswith("A."):
            time_labels = _gen_years(start, end)
        elif res.series_key.startswith("M."):
            time_labels = _gen_months(start, end)
    


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

def to_simple_json_dict(dump: SeriesDump) -> dict:
    return {
        "dataset": dump.dataset,
        "series_key": dump.series_key,
        "meta": dump.meta,
        "data": [{"period": p.period, "value": p.value} for p in dump.points],
    }

def to_dataframe(dump: SeriesDump):
    import pandas as pd  # import locale: pandas diventa dipendenza opzionale

    return pd.DataFrame(
        [{"period": p.period, "value": p.value} for p in dump.points]
    )

def dump_to_json_file(dump: SeriesDump, path: str) -> None:
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(to_simple_json_dict(dump), f, ensure_ascii=False, indent=2)


def dump_to_csv_file(dump: SeriesDump, path: str) -> None:
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["period", "value"])
        for p in dump.points:
            w.writerow([p.period, p.value])
