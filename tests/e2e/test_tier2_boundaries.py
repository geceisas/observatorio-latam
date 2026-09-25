"""
Tier 2: Boundary & Corner Cases Test Suite for Observatorio LATAM.
Covers:
- Empty / malformed chat JSON and invalid HTTP methods (400, 404, 405)
- Out-of-catalog topic queries with honest refusal and 0 hallucinations
- Profile-only SI.POV.NAHC exclusion from LATAM_AVG and comparator redirection
- Renewable energy lag warning on EG.FEC.RNEW.ZS
"""

from __future__ import annotations
import csv
import json
from pathlib import Path
import unittest

from tests.e2e.server_manager import get_shared_server

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = WORKSPACE_ROOT / "data"
PUBLIC_DIR = DATA_DIR / "public"
SNAPSHOT_DIR = DATA_DIR / "snapshots" / "2026-09"


class TestTier2Boundaries(unittest.TestCase):
    """Tier 2 Boundary & Corner Case Tests."""

    @classmethod
    def setUpClass(cls):
        cls.server = get_shared_server()

    def setUp(self):
        super().setUp()
        if not hasattr(self, "server") or self.server is None:
            self.__class__.setUpClass()

    # =========================================================================
    # EMPTY & MALFORMED REQUEST TESTS
    # =========================================================================

    def test_t2_chat_empty_body_returns_400(self):
        """POST /api/chat with empty body returns HTTP 400."""
        status, _, body = self.server.post_json("/api/chat", payload=None, raw_body=b"")
        self.assertEqual(status, 400)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("error", data)

    def test_t2_chat_malformed_json_returns_400(self):
        """POST /api/chat with invalid JSON syntax returns HTTP 400."""
        broken_json = b'{"question": "broken json string...'
        status, _, body = self.server.post_json("/api/chat", payload=None, raw_body=broken_json)
        self.assertEqual(status, 400)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("error", data)

    def test_t2_chat_empty_question_field_returns_400(self):
        """POST /api/chat with empty or whitespace-only question returns HTTP 400."""
        empty_cases = [
            {},
            {"question": ""},
            {"question": "   "},
            {"question": None},
        ]
        for payload in empty_cases:
            status, _, body = self.server.post_json("/api/chat", payload=payload)
            self.assertEqual(status, 400, f"Expected 400 for payload {payload}, got {status}")
            data = json.loads(body.decode("utf-8"))
            self.assertIn("error", data)

    def test_t2_chat_get_method_not_allowed_405(self):
        """GET /api/chat returns HTTP 405 Method Not Allowed."""
        status, headers, body = self.server.get("/api/chat")
        self.assertEqual(status, 405)
        self.assertIn("POST", headers.get("Allow", ""))

    def test_t2_nonexistent_endpoint_returns_404(self):
        """GET /data/public/nonexistent_file.json returns HTTP 404."""
        status, _, body = self.server.get("/data/public/nonexistent_file.json")
        self.assertEqual(status, 404)

    def test_t2_path_traversal_prevention(self):
        """Attempted path traversal returns 403 or 404."""
        status, _, _ = self.server.get("/data/public/../../server.py")
        self.assertIn(status, [403, 404])

    # =========================================================================
    # OUT-OF-CATALOG QUERY TESTS (HONEST REFUSALS)
    # =========================================================================

    def test_t2_out_of_catalog_queries_refusal_badge_and_zero_hallucinations(self):
        """Verify out-of-catalog queries produce honest refusal with 0 unverified numbers."""
        test_queries = [
            "¿Cuál fue el precio de Bitcoin en Colombia en 2024?",
            "¿Quién ganó el mundial de fútbol y cuántos goles anotó?",
            "¿Cuáles son las reservas de litio en Chile?",
            "¿Cuántos turistas visitaron Cancún en el último mes?",
        ]
        for query in test_queries:
            status, _, body = self.server.post_json("/api/chat", payload={"question": query})
            self.assertEqual(status, 200)
            data = json.loads(body.decode("utf-8"))

            self.assertTrue(data.get("out_of_catalog"), f"Query '{query}' should be out_of_catalog")
            self.assertIn("Dato fuera del catálogo", data.get("badge", ""))
            self.assertIn("Candidato Data360 MCP", data.get("badge", ""))
            self.assertIsNone(data.get("chart"), "Chart must be null for out-of-catalog queries")

            ver = data.get("verification", {})
            self.assertTrue(ver.get("passed"))
            self.assertEqual(ver.get("unverified_count"), 0, "No hallucinations permitted")
            self.assertEqual(len(ver.get("unverified_numbers", [])), 0)

    # =========================================================================
    # METHODOLOGICAL EXCLUSIONS: SI.POV.NAHC
    # =========================================================================

    def test_t2_si_pov_nahc_excluded_from_latam_avg(self):
        """SI.POV.NAHC must be excluded from LATAM_AVG aggregate in observations.csv."""
        csv_path = SNAPSHOT_DIR / "observations.csv"
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            nahc_latam_avg = [
                row for row in reader
                if row["indicator"] == "SI.POV.NAHC" and row["iso3"] == "LATAM_AVG"
            ]
        self.assertEqual(
            len(nahc_latam_avg), 0,
            "SI.POV.NAHC must NEVER have LATAM_AVG observations because national poverty lines are not comparable."
        )

    def test_t2_si_pov_nahc_profile_only_weight_zero(self):
        """SI.POV.NAHC must have profile_only=True and weight=0.0 in catalog.json."""
        with open(PUBLIC_DIR / "catalog.json", "r", encoding="utf-8") as f:
            cat = json.load(f)

        nahc = next((i for i in cat["indicators"] if i["code"] == "SI.POV.NAHC"), None)
        self.assertIsNotNone(nahc)
        self.assertTrue(nahc.get("profile_only"))
        self.assertEqual(nahc.get("composite_default_weight"), 0.0)
        self.assertIn("ADVERTENCIA METODOLÓGICA", nahc.get("methodology_note", ""))

    def test_t2_si_pov_nahc_comparison_redirects_to_cepal_pov_harm(self):
        """Asking to compare poverty using SI.POV.NAHC redirects to CEPAL.POV.HARM with warning."""
        payload = {
            "question": "¿Por qué no se puede usar SI.POV.NAHC para comparar la pobreza entre Colombia y México?"
        }
        status, _, body = self.server.post_json("/api/chat", payload=payload)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))

        self.assertFalse(data.get("out_of_catalog"))
        self.assertEqual(data.get("chart", {}).get("indicator"), "CEPAL.POV.HARM")
        self.assertIn("SI.POV.NAHC", data.get("answer", ""))
        self.assertIn("CEPAL.POV.HARM", data.get("answer", ""))
        self.assertIn("Nota metodológica (ADR-001)", data.get("answer", ""))
        self.assertEqual(data.get("verification", {}).get("unverified_count"), 0)

    def test_t2_si_pov_nahc_single_country_profile_allowed(self):
        """Asking for national poverty line for a single country preserves SI.POV.NAHC."""
        payload = {
            "question": "¿Cuál es la pobreza según la línea nacional propia del DANE en Colombia?"
        }
        status, _, body = self.server.post_json("/api/chat", payload=payload)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))

        self.assertFalse(data.get("out_of_catalog"))
        self.assertEqual(data.get("chart", {}).get("indicator"), "SI.POV.NAHC")
        self.assertEqual(data.get("verification", {}).get("unverified_count"), 0)

    # =========================================================================
    # RENEWABLE ENERGY LAG WARNING: EG.FEC.RNEW.ZS
    # =========================================================================

    def test_t2_renewable_lag_warning_flag(self):
        """EG.FEC.RNEW.ZS must have lag_warning: true and capped at 2022 in observations."""
        with open(PUBLIC_DIR / "catalog.json", "r", encoding="utf-8") as f:
            cat = json.load(f)

        fec_ind = next((i for i in cat["indicators"] if i["code"] == "EG.FEC.RNEW.ZS"), None)
        self.assertIsNotNone(fec_ind)
        self.assertTrue(fec_ind.get("lag_warning"), "lag_warning must be true for EG.FEC.RNEW.ZS")
        self.assertIn("rezago", fec_ind.get("methodology_note", "").lower())

        # Check maximum observation year does not exceed 2022 due to international publication lag
        csv_path = SNAPSHOT_DIR / "observations.csv"
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            years = [int(r["year"]) for r in reader if r["indicator"] == "EG.FEC.RNEW.ZS"]

        self.assertGreater(len(years), 0)
        self.assertLessEqual(max(years), 2022, f"EG.FEC.RNEW.ZS data should be capped at 2022, got max {max(years)}")


if __name__ == "__main__":
    unittest.main()
