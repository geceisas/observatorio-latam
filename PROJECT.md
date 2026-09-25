# Project: Observatorio LATAM

## Architecture
Observatorio LATAM is a reproducible Latin American socio-economic and environmental data observatory composed of four decoupled subsystems:
1. **ETL & Data Snapshot Subsystem (`etl/`, `data/`)**:
   - Python-based extraction, harmonization, transformation, statistical validation, deterministic insights generation, and frozen snapshot storage (`2026-09`).
   - Distributes frozen data in `data/snapshots/2026-09/` (CSV, manifest) and `data/public/` (manifest, catalog, countries, coverage, insights, all_observations, individual indicators).
2. **Unified Runtime Server (`server.py`)**:
   - Zero-dependency local runtime server using Python standard library (`http.server`, `threading`, `json`, `urllib`).
   - Serves HTTP 200 on `/` (serving `web/portal/index.html`), `/data/public/*` (snapshot JSON files), and `POST /api/chat` (proxying queries to the verified Python chat engine).
3. **Interactive Web Portal SPA (`web/portal/`)**:
   - Zero-external-dependency, responsive, accessible Single Page Application.
   - Consumes only local `/data/public/*.json` endpoints without browser-side external API calls.
   - Delivers 7 main navigation views, 8 specialized visualizations (including dynamic Composite Index builder and Data Coverage Heatmap), Scrollytelling Martini-glass stories, Okabe-Ito colorblind palette, and trilingual support (ES, PT, EN).
4. **Agentic Chat Engine & Numerical Verifier (`etl/chat_engine.py`, `/api/chat`, `evals/`)**:
   - 5 snapshot tools (`buscar_indicador`, `obtener_serie`, `comparar`, `ranking`, `crear_grafico`).
   - Numerical verifier strictly auditing all numerical tokens against snapshot observations (`unverified_count == 0`).
   - Honest refusal for out-of-catalog topics (`"Dato fuera del catálogo del observatorio · Candidato Data360 MCP"`).
   - Zero-key deterministic execution with 40/40 passing regression evaluations in `evals/run_evals.py`.

```
                  +----------------------------------------------+
                  |         Python ETL Pipeline (etl/)           |
                  |     World Bank API + Calibrated Anchors      |
                  +----------------------+-----------------------+
                                         |
                                         v
                  +----------------------------------------------+
                  |     Frozen Snapshot & Public Distribution    |
                  |   data/snapshots/2026-09/ & data/public/     |
                  +----------------------+-----------------------+
                                         |
                 +-----------------------+-----------------------+
                 |                                               |
                 v                                               v
+----------------------------------+          +----------------------------------+
|     Unified Server (server.py)   |          |     Python Chat Engine (etl/)    |
|   - GET / (web/portal/)          |<-------->|   - 5 Snapshot Tools             |
|   - GET /data/public/*           |          |   - Numerical Verifier           |
|   - POST /api/chat               |          |   - 40/40 Evals Pass             |
+----------------+-----------------+          +----------------------------------+
                 |
                 v
+----------------------------------+
|     Web Portal (web/portal/)     |
|   - 7 Navigation Views           |
|   - 8 New Visualizations         |
|   - Scrollytelling Stories       |
|   - Okabe-Ito Colors & i18n      |
+----------------------------------+
```

## Code Layout
- `server.py`: Root Python HTTP runtime server. Exclusively owned by Milestone 3 Worker.
- `etl/`: ETL extraction, transform, validation, insights, and chat engine. Exclusively owned by Milestone 1 Worker.
  - `etl/run_etl.py`: Master ETL entrypoint.
  - `etl/catalog.yaml`: 15 indicators definition and methodology.
  - `etl/countries.yaml`: 20 countries and 4 aggregates definition.
  - `etl/transform.py`: Data transformation and `LATAM_AVG` calculation.
  - `etl/validate.py`: Range validation and coverage matrix computation.
  - `etl/insights.py`: Deterministic editorial findings and country profiles.
  - `etl/chat_engine.py`: 5 snapshot tools, numerical verifier, query answering.
- `data/`:
  - `data/snapshots/2026-09/`: Frozen snapshot CSV and manifest.
  - `data/public/`: Public distribution JSON files.
