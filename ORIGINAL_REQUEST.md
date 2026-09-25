# Original User Request

## Initial Request — 2026-09-24T23:45:49-05:00

Build and complete the **Observatorio LATAM** platform: a reproducible Latin American socio-economic and environmental data observatory powered by a monthly Python ETL snapshot (`2026-09`), an interactive Web Portal (Homepage, URL-driven Comparator, Country Profiles, 8 specialized visualizations including an adjustable-weights Composite Index and Data Coverage Heatmap, and Martini-glass Scrollytelling), and an Agentic Chat (`/api/chat`) whose tool outputs and numbers are strictly audited by a numerical verifier against the same snapshot.

Working directory: C:\Users\paola_plata\.gemini\antigravity\scratch\observatorio-latam
Integrity mode: development

## Requirements

### R1. Versioned Snapshot & ETL Pipeline (ADR-001)
Maintain and verify the Python ETL pipeline (`etl/run_etl.py`, `etl/catalog.yaml`, `etl/countries.yaml`, `etl/transform.py`, `etl/validate.py`, `etl/insights.py`) covering the 5 priority countries (`COL`, `CHL`, `CRI`, `BRA`, `MEX`), 15 additional Latin American countries (`ARG`, `PER`, `URY`, `ECU`, `PAN`, `DOM`, `BOL`, `PRY`, `GTM`, `HND`, `SLV`, `NIC`, `VEN`, `CUB`, `HTI`), and 4 regional benchmarks (`LATAM_AVG` with explicit country count `n`, `LCN` World Bank, `OED` OECD, `WLD` World) across all 15 indicators incorporating the 7 methodological indicator adjustments (`EN.GHG.CO2.PC.CE.AR5`, `CEPAL.POV.HARM` vs profile-only `SI.POV.NAHC`, `SI.POV.GINI`, `SH.XPD.CHEX.PP.CD`, `SE.SEC.NENR`, `SL.TLF.CACT.FM.ZS`, `EG.FEC.RNEW.ZS`).

### R2. Interactive Web Portal & Local Runtime Server (ADR-002)
Complete the full web portal (`web/portal/index.html`, `web/app/[locale]/...`, and unified local server `server.py`) reading directly from `data/public/*.json` without calling external APIs from the browser:
- **Portada (Homepage):** Pulse cards for the 5 priority countries across the 3 dimensions (latest value, year, sparkline, regional rank, and gap vs `LATAM_AVG` / `LCN`) plus the monthly deterministic findings from `insights.json`.
- **Comparador (Explorer):** Interactive explorer synchronized with URL query parameters (`?indicator=...&countries=...&ref=...&view=...`) supporting Lines, Ranking, Scatter, and Accessible Data Table views, plus CSV/SVG export.
- **Perfiles de País & Dimensiones:** Country huella across Economic, Social, and Environmental dimensions, displaying `SI.POV.NAHC` only in the individual country profile with its methodological warning.
- **8 Visualizaciones Nuevas:** (1) Slope chart 2010→latest, (2) Bump chart ranking over time, (3) Connected trajectory GDP PPP per capita vs CO2 per capita, (4) Change quadrants Δ GDP per capita vs Δ Gini, (5) Regional beeswarm strip across the 20 countries, (6) Diverging z-score gap bars (strengths and lags), (7) Adjustable-weights Composite Index builder with live ranking recalculation, and (8) Data Coverage Heatmap (`coverage.json`).
- **Scrollytelling ("Copa de Martini"):** Guided narrative steps transforming a fixed chart (Costa Rica green decoupling; Chile/Colombia growth vs inequality) ending with an "Explóralo tú" button that opens the comparator with the exact state.
- **UX/UI & i18n:** Fixed Okabe-Ito colorblind-safe palette for priority countries, dashed grey line for regional average, conclusion-driven chart titles, tabular numerals, dark/light mode, and `ES / PT / EN` language switcher.

### R3. Agentic Chat with Snapshot Tools & Numerical Verifier (ADR-003)
Provide the `/api/chat` endpoint (in both `server.py` and `web/app/api/chat/route.ts`) using the 5 tools (`buscar_indicador`, `obtener_serie`, `comparar`, `ranking`, `crear_grafico`) and the numerical verifier (`verify_response_numbers`) working out-of-the-box without requiring an external API key (with optional Gemini support):
- Every response displays the analytical text citing source and year, an inline chart rendered from the snapshot, source cards with `n` country count and Zenodo DOI, a numerical verification badge, and an "Abrir en el comparador" button.
- Out-of-catalog queries are explicitly labeled `"Dato fuera del catálogo del observatorio · Candidato Data360 MCP"` without inventing numbers.

## Verification Resources

The working directory already contains:
- `python etl/run_etl.py`: Generates and validates `data/snapshots/2026-09/` and `data/public/*.json`.
- `python evals/run_evals.py`: Runs the 40 regression questions in `evals/chat-preguntas.yaml` verifying tool indicator selection, ADR-001 replacements, out-of-catalog refusals, and 100% numerical verification (`unverified_count == 0`).

## Acceptance Criteria

### Data & ETL Verification
- [ ] `python etl/run_etl.py` exits with code 0 and produces `data/snapshots/2026-09/observations.csv`, `manifest.json`, and all JSON files in `data/public/` (`catalog.json`, `countries.json`, `insights.json`, `coverage.json`, `all_observations.json`, and `indicators/*.json`).
- [ ] `LATAM_AVG` observations include `n_countries` for every indicator and year, alongside `LCN`, `OED`, and `WLD`.

### Chat & Evaluation Suite Verification
- [ ] `python evals/run_evals.py` exits with code 0 with `40/40` questions passing both indicator selection and the numerical verifier (`unverified_count == 0`).

### Web Portal & API End-to-End Verification
- [ ] `server.py` serves the interactive portal and responds with HTTP 200 on `/`, `/data/public/manifest.json`, `/data/public/insights.json`, and `POST /api/chat`.
- [ ] The portal renders all 7 navigation views (Portada, Comparar, Perfiles de País, 8 Visualizaciones Nuevas incluyendo Índice Compuesto interactivo y Mapa de Cobertura, Historias Scrollytelling, Pregunta/Chat, y Metodología/DOI) using the fixed Okabe-Ito priority country colors (`COL #0072B2`, `CHL #D55E00`, `CRI #009E73`, `BRA #E69F00`, `MEX #CC79A7`).
