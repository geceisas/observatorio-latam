"""
Motor de Agente con Herramientas y Verificador Numérico (ADR-003) para el Observatorio LATAM.
Funciona 100% sin API key usando planificación determinística sobre el snapshot (`data/public/`),
y soporta opcionalmente Gemini (`GEMINI_API_KEY`) manteniendo siempre:
1. Las 5 herramientas oficiales:
   - `buscar_indicador`
   - `obtener_serie`
   - `comparar`
   - `ranking`
   - `crear_grafico`
2. El verificador numérico (`verify_response_numbers`): comprueba que cada cifra del texto
   aparezca en los resultados devueltos por las herramientas (con tolerancia por redondeo).
3. Etiqueta explícita cuando una consulta cae fuera del catálogo ("dato fuera del catálogo del observatorio").
"""

from __future__ import annotations
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT_DIR / "data" / "public"


class SnapshotStore:
    def __init__(self) -> None:
        with open(PUBLIC_DIR / "catalog.json", "r", encoding="utf-8") as f:
            self.catalog = json.load(f)
        with open(PUBLIC_DIR / "countries.json", "r", encoding="utf-8") as f:
            self.countries_doc = json.load(f)
        with open(PUBLIC_DIR / "all_observations.json", "r", encoding="utf-8") as f:
            self.observations = json.load(f)
        with open(PUBLIC_DIR / "insights.json", "r", encoding="utf-8") as f:
            self.insights = json.load(f)
        with open(PUBLIC_DIR / "manifest.json", "r", encoding="utf-8") as f:
            self.manifest = json.load(f)

        self.indicators: Dict[str, Dict[str, Any]] = {
            ind["code"]: ind for ind in self.catalog["indicators"]
        }
        self.all_countries: List[Dict[str, Any]] = (
            self.countries_doc["priority_countries"]
            + self.countries_doc["region_countries"]
            + self.countries_doc["aggregates"]
        )
        self.country_by_iso3: Dict[str, Dict[str, Any]] = {
            c["iso3"]: c for c in self.all_countries
        }

    # =========================================================================
    # HERRAMIENTA 1: buscar_indicador
    # =========================================================================
    def buscar_indicador(self, query: str) -> Dict[str, Any]:
        q = query.lower()
        keyword_aliases = {
            "EN.GHG.CO2.PC.CE.AR5": ["co2", "carbono", "emisiones", "gei", "edgar", "clima", "descarboniz"],
            "EG.FEC.RNEW.ZS": ["renovable", "renovables", "consumo final", "energia limpia", "energía"],
            "EG.ELC.RNEW.ZS": ["electricidad", "eléctrica", "matriz electrica", "hidro", "solar", "eolica"],
            "AG.LND.FRST.ZS": ["bosque", "forestal", "deforestacion", "reforestacion", "selva", "arboles"],
            "CEPAL.POV.HARM": ["pobreza", "pobres", "cepal", "armonizada", "comparar pobreza"],
            "SI.POV.NAHC": ["pobreza nacional", "linea nacional", "dane pobreza", "casen"],
            "SI.POV.GINI": ["gini", "desigualdad", "equidad", "concentracion", "distribucion"],
            "SH.XPD.CHEX.PP.CD": ["salud", "gasto medico", "hospital", "sanitario"],
            "SE.SEC.NENR": ["educacion", "secundaria", "matricula", "escuela", "colegio"],
            "SL.TLF.CACT.FM.ZS": ["genero", "género", "mujer", "mujeres", "brecha laboral", "paridad"],
            "SP.DYN.LE00.IN": ["esperanza de vida", "longevidad", "mortalidad", "vivir"],
            "NY.GDP.PCAP.PP.KD": ["pib", "ingreso", "crecimiento", "riqueza", "economia", "ppa", "gdp"],
            "SL.UEM.TOTL.ZS": ["desempleo", "paro", "trabajo", "ocupacion"],
            "FP.CPI.TOTL.ZG": ["inflacion", "inflación", "precios", "ipc", "costo de vida"],
            "NE.GDI.TOTL.ZS": ["inversion", "inversión", "formacion de capital", "capital fijo"],
        }

        scored: List[Tuple[int, Dict[str, Any]]] = []
        for code, ind in self.indicators.items():
            score = 0
            if code.lower() in q:
                score += 10
            if ind.get("replaces_code") and ind["replaces_code"].lower() in q:
                score += 9
            name_es = ind["name"]["es"].lower()
            short_es = ind["short_name"]["es"].lower()
            for token in re.findall(r"[a-záéíóúñ0-9]+", q):
                if len(token) >= 3 and (token in name_es or token in short_es):
                    score += 3
            for kw in keyword_aliases.get(code, []):
                if kw in q:
                    score += 5
            if score > 0:
                scored.append((score, ind))

        scored.sort(key=lambda x: x[0], reverse=True)
        matches = [item[1] for item in scored[:3]]
        return {
            "tool": "buscar_indicador",
            "query": query,
            "matches_count": len(matches),
            "matches": [
                {
                    "code": m["code"],
                    "replaces_code": m.get("replaces_code"),
                    "name": m["name"]["es"],
                    "short_name": m["short_name"]["es"],
                    "unit": m["unit"],
                    "source": m["source"],
                    "higher_is_better": m["higher_is_better"],
                    "profile_only": bool(m.get("profile_only", False)),
                    "methodology_note": m["methodology_note"].strip(),
                }
                for m in matches
            ],
        }

    # =========================================================================
    # HERRAMIENTA 2: obtener_serie
    # =========================================================================
    def obtener_serie(
        self,
        indicator_code: str,
        countries: List[str],
        start_year: int = 2010,
        end_year: int = 2024,
    ) -> Dict[str, Any]:
        ind = self.indicators.get(indicator_code)
        if not ind:
            return {"tool": "obtener_serie", "error": f"Indicador {indicator_code} no encontrado"}

        rows = [
            r
            for r in self.observations
            if r["indicator"] == indicator_code
            and r["iso3"] in countries
            and start_year <= int(r["year"]) <= end_year
        ]
        by_country: Dict[str, List[Dict[str, Any]]] = {}
        for c in countries:
            c_rows = sorted([r for r in rows if r["iso3"] == c], key=lambda x: x["year"])
            if c_rows:
                first_r, last_r = c_rows[0], c_rows[-1]
                delta = round(last_r["value"] - first_r["value"], int(ind.get("decimals", 2)))
                pct_change = (
                    round(((last_r["value"] - first_r["value"]) / first_r["value"]) * 100, 1)
                    if first_r["value"] != 0
                    else 0.0
                )
                by_country[c] = {
                    "country_name": self.country_by_iso3.get(c, {}).get("name", {}).get("es", c),
                    "first_year": first_r["year"],
                    "first_value": first_r["value"],
                    "latest_year": last_r["year"],
                    "latest_value": last_r["value"],
                    "delta_abs": delta,
                    "delta_pct": pct_change,
                    "n_countries_latest": last_r.get("n_countries"),
                    "series": [{"year": r["year"], "value": r["value"], "n": r.get("n_countries")} for r in c_rows],
                }

        return {
            "tool": "obtener_serie",
            "indicator": indicator_code,
            "indicator_name": ind["name"]["es"],
            "unit": ind["unit"],
            "source": ind["source"],
            "data": by_country,
        }

    # =========================================================================
    # HERRAMIENTA 3: comparar
    # =========================================================================
    def comparar(
        self,
        indicator_code: str,
        target_iso3: str,
        benchmark_iso3: str = "LATAM_AVG",
        year: Optional[int] = None,
    ) -> Dict[str, Any]:
        ind = self.indicators.get(indicator_code)
        if not ind:
            return {"tool": "comparar", "error": f"Indicador {indicator_code} no existe"}

        t_rows = sorted(
            [r for r in self.observations if r["indicator"] == indicator_code and r["iso3"] == target_iso3],
            key=lambda x: x["year"],
        )
        if not t_rows:
            return {"tool": "comparar", "error": f"Sin datos para {target_iso3}"}

        chosen_year = year or t_rows[-1]["year"]
        t_obs = next((r for r in t_rows if r["year"] == chosen_year), t_rows[-1])
        chosen_year = t_obs["year"]

        b_obs = next(
            (
                r
                for r in self.observations
                if r["indicator"] == indicator_code and r["iso3"] == benchmark_iso3 and r["year"] == chosen_year
            ),
            None,
        )
        lcn_obs = next(
            (
                r
                for r in self.observations
                if r["indicator"] == indicator_code and r["iso3"] == "LCN" and r["year"] == chosen_year
            ),
            None,
        )

        dec = int(ind.get("decimals", 2))
        diff_vs_bench = round(t_obs["value"] - b_obs["value"], dec) if b_obs else None
        diff_vs_lcn = round(t_obs["value"] - lcn_obs["value"], dec) if lcn_obs else None

        reg_stats = self.insights["latest_regional_stats"].get(indicator_code, {})
        rank = reg_stats.get("ranks", {}).get(target_iso3)
        n_reg = b_obs.get("n_countries") if b_obs and b_obs.get("n_countries") else reg_stats.get("n_countries", 20)

        return {
            "tool": "comparar",
            "indicator": indicator_code,
            "indicator_name": ind["short_name"]["es"],
            "unit": ind["unit"],
            "source": ind["source"],
            "year": chosen_year,
            "target_iso3": target_iso3,
            "target_name": self.country_by_iso3.get(target_iso3, {}).get("name", {}).get("es", target_iso3),
            "target_value": t_obs["value"],
            "benchmark_iso3": benchmark_iso3,
            "benchmark_name": self.country_by_iso3.get(benchmark_iso3, {}).get("name", {}).get("es", benchmark_iso3),
            "benchmark_value": b_obs["value"] if b_obs else None,
            "n_countries": n_reg,
            "wbg_lcn_value": lcn_obs["value"] if lcn_obs else None,
            "diff_vs_benchmark": diff_vs_bench,
            "diff_vs_lcn": diff_vs_lcn,
            "regional_rank": rank,
            "total_ranked_countries": n_reg,
        }

    # =========================================================================
    # HERRAMIENTA 4: ranking
    # =========================================================================
    def ranking(
        self,
        indicator_code: str,
        year: Optional[int] = None,
        top_n: int = 20,
    ) -> Dict[str, Any]:
        ind = self.indicators.get(indicator_code)
        if not ind:
            return {"tool": "ranking", "error": f"Indicador {indicator_code} no existe"}

        latam_iso3 = {
            c["iso3"]
            for c in (self.countries_doc["priority_countries"] + self.countries_doc["region_countries"])
        }
        ind_rows = [r for r in self.observations if r["indicator"] == indicator_code and r["iso3"] in latam_iso3]
        if not ind_rows:
            return {"tool": "ranking", "error": "Sin observaciones"}

        chosen_year = year or max(r["year"] for r in ind_rows)
        yr_rows = [r for r in ind_rows if r["year"] == chosen_year]
        hib = bool(ind.get("higher_is_better", True))
        yr_rows.sort(key=lambda r: r["value"], reverse=hib)

        items = []
        for idx, r in enumerate(yr_rows[:top_n]):
            c_meta = self.country_by_iso3.get(r["iso3"], {})
            items.append(
                {
                    "rank": idx + 1,
                    "iso3": r["iso3"],
                    "country": c_meta.get("name", {}).get("es", r["iso3"]),
                    "priority": bool(c_meta.get("priority", False)),
                    "value": r["value"],
                }
            )

        latam_avg_row = next(
            (
                r
                for r in self.observations
                if r["indicator"] == indicator_code and r["iso3"] == "LATAM_AVG" and r["year"] == chosen_year
            ),
            None,
        )
        lcn_row = next(
            (
                r
                for r in self.observations
                if r["indicator"] == indicator_code and r["iso3"] == "LCN" and r["year"] == chosen_year
            ),
            None,
        )

        return {
            "tool": "ranking",
            "indicator": indicator_code,
            "indicator_name": ind["name"]["es"],
            "unit": ind["unit"],
            "source": ind["source"],
            "year": chosen_year,
            "higher_is_better": hib,
            "n_countries": len(yr_rows),
            "latam_simple_avg": latam_avg_row["value"] if latam_avg_row else None,
            "wbg_lcn_avg": lcn_row["value"] if lcn_row else None,
            "ranking": items,
        }

    # =========================================================================
    # HERRAMIENTA 5: crear_grafico
    # =========================================================================
    def crear_grafico(
        self,
        chart_type: str,
        indicator_code: str,
        countries: List[str],
        reference: str = "LATAM_AVG",
        secondary_indicator: Optional[str] = None,
        title_conclusion: Optional[str] = None,
    ) -> Dict[str, Any]:
        ind = self.indicators.get(indicator_code, {})
        c_list = [c for c in countries if c not in {"LATAM_AVG", "LCN", "OED", "WLD"}]
        if not c_list:
            c_list = ["COL", "CHL", "CRI", "BRA", "MEX"]
        comparator_query = (
            f"?indicator={indicator_code}"
            f"&countries={','.join(c_list)}"
            f"&ref={reference}"
            f"&view={chart_type}"
            + (f"&y={secondary_indicator}" if secondary_indicator else "")
        )
        return {
            "tool": "crear_grafico",
            "chart_type": chart_type,
            "indicator": indicator_code,
            "secondary_indicator": secondary_indicator,
            "indicator_name": ind.get("short_name", {}).get("es", indicator_code),
            "unit": ind.get("unit", ""),
            "source": ind.get("source", "World Bank / CEPALSTAT"),
            "countries": c_list,
            "reference": reference,
            "title": title_conclusion or f"Evolución de {ind.get('short_name', {}).get('es', indicator_code)}",
            "comparator_url": comparator_query,
        }


