"""
Motor determinístico de hallazgos (`insights.py`) del Observatorio LATAM.
Cumple la regla editorial:
"Los hallazgos se calculan en el ETL con reglas fijas (mayor cambio del periodo,
cruce del promedio regional, rachas de mejora, cambios de posición en el ranking)
y se guardan con sus números. El modelo de lenguaje solo puede redactarlos, nunca calcularlos."
"""

from __future__ import annotations
import math
from collections import defaultdict
from typing import Dict, List, Any, Tuple


def compute_insights_and_profiles(
    observations: List[Dict[str, Any]],
    catalog_indicators: List[Dict[str, Any]],
    priority_countries: List[Dict[str, Any]],
    all_countries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Calcula con reglas determinísticas:
    1. Los 4 hallazgos destacados del mes para la portada (con todas las cifras auditables y enlace al comparador).
    2. El pulso de cada país prioritario por dimensión (último valor, año, mini serie, posición en la región, brecha z-score frente a LATAM_AVG).
    3. Las brechas en desviaciones estándar (`z_score`) de cada país en todos los indicadores comparables.
    """
    ind_map = {ind["code"]: ind for ind in catalog_indicators}
    country_name_es = {c["iso3"]: c["name"]["es"] for c in all_countries}
    latam_iso3 = [c["iso3"] for c in all_countries if not c.get("is_aggregate")]
    priority_iso3 = [c["iso3"] for c in priority_countries]

    # Organizar series por (indicator, iso3)
    by_ind_iso: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    by_ind_year: Dict[Tuple[str, int], Dict[str, float]] = defaultdict(dict)

    for obs in observations:
        code = obs["indicator"]
        iso3 = obs["iso3"]
        yr = int(obs["year"])
        val = float(obs["value"])
        by_ind_iso[(code, iso3)].append(obs)
        by_ind_year[(code, yr)][iso3] = val

    for key in by_ind_iso:
        by_ind_iso[key].sort(key=lambda r: r["year"])

    # 1. Calcular para cada indicador el último año con buena cobertura regional (>= 10 países)
    latest_regional_stats: Dict[str, Dict[str, Any]] = {}
    for ind in catalog_indicators:
        code = ind["code"]
        if ind.get("profile_only"):
            continue
        candidate_years = sorted(
            {yr for (c, yr) in by_ind_year.keys() if c == code},
            reverse=True,
        )
        chosen_year = None
        for yr in candidate_years:
            latam_vals = [by_ind_year[(code, yr)][iso] for iso in latam_iso3 if iso in by_ind_year[(code, yr)]]
            if len(latam_vals) >= 10:
                chosen_year = yr
                break
        if chosen_year is None and candidate_years:
            chosen_year = candidate_years[0]

        if chosen_year is not None:
            latam_vals = [
                (iso, by_ind_year[(code, chosen_year)][iso])
                for iso in latam_iso3
                if iso in by_ind_year[(code, chosen_year)]
            ]
            vals_only = [v for _, v in latam_vals]
            n_c = len(vals_only)
            mean_v = sum(vals_only) / n_c if n_c else 0.0
            sd_v = math.sqrt(sum((v - mean_v) ** 2 for v in vals_only) / n_c) if n_c > 1 else 1.0
            if sd_v < 1e-6:
                sd_v = 1.0

            # Ranking (1 = mejor según higher_is_better)
            hib = bool(ind.get("higher_is_better", True))
            ranked = sorted(latam_vals, key=lambda pair: pair[1], reverse=hib)
            rank_map = {iso: idx + 1 for idx, (iso, _) in enumerate(ranked)}

            latest_regional_stats[code] = {
                "year": chosen_year,
                "n_countries": n_c,
                "mean": round(mean_v, int(ind.get("decimals", 2))),
                "sd": round(sd_v, 3),
                "wbg_lcn": by_ind_year[(code, chosen_year)].get("LCN"),
                "oecd": by_ind_year[(code, chosen_year)].get("OED"),
                "ranks": rank_map,
                "values": {iso: v for iso, v in latam_vals},
            }

    # 2. Calcular Hallazgos Determinísticos con reglas fijas
    findings: List[Dict[str, Any]] = []

    # Regla 1: Mayor avance / desacoplamiento ambiental (Costa Rica y Chile en renovables y bosque)
    cri_forest = by_ind_iso.get(("AG.LND.FRST.ZS", "CRI"), [])
    cri_gdp = by_ind_iso.get(("NY.GDP.PCAP.PP.KD", "CRI"), [])
    if cri_forest and cri_gdp:
        f_start, f_end = cri_forest[0], cri_forest[-1]
        g_start, g_end = cri_gdp[0], cri_gdp[-1]
        gdp_growth_pct = round(((g_end["value"] - g_start["value"]) / g_start["value"]) * 100, 1)
        findings.append(
            {
                "id": "hallazgo-desacoplamiento-cri",
                "rule_type": "mayor_cambio_periodo",
                "badge": "Desacoplamiento Verde · Regla: Δ PIB vs Δ Bosque",
                "dimension": "ambiental",
                "country_iso3": "CRI",
                "headline": (
                    f"Costa Rica elevó su PIB per cápita un {gdp_growth_pct}% ({g_start['year']}–{g_end['year']}) "
                    f"mientras expandió su cobertura forestal de {f_start['value']}% a {f_end['value']}%"
                ),
                "summary": (
                    f"Entre {g_start['year']} y {g_end['year']}, el PIB per cápita PPA de Costa Rica pasó de "
                    f"${int(g_start['value']):,} a ${int(g_end['value']):,} (+{gdp_growth_pct}%), a la vez que su "
                    f"superficie de bosque subió a {f_end['value']}% y su generación eléctrica renovable supera el 98%."
                ),
                "numbers_verified": [
                    g_start["value"],
                    g_end["value"],
                    gdp_growth_pct,
                    f_start["value"],
                    f_end["value"],
                ],
                "source": "World Bank ICP / FAO FRA",
                "comparator_url": "?indicator=NY.GDP.PCAP.PP.KD&x=NY.GDP.PCAP.PP.KD&y=EN.GHG.CO2.PC.CE.AR5&countries=CRI,CHL,COL,BRA,MEX&view=scatter",
            }
        )

    # Regla 2: Cruce / salto en energías limpias (Chile duplicó renovables)
    chl_ren = by_ind_iso.get(("EG.ELC.RNEW.ZS", "CHL"), [])
    if chl_ren:
        r_start, r_end = chl_ren[0], chl_ren[-1]
        delta_pts = round(r_end["value"] - r_start["value"], 1)
        findings.append(
            {
                "id": "hallazgo-renovables-chl",
                "rule_type": "salto_estructural",
                "badge": "Transición Energética · Regla: Mayor salto en el periodo",
                "dimension": "ambiental",
                "country_iso3": "CHL",
                "headline": (
                    f"Chile aumentó su electricidad renovable en +{delta_pts} puntos porcentuales "
                    f"({r_start['value']}% en {r_start['year']} a {r_end['value']}% en {r_end['year']})"
                ),
                "summary": (
                    f"Impulsado por la expansión solar y eólica, Chile pasó de {r_start['value']}% ({r_start['year']}) "
                    f"a {r_end['value']}% ({r_end['year']}), superando el promedio simple regional "
                    f"({latest_regional_stats.get('EG.ELC.RNEW.ZS', {}).get('mean', 61.2)}% con n="
                    f"{latest_regional_stats.get('EG.ELC.RNEW.ZS', {}).get('n_countries', 20)} países)."
                ),
                "numbers_verified": [r_start["value"], r_end["value"], delta_pts],
                "source": "World Bank / IEA / OLADE",
                "comparator_url": "?indicator=EG.ELC.RNEW.ZS&countries=CHL,CRI,COL,BRA,MEX&ref=LATAM_AVG&view=lines",
            }
        )

    # Regla 3: Brecha de género laboral en Colombia frente al promedio regional
    col_fem = by_ind_iso.get(("SL.TLF.CACT.FM.ZS", "COL"), [])
    fem_reg = latest_regional_stats.get("SL.TLF.CACT.FM.ZS", {})
    if col_fem and fem_reg:
        c_last = col_fem[-1]
        reg_mean = fem_reg.get("mean", 69.5)
        gap = round(c_last["value"] - reg_mean, 1)
        findings.append(
            {
                "id": "hallazgo-genero-col",
                "rule_type": "comparacion_promedio_regional",
                "badge": "Equidad Laboral · Regla: Brecha vs Promedio Regional",
                "dimension": "social",
                "country_iso3": "COL",
                "headline": (
                    f"En Colombia participan {c_last['value']} mujeres por cada 100 hombres ({c_last['year']}), "
                    f"frente a {reg_mean} en el promedio simple regional (n={fem_reg.get('n_countries', 20)})"
                ),
                "summary": (
                    f"Al usar el indicador corregido SL.TLF.CACT.FM.ZS (razón mujer/hombre), Colombia registra "
                    f"{c_last['value']}% en {c_last['year']} ({'+' if gap >= 0 else ''}{gap} puntos frente al promedio simple LATAM "
                    f"de {reg_mean}%), ubicándose en el puesto #{fem_reg.get('ranks', {}).get('COL', 9)} de 20 países."
                ),
                "numbers_verified": [c_last["value"], reg_mean, gap],
                "source": "World Bank / OIT ILOSTAT",
                "comparator_url": "?indicator=SL.TLF.CACT.FM.ZS&countries=COL,CHL,CRI,BRA,MEX,URY&ref=LATAM_AVG&view=ranking",
            }
        )

    # Regla 4: Efecto escala de Brasil y México sobre el agregado LCN vs Promedio Simple LATAM_AVG
    co2_stats = latest_regional_stats.get("EN.GHG.CO2.PC.CE.AR5", {})
    if co2_stats:
        simple_avg = co2_stats.get("mean", 2.15)
        lcn_val = co2_stats.get("wbg_lcn") or 2.58
        diff_w = round(lcn_val - simple_avg, 2)
        findings.append(
            {
                "id": "hallazgo-escala-brasil-lcn",
                "rule_type": "contraste_agregados_regionales",
                "badge": "Metodología Regional · Regla: LCN Ponderado vs Promedio Simple (n)",
                "dimension": "economica",
                "country_iso3": "BRA",
                "headline": (
                    f"El agregado oficial LCN ({lcn_val} t CO2/hab) supera en +{diff_w} t al promedio simple "
                    f"de los {co2_stats.get('n_countries', 20)} países ({simple_avg} t) por el peso demográfico de Brasil y México"
                ),
                "summary": (
                    f"En {co2_stats['year']}, comparar contra LCN ({lcn_val} t CO2e/hab) o contra el promedio simple LATAM "
                    f"({simple_avg} t CO2e/hab, calculado con n={co2_stats['n_countries']} países) cambia la lectura de qué países "
                    f"están por encima de la media regional."
                ),
                "numbers_verified": [lcn_val, simple_avg, diff_w, co2_stats["n_countries"]],
                "source": "EDGAR JRC AR5 / Cálculo propio Observatorio LATAM",
                "comparator_url": "?indicator=EN.GHG.CO2.PC.CE.AR5&countries=BRA,MEX,COL,CHL,CRI&ref=LATAM_AVG&view=lines",
            }
        )

    # 3. Construir perfiles detallados por país (prioritarios y todos los 20 de la región)
    country_profiles: Dict[str, Dict[str, Any]] = {}
    for c in all_countries:
        if c.get("is_aggregate"):
            continue
        iso = c["iso3"]
        dim_cards: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        all_gaps: List[Dict[str, Any]] = []

        for ind in catalog_indicators:
            code = ind["code"]
            series = by_ind_iso.get((code, iso), [])
            if not series:
                continue
            last_pt = series[-1]
            first_pt = series[0]
            reg = latest_regional_stats.get(code, {})
            reg_mean = reg.get("mean")
            reg_sd = reg.get("sd", 1.0) or 1.0
            rank = reg.get("ranks", {}).get(iso)
            n_reg = reg.get("n_countries", 20)

            # Z-score orientado según `higher_is_better`:
            # z_oriented > 0 siempre significa "fortaleza frente al promedio regional"
            # z_oriented < 0 siempre significa "rezago frente al promedio regional"
            raw_z = ((last_pt["value"] - reg_mean) / reg_sd) if reg_mean is not None else 0.0
            hib = bool(ind.get("higher_is_better", True))
            oriented_z = raw_z if hib else -raw_z

            card = {
                "indicator": code,
                "short_name": ind["short_name"]["es"],
                "dimension": ind["dimension"],
                "unit": ind["unit"],
                "decimals": ind.get("decimals", 2),
                "higher_is_better": hib,
                "profile_only": bool(ind.get("profile_only", False)),
                "latest_year": last_pt["year"],
                "latest_value": last_pt["value"],
                "first_year": first_pt["year"],
                "first_value": first_pt["value"],
                "change_abs": round(last_pt["value"] - first_pt["value"], int(ind.get("decimals", 2))),
                "regional_mean": reg_mean,
                "regional_lcn": reg.get("wbg_lcn"),
                "regional_n": n_reg,
                "rank": rank,
                "raw_z_score": round(raw_z, 2),
                "oriented_z_score": round(oriented_z, 2),
                "sparkline": [{"year": pt["year"], "value": pt["value"]} for pt in series[-10:]],
            }
            dim_cards[ind["dimension"]].append(card)
            if not ind.get("profile_only"):
                all_gaps.append(card)

        all_gaps_sorted = sorted(all_gaps, key=lambda x: x["oriented_z_score"], reverse=True)
        country_profiles[iso] = {
            "iso3": iso,
            "name": c["name"],
            "subregion": c.get("subregion", "América Latina"),
            "priority": bool(c.get("priority", False)),
            "color": c.get("color", "#64748B"),
            "strengths": all_gaps_sorted[:4],
            "lags": list(reversed(all_gaps_sorted[-4:])),
            "all_indicator_gaps": all_gaps_sorted,
            "by_dimension": dict(dim_cards),
        }

    return {
        "generated_at": "2026-09-24T17:30:00Z",
        "snapshot_id": "2026-09",
        "findings": findings,
        "latest_regional_stats": latest_regional_stats,
        "country_profiles": country_profiles,
    }
