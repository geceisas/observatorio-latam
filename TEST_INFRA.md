# Observatorio LATAM — Testing Infrastructure Specification (`TEST_INFRA.md`)

## 1. Architectural Philosophy: Requirement-Driven Opaque-Box Testing

The **Observatorio LATAM** test suite is built on an **opaque-box, requirement-driven methodology**. Unlike white-box unit tests that inspect internal object mutations or private variables, the E2E suite treats each subsystem as a black box with strict observable contracts:

1. **Direct File System Contracts**: Frozen snapshot datasets (`data/snapshots/2026-09/observations.csv`, `manifest.json`) and public distribution JSON files (`data/public/*.json`) are evaluated purely on schema compliance, cryptographic hash verification (SHA-256), range validations, and statistical properties.
2. **Standard HTTP Network Contracts**: The unified local runtime server (`server.py`) is verified over actual TCP sockets via HTTP requests (`GET /`, `GET /data/public/*`, `OPTIONS /api/chat`, `POST /api/chat`), evaluating HTTP status codes, headers (MIME types, CORS), and JSON response payloads.
3. **Static Web Portal Assets**: Portal views, stylesheets, and scripts (`web/portal/index.html`, `portal.js`, `portal.css`) are verified against accessibility, colorblind safety (Okabe-Ito palette), typography (tabular numerals), trilingual support (ES, PT, EN), and responsive visualizer bindings.
4. **Agentic Analytical & Verification Contracts**: The Chat API (`/api/chat`) and underlying analytical engine (`etl/chat_engine.py`) are tested for tool orchestration, out-of-catalog honest refusals (`Dato fuera del catálogo`), zero hallucinations, and 100% numerical verification against snapshot observations.

```
+-------------------------------------------------------------------------------+
|                       E2E TEST RUNNER (run_e2e_tests.py)                       |
+-------------------------------------------------------------------------------+
       |                         |                       |              |
       v                         v                       v              v
+---------------+       +------------------+     +---------------+  +------------+
|    Tier 1     |       |      Tier 2      |     |    Tier 3     |  |   Tier 4   |
| Feature       |       | Boundary &       |     | Cross-Feature |  | Real-World |
| Coverage      |       | Corner Cases     |     | Combinations  |  | Scenarios  |
+---------------+       +------------------+     +---------------+  +------------+
       |                         |                       |              |
       +-------------------------+-----------------------+--------------+
                                 |
                                 v
        +--------------------------------------------------+
        | Ephemeral Test Server (tests/e2e/server_manager) |
        | Socket-bound ThreadingHTTPServer (server.py)     |
        +--------------------------------------------------+
                                 |
       +-------------------------+-------------------------+
       |                         |                         |
       v                         v                         v
[GET / (HTML)]          [GET /data/public/*]      [POST /api/chat]
[MIME / Assets]         [Snapshot Validation]     [100% Verifier]
```

---

## 2. 4-Tier Test Architecture & Methodology

The test suite is structured into 4 distinct tiers, providing comprehensive coverage across all 51 features in the `PROJECT.md` Feature Inventory:

### Tier 1: Feature Coverage
Validates the presence, structure, and baseline functionality of all primary assets:
- **ETL Outputs & Snapshot**:
  - `manifest.json`: Snapshot metadata (`2026-09`), semantic version (`2026.09`), Zenodo DOI (`10.5281/zenodo.obs-latam-2026-09`), APA citation, aggregate definitions (`LATAM_AVG`, `LCN`, `OED`, `WLD`), and validation status (`PASSED`, 0 violations).
  - `observations.csv`: SHA-256 cryptographic verification matching manifest, 5,257 observation rows, schema headers (`indicator,iso3,year,value,source,downloaded_at,is_estimate,n_countries`).
  - `catalog.json`: 15 indicators across 3 dimensions (`economica`, `social`, `ambiental`), bounded `valid_range`, `higher_is_better` directionality, composite default weights summing to 1.0, and the 7 ADR-001 methodological adjustments.
  - `countries.json`: 5 priority countries with Okabe-Ito colorblind-safe hex values (`COL #0072B2`, `CHL #D55E00`, `CRI #009E73`, `BRA #E69F00`, `MEX #CC79A7`), 15 regional countries, and 4 aggregates.
  - `coverage.json`: Completeness matrix across 20 countries and 15 indicators.
  - `insights.json`: 4 deterministic monthly insights (CRI decoupling, CHL renewables jump, COL gender parity, BRA scale impact).
  - Indicator JSONs: Complete set of 15 individual JSON files in `data/public/indicators/`.
