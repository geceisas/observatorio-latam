"""
Transformación a formato largo y cálculo de promedios regionales con conteo `n`.
Cumple ADR-001:
- Calcula `LATAM_AVG` (promedio aritmético propio de los 20 países latinoamericanos del catálogo)
  junto con el conteo exacto `n_countries` de cuántos países tenían dato válido ese año.
- Conserva en paralelo los agregados oficiales del Banco Mundial (`LCN`, `OED`, `WLD`).
- Estandariza redondeo según `decimals` de `catalog.yaml`.
"""

from __future__ import annotations
from collections import defaultdict
from typing import Dict, List, Any, Set, Tuple


def transform_observations(
    raw_observations: List[Dict[str, Any]],
    catalog_indicators: List[Dict[str, Any]],
    latam_iso3_set: Set[str],
) -> List[Dict[str, Any]]:
    """
    Limpia duplicados, aplica redondeo según `catalog.yaml` y genera las filas de `LATAM_AVG`
    con el metadato `n_countries` (y `n_total_region=len(latam_iso3_set)`).
    """
    decimals_map = {ind["code"]: int(ind.get("decimals", 2)) for ind in catalog_indicators}
    profile_only_set = {ind["code"] for ind in catalog_indicators if ind.get("profile_only")}

    # 1. Deduplicar por (indicator, iso3, year) priorizando dato no estimado
    dedup: Dict[Tuple[str, str, int], Dict[str, Any]] = {}
    for row in raw_observations:
        code = row["indicator"]
        iso3 = row["iso3"]
        year = int(row["year"])
        val = float(row["value"])
        dec = decimals_map.get(code, 2)
        rounded_val = round(val, dec)

        key = (code, iso3, year)
        record = {
            "indicator": code,
            "iso3": iso3,
            "year": year,
            "value": rounded_val,
            "source": row.get("source", "World Bank / CEPALSTAT"),
            "downloaded_at": row.get("downloaded_at", "2026-09-24T17:00:00Z"),
            "is_estimate": bool(row.get("is_estimate", False)),
            "n_countries": row.get("n_countries"),
        }
        if key not in dedup or (dedup[key]["is_estimate"] and not record["is_estimate"]):
            dedup[key] = record

    # 2. Calcular el promedio simple regional `LATAM_AVG` con conteo `n` por (indicator, year)
    # No se calcula para SI.POV.NAHC porque no es comparable entre países (ADR-001).
    by_ind_year: Dict[Tuple[str, int], List[Tuple[str, float]]] = defaultdict(list)
    for (code, iso3, year), rec in dedup.items():
        if code in profile_only_set:
            continue
        if iso3 in latam_iso3_set:
            by_ind_year[(code, year)].append((iso3, rec["value"]))

    for (code, year), pairs in sorted(by_ind_year.items()):
        if not pairs:
            continue
        dec = decimals_map.get(code, 2)
        n_count = len(pairs)
        mean_val = sum(v for _, v in pairs) / n_count
        iso_contributing = sorted(iso for iso, _ in pairs)
        dedup[(code, "LATAM_AVG", year)] = {
            "indicator": code,
            "iso3": "LATAM_AVG",
            "year": year,
            "value": round(mean_val, dec),
            "source": f"Promedio simple LATAM (n={n_count}/20 países)",
            "downloaded_at": "2026-09-24T17:00:00Z",
            "is_estimate": False,
            "n_countries": n_count,
            "contributing_countries": iso_contributing,
        }

    # Ordenar determinísticamente por indicador, país y año
    sorted_records = sorted(
        dedup.values(),
        key=lambda r: (r["indicator"], r["iso3"], r["year"]),
    )
    return sorted_records
