/**
 * Herramientas oficiales del Agente sobre el Snapshot (`data/public/`).
 * Cumple ADR-003:
 * 1. `buscar_indicador`: busca en catalog.json con alias de palabras clave y códigos reemplazados (ADR-001)
 * 2. `obtener_serie`: devuelve la serie temporal exacta del snapshot, deltas absolutos y porcentuales
 * 3. `comparar`: compara un país contra `LATAM_AVG` (con conteo `n`) y contra el agregado del Banco Mundial (`LCN`)
 * 4. `ranking`: ordena los 20 países de la región según `higher_is_better`
 * 5. `crear_grafico`: devuelve la especificación visual y la URL de estado para el botón "Abrir en el comparador"
 */

import fs from "fs";
import path from "path";

export interface Observation {
  indicator: string;
  iso3: string;
  year: number;
  value: number;
  source: string;
  downloaded_at: string;
  is_estimate: boolean;
  n_countries?: number;
}

function resolvePublicDataDir(): string {
  const candidates = [
    path.resolve(__dirname, "../../../data/public"),
    path.resolve(__dirname, "..", "..", "..", "data", "public"),
    path.resolve(process.cwd(), "data", "public"),
    path.resolve(process.cwd(), "..", "data", "public"),
    path.resolve(process.cwd(), "web", "..", "data", "public"),
  ];
  for (const dir of candidates) {
    try {
      if (fs.existsSync(path.join(dir, "catalog.json"))) {
        return dir;
      }
    } catch {
      // Continue to next candidate
    }
  }
  return path.resolve(process.cwd(), "data", "public");
}

export const PUBLIC_DATA_DIR = resolvePublicDataDir();

let cachedSnapshotData: {
  catalog: any;
  countries: any;
  observations: Observation[];
  manifest: any;
  insights: any;
} | null = null;

export function loadSnapshotData() {
  if (cachedSnapshotData) {
    return cachedSnapshotData;
  }
  const catalog = JSON.parse(fs.readFileSync(path.join(PUBLIC_DATA_DIR, "catalog.json"), "utf-8"));
  const countries = JSON.parse(fs.readFileSync(path.join(PUBLIC_DATA_DIR, "countries.json"), "utf-8"));
  const observations: Observation[] = JSON.parse(
    fs.readFileSync(path.join(PUBLIC_DATA_DIR, "all_observations.json"), "utf-8")
  );
  const manifest = JSON.parse(fs.readFileSync(path.join(PUBLIC_DATA_DIR, "manifest.json"), "utf-8"));
  let insights: any = {};
  const insightsPath = path.join(PUBLIC_DATA_DIR, "insights.json");
  if (fs.existsSync(insightsPath)) {
    try {
      insights = JSON.parse(fs.readFileSync(insightsPath, "utf-8"));
    } catch {
      insights = {};
    }
  }
  cachedSnapshotData = { catalog, countries, observations, manifest, insights };
  return cachedSnapshotData;
}

export function buscarIndicador(query: string) {
  const { catalog } = loadSnapshotData();
  const q = query.toLowerCase();

  const keywordAliases: Record<string, string[]> = {
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
  };

  const tokens = q.match(/[a-záéíóúñ0-9]+/g) || [];
  const scored: Array<{ score: number; ind: any }> = [];

  for (const ind of catalog.indicators) {
    let score = 0;
    const codeLower = ind.code.toLowerCase();
    if (q.includes(codeLower)) score += 10;
    if (ind.replaces_code && q.includes(ind.replaces_code.toLowerCase())) score += 9;

    const nameEs = (ind.name?.es || "").toLowerCase();
    const shortEs = (ind.short_name?.es || "").toLowerCase();

    for (const tok of tokens) {
      if (tok.length >= 3 && (nameEs.includes(tok) || shortEs.includes(tok))) {
        score += 3;
      }
    }

    const aliases = keywordAliases[ind.code] || [];
    for (const kw of aliases) {
      if (q.includes(kw)) score += 5;
    }

    if (score > 0) {
      scored.push({ score, ind });
    }
  }

  scored.sort((a, b) => b.score - a.score);
  const topMatches = scored.slice(0, 3).map((item) => ({
    code: item.ind.code,
    replaces_code: item.ind.replaces_code ?? null,
    name: item.ind.name?.es ?? item.ind.code,
    short_name: item.ind.short_name?.es ?? item.ind.code,
    unit: item.ind.unit ?? "",
    source: item.ind.source ?? "",
    higher_is_better: Boolean(item.ind.higher_is_better),
    profile_only: Boolean(item.ind.profile_only),
    methodology_note: (item.ind.methodology_note ?? "").trim(),
    raw: item.ind,
  }));

  return {
    tool: "buscar_indicador",
    query,
    matches_count: topMatches.length,
    matches: topMatches,
  };
}

