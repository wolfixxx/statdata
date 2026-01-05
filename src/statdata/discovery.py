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
    c = get_client(source_id)
    msg = c.datastructure(dataset)

    dsd = getattr(msg, "structure", None)
    if isinstance(dsd, dict) and dsd:
        dsd_obj = next(iter(dsd.values()))
    else:
        dsd_obj = dsd
    if dsd_obj is None:
        raise RuntimeError("DSD non disponibile.")

    # recupera dimensioni
    dims = []
    for path in (("dimensions", "series"), ("dimensions", "observation"), ("dimensions",)):
        cur = dsd_obj
        for p in path:
            if not hasattr(cur, p):
                break
            cur = getattr(cur, p)
        else:
            if cur:
                dims = list(cur)
                break

    # trova la dimensione richiesta
    target = None
    for d in dims:
        if getattr(d, "id", None) == dim_id:
            target = d
            break

    if target is None:
        raise KeyError(f"Dimensione {dim_id!r} non trovata")

    enum = getattr(target, "local_representation", None)
    enum = getattr(enum, "enumerated", None) if enum is not None else None

    print(f"[DEBUG] enum type: {type(enum)}")

    if enum is None:
        print("[DEBUG] enum=None → nessuna codelist")
        return []

    out: list[CodeInfo] = []

    # CASO A: enum è dict
    if isinstance(enum, dict):
        print(f"[DEBUG] enum dict con {len(enum)} elementi")
        for code, obj in enum.items():
            out.append(CodeInfo(code=str(code), name=_pick_name(obj)))
            if max_items and len(out) >= max_items:
                break
        return out

    # CASO B: enum ha .items()
    if hasattr(enum, "items") and callable(enum.items):
        items = list(enum.items())
        print(f"[DEBUG] enum.items() con {len(items)} elementi")
        for code, obj in items:
            out.append(CodeInfo(code=str(code), name=_pick_name(obj)))
            if max_items and len(out) >= max_items:
                break
        return out

    # CASO C: enum ha .codes
    if hasattr(enum, "codes"):
        codes = list(enum.codes)
        print(f"[DEBUG] enum.codes con {len(codes)} elementi")
        for obj in codes:
            out.append(CodeInfo(code=str(getattr(obj, 'id', '')), name=_pick_name(obj)))
            if max_items and len(out) >= max_items:
                break
        return out
    
    # CASO D: sdmx1 Codelist (spesso enum.items è un dict, NON un metodo)
    items_attr = getattr(enum, "items", None)
    if isinstance(items_attr, dict):
        print(f"[DEBUG] Codelist enum.items dict con {len(items_attr)} elementi")
        for code, obj in items_attr.items():
            out.append(CodeInfo(code=str(code), name=_pick_name(obj)))
            if max_items and len(out) >= max_items:
                break
        return out

    # fallback: enum iterabile (lista di Code)
    if hasattr(enum, "__iter__"):
        seq = list(enum)
        print(f"[DEBUG] Codelist iterabile con {len(seq)} elementi")
        for obj in seq:
            out.append(CodeInfo(code=str(getattr(obj, "id", "")), name=_pick_name(obj)))
            if max_items and len(out) >= max_items:
                break
        return out


    print("[DEBUG] enum presente ma formato non gestito")
    return []
