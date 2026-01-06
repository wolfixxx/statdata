# src/statdata/wizard.py
from __future__ import annotations

import json
import os
import re
from typing import Optional

import requests

from .discovery import describe_dataset, list_dataflows, list_dimension_codes
from .fetch import fetch_data
from .formats import dump_to_csv_file, dump_to_json_file, to_minimal_series_dump
from .query import GuidedQueryError, QuerySpec, build_series_key
from .sources import list_sources

CTX_FILE = ".statdata_wizard.json"


def _load_ctx() -> dict:
    if os.path.exists(CTX_FILE):
        try:
            with open(CTX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_ctx(ctx: dict) -> None:
    try:
        with open(CTX_FILE, "w", encoding="utf-8") as f:
            json.dump(ctx, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _normalize_period(s: str) -> str:
    s = s.strip()
    if not s:
        return s

    # Autocorrezione: 25-12-01 -> 2025-12-01 (assume 2000+)
    if re.match(r"^\d{2}-\d{2}-\d{2}$", s):
        yy, mm, dd = s.split("-")
        s = f"20{yy}-{mm}-{dd}"

    # Autocorrezione: 25-12 -> 2025-12
    if re.match(r"^\d{2}-\d{2}$", s):
        yy, mm = s.split("-")
        s = f"20{yy}-{mm}"

    # Autocorrezione: 25 -> 2025
    if re.match(r"^\d{2}$", s):
        s = f"20{s}"

    return s


def _validate_period(s: str) -> bool:
    # accetta: YYYY, YYYY-MM, YYYY-MM-DD, YYYY-Qn
    if not s:
        return True
    return bool(re.match(r"^\d{4}$|^\d{4}-\d{2}$|^\d{4}-\d{2}-\d{2}$|^\d{4}-Q[1-4]$", s))


def _ask(prompt: str, default: Optional[str] = None) -> str:
    if default:
        prompt = f"{prompt} [{default}] "
    else:
        prompt = f"{prompt} "
    s = input(prompt).strip()
    return s if s else (default or "")


def _choose_from_list(title: str, items: list[tuple[str, str]], *, default_id: str | None = None) -> str:
    """
    items: [(id, name)]
    Consente:
      - selezione per numero
      - inserimento id diretto
      - ricerca (scrivi /testo)
    """
    print(f"\n{title}")
    view = items[:30]
    for i, (iid, name) in enumerate(view, start=1):
        print(f"{i:>2}. {iid}\t{name}")
    if len(items) > len(view):
        print(f"... (mostrati {len(view)} su {len(items)})")

    while True:
        s = _ask("Seleziona (numero / id / /cerca):", default_id).strip()
        if not s:
            continue
        if s.startswith("/"):
            q = s[1:].strip().lower()
            hits = [(iid, name) for (iid, name) in items if q in (name or "").lower() or q in iid.lower()]
            if not hits:
                print("Nessun match.")
                continue
            view = hits[:30]
            print("\nRisultati:")
            for i, (iid, name) in enumerate(view, start=1):
                print(f"{i:>2}. {iid}\t{name}")
            if len(hits) > len(view):
                print(f"... (mostrati {len(view)} su {len(hits)})")
            continue
        if s.isdigit():
            idx = int(s)
            if 1 <= idx <= len(view):
                return view[idx - 1][0]
            print("Numero fuori range.")
            continue
        # id diretto
        return s


def _pick_code(source_id: str, dataset: str, dim_id: str) -> str:
    """
    Mostra esempi e permette ricerca. Restituisce un CODE.
    """
    print(f"\nDimensione: {dim_id}")
    print("Suggerimento: puoi cercare scrivendo /testo (es. /italy, /usd, /daily)")

    # primo batch
    codes = list_dimension_codes(source_id, dataset, dim_id, max_items=50)
    view = [(c.code, c.name or "") for c in codes]
    if not view:
        # dimensione senza codelist (capita)
        return _ask(f"Inserisci valore per {dim_id} (nessuna lista disponibile):").strip()

    for i, (code, name) in enumerate(view, start=1):
        print(f"{i:>2}. {code}\t{name}")

    while True:
        s = _ask(f"Seleziona {dim_id} (numero / CODE / /cerca):").strip()
        if not s:
            continue
        if s.startswith("/"):
            q = s[1:].strip().lower()
            # usa batch più grande per cercare meglio
            big = list_dimension_codes(source_id, dataset, dim_id, max_items=500)
            hits = [(c.code, c.name or "") for c in big if q in (c.name or "").lower() or q in c.code.lower()]
            if not hits:
                print("Nessun match.")
                continue
            view = hits[:50]
            print("\nRisultati:")
            for i, (code, name) in enumerate(view, start=1):
                print(f"{i:>2}. {code}\t{name}")
            if len(hits) > len(view):
                print(f"... (mostrati {len(view)} su {len(hits)})")
            continue
        if s.isdigit():
            idx = int(s)
            if 1 <= idx <= len(view):
                return view[idx - 1][0]
            print("Numero fuori range.")
            continue
        return s  # CODE diretto


def _pretty_http_error(e: Exception) -> str:
    if isinstance(e, requests.HTTPError):
        r = getattr(e, "response", None)
        if r is not None:
            return f"HTTP {r.status_code} - {r.url}"
    return str(e)


def wizard() -> int:
    ctx = _load_ctx()

    # 1) Source
    sources = list_sources()
    src_items = [(s.id, getattr(s, "name", s.id)) for s in sources]
    default_src = ctx.get("source_id")
    source_id = _choose_from_list("Sorgenti disponibili:", src_items, default_id=default_src)
    ctx["source_id"] = source_id
    _save_ctx(ctx)

    # 2) Dataset
    print("\nCarico dataset (dataflows)...")
    dataflows = list_dataflows(source_id, max_items=2000)
    df_items = [(d.id, d.name or "") for d in dataflows]
    default_ds = ctx.get("dataset") if ctx.get("source_id") == source_id else None
    dataset = _choose_from_list("Dataset disponibili (usa /cerca):", df_items, default_id=default_ds)
    ctx["dataset"] = dataset
    _save_ctx(ctx)

    # 3) Dimensioni richieste
    dims = describe_dataset(source_id, dataset)
    dim_ids = [d.id for d in dims if d.id and d.id != "TIME_PERIOD"]

    print("\nDimensioni richieste per una serie univoca:")
    print(", ".join(dim_ids) if dim_ids else "(nessuna)")

    filters: dict[str, str] = {}
    for did in dim_ids:
        filters[did] = _pick_code(source_id, dataset, did)

    # 4) Date
    print("\nIntervallo date (opzionale ma consigliato).")
    start = _normalize_period(_ask("start (YYYY-MM-DD / YYYY-MM / YYYY / YYYY-Qn):", ctx.get("start")))
    end = _normalize_period(_ask("end   (YYYY-MM-DD / YYYY-MM / YYYY / YYYY-Qn):", ctx.get("end")))

    if start and not _validate_period(start):
        print("Formato start non valido. Esempi: 2025-12-01, 2025-12, 2025, 2025-Q4")
        return 2
    if end and not _validate_period(end):
        print("Formato end non valido. Esempi: 2025-12-10, 2025-12, 2025, 2025-Q4")
        return 2

    ctx["start"] = start
    ctx["end"] = end
    _save_ctx(ctx)

    # 5) Output
    fmt = _ask("Output (print/csv/json):", ctx.get("output", "print")).lower()
    if fmt not in ("print", "csv", "json"):
        fmt = "print"
    ctx["output"] = fmt
    _save_ctx(ctx)

    out_path = ""
    if fmt in ("csv", "json"):
        out_path = _ask("Percorso file output:", ctx.get("out_path", f"out.{fmt}"))
        ctx["out_path"] = out_path
        _save_ctx(ctx)

    # 6) Build query + fetch
    spec = QuerySpec(source_id=source_id, dataset=dataset, filters=filters, start=start or None, end=end or None)

    try:
        bq = build_series_key(spec, require_single_series=True)
    except GuidedQueryError as e:
        print("\nERRORE: filtri incompleti o ambigui.")
        print(str(e))
        print(json.dumps(e.details, ensure_ascii=False, indent=2))
        return 2
    except Exception as e:
        print("\nERRORE build query:", e)
        return 2

    print("\nQuery costruita:")
    print("dataset:", bq.dataset)
    print("key:", bq.series_key)
    if bq.params:
        print("params:", bq.params)

    try:
        res = fetch_data(bq, source_id, parse=True)
        dump = to_minimal_series_dump(res)
    except requests.HTTPError as e:
        msg = _pretty_http_error(e)
        if "service/data" in msg and "404" in msg:
            print("\nERRORE: la serie non esiste (combinazione filtri non valida).")
            print("Dettaglio:", msg)
            print("Suggerimento: cambia EXR_TYPE/EXR_SUFFIX o altri codici e riprova.")
            return 3
        print("\nERRORE HTTP:", msg)
        return 3
    except Exception as e:
        print("\nERRORE fetch/parse:", e)
        return 3

    if not dump.points:
        print("\nNESSUN DATO trovato per questa combinazione / intervallo date.")
        return 4

    # 7) Output finale
    if fmt == "print":
        print("\nRisultato (prime 20 righe):")
        for p in dump.points[:20]:
            print(f"{p.period}\t{p.value}")
        if len(dump.points) > 20:
            print(f"... ({len(dump.points)} punti)")
        return 0

    if fmt == "csv":
        dump_to_csv_file(dump, out_path)
        print(f"\nScritto CSV: {out_path}")
        return 0

    if fmt == "json":
        dump_to_json_file(dump, out_path)
        print(f"\nScritto JSON: {out_path}")
        return 0

    return 0