- **Runtime Server Endpoints**:
  - `GET /`: Returns HTTP 200 with `text/html; charset=utf-8` serving the single-page portal.
  - `GET /data/public/*`: Serves JSON files with `application/json; charset=utf-8`.
  - `OPTIONS /api/chat`: CORS preflight responding with HTTP 200 and `Access-Control-Allow-Origin: *`.
  - `POST /api/chat`: Baseline query execution returning verified payload with inline chart and sources.
- **Web Portal Assets**:
  - `web/portal/index.html`: Structural verification of 7 SPA views (`#view-portada`, `#view-comparador`, `#view-perfiles`, `#view-visualizaciones`, `#view-historias`, `#view-chat`, `#view-metodologia`), language switchers, and theme toggles.
  - `web/portal/portal.css`: Okabe-Ito CSS variables, tabular numerals (`tabular-nums`), and dark/light mode rules.
  - `web/portal/portal.js`: Trilingual dictionary (`es`, `pt`, `en`), 8 specialized visualization renderers, and event listeners.

### Tier 2: Boundary & Corner Cases
Tests system resilience, error handling, and strict methodological rules:
- **Empty & Malformed Requests**:
  - Empty POST body or missing `Content-Length` header -> HTTP 400.
  - Malformed JSON syntax (broken string or syntax error) -> HTTP 400.
  - Empty or whitespace question strings (`""`, `"   "`, `null`) -> HTTP 400.
  - Prohibited HTTP methods (`GET /api/chat`) -> HTTP 405 Method Not Allowed.
  - Path traversal attempts (`GET /data/public/../../server.py`) -> HTTP 403 or 404.
- **Out-of-Catalog Topics (Honest Refusal & Zero Hallucinations)**:
  - Unrelated queries (Bitcoin, soccer, lithium reserves, monthly tourism).
  - Response tagged with `out_of_catalog: true`.
  - Display badge: `"Dato fuera del catálogo del observatorio · Candidato Data360 MCP"`.
  - Inline chart is explicitly `null`.
  - Zero hallucinations: `unverified_count == 0` and `unverified_numbers == []`.
- **Methodological Exclusion of `SI.POV.NAHC`**:
  - National poverty lines are officially non-comparable across nations (each institute defines its own basket).
  - Verified absent from `LATAM_AVG` in `observations.csv`.
  - Assigned `profile_only: true` and `composite_default_weight: 0.0` in `catalog.json`.
  - Multi-country comparison queries automatically redirect to `CEPAL.POV.HARM` with ADR-001 disclaimer.
  - Single-country inquiries permitted only within national profile scope.
- **Renewable Energy Lag Warning (`EG.FEC.RNEW.ZS`)**:
  - `lag_warning: true` in `catalog.json`.
  - Data capped at 2022 to account for 2-3 year international reporting lag.

### Tier 3: Cross-Feature Combinations
Tests interaction between multiple platform components:
- **Comparator Query URL Parameters**:
  - Parameter syntax: `?indicator={code}&countries={iso3_csv}&ref={ref}&view={view}&x={code}&y={code}`.
  - Validates that parameters resolve to existing indicators, valid ISO-3 country codes, and permitted view modes (`lines`, `ranking`, `scatter`, `table`).
