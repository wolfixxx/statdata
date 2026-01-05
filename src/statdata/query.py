# src/statdata/query.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .client import get_client
from .discovery import describe_dataset, list_dimension_codes


class GuidedQueryError(ValueError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}

@dataclass(frozen=True)
class QuerySpec:
    source_id: str
    dataset: str
    filters: dict[str, str]          # es. {"geo":"IT","freq":"Q",...}
    start: str | None = None         # "2015" o "2015-Q1" ecc (grezzo)
    end: str | None = None
    format: str | None = None        # "sdmx-ml", "sdmx-json" (opzionale)


@dataclass(frozen=True)
class BuiltQuery:
    dataset: str
    series_key: str                  # es. "Q.CA.IT...."
    params: dict[str, Any]           # per fetch (start/end ecc)


def _pick_name(obj: Any) -> str:
    nm = getattr(obj, "name", None)
    if isinstance(nm, dict):
        return nm.get("en") or next(iter(nm.values()), "")
    return str(nm) if nm is not None else ""


def build_series_key(spec: QuerySpec, *, require_single_series: bool = True) -> BuiltQuery:
    """
    Costruisce una series_key SDMX corretta (ordine dimensioni) usando i metadata del dataset.
    Se require_single_series=True, richiede che tutte le dimensioni (tranne TIME) siano fissate.
    """
    c = get_client(spec.source_id)

    # Recupera la struttura: determina ordine dimensioni e (se presenti) codelist
    # sdmx1: dsd(dataset_id=...) oppure datastructure(...). Usiamo dsd.
    msg = c.datastructure(spec.dataset)

    # Estrai DSD
    dsd = None
    for attr in ("structure", "datastructure", "structures"):
        if hasattr(msg, attr):
            dsd = getattr(msg, attr)
            break
    if dsd is None:
        # fallback comune: msg.structure è dict-like
        dsd = getattr(msg, "structure", None)

    # dsd può contenere più strutture; prendiamo la prima disponibile
    # In sdmx1 tipico: msg.structure["<id>"] o msg.structure.datastructure
    dsd_obj = None
    if isinstance(dsd, dict) and dsd:
        dsd_obj = next(iter(dsd.values()))
    else:
        dsd_obj = dsd

    if dsd_obj is None:
        raise RuntimeError("Impossibile ottenere la DataStructure per questo dataset.")

    # Dimensioni in ordine: di solito dsd_obj.dimensions.observation o series
    dims = None
    for path in (
        ("dimensions", "series"),
        ("dimensions", "observation"),
        ("dimensions",),
    ):
        cur = dsd_obj
        ok = True
        for p in path:
            if not hasattr(cur, p):
                ok = False
                break
            cur = getattr(cur, p)
        if ok and cur:
            dims = cur
            break

    if not dims:
        raise RuntimeError("DSD non contiene dimensioni leggibili.")

    # dims spesso è list-like di Dimension
    dim_list = list(dims)

    # identifica TIME (se presente)
    time_ids = {"TIME_PERIOD", "TIME", "time"}
    non_time_dims = [d for d in dim_list if getattr(d, "id", "") not in time_ids]

    # Validazione: tutte le dimensioni richieste esistono
    dim_ids = {getattr(d, "id", "") for d in dim_list}
    unknown = [k for k in spec.filters.keys() if k not in dim_ids]
    if unknown:
        raise KeyError(f"Filtri su dimensioni inesistenti: {unknown}. Dimensioni valide: {sorted(dim_ids)}")

    # Costruzione key: per ogni dimensione (non-time), prendi codice o '*'
    key_parts: list[str] = []
    missing_required: list[str] = []

    for d in non_time_dims:
        did = getattr(d, "id", "")
        if did in spec.filters:
            code = spec.filters[did]
            key_parts.append(code)
        else:
            key_parts.append("*")
            if require_single_series:
                missing_required.append(did)

    if missing_required:
        guidance = {}

        dims_info = describe_dataset(spec.source_id, spec.dataset)
        dims_map = {d.id: d for d in dims_info}

        for did in missing_required:
            codes = list_dimension_codes(
                spec.source_id,
                spec.dataset,
                did,
                max_items=10,
            )
            guidance[did] = {
                "description": dims_map.get(did).name if did in dims_map else "",
                "examples": [(c.code, c.name) for c in codes],
            }

        raise GuidedQueryError(
            message="Mancano filtri obbligatori per costruire una serie univoca.",
            details=guidance,
        )

    series_key = ".".join(key_parts)

    params: dict[str, Any] = {}
    if spec.start:
        params["startPeriod"] = spec.start
    if spec.end:
        params["endPeriod"] = spec.end
    # format: lo gestiremo nel fetch; qui lo passiamo solo come intenzione
    if spec.format:
        params["format"] = spec.format

    return BuiltQuery(dataset=spec.dataset, series_key=series_key, params=params)
