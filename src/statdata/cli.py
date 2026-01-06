# src/statdata/cli.py
from __future__ import annotations

import argparse
import json
import sys

from .discovery import describe_dataset, list_dataflows, list_dimension_codes
from .fetch import fetch_data
from .formats import (
    dump_to_csv_file,
    dump_to_json_file,
    to_minimal_series_dump,
    to_simple_json_dict,
)
from .query import GuidedQueryError, QuerySpec, build_series_key
from .sources import list_sources
from .wizard import wizard as wizard_run


def cmd_sources(_args: argparse.Namespace) -> int:
    for s in list_sources():
        print(f"{s.id}")
    return 0


def cmd_datasets(args: argparse.Namespace) -> int:
    d = list_dataflows(args.source, max_items=args.max)
    for x in d:
        if args.contains and args.contains.lower() not in (x.name or "").lower():
            continue
        print(f"{x.id}\t{x.name}")
    return 0


def cmd_describe(args: argparse.Namespace) -> int:
    dims = describe_dataset(args.source, args.dataset)
    for d in dims:
        print(f"{d.position}\t{d.id}\t{d.name}")
    return 0


def cmd_codes(args: argparse.Namespace) -> int:
    codes = list_dimension_codes(args.source, args.dataset, args.dimension, max_items=args.max)
    for c in codes:
        print(f"{c.code}\t{c.name}")
    return 0


def _parse_filters(kvs: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for kv in kvs:
        if "=" not in kv:
            raise ValueError(f"Filtro invalido {kv!r}. Usa formato dim=CODE")
        k, v = kv.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k or not v:
            raise ValueError(f"Filtro invalido {kv!r}. Usa formato dim=CODE")
        out[k] = v
    return out


def cmd_build(args: argparse.Namespace) -> int:
    spec = QuerySpec(
        source_id=args.source,
        dataset=args.dataset,
        filters=_parse_filters(args.filter),
        start=args.start,
        end=args.end,
    )
    try:
        bq = build_series_key(spec, require_single_series=not args.allow_multi)
    except GuidedQueryError as e:
        print(str(e), file=sys.stderr)
        print(json.dumps(e.details, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    print("dataset:", bq.dataset)
    print("key:", bq.series_key)
    if bq.params:
        print("params:", json.dumps(bq.params, ensure_ascii=False))
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    spec = QuerySpec(
        source_id=args.source,
        dataset=args.dataset,
        filters=_parse_filters(args.filter),
        start=args.start,
        end=args.end,
    )
    try:
        bq = build_series_key(spec, require_single_series=True)
    except GuidedQueryError as e:
        print(str(e), file=sys.stderr)
        print(json.dumps(e.details, ensure_ascii=False, indent=2), file=sys.stderr)
        return 2

    res = fetch_data(bq, args.source, parse=not args.raw)
    if args.raw:
        if not res.raw:
            print("raw non disponibile: usa --raw solo con fetch(parse=False) oppure abilita fallback raw.", file=sys.stderr)
            return 3
        sys.stdout.buffer.write(res.raw)
        return 0

    dump = to_minimal_series_dump(res)

    if args.out_json:
        dump_to_json_file(dump, args.out_json)
    if args.out_csv:
        dump_to_csv_file(dump, args.out_csv)

    if args.print_json:
        print(json.dumps(to_simple_json_dict(dump), ensure_ascii=False, indent=2))
    else:
        for p in dump.points[: args.head]:
            print(f"{p.period}\t{p.value}")
        if len(dump.points) > args.head:
            print(f"... ({len(dump.points)} points)")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="statdata", description="SDMX data fetcher.")
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("sources", help="List sources.")
    ps.set_defaults(fn=cmd_sources)

    pd = sub.add_parser("datasets", help="List datasets (dataflows) for a source.")
    pd.add_argument("source")
    pd.add_argument("--max", type=int, default=200)
    pd.add_argument("--contains", default="", help="Filter by substring in dataset name.")
    pd.set_defaults(fn=cmd_datasets)

    pds = sub.add_parser("describe", help="Describe dataset dimensions.")
    pds.add_argument("source")
    pds.add_argument("dataset")
    pds.set_defaults(fn=cmd_describe)

    pc = sub.add_parser("codes", help="List codes for a dimension of a dataset.")
    pc.add_argument("source")
    pc.add_argument("dataset")
    pc.add_argument("dimension")
    pc.add_argument("--max", type=int, default=50)
    pc.set_defaults(fn=cmd_codes)

    pb = sub.add_parser("build", help="Build a series key from filters.")
    pb.add_argument("source")
    pb.add_argument("dataset")
    pb.add_argument("--filter", action="append", default=[], help="dim=CODE (repeatable)")
    pb.add_argument("--start", default=None)
    pb.add_argument("--end", default=None)
    pb.add_argument("--allow-multi", action="store_true", help="Allow wildcard (*) for missing dims.")
    pb.set_defaults(fn=cmd_build)

    pf = sub.add_parser("fetch", help="Fetch data for a single series.")
    pf.add_argument("source")
    pf.add_argument("dataset")
    pf.add_argument("--filter", action="append", default=[], help="dim=CODE (repeatable)")
    pf.add_argument("--start", default=None)
    pf.add_argument("--end", default=None)
    pf.add_argument("--head", type=int, default=10)
    pf.add_argument("--print-json", action="store_true")
    pf.add_argument("--out-json", default=None)
    pf.add_argument("--out-csv", default=None)
    pf.add_argument("--raw", action="store_true", help="Output raw SDMX bytes (no parse).")
    pf.set_defaults(fn=cmd_fetch)

    pw = sub.add_parser("wizard", help="Interactive wizard to build a query and fetch data.")
    pw.set_defaults(fn=lambda _args: wizard_run())

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
