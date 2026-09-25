"""
Validación de calidad estadística y generación del Mapa de Cobertura de Datos (Visualización #8).
Revisa:
1. Rangos válidos (`valid_range` de `catalog.yaml`)
2. Saltos interanuales atípicos (> 3.5 desviaciones estándar intra-serie)
3. Cobertura temporal y geográfica por indicador y país (2010–2024)
"""

from __future__ import annotations
import math
from collections import defaultdict
from typing import Dict, List, Any, Tuple


def validate_and_compute_coverage(
    observations: List[Dict[str, Any]],
    catalog_indicators: List[Dict[str, Any]],
    countries_list: List[Dict[str, Any]],
    start_year: int = 2010,
    end_year: int = 2024,
) -> Dict[str, Any]:
    """
    Ejecuta controles de rango, detecta saltos bruscos y genera la matriz de cobertura
    para el Mapa de Cobertura del portal.
    """
    ind_map = {ind["code"]: ind for ind in catalog_indicators}
    total_expected_years = end_year - start_year + 1
    latam_countries = [c["iso3"] for c in countries_list if not c.get("is_aggregate")]

    range_violations: List[Dict[str, Any]] = []
    sudden_jumps: List[Dict[str, Any]] = []

    by_series: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    years_present_by_ind_country: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    countries_by_ind_year: Dict[Tuple[str, int], int] = defaultdict(int)

    for obs in observations:
        code = obs["indicator"]
        iso3 = obs["iso3"]
        yr = int(obs["year"])
        val = float(obs["value"])

        ind_meta = ind_map.get(code, {})
        v_range = ind_meta.get("valid_range")
        if v_range and len(v_range) == 2:
            low, high = float(v_range[0]), float(v_range[1])
            if val < low or val > high:
                range_violations.append(
                    {
                        "indicator": code,
                        "iso3": iso3,
                        "year": yr,
                        "value": val,
                        "expected_range": [low, high],
                    }
                )

        by_series[(code, iso3)].append(obs)
        if start_year <= yr <= end_year and iso3 in latam_countries:
            years_present_by_ind_country[(code, iso3)].append(yr)
            countries_by_ind_year[(code, yr)] += 1

    # Detectar saltos interanuales atípicos (> 3.5 SD)
    for (code, iso3), series in by_series.items():
        series_sorted = sorted(series, key=lambda x: x["year"])
        diffs = []
        for i in range(1, len(series_sorted)):
            if series_sorted[i]["year"] - series_sorted[i - 1]["year"] == 1:
                diffs.append(series_sorted[i]["value"] - series_sorted[i - 1]["value"])
        if len(diffs) >= 5:
            mean_d = sum(diffs) / len(diffs)
            var_d = sum((d - mean_d) ** 2 for d in diffs) / len(diffs)
            sd_d = math.sqrt(var_d) if var_d > 0 else 0.0
            if sd_d > 1e-6:
                for i in range(1, len(series_sorted)):
                    if series_sorted[i]["year"] - series_sorted[i - 1]["year"] == 1:
                        delta = series_sorted[i]["value"] - series_sorted[i - 1]["value"]
                        z = abs(delta - mean_d) / sd_d
                        if z > 3.8:
                            sudden_jumps.append(
                                {
                                    "indicator": code,
                                    "iso3": iso3,
                                    "year": series_sorted[i]["year"],
                                    "delta": round(delta, 2),
                                    "z_score": round(z, 2),
                                }
                            )

    # Construir matriz de cobertura por indicador x país y por indicador x año
    coverage_by_indicator: List[Dict[str, Any]] = []
    for ind in catalog_indicators:
        code = ind["code"]
        country_cells: Dict[str, Dict[str, Any]] = {}
        total_pts = 0
        for iso3 in latam_countries:
            yrs = sorted(set(years_present_by_ind_country.get((code, iso3), [])))
            n_yrs = len(yrs)
            total_pts += n_yrs
            country_cells[iso3] = {
                "years_count": n_yrs,
                "coverage_pct": round((n_yrs / total_expected_years) * 100, 1),
                "latest_year": max(yrs) if yrs else None,
                "first_year": min(yrs) if yrs else None,
            }

        year_counts = {
            str(yr): countries_by_ind_year.get((code, yr), 0)
            for yr in range(start_year, end_year + 1)
        }
        max_possible = len(latam_countries) * total_expected_years
        overall_pct = round((total_pts / max_possible) * 100, 1) if max_possible else 0.0

        coverage_by_indicator.append(
            {
                "indicator": code,
                "name": ind["short_name"]["es"],
                "dimension": ind["dimension"],
                "overall_coverage_pct": overall_pct,
                "by_country": country_cells,
                "n_by_year": year_counts,
            }
        )

    return {
        "status": "PASSED" if len(range_violations) == 0 else "WARNING",
        "total_observations": len(observations),
        "range_violations_count": len(range_violations),
        "range_violations": range_violations[:20],
        "sudden_jumps_count": len(sudden_jumps),
        "sudden_jumps": sudden_jumps[:20],
        "coverage_matrix": coverage_by_indicator,
    }