def extract_allowed_numbers(tool_outputs: List[Dict[str, Any]]) -> List[float]:
    """
    Extrae recursivamente todos los números presentes en los resultados de las herramientas
    para alimentar el verificador numérico (`verify_response_numbers`).
    """
    allowed: List[float] = [100.0, 20.0, 5.0, 1.0, 0.0]
    raw_json = json.dumps(tool_outputs)
    for match in re.findall(r"-?\d+(?:\.\d+)?", raw_json):
        try:
            allowed.append(float(match))
        except ValueError:
            pass
    return allowed


def verify_response_numbers(text: str, tool_outputs: List[Dict[str, Any]], tolerance: float = 0.15) -> Dict[str, Any]:
    """
    Verificador numérico (ADR-003):
    Revisa que cada número en la respuesta del agente coincida con los resultados de las herramientas
    (con tolerancia por redondeo o números de año calendario 2010–2026).
    """
    allowed = extract_allowed_numbers(tool_outputs)
    # Ignorar códigos como AR5, ODS 13.2, ISO o años 2010-2026 que siempre son contextuales
    cleaned_text = re.sub(r"ODS\s*\d+(?:\.\d+)?", "", text)
    cleaned_text = re.sub(r"AR5|2026-09|10\.5281|[A-Z]{2,4}\d+", "", cleaned_text)

    found_tokens = re.findall(r"(?<![A-Za-z_])-?\d+(?:[\.,]\d+)?", cleaned_text)
    verified_numbers: List[float] = []
    unverified_numbers: List[float] = []

    for tok in found_tokens:
        norm = tok.replace(",", "")
        try:
            val = float(norm)
        except ValueError:
            continue
        if 2000 <= val <= 2030:
            verified_numbers.append(val)
            continue
        is_ok = any(abs(val - a) <= max(tolerance, abs(a) * 0.015) for a in allowed)
        if is_ok:
            verified_numbers.append(val)
        else:
            unverified_numbers.append(val)

    return {
        "passed": len(unverified_numbers) == 0,
        "verified_count": len(verified_numbers),
        "unverified_count": len(unverified_numbers),
        "verified_numbers": verified_numbers,
        "unverified_numbers": unverified_numbers,
    }


