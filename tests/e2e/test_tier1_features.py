"""
Tier 1: Feature Coverage Test Suite for Observatorio LATAM.
Covers:
- ETL files & snapshot: observations.csv, manifest.json, catalog.json, countries.json, coverage.json, insights.json
- Server endpoints: GET /, GET /data/public/*, OPTIONS /api/chat, POST /api/chat
- Web portal assets: web/portal/index.html, portal.js, portal.css
"""

from __future__ import annotations
import csv
import hashlib
import json
from pathlib import Path
import unittest

from tests.e2e.server_manager import get_shared_server

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = WORKSPACE_ROOT / "data"
PUBLIC_DIR = DATA_DIR / "public"
SNAPSHOT_DIR = DATA_DIR / "snapshots" / "2026-09"
WEB_PORTAL_DIR = WORKSPACE_ROOT / "web" / "portal"


class TestTier1Features(unittest.TestCase):
    """Tier 1 Feature Coverage Tests."""

    @classmethod
    def setUpClass(cls):
        cls.server = get_shared_server()

    def setUp(self):
        super().setUp()
        if not hasattr(self, "server") or self.server is None:
            self.__class__.setUpClass()

    # =========================================================================
    # ETL & SNAPSHOT INTEGRITY TESTS
    # =========================================================================

    def test_t1_manifest_metadata_and_integrity(self):
        """Verify manifest.json metadata fields, versioning, DOI, and validation status."""
        manifest_path = PUBLIC_DIR / "manifest.json"
        self.assertTrue(manifest_path.is_file(), f"Missing {manifest_path}")

        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertEqual(manifest.get("snapshot_id"), "2026-09")
        self.assertEqual(manifest.get("version"), "2026.09")
        self.assertEqual(manifest.get("zenodo_doi"), "10.5281/zenodo.obs-latam-2026-09")
        self.assertIn("citation_apa", manifest)
        self.assertEqual(manifest.get("total_observations"), 5257)
        self.assertEqual(manifest.get("indicators_count"), 15)
        self.assertEqual(manifest.get("countries_count"), 20)
        self.assertEqual(manifest.get("validation_status"), "PASSED")
        self.assertEqual(manifest.get("range_violations_count"), 0)

        expected_aggregates = ["LATAM_AVG", "LCN", "OED", "WLD"]
        self.assertEqual(manifest.get("aggregates"), expected_aggregates)

    def test_t1_observations_csv_and_sha256_hash(self):
        """Verify observations.csv schema, exact observation count, and SHA-256 match."""
        csv_path = SNAPSHOT_DIR / "observations.csv"
        self.assertTrue(csv_path.is_file(), f"Missing {csv_path}")

        with open(PUBLIC_DIR / "manifest.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # Check SHA-256
        hasher = hashlib.sha256()
        with open(csv_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        calc_sha = hasher.hexdigest()
        self.assertEqual(calc_sha, manifest.get("sha256_observations_csv"))

        # Verify CSV rows and schema
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            expected_headers = ["indicator", "iso3", "year", "value", "source", "downloaded_at", "is_estimate", "n_countries"]
            self.assertEqual(reader.fieldnames, expected_headers)
            rows = list(reader)
            self.assertEqual(len(rows), 5257)

            # Spot-check data validity
            years = {int(r["year"]) for r in rows}
            self.assertTrue(min(years) >= 2010)
            self.assertTrue(max(years) <= 2025)

            indicators = {r["indicator"] for r in rows}
            self.assertEqual(len(indicators), 15)

    def test_t1_catalog_indicators_and_dimensions(self):
        """Verify catalog.json schema, 15 indicators, 3 dimensions, and valid ranges."""
        catalog_path = PUBLIC_DIR / "catalog.json"
        self.assertTrue(catalog_path.is_file(), f"Missing {catalog_path}")

        with open(catalog_path, "r", encoding="utf-8") as f:
            cat = json.load(f)

        self.assertEqual(cat.get("version"), "2026.09")
        dimensions = cat.get("dimensions", [])
        self.assertEqual(len(dimensions), 3)
        dim_slugs = {d["slug"] for d in dimensions}
        self.assertEqual(dim_slugs, {"economica", "social", "ambiental"})

        indicators = cat.get("indicators", [])
        self.assertEqual(len(indicators), 15)

        for ind in indicators:
            self.assertIn("code", ind)
            self.assertIn("dimension", ind)
            self.assertIn(ind["dimension"], dim_slugs)
            self.assertIn("name", ind)
            self.assertIn("es", ind["name"])
            self.assertIn("unit", ind)
            self.assertIn("higher_is_better", ind)
            self.assertIn("valid_range", ind)
            self.assertEqual(len(ind["valid_range"]), 2)
            self.assertTrue(ind["valid_range"][0] <= ind["valid_range"][1])
            self.assertIn("methodology_note", ind)

    def test_t1_catalog_adr001_methodological_adjustments(self):
        """Verify the 7 specific ADR-001 indicator adjustments in catalog.json."""
        with open(PUBLIC_DIR / "catalog.json", "r", encoding="utf-8") as f:
            cat = json.load(f)

        ind_map = {i["code"]: i for i in cat["indicators"]}

        # 1. CO2 EDGAR AR5 replaces deprecated EN.ATM.CO2E.PC
        self.assertIn("EN.GHG.CO2.PC.CE.AR5", ind_map)
        self.assertEqual(ind_map["EN.GHG.CO2.PC.CE.AR5"].get("replaces_code"), "EN.ATM.CO2E.PC")
        self.assertFalse(ind_map["EN.GHG.CO2.PC.CE.AR5"]["higher_is_better"])

        # 2. CEPAL.POV.HARM replaces SI.POV.NAHC for regional comparisons
        self.assertIn("CEPAL.POV.HARM", ind_map)
        self.assertEqual(ind_map["CEPAL.POV.HARM"].get("replaces_code"), "SI.POV.NAHC")

        # 3. SI.POV.NAHC is profile-only with 0 weight in composite index
        self.assertIn("SI.POV.NAHC", ind_map)
        self.assertTrue(ind_map["SI.POV.NAHC"].get("profile_only"))
        self.assertEqual(ind_map["SI.POV.NAHC"].get("composite_default_weight"), 0.0)

        # 4. SI.POV.GINI preserves exact measurement year
        self.assertIn("SI.POV.GINI", ind_map)
        self.assertTrue(ind_map["SI.POV.GINI"].get("show_exact_year"))

        # 5. SH.XPD.CHEX.PP.CD replaces current US$ with PPP
        self.assertIn("SH.XPD.CHEX.PP.CD", ind_map)
        self.assertEqual(ind_map["SH.XPD.CHEX.PP.CD"].get("replaces_code"), "SH.XPD.CHEX.PC.CD")

        # 6. SE.SEC.NENR net secondary enrollment bounded [20, 100]
        self.assertIn("SE.SEC.NENR", ind_map)
        self.assertEqual(ind_map["SE.SEC.NENR"].get("replaces_code"), "SE.SEC.ENRR")
        self.assertEqual(ind_map["SE.SEC.NENR"]["valid_range"], [20.0, 100.0])

        # 7. SL.TLF.CACT.FM.ZS female-to-male labor ratio (100 = parity)
        self.assertIn("SL.TLF.CACT.FM.ZS", ind_map)
        self.assertEqual(ind_map["SL.TLF.CACT.FM.ZS"].get("replaces_code"), "SL.TLF.CACT.FE.ZS")
        self.assertEqual(ind_map["SL.TLF.CACT.FM.ZS"]["unit"], "% (100 = paridad)")

    def test_t1_countries_and_okabe_ito_colors(self):
        """Verify countries.json contains 5 priority countries with Okabe-Ito colors, 15 regional countries, 4 aggregates."""
        with open(PUBLIC_DIR / "countries.json", "r", encoding="utf-8") as f:
            c_doc = json.load(f)

        priority = c_doc.get("priority_countries", [])
        self.assertEqual(len(priority), 5)
        p_map = {c["iso3"]: c for c in priority}

        expected_okabe_ito = {
            "COL": "#0072B2",
            "CHL": "#D55E00",
            "CRI": "#009E73",
            "BRA": "#E69F00",
            "MEX": "#CC79A7",
        }
        for iso3, expected_color in expected_okabe_ito.items():
            self.assertIn(iso3, p_map)
            self.assertEqual(p_map[iso3]["color"], expected_color)
            self.assertTrue(p_map[iso3]["priority"])

        regional = c_doc.get("region_countries", [])
        self.assertEqual(len(regional), 15)
        regional_iso3 = {c["iso3"] for c in regional}
        expected_regional = {"ARG", "PER", "URY", "ECU", "PAN", "DOM", "BOL", "PRY", "GTM", "HND", "SLV", "NIC", "VEN", "CUB", "HTI"}
        self.assertEqual(regional_iso3, expected_regional)

        aggregates = c_doc.get("aggregates", [])
        self.assertEqual(len(aggregates), 4)
        agg_map = {a["iso3"]: a for a in aggregates}
        self.assertIn("LATAM_AVG", agg_map)
        self.assertEqual(agg_map["LATAM_AVG"].get("line_style"), "dashed")
        self.assertIn("LCN", agg_map)
        self.assertIn("OED", agg_map)
        self.assertIn("WLD", agg_map)

    def test_t1_coverage_and_insights_files(self):
        """Verify coverage.json and insights.json exist and are well-formed."""
        with open(PUBLIC_DIR / "coverage.json", "r", encoding="utf-8") as f:
            coverage = json.load(f)
        self.assertIn("coverage_matrix", coverage)
        self.assertIn("range_violations", coverage)
        self.assertIn("sudden_jumps", coverage)

        with open(PUBLIC_DIR / "insights.json", "r", encoding="utf-8") as f:
            insights = json.load(f)
        findings = insights.get("findings", [])
        self.assertGreaterEqual(len(findings), 4)

        finding_ids = {f["id"] for f in findings}
        self.assertIn("hallazgo-desacoplamiento-cri", finding_ids)
        self.assertIn("hallazgo-renovables-chl", finding_ids)
        self.assertIn("hallazgo-genero-col", finding_ids)
        self.assertIn("hallazgo-escala-brasil-lcn", finding_ids)

        for find in findings:
            self.assertIn("comparator_url", find)
            self.assertTrue(find["comparator_url"].startswith("?"))
            self.assertIn("numbers_verified", find)
            self.assertIsInstance(find["numbers_verified"], list)

    def test_t1_all_indicators_json_files(self):
        """Verify all 15 indicator JSON files exist in data/public/indicators/."""
        indicators_dir = PUBLIC_DIR / "indicators"
        self.assertTrue(indicators_dir.is_dir())

        with open(PUBLIC_DIR / "catalog.json", "r", encoding="utf-8") as f:
            cat = json.load(f)

        for ind in cat["indicators"]:
            ind_file = indicators_dir / f"{ind['code']}.json"
            self.assertTrue(ind_file.is_file(), f"Missing indicator file: {ind_file}")
            with open(ind_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data.get("indicator", {}).get("code"), ind["code"])
            self.assertIn("observations", data)

    # =========================================================================
    # SERVER RUNTIME HTTP ENDPOINT TESTS
    # =========================================================================

    def test_t1_server_root_index_html(self):
        """GET / returns HTTP 200 with text/html content serving Observatorio LATAM."""
        status, headers, body = self.server.get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        body_text = body.decode("utf-8")
        self.assertIn("Observatorio LATAM", body_text)
        self.assertIn("view-portada", body_text)
        self.assertIn("portal.js", body_text)

    def test_t1_server_public_json_endpoints(self):
        """GET /data/public/* endpoints return HTTP 200 with application/json."""
        endpoints = [
            "/data/public/manifest.json",
            "/data/public/catalog.json",
            "/data/public/countries.json",
            "/data/public/coverage.json",
            "/data/public/insights.json",
            "/data/public/indicators/EN.GHG.CO2.PC.CE.AR5.json",
        ]
        for ep in endpoints:
            status, headers, body = self.server.get(ep)
            self.assertEqual(status, 200, f"Endpoint {ep} returned status {status}")
            self.assertIn("application/json", headers.get("Content-Type", ""), f"Wrong MIME for {ep}")
            parsed = json.loads(body.decode("utf-8"))
            self.assertIsInstance(parsed, dict, f"Content for {ep} is not JSON object")

    def test_t1_server_chat_options_cors(self):
        """OPTIONS /api/chat returns HTTP 200 with CORS headers."""
        status, headers, _ = self.server.options("/api/chat")
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("Access-Control-Allow-Origin"), "*")
        self.assertIn("POST", headers.get("Access-Control-Allow-Methods", ""))

    def test_t1_server_chat_post_in_catalog(self):
        """POST /api/chat with in-catalog query returns HTTP 200 with 100% verified numbers."""
        payload = {
            "question": "¿Cuánto emite de CO2 per cápita Colombia y cómo se compara con el promedio regional?"
        }
        status, headers, body = self.server.post_json("/api/chat", payload)
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers.get("Content-Type", ""))

        data = json.loads(body.decode("utf-8"))
        self.assertFalse(data.get("out_of_catalog"))
        self.assertIn("Verificado", data.get("badge", ""))
        self.assertTrue("Colombia" in data.get("answer", "") or "COL" in data.get("answer", ""))

        # Verification audit
        ver = data.get("verification", {})
        self.assertTrue(ver.get("passed"))
        self.assertEqual(ver.get("unverified_count"), 0)
        self.assertGreater(ver.get("verified_count", 0), 0)

        # Inline chart and sources
        chart = data.get("chart")
        self.assertIsNotNone(chart)
        self.assertEqual(chart.get("indicator"), "EN.GHG.CO2.PC.CE.AR5")
        self.assertIn("comparator_url", chart)
        self.assertTrue(chart["comparator_url"].startswith("?"))

        sources = data.get("sources", [])
        self.assertGreater(len(sources), 0)
        self.assertIn("doi", sources[0])

    # =========================================================================
    # WEB PORTAL ASSETS TESTS
    # =========================================================================

    def test_t1_portal_index_html_7_views(self):
        """Verify web/portal/index.html includes all 7 main SPA navigation views."""
        html_path = WEB_PORTAL_DIR / "index.html"
        self.assertTrue(html_path.is_file(), f"Missing {html_path}")

        content = html_path.read_text(encoding="utf-8")
        expected_views = [
            "view-portada",
            "view-comparador",
            "view-perfiles",
            "view-visualizaciones",
            "view-historias",
            "view-chat",
            "view-metodologia",
        ]
        for v in expected_views:
            self.assertIn(f'id="{v}"', content, f"View id {v} missing in index.html")

        # Check language switchers
        self.assertIn('data-lang="es"', content)
        self.assertIn('data-lang="pt"', content)
        self.assertIn('data-lang="en"', content)

        # Check theme switcher
        self.assertIn("theme-toggle-btn", content)

    def test_t1_portal_css_okabe_ito_and_tabular_numerals(self):
        """Verify portal.css contains Okabe-Ito color variables and tabular numerals."""
        css_path = WEB_PORTAL_DIR / "portal.css"
        self.assertTrue(css_path.is_file(), f"Missing {css_path}")

        css_content = css_path.read_text(encoding="utf-8")
        self.assertIn("--color-col: #0072B2", css_content)
        self.assertIn("--color-chl: #D55E00", css_content)
        self.assertIn("--color-cri: #009E73", css_content)
        self.assertIn("--color-bra: #E69F00", css_content)
        self.assertIn("--color-mex: #CC79A7", css_content)
        self.assertIn("--color-latam-avg: #94A3B8", css_content)

        # Tabular numerals for financial / statistical precision
        self.assertIn("tabular-nums", css_content)
        self.assertIn('[data-theme="dark"]', css_content)

    def test_t1_portal_js_i18n_and_visualizations(self):
        """Verify portal.js defines translations (es, pt, en) and specialized visualization components."""
        js_path = WEB_PORTAL_DIR / "portal.js"
        self.assertTrue(js_path.is_file(), f"Missing {js_path}")

        js_content = js_path.read_text(encoding="utf-8")
        # Check i18n
        self.assertIn("es:", js_content)
        self.assertIn("pt:", js_content)
        self.assertIn("en:", js_content)

        # Check 8 Visualizations presence
        expected_vis_terms = [
            "Slope",               # Slope chart 2010 -> latest
            "Bump",                # Bump chart ranking over time
            "Connected",           # Connected trajectory GDP vs CO2
            "Quadrants",           # Change quadrants Δ GDP vs Δ Gini
            "Beeswarm",            # Regional beeswarm strip
            "Z-Score",             # Diverging z-score gap bars
            "Composite",           # Composite index builder
            "Coverage",            # Data coverage heatmap
        ]
        for term in expected_vis_terms:
            self.assertTrue(
                term.lower() in js_content.lower(),
                f"Visualization '{term}' not found in portal.js",
            )


if __name__ == "__main__":
    unittest.main()