export function obtenerSerie(
  indicatorCode: string,
  countries: string[],
  startYear = 2010,
  endYear = 2024
) {
  const { catalog, countries: countriesDoc, observations } = loadSnapshotData();
  const ind = catalog.indicators.find((i: any) => i.code === indicatorCode);
  const rows = observations.filter(
    (r) =>
      r.indicator === indicatorCode &&
      countries.includes(r.iso3) &&
      r.year >= startYear &&
      r.year <= endYear
  );

  const allCountriesList = [
    ...(countriesDoc.priority_countries || []),
    ...(countriesDoc.region_countries || []),
    ...(countriesDoc.aggregates || []),
  ];
  const countryByIso3 = new Map<string, any>(allCountriesList.map((c: any) => [c.iso3, c]));

  const byCountry: Record<string, any> = {};
  const decimals = ind?.decimals ?? 2;

  for (const c of countries) {
    const cRows = rows.filter((r) => r.iso3 === c).sort((a, b) => a.year - b.year);
    if (cRows.length > 0) {
      const firstR = cRows[0];
      const lastR = cRows[cRows.length - 1];
      const delta = Number((lastR.value - firstR.value).toFixed(decimals));
      const pctChange =
        firstR.value !== 0
          ? Number((((lastR.value - firstR.value) / firstR.value) * 100).toFixed(1))
          : 0.0;

      const meta = countryByIso3.get(c);
      byCountry[c] = {
        country_name: meta?.name?.es ?? c,
        first_year: firstR.year,
        first_value: firstR.value,
        latest_year: lastR.year,
        latest_value: lastR.value,
        delta_abs: delta,
        delta_pct: pctChange,
        n_countries_latest: lastR.n_countries ?? null,
        series: cRows.map((r) => ({ year: r.year, value: r.value, n: r.n_countries ?? null })),
      };
    }
  }

  return {
    tool: "obtener_serie",
    indicator: indicatorCode,
    indicator_name: ind?.name?.es ?? indicatorCode,
    unit: ind?.unit ?? "",
    source: ind?.source ?? "",
    data: byCountry,
    observations: rows,
  };
}

export function compararConPromedio(
  indicatorCode: string,
  targetIso3: string,
  benchmarkIso3 = "LATAM_AVG",
  year?: number
) {
  const { catalog, countries: countriesDoc, observations, insights } = loadSnapshotData();
  const ind = catalog.indicators.find((i: any) => i.code === indicatorCode);

  const tRows = observations
    .filter((r) => r.indicator === indicatorCode && r.iso3 === targetIso3)
    .sort((a, b) => a.year - b.year);

  if (tRows.length === 0) {
    return {
      tool: "comparar",
      error: `Sin datos para ${targetIso3}`,
      indicator: indicatorCode,
      targetIso3,
    };
  }

  const chosenYear = year ?? tRows[tRows.length - 1].year;
  const targetObs = tRows.find((r) => r.year === chosenYear) ?? tRows[tRows.length - 1];
  const actualYear = targetObs.year;

  const benchObs = observations.find(
    (r) => r.indicator === indicatorCode && r.iso3 === benchmarkIso3 && r.year === actualYear
  );
  const lcnObs = observations.find(
    (r) => r.indicator === indicatorCode && r.iso3 === "LCN" && r.year === actualYear
  );

  const allCountriesList = [
    ...(countriesDoc.priority_countries || []),
    ...(countriesDoc.region_countries || []),
    ...(countriesDoc.aggregates || []),
  ];
  const countryByIso3 = new Map<string, any>(allCountriesList.map((c: any) => [c.iso3, c]));

  const decimals = ind?.decimals ?? 2;
  const diffVsBench =
    targetObs && benchObs ? Number((targetObs.value - benchObs.value).toFixed(decimals)) : null;
  const diffVsLcn =
    targetObs && lcnObs ? Number((targetObs.value - lcnObs.value).toFixed(decimals)) : null;

  const regStats = insights?.latest_regional_stats?.[indicatorCode] ?? {};
  const rank = regStats?.ranks?.[targetIso3] ?? null;
  const nReg = benchObs?.n_countries ?? regStats?.n_countries ?? 20;

  const targetName = countryByIso3.get(targetIso3)?.name?.es ?? targetIso3;
  const benchmarkName = countryByIso3.get(benchmarkIso3)?.name?.es ?? benchmarkIso3;

  return {
    tool: "comparar",
    indicator: indicatorCode,
    indicator_name: ind?.short_name?.es ?? ind?.name?.es ?? indicatorCode,
    unit: ind?.unit ?? "",
    source: ind?.source ?? "",
    year: actualYear,
    target_iso3: targetIso3,
    target_name: targetName,
    target_value: targetObs?.value ?? null,
    benchmark_iso3: benchmarkIso3,
    benchmark_name: benchmarkName,
    benchmark_value: benchObs?.value ?? null,
    n_countries: nReg,
    wbg_lcn_value: lcnObs?.value ?? null,
    diff_vs_benchmark: diffVsBench,
    diff_vs_lcn: diffVsLcn,
    regional_rank: rank,
    total_ranked_countries: nReg,
    // CamelCase aliases
    targetIso3,
    targetValue: targetObs?.value ?? null,
    benchmarkIso3,
    benchmarkValue: benchObs?.value ?? null,
    nCountries: nReg,
    wbgLcnValue: lcnObs?.value ?? null,
    diffVsBenchmark: diffVsBench,
    diffVsLcn: diffVsLcn,
  };
}

