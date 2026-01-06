# statdata

**statdata** è un toolkit Python per il **download guidato di dati macroeconomici via SDMX**, pensato per:
- evitare hard-coding di sigle oscure
- separare chiaramente *fetch dati* da *storage / normalizzazione / analisi*
- funzionare da **libreria**, **CLI** e **building block** per pipeline più grandi

Non normalizza.  
Scarica e restituisce dati **nel modo più trasparente possibile**.

---

## Obiettivi del progetto

- Accesso unificato a fonti statistiche SDMX gratuite
- Scoperta guidata di:
  - dataset (dataflow)
  - dimensioni
  - codici validi
- Costruzione **assistita** delle query (series key)
- Download dati grezzi
- Output semplici e riutilizzabili (Python / JSON / CSV)

Il progetto nasce per evitare questo problema classico:

> “So *cosa* voglio (GDP, CPI, disoccupazione),  
> ma non conosco `B1GQ`, `CLV05_MEUR`, `Y15-74`, `SP00`, ecc.”

---

## Fonti supportate (SDMX)

- Eurostat
- ECB
- OECD (via workaround SDMX-JSON)
- IMF / IMF_DATA / IMF_DATA3
- BIS
- ISTAT
- UNSD (ONU)

Tutte **fonti gratuite e ufficiali**.

---

## Architettura (concettuale)

[ SDMX API ]
↓
discovery.py → dataset / dimensioni / codici
↓
query.py → costruzione series_key guidata
↓
fetch.py → download SDMX
↓
formats.py → output grezzo (no normalizzazione)


Ogni blocco fa **una sola cosa**.

---

## Struttura del progetto

statdata/
└── src/statdata/
├── client.py # wrapper sdmx.Client / clients speciali
├── sources.py # registry fonti SDMX
├── discovery.py # dataset, dimensioni, codelist
├── query.py # query builder guidato
├── fetch.py # download dati
├── formats.py # output (series, json, csv, df)
└── cli.py # interfaccia a linea di comando

---

### Dataset
Un *dataset* è una tabella multidimensionale:  
GDP, CPI, disoccupazione, tassi, ecc.

### Dimensioni
Ogni dataset ha dimensioni come:
- `geo` → paese
- `freq` → frequenza
- `unit` → unità di misura
- `sex`, `age`, ecc.

### Codici
Ogni dimensione accetta **solo certi codici** (es. `IT`, `Q`, `SA`).

### Series key
Una **series key** è una riga specifica del dataset:

Q.THS_PER.T.Y15-74.TOTAL.IT

statdata **ti guida** a costruirla correttamente.

---

## Uso come libreria (Python)

### 1. Scoprire dataset

from statdata.discovery import list_dataflows
list_dataflows("eurostat")

### 2. Scoprire dimensioni

from statdata.discovery import describe_dataset
describe_dataset("eurostat", "LFSQ_UGAD")

### 3. Scoprire codici validi

from statdata.discovery import list_dimension_codes
list_dimension_codes("eurostat", "LFSQ_UGAD", "geo")

### 4. Costruire query guidata

from statdata.query import QuerySpec, build_series_key
spec = QuerySpec(
    source_id="eurostat",
    dataset="LFSQ_UGAD",
    filters={...},
    start="2018-Q1",
    end="2019-Q4",
)
bq = build_series_key(spec)

### 5. Fetch dati

from statdata.fetch import fetch_data
res = fetch_data(bq, "eurostat")

### 6. Output

from statdata.formats import to_minimal_series_dump
dump = to_minimal_series_dump(res)

---

## Query guidata (feature chiave)

Se mancano filtri obbligatori:

GuidedQueryError:
- dimensioni mancanti
- descrizione
- esempi di codici validi


Questo rende il sistema auto-documentante.

---

## CLI (Command Line Interface)

Esempi:

statdata sources
statdata datasets eurostat
statdata describe eurostat LFSQ_UGAD
statdata codes eurostat LFSQ_UGAD geo


Fetch dati:

statdata fetch eurostat LFSQ_UGAD \
  --filter freq=Q --filter geo=IT ...
  --start 2018-Q1 --end 2019-Q4


Output su file:

--out-json out.json
--out-csv out.csv

---

## A cosa serve davvero

statdata è un building block:

per pipeline macroeconomiche

per ETL personalizzati

per modelli quantitativi

per indicatori compositi

Può stare sotto a:

database loader

normalizzatori

indicator builder

sistemi di backtesting


---


## Stato del progetto

Core funzionante

Eurostat validato end-to-end

Altre fonti: in fase di hardening (endpoint inconsistenti SDMX)

## Limitazioni conosciute

SDMX non uniforme: stessa dimensione può chiamarsi geo / GEO / REF_AREA a seconda della fonte/dataset.

Label mancanti: alcune fonti non forniscono nomi umani per dimensioni; spesso solo i codici hanno label.

Time labels: per alcune risposte SDMX, i periodi tempo non arrivano come stringhe; statdata usa fallback basato su start/end + freq (funziona per serie regolari).

Buchi temporali: se una serie ha missing period, il fallback tempo può non rappresentare correttamente i buchi (serve parsing SDMX-JSON o gestione più ricca).

OECD: discovery dataset non passa da sdmx1 ma da endpoint REST + parsing minimale (id+name), quindi describe/codes/fetch possono richiedere test dataset-specifici.

IMF: imf può esporre strutture; per dati si usa imf_data. (Hai escluso imf_data3 per instabilità parsing.)

Performance: list_dimension_codes può essere pesante (es. geo con migliaia di codici).

Rate limiting / timeouts: le API possono limitare o rispondere lentamente; al momento retry/backoff non è centralizzato.

Compatibilità Python: Python 3.13 può richiedere dipendenze aggiuntive (es. packaging).



