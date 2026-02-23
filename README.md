# GBIF Advanced Downloader v2

A desktop GUI application for downloading, filtering, and exporting occurrence records from the [GBIF](https://www.gbif.org/) (Global Biodiversity Information Facility) database — with a focus on entomological collections.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)
![Platform](https://img.shields.io/badge/Platform-Windows%20|%20macOS%20|%20Linux-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)
![GBIF API](https://img.shields.io/badge/Data%20Source-GBIF%20API%20v1-orange?logo=data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZmlsbD0id2hpdGUiIGQ9Ik0xMiAyQzYuNDggMiAyIDYuNDggMiAxMnM0LjQ4IDEwIDEwIDEwIDEwLTQuNDggMTAtMTBTMTcuNTIgMiAxMiAyem0wIDE4Yy00LjQyIDAtOC0zLjU4LTgtOHMzLjU4LTggOC04IDggMy41OCA4IDgtMy41OCA4LTggOHoiLz48L3N2Zz4=)

## Features

- **Genus-level or species-level queries** — search by genus (e.g., *Nebria*) or filter specific epithets (e.g., `germarii, castanea`)
- **Museum-only toggle** — choose between downloading only preserved specimens (museum data) or all observation types (citizen science, human observations, etc.)
- **Configurable filters:**
  - Year range (start year)
  - Coordinate uncertainty threshold (meters)
  - Require/exclude records missing year, elevation, or uncertainty data
- **Color-coded Excel output** — records with unknown coordinate uncertainty are highlighted in yellow
- **Year-by-year pagination** — handles large datasets by iterating through years and paginating within each, respecting GBIF's 100k offset limit
- **Robust networking** — automatic retries with exponential backoff, rate-limit (HTTP 429) handling, configurable timeouts
- **Record deduplication** — prevents duplicate occurrences via GBIF occurrence keys
- **Interruptible** — stop the download at any time and keep the records collected so far
- **Export to Excel (.xlsx) or CSV**

## Screenshot

The application provides a clean tkinter interface with labeled sections for taxonomy, spatial/temporal parameters, and inclusion/exclusion rules:

```
┌─────────────────────────────────────────────┐
│        GBIF Advanced Downloader v2          │
├─────────────────────────────────────────────┤
│ 1. Taxonomy                                 │
│    Genus: [Nebria          ]  [?]           │
│    Species (Optional): [   ]  [?]           │
├─────────────────────────────────────────────┤
│ 2. Temporal & Spatial Parameters            │
│    Start Year: [1800       ]  [?]           │
│    Uncertainty Limit (m): [1000]  [?]       │
├─────────────────────────────────────────────┤
│ 3. Inclusion/Exclusion Rules                │
│    ☑ Museum data only (Preserved Specimen)  │
│    ☑ Exclude records without YEAR           │
│    ☑ Exclude records without ELEVATION      │
│    ☑ Keep records with unknown uncertainty  │
├─────────────────────────────────────────────┤
│ Status: Ready                               │
│ [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░] 85%    │
│ Year 2019 | Valid: 12,450 | Read: 38,200    │
├─────────────────────────────────────────────┤
│  [ START DOWNLOAD ]    [ STOP ]             │
└─────────────────────────────────────────────┘
```

## Installation

### Option A: Portable Windows Executable (no Python required)

1. Go to the [Releases](https://github.com/Camponotus-vagus/nebria_downloader_v2/releases) page
2. Download `GBIF_Downloader_v2.exe`
3. Double-click to run

> **Note:** Windows Defender may show a SmartScreen warning on first launch (common with PyInstaller builds). Click *"More info"* → *"Run anyway"*.

### Option B: Run from source (any OS)

```bash
# Clone the repository
git clone https://github.com/Camponotus-vagus/nebria_downloader_v2.git
cd nebria_downloader_v2

# Install dependencies
pip install -r requirements.txt

# Run
python gbif_nebria_downloader_v2.py
```

**Requirements:** Python 3.10+, tkinter (included with most Python distributions)

## Usage

1. **Set the genus** — type the genus name (default: *Nebria*)
2. **Optionally filter species** — comma-separated list of specific epithets
3. **Configure parameters:**
   - *Start Year*: earliest year to include (default: 1800)
   - *Uncertainty Limit*: max coordinate uncertainty in meters (default: 1000m)
4. **Toggle inclusion rules:**
   - **Museum data only**: when enabled, only downloads `PRESERVED_SPECIMEN` records; when disabled, downloads all basis-of-record types and adds a `Basis of Record` column to the output
   - **Exclude without year/elevation**: discard records missing these fields
   - **Keep unknown uncertainty**: retain records where uncertainty is not reported (highlighted in yellow in Excel)
5. Click **START DOWNLOAD** and wait for completion
6. Choose where to save the `.xlsx` or `.csv` file

## Output Format

| Column | Description |
|--------|-------------|
| Year | Collection year |
| Date | Full event date |
| Latitude / Longitude | Decimal coordinates |
| Uncertainty (m) | Coordinate uncertainty in meters (blank = unknown) |
| Elevation (m) | Elevation in meters |
| Locality | Locality description |
| Genus / Species / Scientific Name | Taxonomic fields |
| Institution | Institution code (e.g., MZUF, NHMW) |
| Catalog No | Specimen catalog number |
| Recorded By | Collector name(s) |
| Country | Country of occurrence |
| Basis of Record | *Only when museum-only is disabled* — observation type |
| Link | Direct link to the GBIF occurrence page |

## Building the Windows Executable

The `.exe` is built automatically via GitHub Actions on every push to `main`. To trigger a manual build:

1. Go to **Actions** → **Build Windows EXE**
2. Click **Run workflow**
3. Download the artifact from the completed run

The workflow uses PyInstaller on a `windows-latest` runner with Python 3.12.

## Technical Details

- **GBIF API v1** — uses `/v1/species/match` for taxon lookup and `/v1/occurrence/search` for paginated occurrence queries
- **Year-by-year iteration** — avoids hitting the GBIF 100,000 offset hard limit by partitioning queries by year
- **Retry logic** — up to 5 retries per request with exponential backoff; respects `Retry-After` headers on HTTP 429
- **Thread-safe GUI** — all UI updates from the download thread go through `root.after()` to prevent tkinter race conditions
- **Deduplication** — occurrence keys are tracked in a set to prevent duplicate records across paginated responses

## Dependencies

| Package | Purpose |
|---------|---------|
| `requests` | HTTP client for GBIF API |
| `pandas` | Data manipulation and export |
| `openpyxl` | Excel writing with conditional formatting |
| `tkinter` | GUI framework (bundled with Python) |

## License

This project is released under the [MIT License](LICENSE).

## Acknowledgements

- Occurrence data provided by [GBIF.org](https://www.gbif.org/)
- Built with the [GBIF API v1](https://www.gbif.org/developer/summary)