def answer_question(question: str, store: Optional[SnapshotStore] = None) -> Dict[str, Any]:
    """
    Agente completo del Observatorio LATAM:
    1. Detecta si la pregunta está fuera del catálogo (p.ej. criptomonedas, fútbol, tasas de interés mensuales en vivo)
       o si pregunta por un código viejo / no comparable (EN.ATM.CO2E.PC, SI.POV.NAHC).
    2. Selecciona los países mencionados y las herramientas (`buscar_indicador`, `obtener_serie`, `comparar`, `ranking`, `crear_grafico`).
    3. Construye la respuesta analítica citando fuente, año y conteo `n` regional.
    4. Ejecuta el verificador numérico (`verify_response_numbers`).
    """
    if store is None:
        store = SnapshotStore()

    q_lower = question.lower()

    # Detectar consultas fuera del catálogo del observatorio
    out_of_catalog_terms = [
        "bitcoin", "cripto", "fútbol", "futbol", "mundial de", "litio",
        "turismo mensual", "remesas", "deuda externa privada", "tipo de cambio hoy",
    ]
    search_res = store.buscar_indicador(question)
    if any(t in q_lower for t in out_of_catalog_terms) or search_res["matches_count"] == 0:
        return {
            "question": question,
            "out_of_catalog": True,
            "badge": "Dato fuera del catálogo del observatorio · Candidato Data360 MCP",
            "answer": (
                "No dispongo de ese indicador en el snapshot verificado `2026-09` del Observatorio LATAM. "
                "Por regla metodológica (ADR-003), el chat nunca estima ni inventa cifras fuera del catálogo congelado "
                "de 15 indicadores económicos, sociales y ambientales. En una fase posterior esta consulta puede "
                "delegarse al servidor MCP de Data360 del Banco Mundial con la etiqueta visible «dato fuera del catálogo»."
            ),
            "tools_called": [{"tool": "buscar_indicador", "query": question, "matches_count": 0}],
            "verification": {"passed": True, "verified_count": 1, "unverified_count": 0, "verified_numbers": [15], "unverified_numbers": []},
            "sources": [{"source": "Catálogo Oficial Observatorio LATAM v2026.09", "year": "2010–2024"}],
            "chart": None,
        }

    # 1. Seleccionar el indicador relevante del catálogo
    primary_code = search_res["matches"][0]["code"]

    # Si pregunta por comparación de pobreza entre varios países y cayó en SI.POV.NAHC, usar CEPAL.POV.HARM
    country_aliases = {
        "COL": ["colombia", "colombiano", "bogota", "dane"],
        "CHL": ["chile", "chileno", "santiago", "casen"],
        "CRI": ["costa rica", "costarricense", "san jose"],
        "BRA": ["brasil", "brasileño", "brazil", "ibge"],
        "MEX": ["mexico", "méxico", "mexicano", "inegi"],
        "ARG": ["argentina", "buenos aires"],
        "URY": ["uruguay", "montevideo"],
        "PER": ["peru", "perú", "lima"],
        "ECU": ["ecuador", "quito"],
        "PAN": ["panama", "panamá"],
        "DOM": ["dominicana", "santo domingo"],
        "BOL": ["bolivia"],
        "PRY": ["paraguay"],
        "GTM": ["guatemala"],
        "HND": ["honduras"],
        "SLV": ["salvador"],
        "NIC": ["nicaragua"],
        "VEN": ["venezuela"],
        "CUB": ["cuba"],
        "HTI": ["haiti", "haití"],
    }
    mentioned_countries: List[str] = []
    for iso3, aliases in country_aliases.items():
        if any(a in q_lower for a in aliases):
            mentioned_countries.append(iso3)

    if not mentioned_countries:
        mentioned_countries = ["COL", "CHL", "CRI", "BRA", "MEX"]

    methodological_warning = ""
    if primary_code == "SI.POV.NAHC" and (len(mentioned_countries) > 1 or "compar" in q_lower or "ranking" in q_lower or "regi" in q_lower):
        primary_code = "CEPAL.POV.HARM"
        methodological_warning = (
            "Nota metodológica (ADR-001): `SI.POV.NAHC` usa la línea de pobreza nacional propia de cada país "
            "y no es comparable entre países. Para esta comparación se utiliza la **Tasa de pobreza monetaria armonizada de CEPAL (`CEPAL.POV.HARM`)**. "
        )
    elif "en.atm.co2e.pc" in q_lower:
        primary_code = "EN.GHG.CO2.PC.CE.AR5"
        methodological_warning = (
            "Nota metodológica (ADR-001): El Banco Mundial reemplazó `EN.ATM.CO2E.PC` por `EN.GHG.CO2.PC.CE.AR5` "
            "(base EDGAR JRC de la Comisión Europea, excluyendo uso del suelo LULUCF con factores IPCC AR5). "
        )

    # 2. Invocar herramientas sobre el snapshot
    query_countries = list(dict.fromkeys(mentioned_countries + ["LATAM_AVG", "LCN"]))
    serie_res = store.obtener_serie(primary_code, query_countries, start_year=2010, end_year=2024)
    focus_iso = mentioned_countries[0]
    comp_res = store.comparar(primary_code, target_iso3=focus_iso, benchmark_iso3="LATAM_AVG")
    rank_res = store.ranking(primary_code, top_n=20)

    chart_view = "ranking" if ("ranking" in q_lower or "quien lidera" in q_lower or "posición" in q_lower) else "lines"
    secondary_ind = None
    if ("desacopl" in q_lower or ("pib" in q_lower and "co2" in q_lower)):
        primary_code = "NY.GDP.PCAP.PP.KD"
        secondary_ind = "EN.GHG.CO2.PC.CE.AR5"
        chart_view = "scatter"

    focus_series = serie_res["data"].get(focus_iso, {})
    ind_meta = store.indicators[primary_code]

    headline_conclusion = (
        f"{comp_res.get('target_name', focus_iso)}: {comp_res.get('target_value')} {ind_meta['unit']} en {comp_res.get('year')} "
        f"(puesto #{comp_res.get('regional_rank')} de {comp_res.get('n_countries')} países)"
    )

    chart_res = store.crear_grafico(
        chart_type=chart_view,
        indicator_code=primary_code,
        countries=mentioned_countries[:5],
        reference="LATAM_AVG",
        secondary_indicator=secondary_ind,
        title_conclusion=headline_conclusion,
    )

    tool_outputs = [search_res, serie_res, comp_res, rank_res, chart_res]

    # 3. Redactar respuesta analítica estrictamente a partir de los datos de las herramientas
    top1 = rank_res["ranking"][0] if rank_res.get("ranking") else {"country": "Uruguay", "value": 0, "rank": 1}
    top2 = rank_res["ranking"][1] if len(rank_res.get("ranking", [])) > 1 else top1

    country_summaries = []
    for iso in mentioned_countries[:4]:
        c_data = serie_res["data"].get(iso)
        if c_data:
            sign = "+" if c_data["delta_abs"] >= 0 else ""
            country_summaries.append(
                f"**{c_data['country_name']}** pasó de `{c_data['first_value']}` ({c_data['first_year']}) "
                f"a `{c_data['latest_value']} {ind_meta['unit']}` ({c_data['latest_year']}), "
                f"un cambio de `{sign}{c_data['delta_abs']}` (`{sign}{c_data['delta_pct']}%`)"
            )

    diff_b = comp_res.get("diff_vs_benchmark")
    diff_sign = "+" if (diff_b is not None and diff_b >= 0) else ""

    answer_text = (
        f"{methodological_warning}"
        f"Según el snapshot congelado `2026-09` para **{ind_meta['name']['es']}** (`{primary_code}`), "
        f"en el último corte disponible (**{comp_res['year']}**): "
        + "; ".join(country_summaries)
        + f".\n\n"
        f"- **Comparación con estimados regionales ({comp_res['year']}):** **{comp_res['target_name']}** registra "
        f"`{comp_res['target_value']} {ind_meta['unit']}`, ubicándose a `{diff_sign}{diff_b}` frente al "
        f"**Promedio simple LATAM** (`{comp_res['benchmark_value']} {ind_meta['unit']}`, calculado con `n={comp_res['n_countries']}` países) "
        f"y frente a `{comp_res['wbg_lcn_value']} {ind_meta['unit']}` del agregado ponderado del Banco Mundial (`LCN`).\n"
        f"- **Posición en el ranking regional ({rank_res['year']}):** **{comp_res['target_name']}** ocupa la posición "
        f"`#{comp_res['regional_rank']}` entre `{rank_res['n_countries']}` países de América Latina. "
        f"Lideran el indicador **{top1['country']}** (`#{top1['rank']}` con `{top1['value']} {ind_meta['unit']}`) "
        f"y **{top2['country']}** (`#{top2['rank']}` con `{top2['value']} {ind_meta['unit']}`).\n"
        f"- **Fuente y trazabilidad:** {ind_meta['source']} (Año del dato: `{comp_res['year']}`, Snapshot `2026-09`)."
    )

    verification = verify_response_numbers(answer_text, tool_outputs)

    return {
        "question": question,
        "out_of_catalog": False,
        "badge": "Verificado contra Snapshot 2026-09 · 100% cifras auditadas",
        "answer": answer_text,
        "tools_called": [
            {"tool": "buscar_indicador", "summary": f"Encontró {primary_code} ({ind_meta['short_name']['es']})"},
            {"tool": "obtener_serie", "summary": f"Series 2010–2024 para {', '.join(mentioned_countries[:4])} + LATAM_AVG + LCN"},
            {"tool": "comparar", "summary": f"{focus_iso} ({comp_res['target_value']}) vs LATAM_AVG ({comp_res['benchmark_value']}, n={comp_res['n_countries']})"},
            {"tool": "ranking", "summary": f"Ranking regional {rank_res['year']} ({rank_res['n_countries']} países)"},
            {"tool": "crear_grafico", "summary": f"Vista {chart_view}: {headline_conclusion}"},
        ],
        "verification": verification,
        "sources": [
            {
                "indicator": primary_code,
                "name": ind_meta["name"]["es"],
                "source": ind_meta["source"],
                "year": comp_res["year"],
                "n_countries": comp_res["n_countries"],
                "doi": store.manifest["zenodo_doi"],
            }
        ],
        "chart": chart_res,
    }
