"""
Tier 3: Cross-Feature Combinations Test Suite for Observatorio LATAM.
Covers:
- Comparator query URL parameters schema and reflection
- Scrollytelling 'Explóralo tú' URL parameters mapping to valid snapshot data
- Chat inline chart comparator URL consistency with generated chart spec
- Composite index recalculation with dynamic weights and directionality
"""

from __future__ import annotations
import json
from pathlib import Path
import re
import unittest
import urllib.parse

from tests.e2e.server_manager import get_shared_server

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = WORKSPACE_ROOT / "data"
PUBLIC_DIR = DATA_DIR / "public"
HISTORIAS_DIR = WORKSPACE_ROOT / "web" / "content" / "historias"


class TestTier3Combinations(unittest.TestCase):
    """Tier 3 Cross-Feature Combination Tests."""

    @classmethod
    def setUpClass(cls):
        cls.server = get_shared_server()

        with open(PUBLIC_DIR / "catalog.json", "r", encoding="utf-8") as f:
            cls.catalog = json.load(f)
        with open(PUBLIC_DIR / "countries.json", "r", encoding="utf-8") as f:
            cls.countries_doc = json.load(f)
        with open(PUBLIC_DIR / "all_observations.json", "r", encoding="utf-8") as f:
            cls.all_observations = json.load(f)

        cls.obs_dict = {}
        for row in cls.all_observations:
            cls.obs_dict.setdefault(row["indicator"], {}).setdefault(row["iso3"], {})[str(row["year"])] = row["value"]

        cls.valid_indicators = {i["code"]: i for i in cls.catalog["indicators"]}
        cls.valid_countries = {
            c["iso3"]: c
            for c in (
                cls.countries_doc["priority_countries"]
                + cls.countries_doc["region_countries"]
                + cls.countries_doc["aggregates"]
            )
        }

    def setUp(self):
        super().setUp()
        if not hasattr(self, "server") or self.server is None or not hasattr(self, "obs_dict"):
            self.__class__.setUpClass()

    # =========================================================================
    # COMPARATOR QUERY URL PARAMETERS
    # =========================================================================

    def test_t3_comparator_query_url_parsing_and_schema(self):
        """Validate parsing and validation of standard comparator query URLs."""
        test_urls = [
            "?indicator=EN.GHG.CO2.PC.CE.AR5&countries=COL,CHL,CRI,BRA,MEX&ref=LATAM_AVG&view=lines",
            "?indicator=NY.GDP.PCAP.PP.KD&countries=CHL,URY,PAN,CRI,COL&ref=LCN&view=ranking",
            "?indicator=NY.GDP.PCAP.PP.KD&x=NY.GDP.PCAP.PP.KD&y=EN.GHG.CO2.PC.CE.AR5&countries=CRI,CHL,COL,BRA,MEX&view=scatter",
            "?indicator=SI.POV.GINI&countries=COL,BRA,CHL,MEX,CRI&ref=LATAM_AVG&view=table",
        ]

        allowed_views = {"lines", "ranking", "scatter", "table"}

        for url in test_urls:
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)

            # Indicator must exist
            ind_code = params.get("indicator", [None])[0]
            self.assertIn(ind_code, self.valid_indicators, f"Unknown indicator {ind_code} in {url}")

            # Secondary / x-y indicators if present
            if "y" in params:
                self.assertIn(params["y"][0], self.valid_indicators)
            if "x" in params:
                self.assertIn(params["x"][0], self.valid_indicators)

            # Countries must exist
            if "countries" in params:
                countries = params["countries"][0].split(",")
                for c in countries:
                    self.assertIn(c, self.valid_countries, f"Unknown country {c} in {url}")

            # Ref benchmark if present
            if "ref" in params:
                ref = params["ref"][0]
                self.assertIn(ref, self.valid_countries)
                self.assertTrue(self.valid_countries[ref].get("is_aggregate", False))

            # View mode
            if "view" in params:
                view = params["view"][0]
                self.assertIn(view, allowed_views)

    # =========================================================================
    # SCROLLYTELLING URL PARAMETERS
    # =========================================================================

    def test_t3_scrollytelling_urls_resolve_to_valid_dataset(self):
        """Verify that comparator URLs embedded in scrollytelling stories resolve to valid observations."""
        self.assertTrue(HISTORIAS_DIR.is_dir(), f"Missing {HISTORIAS_DIR}")

        story_files = list(HISTORIAS_DIR.glob("*.mdx"))
        self.assertGreaterEqual(len(story_files), 2, "Expected at least 2 story mdx files")

        url_patterns = [
            r'comparator_state:\s*"(.*?)"',
            r'url="(.*?)"',
        ]

        found_urls = []
        for sf in story_files:
            content = sf.read_text(encoding="utf-8")
            for pattern in url_patterns:
                for match in re.findall(pattern, content):
                    if match.startswith("?"):
                        found_urls.append((sf.name, match))

        self.assertGreater(len(found_urls), 0, "No comparator URLs found in stories")

        for story_name, url in found_urls:
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)

            primary_ind = params.get("indicator", [None])[0]
            self.assertIn(
                primary_ind, self.valid_indicators,
                f"Story {story_name} references unknown indicator {primary_ind}"
            )

            countries = params.get("countries", [""])[0].split(",")
            for c in countries:
                if not c:
                    continue
                self.assertIn(c, self.valid_countries, f"Story {story_name} references unknown country {c}")
                # Verify observation exists in all_observations
                ind_obs = self.obs_dict.get(primary_ind, {})
                c_obs = ind_obs.get(c, {})
                self.assertGreater(
                    len(c_obs), 0,
                    f"Story {story_name} country {c} has no observations for {primary_ind}"
                )

    # =========================================================================
    # CHAT INLINE CHART COMPARATOR URL CONSISTENCY
    # =========================================================================

    def test_t3_chat_inline_chart_comparator_urls(self):
        """Verify POST /api/chat returns chart with valid comparator_url matching response specs."""
        test_questions = [
            ("¿Cuál es el PIB per cápita de Costa Rica y cómo creció?", "NY.GDP.PCAP.PP.KD"),
            ("¿Cómo se comparan las emisiones de CO2 entre Colombia y Chile?", "EN.GHG.CO2.PC.CE.AR5"),
            ("Ranking de generación eléctrica renovable en América Latina", "EG.ELC.RNEW.ZS"),
            ("¿Existe desacoplamiento entre PIB y emisiones de CO2 en Costa Rica?", "NY.GDP.PCAP.PP.KD"),
        ]

        for q, expected_ind in test_questions:
            status, _, body = self.server.post_json("/api/chat", payload={"question": q})
            self.assertEqual(status, 200)
            data = json.loads(body.decode("utf-8"))

            self.assertFalse(data.get("out_of_catalog"))
            chart = data.get("chart")
            self.assertIsNotNone(chart, f"Expected chart for query: {q}")
            self.assertEqual(chart.get("indicator"), expected_ind)

            comp_url = chart.get("comparator_url")
            self.assertIsNotNone(comp_url)
            self.assertTrue(comp_url.startswith("?"))

            # Validate comparator URL contents
            parsed = urllib.parse.urlparse(comp_url)
            params = urllib.parse.parse_qs(parsed.query)

            self.assertEqual(params.get("indicator", [None])[0], chart["indicator"])
            self.assertEqual(params.get("view", [None])[0], chart["chart_type"])

            # Verify countries in comparator URL match chart countries
            url_countries = set(params.get("countries", [""])[0].split(","))
            chart_countries = set(chart.get("countries", []))
            self.assertTrue(
                chart_countries.issubset(url_countries) or url_countries.issubset(chart_countries),
                f"Country mismatch between chart {chart_countries} and URL {url_countries}"
            )

    # =========================================================================
    # COMPOSITE INDEX RECALCULATION & DIRECTIONALITY
    # =========================================================================

    def test_t3_composite_index_dynamic_recalculation_and_directionality(self):
        """Verify dynamic calculation of composite index across 20 countries respects directionality."""
        regional_iso3 = [c["iso3"] for c in self.countries_doc["priority_countries"] + self.countries_doc["region_countries"]]
        self.assertEqual(len(regional_iso3), 20)

        # Build latest value vector for each country across 14 indicators (excluding SI.POV.NAHC)
        eligible_indicators = [
            i for i in self.catalog["indicators"]
            if not i.get("profile_only", False)
        ]
        self.assertEqual(len(eligible_indicators), 14)

        # Extract latest available values per indicator and country
        data_matrix: dict[str, dict[str, float]] = {c: {} for c in regional_iso3}
        for ind in eligible_indicators:
            code = ind["code"]
            ind_data = self.obs_dict.get(code, {})
            for c in regional_iso3:
                series = ind_data.get(c, {})
                if series:
                    max_yr = max(series.keys())
                    data_matrix[c][code] = float(series[max_yr])
                else:
                    data_matrix[c][code] = 0.0

        def calculate_composite_index(weights: dict[str, float]) -> list[tuple[str, float, int]]:
            # Min-Max Normalization per indicator
            normalized: dict[str, dict[str, float]] = {c: {} for c in regional_iso3}
            for ind in eligible_indicators:
                code = ind["code"]
                vals = [data_matrix[c].get(code, 0.0) for c in regional_iso3]
                min_v = min(vals)
                max_v = max(vals)
                rng = (max_v - min_v) if max_v != min_v else 1.0

                for c in regional_iso3:
                    raw = data_matrix[c].get(code, 0.0)
                    norm = (raw - min_v) / rng
                    # Invert if higher is worse (poverty, CO2, Gini, unemployment, inflation)
                    if not ind.get("higher_is_better", True):
                        norm = 1.0 - norm
                    normalized[c][code] = norm

            # Compute weighted sum
            scores: list[tuple[str, float]] = []
            total_w = sum(weights.values()) or 1.0
            for c in regional_iso3:
                c_score = sum(normalized[c][code] * (weights.get(code, 0.0) / total_w) for code in weights)
                scores.append((c, round(c_score * 100.0, 2)))

            scores.sort(key=lambda x: x[1], reverse=True)
            # Assign ranks 1..20
            ranked = [(s[0], s[1], rank + 1) for rank, s in enumerate(scores)]
            return ranked

        # Scenario A: Default weights from catalog
        default_weights = {i["code"]: i.get("composite_default_weight", 0.0) for i in eligible_indicators}
        self.assertAlmostEqual(sum(default_weights.values()), 1.0, places=2)
        ranking_default = calculate_composite_index(default_weights)
        self.assertEqual(len(ranking_default), 20)
        ranks = [r[2] for r in ranking_default]
        self.assertEqual(ranks, list(range(1, 21)))

        # Scenario B: 100% weight on Renewable Electricity (EG.ELC.RNEW.ZS)
        green_weights = {"EG.ELC.RNEW.ZS": 1.0}
        ranking_green = calculate_composite_index(green_weights)
        top_green = ranking_green[0][0]
        # Costa Rica or Paraguay should be #1 in renewable electricity
        self.assertIn(top_green, ["CRI", "PRY"])

        # Scenario C: 100% weight on GDP per capita (NY.GDP.PCAP.PP.KD)
        gdp_weights = {"NY.GDP.PCAP.PP.KD": 1.0}
        ranking_gdp = calculate_composite_index(gdp_weights)
        top_gdp = ranking_gdp[0][0]
        # Chile, Panama, or Uruguay should be #1 in GDP per capita PPP
        self.assertIn(top_gdp, ["CHL", "PAN", "URY"])

        # Confirm dynamic weights produce distinct rankings
        self.assertNotEqual([r[0] for r in ranking_green], [r[0] for r in ranking_gdp])


if __name__ == "__main__":
    unittest.main()