- `web/`:
  - `web/portal/index.html`: Web portal entrypoint and UI views. Exclusively owned by Milestone 2 Worker.
  - `web/portal/portal.js`: Web portal client-side router, visualizers, scrollytelling, and i18n logic.
  - `web/portal/portal.css`: Web portal styling, Okabe-Ito color variables, tabular numbers, light/dark themes.
  - `web/content/historias/`: Scrollytelling story source MDX files.
  - `web/app/api/chat/route.ts`: Next.js App Router chat handler aligned with `etl/chat_engine.py`.
  - `web/lib/chat/`: TypeScript chat tools and verifier.
- `evals/`:
  - `evals/run_evals.py`: 40-question automated regression evaluator.
  - `evals/chat-preguntas.yaml`: 40 regression test questions with expected indicators and verifications.
- `tests/`:
  - `tests/e2e/`: Opaque-box E2E test suite (Tiers 1-4) owned by E2E Testing Track.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Full ETL Pipeline Execution | Complete monthly pipeline execution via `python etl/run_etl.py` exiting with 0 | M1 | Survey R1 |
| 2 | Priority Countries Setup | 5 priority countries (`COL`, `CHL`, `CRI`, `BRA`, `MEX`) with Okabe-Ito palette | M1 | Survey R1 |
| 3 | Regional Countries Coverage | 15 additional Latin American countries (`ARG`, `PER`, `URY`, etc., total 20) | M1 | Survey R1 |
| 4 | Regional Aggregates Calculation | `LATAM_AVG` with explicit `n_countries`, plus `LCN`, `OED`, `WLD` benchmarks | M1 | Survey R1 |
| 5 | Environmental Dimension Indicators | 4 indicators (`EN.GHG.CO2.PC.CE.AR5`, `EG.FEC.RNEW.ZS`, `AG.LND.FRST.ZS`, `EG.ELC.RNEW.ZS`) | M1 | Survey R1 |
| 6 | Social Dimension Indicators | 7 indicators (`CEPAL.POV.HARM`, `SI.POV.NAHC`, `SI.POV.GINI`, `SH.XPD.CHEX.PP.CD`, `SE.SEC.NENR`, `SL.TLF.CACT.FM.ZS`, `SP.DYN.LE00.IN`) | M1 | Survey R1 |
| 7 | Economic Dimension Indicators | 4 indicators (`NY.GDP.PCAP.PP.KD`, `SL.UEM.TOTL.ZS`, `FP.CPI.TOTL.ZG`, `NE.GDI.TOTL.ZS`) | M1 | Survey R1 |
| 8 | Methodological Adjustment 1 | `EN.GHG.CO2.PC.CE.AR5` replaces deprecated `EN.ATM.CO2E.PC` (EDGAR JRC AR5) | M1 | Survey R1 |
| 9 | Methodological Adjustment 2 | `CEPAL.POV.HARM` for regional poverty comparison across 20 countries | M1 | Survey R1 |
| 10 | Methodological Adjustment 3 | `SI.POV.NAHC` designated `profile_only: true` with warning, excluded from `LATAM_AVG` | M1 | Survey R1 |
| 11 | Methodological Adjustment 4 | `SI.POV.GINI` survey exact year preserved, non-annual gaps handled | M1 | Survey R1 |
| 12 | Methodological Adjustment 5 | `SH.XPD.CHEX.PP.CD` health expenditure in current international PPP $ | M1 | Survey R1 |
| 13 | Methodological Adjustment 6 | `SE.SEC.NENR` net secondary enrollment bounded in [0, 100%] | M1 | Survey R1 |
| 14 | Methodological Adjustment 7 | `SL.TLF.CACT.FM.ZS` female-to-male labor participation ratio (100 = parity) | M1 | Survey R1 |
| 15 | Renewable Energy Lag Warning | `EG.FEC.RNEW.ZS` flagged with `lag_warning: true` and capped at 2022 | M1 | Survey R1 |
| 16 | Snapshot Storage & Hash | `data/snapshots/2026-09/observations.csv` (5,257 rows) and `manifest.json` with SHA-256 | M1 | Survey R1 |
| 17 | Public Distribution Files | `data/public/` JSON files (`manifest`, `catalog`, `countries`, `coverage`, `insights`, `all_observations`, 15 `indicators/*.json`) | M1 | Survey R1 |
| 18 | Statistical Quality Validation | Validation of valid ranges, jump detection (>3.8 SD), coverage matrix | M1 | Survey R1 |
| 19 | Deterministic Monthly Insights | 4 editorial rules (CRI decoupling, CHL renewables, COL gender gap, BRA scale) in `insights.json` | M1 | Survey R1 |
| 20 | Web Portal Entrypoint | `web/portal/index.html` single-page portal application | M2 | Survey R2 |
| 21 | View 1: Portada (Homepage) | Pulse cards (5 priority countries x 3 dimensions, sparklines, rank, gaps vs LATAM_AVG/LCN) + deterministic findings | M2 | Survey R2 |
| 22 | View 2: Comparador (Explorer) | Synchronized URL query params (`?indicator=...&countries=...&ref=...&view=...`), Lines, Ranking, Scatter, Accessible Data Table, CSV/SVG export | M2 | Survey R2 |
| 23 | View 3: Perfiles de País | Country huella across 3 dimensions; `SI.POV.NAHC` shown exclusively with methodological disclaimer | M2 | Survey R2 |
| 24 | Vis 1: Slope Chart | 2010 -> latest comparison across countries | M2 | Survey R2 |
| 25 | Vis 2: Bump Chart | Country rankings over time (2010–2024) | M2 | Survey R2 |
| 26 | Vis 3: Connected Trajectory | GDP PPP per capita vs CO2 per capita connected chronologically | M2 | Survey R2 |
| 27 | Vis 4: Change Quadrants | Δ GDP per capita vs Δ Gini (2010–2024) with 4 labeled quadrants | M2 | Survey R2 |
| 28 | Vis 5: Regional Beeswarm Strip | 1D distribution strip across 20 countries with vertical jitter | M2 | Survey R2 |
| 29 | Vis 6: Diverging Z-score Gap Bars | Country strengths ($z > 0$) and lags ($z < 0$) vs regional average | M2 | Survey R2 |
| 30 | Vis 7: Composite Index Builder | Adjustable weights with live live ranking recalculation and directionality | M2 | Survey R2 |
| 31 | Vis 8: Data Coverage Heatmap | Indicator vs country data completeness matrix from `coverage.json` | M2 | Survey R2 |
| 32 | View 5: Scrollytelling Stories | Martini-glass narrative: Costa Rica green decoupling & Chile/Colombia inequality with "Explóralo tú" button | M2 | Survey R2 |
| 33 | View 6: Pregunta / Chat UI | Portal chat interface with message history, badges, inline chart, sources card, "Abrir en comparador" | M2 | Survey R2 |
| 34 | View 7: Metodología & DOI | Methodology documentation, Zenodo DOI citation, ADR notes, JSON downloads | M2 | Survey R2 |
| 35 | Okabe-Ito Color Palette | Colorblind-safe colors (`COL #0072B2`, `CHL #D55E00`, `CRI #009E73`, `BRA #E69F00`, `MEX #CC79A7`, dashed `#94A3B8` for LATAM_AVG) | M2 | Survey R2 |
| 36 | Typography & Themes | Conclusion chart titles, tabular numerals (`font-variant-numeric: tabular-nums`), Light/Dark mode | M2 | Survey R2 |
| 37 | Trilingual i18n Switcher | Seamless ES / PT / EN language switcher using multilingual metadata | M2 | Survey R2 |
| 38 | Root Local Server `server.py` | Unified HTTP runtime responding HTTP 200 on `/`, `/data/public/*`, `POST /api/chat` | M3 | Survey R2/R3 |
| 39 | API Chat Route `POST /api/chat` | Server endpoint parsing question, executing chat engine, returning verified payload | M3 | Survey R3 |
| 40 | Snapshot Tool: `buscar_indicador` | Fuzzy indicator search with alias resolution and ADR-001 replacement mapping | M3 | Survey R3 |
| 41 | Snapshot Tool: `obtener_serie` | Multi-country series 2010–2024 with deltas and latest value | M3 | Survey R3 |
| 42 | Snapshot Tool: `comparar` | Target country vs `LATAM_AVG` (with `n_countries`) and `LCN` | M3 | Survey R3 |
| 43 | Snapshot Tool: `ranking` | Sorted 20-country ranking respecting `higher_is_better` | M3 | Survey R3 |
| 44 | Snapshot Tool: `crear_grafico` | Visual spec generator with comparator query string | M3 | Survey R3 |
| 45 | Numerical Verifier | `verify_response_numbers` auditing response against snapshot with `unverified_count == 0` | M3 | Survey R3 |
| 46 | Out-of-Catalog Query Handling | Explicit label `"Dato fuera del catálogo..."`, 0 invented figures | M3 | Survey R3 |
| 47 | Zero-Key Execution | Complete local deterministic execution without requiring external API key | M3 | Survey R3 |
| 48 | Next.js API Parity | `web/app/api/chat/route.ts` & `web/lib/chat/` aligned with `etl/chat_engine.py` | M3 | Survey R3 |
| 49 | 40-Question Regression Evals | `python evals/run_evals.py` passing 40/40 with exit code 0 | M3 | Survey R3 |
| 50 | Comprehensive E2E Testing Suite | Requirements-driven opaque-box test suite (Tiers 1-4) | E2E | Dual Track |
| 51 | Adversarial Hardening (Tier 5) | White-box stress tests exposing potential edge cases | Final M | Dual Track |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| E2E | E2E Testing Suite Track | Design and implement opaque-box test runner and Tiers 1-4 test cases in `tests/e2e/`, publish `TEST_READY.md` | None | DONE |
| M1 | Versioned Snapshot & ETL Pipeline | Verify reproducibility, snapshot generation (`data/snapshots/2026-09/`), and public distribution (`data/public/*.json`) | None | DONE |
| M2 | Interactive Web Portal SPA | Build `web/portal/index.html`, `portal.js`, `portal.css` with 7 views, 8 visualizations, Scrollytelling, Okabe-Ito, i18n | M1 | DONE |
| M3 | Unified Runtime Server & Chat Integration | Create `server.py` serving `/`, `/data/public/*`, `POST /api/chat`; align `web/app/api/chat/route.ts`; verify evals | M1 | DONE |
| M4 | Final Milestone: 100% E2E Pass & Hardening | Phase 1: Pass 100% E2E test suite (Tiers 1-4); Phase 2: Adversarial coverage hardening (Tier 5) | M2, M3, E2E | DONE |