export function obtenerRanking(indicatorCode: string, year?: number, topN = 20) {
  const { catalog, countries: countriesDoc, observations } = loadSnapshotData();
  const ind = catalog.indicators.find((i: any) => i.code === indicatorCode);

  const allCountriesList = [
    ...(countriesDoc.priority_countries || []),
    ...(countriesDoc.region_countries || []),
  ];
  const latamIso3 = new Set(allCountriesList.map((c: any) => c.iso3));
  const countryByIso3 = new Map<string, any>(
    [...allCountriesList, ...(countriesDoc.aggregates || [])].map((c: any) => [c.iso3, c])
  );

  const indRows = observations.filter(
    (r) => r.indicator === indicatorCode && latamIso3.has(r.iso3)
  );

  if (indRows.length === 0) {
    return {
      tool: "ranking",
      error: "Sin observaciones",
      indicator: indicatorCode,
      ranking: [],
    };
  }

  const chosenYear = year ?? Math.max(...indRows.map((r) => r.year));
  const hib = Boolean(ind?.higher_is_better);
  const yrRows = indRows.filter((r) => r.year === chosenYear);
  yrRows.sort((a, b) => (hib ? b.value - a.value : a.value - b.value));

  const items = yrRows.slice(0, topN).map((r, idx) => {
    const cMeta = countryByIso3.get(r.iso3);
    return {
      rank: idx + 1,
      iso3: r.iso3,
      country: cMeta?.name?.es ?? r.iso3,
      priority: Boolean(cMeta?.priority),
      value: r.value,
    };
  });

  const latamAvgRow = observations.find(
    (r) => r.indicator === indicatorCode && r.iso3 === "LATAM_AVG" && r.year === chosenYear
  );
  const lcnRow = observations.find(
    (r) => r.indicator === indicatorCode && r.iso3 === "LCN" && r.year === chosenYear
  );

  return {
    tool: "ranking",
    indicator: indicatorCode,
    indicator_name: ind?.name?.es ?? indicatorCode,
    unit: ind?.unit ?? "",
    source: ind?.source ?? "",
    year: chosenYear,
    higher_is_better: hib,
    higherIsBetter: hib,
    n_countries: yrRows.length,
    nCountries: yrRows.length,
    latam_simple_avg: latamAvgRow?.value ?? null,
    wbg_lcn_avg: lcnRow?.value ?? null,
    ranking: items,
  };
}

export function crearGraficoSpec(params: {
  chartType?: "lines" | "ranking" | "scatter" | "table";
  chart_type?: "lines" | "ranking" | "scatter" | "table";
  indicatorCode?: string;
  indicator?: string;
  countries: string[];
  reference?: string;
  secondaryIndicator?: string | null;
  secondary_indicator?: string | null;
  titleConclusion?: string;
  title?: string;
}) {
  const chartType = params.chart_type ?? params.chartType ?? "lines";
  const indicatorCode = params.indicator ?? params.indicatorCode ?? "";
  const secondaryIndicator = params.secondary_indicator ?? params.secondaryIndicator ?? null;
  const title = params.title ?? params.titleConclusion ?? "";
  const reference = params.reference ?? "LATAM_AVG";

  const { catalog } = loadSnapshotData();
  const ind = catalog.indicators.find((i: any) => i.code === indicatorCode);

  const cList = params.countries.filter(
    (c) => !["LATAM_AVG", "LCN", "OED", "WLD"].includes(c)
  );
  const finalCountries = cList.length > 0 ? cList : ["COL", "CHL", "CRI", "BRA", "MEX"];

  const query = new URLSearchParams({
    indicator: indicatorCode,
    countries: finalCountries.join(","),
    ref: reference,
    view: chartType,
  });
  if (secondaryIndicator) {
    query.set("y", secondaryIndicator);
  }

  const compUrl = `?${query.toString()}`;

  return {
    tool: "crear_grafico",
    chart_type: chartType,
    indicator: indicatorCode,
    secondary_indicator: secondaryIndicator,
    indicator_name: ind?.short_name?.es ?? ind?.name?.es ?? indicatorCode,
    unit: ind?.unit ?? "",
    source: ind?.source ?? "World Bank / CEPALSTAT",
    countries: finalCountries,
    reference,
    title: title || `Evolución de ${ind?.short_name?.es ?? indicatorCode}`,
    comparator_url: compUrl,
    // CamelCase compatibility
    chartType,
    indicatorCode,
    secondaryIndicator,
    titleConclusion: title,
  };
}