- **Scrollytelling URLs ("Explóralo tú")**:
  - Parses MDX story sources (`web/content/historias/*.mdx`) and `insights.json`.
  - Verifies that every embedded "Explóralo tú" link points to valid indicators and countries with non-empty observations in `all_observations.json`.
- **Chat Inline Chart Comparator URLs**:
  - Confirms that every in-catalog chat response generates a chart spec containing a valid `comparator_url`.
  - Verifies synchronicity: URL indicator, view, and country list exactly match the chart properties.
- **Composite Index Builder Dynamic Recalculation**:
  - Evaluates live min-max normalization across 20 countries.
  - Tests directionality inversion for indicators where higher is worse (`1.0 - norm`).
  - Tests weight rebalancing (e.g. 100% green vs 100% economic) and confirms ranks recalculate dynamically into integers 1..20 without NaNs.

### Tier 4: Real-World Scenarios
Tests domain-specific socioeconomic and environmental analytical scenarios:
- **Costa Rica Green Decoupling**:
  - Validates Costa Rica empirical decoupling: GDP per capita PPP (`NY.GDP.PCAP.PP.KD`) grew >40% (2010–2024), forest area (`AG.LND.FRST.ZS`) expanded >55%, clean electricity (`EG.ELC.RNEW.ZS`) exceeded 95%, and CO2 per capita remained far below the OECD average (`OED`).
  - Confirms chat responses for Costa Rica decoupling pass numerical verification with 0 unverified numbers.
- **Chile & Colombia Inequality & Labor Parity**:
  - Chile high GDP per capita PPP (>$30,000 in 2024) contrasted with persistent inequality (Gini >40 vs OECD 32.1).
  - Colombia Gini >50 and female-to-male labor participation ratio (`SL.TLF.CACT.FM.ZS`) >65% (71.1% vs 69.2% regional avg).
  - Confirms poverty comparison adheres to `CEPAL.POV.HARM`.
- **Brasil Scale Impact & Regional Aggregates Contrast**:
  - Contrasts World Bank weighted aggregate `LCN` (dominated by Brazil and Mexico) against the simple arithmetic mean `LATAM_AVG`.
  - Confirms `LATAM_AVG` is mathematically reproducible from the arithmetic mean of reporting countries for a given indicator and year.

---

## 3. Server Lifecycle & Test Environment Management

To guarantee zero test interference, the test suite includes an automated server manager (`tests/e2e/server_manager.py`):

1. **Ephemeral Port Allocation**: The server binds to port 0 (`socket.bind(('127.0.0.1', 0))`), allowing the operating system to dynamically assign an unused high port. This prevents port collisions with other local processes.
2. **Threaded Execution**: The server instance is launched in a background daemon thread using Python standard library `ThreadingHTTPServer`.
3. **Readiness Probe**: Before any test executes, the test runner polls `GET /` until an HTTP 200 response is received (with a 5.0-second timeout).
4. **Shared Instance with Clean Teardown**: A lazily initialized shared server (`get_shared_server()`) is reused across test suites for optimal execution speed (~3-5 seconds total suite runtime), with guaranteed graceful shutdown (`shutdown()`, `server_close()`) at suite completion.

---

## 4. Execution Instructions

### Running the Complete E2E Suite
From the workspace root:

```bash
python tests/e2e/run_e2e_tests.py
```

### Running Individual Tiers
Individual test files can be executed independently using standard Python unittest:

```bash
# Tier 1 only
python -m unittest tests/e2e/test_tier1_features.py

# Tier 2 only
python -m unittest tests/e2e/test_tier2_boundaries.py

# Tier 3 only
python -m unittest tests/e2e/test_tier3_combinations.py

# Tier 4 only
python -m unittest tests/e2e/test_tier4_scenarios.py
```

### Verification Criteria
- All tests execute cleanly and report `[PASS]`.
- Exit code is `0` on success, `1` on any failure.
- No third-party packages required (100% Python standard library).