## Interface Contracts

### 1. Web Portal <-> Server Runtime (`server.py`)
- `GET /` -> HTTP 200 `text/html; charset=utf-8` serving `web/portal/index.html`.
- `GET /data/public/{filename}.json` -> HTTP 200 `application/json; charset=utf-8`.
- `GET /data/public/indicators/{code}.json` -> HTTP 200 `application/json; charset=utf-8`.
- `POST /api/chat` -> HTTP 200 `application/json; charset=utf-8`.
  - Request body: `{"question": string}`
  - Response body:
    ```json
    {
      "question": string,
      "out_of_catalog": boolean,
      "badge": string,
      "answer": string,
      "tools_called": [{"tool": string, "summary": string}],
      "verification": {
        "passed": boolean,
        "verified_count": number,
        "unverified_count": number,
        "verified_numbers": [number],
        "unverified_numbers": [number]
      },
      "sources": [
        {
          "indicator": string,
          "name": string,
          "source": string,
          "year": number,
          "n_countries": number,
          "doi": string
        }
      ],
      "chart": {
        "tool": "crear_grafico",
        "chart_type": "lines" | "ranking" | "scatter" | "table",
        "indicator": string,
        "secondary_indicator": string | null,
        "indicator_name": string,
        "unit": string,
        "source": string,
        "countries": [string],
        "reference": string,
        "title": string,
        "comparator_url": string
      } | null
    }
    ```

### 2. Server Runtime (`server.py`) <-> Python Chat Engine (`etl/chat_engine.py`)
- Python function signature:
  `answer_question(query: str, store: SnapshotStore = None) -> dict`
- Input: `query` (str)
- Output: Standard verified chat response dict matching the contract above.
- Error handling: Graceful handling of malformed input, returns HTTP 400 on invalid JSON.

### 3. Comparator URL Synchronization Contract
- Query parameter format:
  `?indicator={indicator_code}&countries={iso3_csv}&ref={benchmark_iso3}&view={lines|ranking|scatter|table}&y={secondary_indicator}`
- Example:
  `?indicator=EN.GHG.CO2.PC.CE.AR5&countries=COL,CHL,CRI,BRA,MEX&ref=LATAM_AVG&view=lines`
- Bidirectional contract: Clicking "Explóralo tú" or chat "Abrir en el comparador" sets this URL hash/query; user changes in comparator update the browser URL bar.
