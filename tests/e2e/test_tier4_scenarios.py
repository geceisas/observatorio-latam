"""
Tier 4: Real-World Scenarios Test Suite for Observatorio LATAM.
Covers:
- Costa Rica Decoupling: GDP growth vs forest expansion, high renewables, and low CO2
- Chile / Colombia Inequality & Labor Parity: Chile high GDP + high Gini vs Colombia Gini & labor parity
- Brasil Scale Impact: Weighted regional aggregate (LCN) vs simple arithmetic average (LATAM_AVG)
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


class TestTier4Scenarios(unittest.TestCase):
    """Tier 4 Real-World Application Scenario Tests."""

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

        with open(PUBLIC_DIR / "insights.json", "r", encoding="utf-8") as f:
            cls.insights = json.load(f)

    def setUp(self):
        super().setUp()
        if not hasattr(self, "server") or self.server is None or not hasattr(self, "obs_dict"):
            self.__class__.setUpClass()

    # =========================================================================
    # SCENARIO 1: COSTA RICA GREEN DECOUPLING
    # =========================================================================

    def test_t4_costa_rica_decoupling_data_consistency(self):
        """Verify Costa Rica empirical decoupling: GDP per capita growth alongside forest expansion and clean electricity."""
        cri_gdp = self.obs_dict["NY.GDP.PCAP.PP.KD"]["CRI"]
        cri_forest = self.obs_dict["AG.LND.FRST.ZS"]["CRI"]
        cri_clean_elc = self.obs_dict["EG.ELC.RNEW.ZS"]["CRI"]
        cri_co2 = self.obs_dict["EN.GHG.CO2.PC.CE.AR5"]["CRI"]

        # GDP grew significantly from 2010 to 2024
        gdp_2010 = float(cri_gdp["2010"])
        gdp_2024 = float(cri_gdp["2024"])
        gdp_growth_pct = ((gdp_2024 - gdp_2010) / gdp_2010) * 100.0
        self.assertGreater(gdp_growth_pct, 40.0, f"Expected CRI GDP growth >40%, got {gdp_growth_pct:.1f}%")

        # Forest coverage expanded and exceeds 55%
        forest_latest_yr = max(cri_forest.keys())
        forest_val = float(cri_forest[forest_latest_yr])
        self.assertGreater(forest_val, 55.0, f"Expected CRI forest coverage >55%, got {forest_val}%")

        # Renewable electricity generation exceeds 95%
        clean_elc_latest_yr = max(cri_clean_elc.keys())
        clean_elc_val = float(cri_clean_elc[clean_elc_latest_yr])
        self.assertGreater(clean_elc_val, 95.0, f"Expected CRI renewable electricity >95%, got {clean_elc_val}%")

        # CO2 per capita is far below OECD benchmark (OED)
        oed_co2 = self.obs_dict["EN.GHG.CO2.PC.CE.AR5"]["OED"]
        co2_latest_yr = max(cri_co2.keys())
        self.assertLess(
            float(cri_co2[co2_latest_yr]),
            float(oed_co2[co2_latest_yr]),
            "CRI CO2 per capita must be substantially lower than OECD average"
        )

    def test_t4_costa_rica_decoupling_chat_response(self):
        """Verify chat agent returns audited analysis of Costa Rica green decoupling."""
        payload = {
            "question": "¿Cómo logró Costa Rica crecer económicamente mientras descarbonizaba su matriz y recuperaba bosque?"
        }
        status, _, body = self.server.post_json("/api/chat", payload=payload)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))

        self.assertFalse(data.get("out_of_catalog"))
        self.assertTrue("Costa Rica" in data.get("answer", "") or "CRI" in data.get("answer", ""))
        self.assertTrue(data.get("verification", {}).get("passed"))
        self.assertEqual(data.get("verification", {}).get("unverified_count"), 0)

    # =========================================================================
    # SCENARIO 2: CHILE & COLOMBIA INEQUALITY & LABOR PARITY
    # =========================================================================

    def test_t4_chile_vs_colombia_income_and_gini_gap(self):
        """Verify Chile higher GDP per capita vs persistent inequality, and Colombia Gini & labor parity."""
        chl_gdp = float(self.obs_dict["NY.GDP.PCAP.PP.KD"]["CHL"]["2024"])
        col_gdp = float(self.obs_dict["NY.GDP.PCAP.PP.KD"]["COL"]["2024"])
        self.assertGreater(chl_gdp, col_gdp, "Chile GDP per capita must exceed Colombia")

        # Gini comparison
        chl_gini = self.obs_dict["SI.POV.GINI"]["CHL"]
        col_gini = self.obs_dict["SI.POV.GINI"]["COL"]
        chl_gini_latest = float(chl_gini[max(chl_gini.keys())])
        col_gini_latest = float(col_gini[max(col_gini.keys())])

        # Both have elevated Gini (>40), with Colombia exhibiting greater concentration (>50)
        self.assertGreater(chl_gini_latest, 40.0)
        self.assertGreater(col_gini_latest, 50.0)

        # Colombia female/male labor ratio (100 = parity)
        col_ratio_series = self.obs_dict["SL.TLF.CACT.FM.ZS"]["COL"]
        col_ratio_latest = float(col_ratio_series[max(col_ratio_series.keys())])
        self.assertGreater(col_ratio_latest, 65.0)

        # Poverty comparison between CHL and COL must use CEPAL.POV.HARM
        chl_poverty = float(self.obs_dict["CEPAL.POV.HARM"]["CHL"]["2024"])
        col_poverty = float(self.obs_dict["CEPAL.POV.HARM"]["COL"]["2024"])
        self.assertLess(chl_poverty, col_poverty, "Chile harmonized poverty must be lower than Colombia")

    def test_t4_chile_colombia_chat_query_adherence(self):
        """Verify chat agent adheres to ADR-001 harmonized poverty when comparing Chile and Colombia."""
        payload = {
            "question": "¿Cómo se comparan la pobreza y la desigualdad entre Chile y Colombia?"
        }
        status, _, body = self.server.post_json("/api/chat", payload=payload)
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))

        self.assertFalse(data.get("out_of_catalog"))
        self.assertTrue(data.get("verification", {}).get("passed"))
        self.assertEqual(data.get("verification", {}).get("unverified_count"), 0)
        # Check that CEPAL.POV.HARM or SI.POV.GINI was used
        indicator_used = data.get("chart", {}).get("indicator")
        self.assertIn(indicator_used, ["CEPAL.POV.HARM", "SI.POV.GINI"])

    # =========================================================================
    # SCENARIO 3: BRASIL SCALE IMPACT & REGIONAL AGGREGATES CONTRAST
    # =========================================================================

    def test_t4_brasil_scale_impact_and_latam_avg_vs_lcn(self):
        """Verify difference between weighted LCN aggregate (driven by Brazil) and simple LATAM_AVG with n countries."""
        # Test GDP per capita PPP: LCN vs LATAM_AVG
        latam_avg_gdp = self.obs_dict["NY.GDP.PCAP.PP.KD"]["LATAM_AVG"]
        lcn_gdp = self.obs_dict["NY.GDP.PCAP.PP.KD"]["LCN"]

        # Both must exist and have data
        self.assertGreater(len(latam_avg_gdp), 0)
        self.assertGreater(len(lcn_gdp), 0)

        # LCN and LATAM_AVG values diverge because LCN is population/GDP weighted, not simple average
        common_years = set(latam_avg_gdp.keys()) & set(lcn_gdp.keys())
        divergence_found = False
        for yr in common_years:
            val_latam = float(latam_avg_gdp[yr])
            val_lcn = float(lcn_gdp[yr])
            if abs(val_latam - val_lcn) > 10.0:  # Noticeable statistical difference
                divergence_found = True
                break
        self.assertTrue(divergence_found, "LATAM_AVG (simple) and LCN (weighted) must statistically diverge")

    def test_t4_latam_avg_arithmetic_reproducibility(self):
        """Verify that LATAM_AVG represents the exact arithmetic mean of reporting countries."""
        csv_path = SNAPSHOT_DIR / "observations.csv"
        target_indicator = "NY.GDP.PCAP.PP.KD"
        target_year = "2022"

        regional_iso3 = {c["iso3"] for c in self.countries_doc["priority_countries"] + self.countries_doc["region_countries"]}

        country_values = []
        latam_avg_recorded = None
        latam_n_countries = None
        latam_source = ""

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["indicator"] == target_indicator and row["year"] == target_year:
                    iso = row["iso3"]
                    if iso in regional_iso3 and row["value"]:
                        country_values.append(float(row["value"]))
                    elif iso == "LATAM_AVG":
                        latam_avg_recorded = float(row["value"])
                        latam_n_countries = row.get("n_countries")
                        latam_source = row.get("source", "")

        self.assertIsNotNone(latam_avg_recorded, f"Missing LATAM_AVG for {target_indicator} in {target_year}")
        self.assertGreater(len(country_values), 15, "Expected majority of 20 countries reporting in 2022")

        calculated_mean = sum(country_values) / len(country_values)
        # Check within standard precision rounding
        self.assertAlmostEqual(
            calculated_mean, latam_avg_recorded, delta=1.0,
            msg=f"Calculated mean {calculated_mean:.2f} differs from recorded LATAM_AVG {latam_avg_recorded:.2f}"
        )

        # Check n_countries is reflected in n_countries column or source description
        self.assertTrue(
            str(len(country_values)) == str(latam_n_countries) or f"n={len(country_values)}" in latam_source,
            f"Expected n={len(country_values)} in source or n_countries, got n_countries={latam_n_countries}, source={latam_source}"
        )


if __name__ == "__main__":
    unittest.main()
