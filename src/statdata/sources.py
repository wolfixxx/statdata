# src/statdata/sources.py
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Source:
    id: str          # id interno statdata (minuscolo)
    name: str
    sdmx_id: str     # id riconosciuto da sdmx1 (es. ESTAT, ECB, OECD)
    base_url: str
    notes: str = ""


SOURCES: dict[str, Source] = {
    # Eurostat SDMX REST (official)
    "eurostat": Source(
    id="eurostat",
    name="Eurostat",
    sdmx_id="ESTAT",
    base_url="https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/",
    notes="EU official statistics (SDMX 2.1 REST).",
    ),
    # ECB SDMX 2.1 REST (data portal)
    "ecb": Source(
        id="ecb",
        name="European Central Bank",
        sdmx_id="ECB",
        base_url="https://data-api.ecb.europa.eu/service/",
        notes="ECB SDMX 2.1 REST (Data Portal).",
    ),
    # OECD SDMX (often proxied; use official SDMX endpoint)
    "oecd": Source(
        id="oecd",
        name="OECD",
        sdmx_id="OECD",
        base_url="https://stats-nxd.oecd.org/restsdmx/sdmx.ashx/",
        notes="OECD SDMX endpoint.",
    ),
    # IMF SDMX Central
    "imf": Source(
        id="imf",
        name="IMF (SDMX Central)",
        sdmx_id="IMF",
        base_url="https://sdmxcentral.imf.org/ws/public/sdmxapi/rest/",
        notes="IMF SDMX Central public REST API.",
    ),
    # BIS SDMX
    "bis": Source(
        id="bis",
        name="BIS",
        sdmx_id="BIS",
        base_url="https://stats.bis.org/api/v1/",
        notes="BIS public API (SDMX-like).",
    ),
    # ISTAT SDMX
    "istat": Source(
        id="istat",
        name="ISTAT",
        sdmx_id="ISTAT",
        base_url="https://sdmx.istat.it/SDMXWS/rest/",
        notes="Italian official statistics (SDMX).",
    ),
    # UNSD SDMX
    "unsd": Source(
        id="unsd",
        name="UNSD",
        sdmx_id="UNSD",
        base_url="https://sdmx.un.org/ws/public/sdmxapi/rest/",
        notes="United Nations Statistics Division SDMX API.",),}



def list_sources() -> list[Source]:
    return sorted(SOURCES.values(), key=lambda s: s.id)


def get_source(source_id: str) -> Source:
    try:
        return SOURCES[source_id]
    except KeyError as e:
        raise KeyError(f"Unknown source_id={source_id!r}. Available: {', '.join(SOURCES)}") from e
