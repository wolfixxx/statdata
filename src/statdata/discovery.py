# src/statdata/discovery.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .client import get_client


def _pick_name(obj) -> str:
    nm = getattr(obj, "name", None)
    if isinstance(nm, dict):
        return nm.get("en") or next(iter(nm.values()), "")
    return str(nm) if nm is not None else ""


@dataclass(frozen=True)
class DataflowInfo:
    id: str
    name: str


def list_dataflows(source_id: str, *, max_items: int | None = 200) -> list[DataflowInfo]:
    """
    Scarica e lista i Dataflow (dataset) disponibili per una fonte.
    Ritorna una lista di (id, name) leggibili.
    """
    c = get_client(source_id)

    # sdmx1: request dataflow list
    msg = c.dataflow()

    dflows = getattr(msg, "dataflow", None) or getattr(msg, "dataflows", None)
    if dflows is None:
        # fallback: tenta accesso generico
        dflows = getattr(msg, "dataflow", {})

    out: list[DataflowInfo] = []

    # msg.dataflow di solito è dict-like: {id: DataflowDefinition}
    if isinstance(dflows, dict):
        items: Iterable[tuple[str, object]] = dflows.items()
    else:
        # oppure lista/iterabile di oggetti con .id
        items = ((getattr(df, "id", ""), df) for df in dflows)

    for df_id, df in items:
        if not df_id:
            df_id = getattr(df, "id", "") or ""
        # name può essere dict di lingue o oggetto i18n; qui prendiamo una stringa “umana”
        nm = getattr(df, "name", None)
        if isinstance(nm, dict):
            name = nm.get("en") or next(iter(nm.values()), "")
        else:
            name = str(nm) if nm is not None else ""
        out.append(DataflowInfo(id=str(df_id), name=name))

        if max_items is not None and len(out) >= max_items:
            break

    return out

from dataclasses import dataclass


@dataclass(frozen=True)
class DimensionInfo:
    id: str
    name: str
    position: int

@dataclass(frozen=True)
class CodeInfo:
    code: str
    name: str


def describe_dataset(source_id: str, dataset: str) -> list[DimensionInfo]:
    """
    Ritorna le dimensioni del dataset in ordine (per costruire la series_key),
    con nomi leggibili.
    """
    c = get_client(source_id)
    msg = c.datastructure(dataset)

    # Prendi la prima DSD disponibile
    dsd = getattr(msg, "structure", None)
    if isinstance(dsd, dict) and dsd:
        dsd_obj = next(iter(dsd.values()))
    else:
        dsd_obj = dsd
    if dsd_obj is None:
        raise RuntimeError("DSD non disponibile.")

    dims = None
    for path in (("dimensions", "series"), ("dimensions", "observation"), ("dimensions",)):
        cur = dsd_obj
        ok = True
        for p in path:
            if not hasattr(cur, p):
                ok = False
                break
            cur = getattr(cur, p)
        if ok and cur:
            dims = list(cur)
            break
    if not dims:
        raise RuntimeError("Dimensioni non disponibili nel DSD.")

    out: list[DimensionInfo] = []
    for i, d in enumerate(dims):
        did = getattr(d, "id", "")
        out.append(DimensionInfo(id=str(did), name=_pick_name(d), position=i))
    return out


def list_dimension_codes(source_id: str, dataset: str, dim_id: str, *, max_items: int | None = 200) -> list[CodeInfo]:
    """
    Ritorna i codici ammessi per una dimensione del dataset (con label).
    Nota: non tutte le fonti espongono label complete per ogni code in modo uniforme.
    """
    c = get_client(source_id)
    msg = c.datastructure(dataset)

    dsd = getattr(msg, "structure", None)
    if isinstance(dsd, dict) and dsd:
        dsd_obj = next(iter(dsd.values()))
    else:
        dsd_obj = dsd
    if dsd_obj is None:
        raise RuntimeError("DSD non disponibile.")

    # trova la dimensione e la sua codelist/enumeration
    dims = []
    for path in (("dimensions", "series"), ("dimensions", "observation"), ("dimensions",)):
        cur = dsd_obj
        ok = True
        for p in path:
            if not hasattr(cur, p):
                ok = False
                break
            cur = getattr(cur, p)
        if ok and cur:
            dims = list(cur)
            break

    target = None
    for d in dims:
        if getattr(d, "id", None) == dim_id:
            target = d
            break
    if target is None:
        raise KeyError(f"Dimensione {dim_id!r} non trovata in dataset {dataset!r}")

    enum = getattr(target, "local_representation", None)
    enum = getattr(enum, "enumerated", None) if enum is not None else None
    if enum is None:
        # dimensione libera/non enumerata
        return []


    # enum è spesso una Codelist con .items() o .codes
    codes: list[CodeInfo] = []

    # Caso 1: enum è un dict {code: obj}
    if isinstance(enum, dict):
        for code, obj in enum.items():
            codes.append(CodeInfo(code=str(code), name=_pick_name(obj)))
            if max_items is not None and len(codes) >= max_items:
                break
        return codes

    # Caso 2: enum ha .items() (codelist dict-like)
    items_attr = getattr(enum, "items", None)
    if callable(items_attr):
        for code, obj in enum.items():
            codes.append(CodeInfo(code=str(code), name=_pick_name(obj)))
            if max_items is not None and len(codes) >= max_items:
                break
        return codes

    # Caso 3: enum ha .codes (lista)
    codes_attr = getattr(enum, "codes", None)
    if codes_attr is not None:
        for obj in codes_attr:
            codes.append(CodeInfo(code=str(getattr(obj, "id", "")), name=_pick_name(obj)))
            if max_items is not None and len(codes) >= max_items:
                break
        return codes

    return []


    # fallback
    if hasattr(enum, "codes"):
        for obj in enum.codes:
            codes.append(CodeInfo(code=str(getattr(obj, "id", "")), name=_pick_name(obj)))
            if max_items is not None and len(codes) >= max_items:
                break
    return codes
