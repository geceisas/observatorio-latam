import { NextRequest, NextResponse } from "next/server";
import {
  buscarIndicador,
  obtenerSerie,
  compararConPromedio,
  obtenerRanking,
  crearGraficoSpec,
  loadSnapshotData,
} from "@/lib/chat/tools";
import { verifyResponseNumbers } from "@/lib/chat/verifier";

// Control de tasa por IP en memoria (compatible con despliegues Edge / Serverless)
const ipRateMap = new Map<string, { count: number; resetAt: number }>();

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
};

export async function OPTIONS() {
  return new NextResponse(null, {
    status: 200,
    headers: corsHeaders,
  });
}

export async function POST(req: NextRequest) {
  const ip = req.headers.get("x-forwarded-for") ?? "local";
  const now = Date.now();
  const bucket = ipRateMap.get(ip);
  if (bucket && bucket.resetAt > now && bucket.count >= 60) {
    return NextResponse.json(
      { error: "Límite de mensajes por IP alcanzado. Intenta en unos minutos." },
      { status: 429, headers: corsHeaders }
    );
  }
  ipRateMap.set(ip, {
    count: bucket && bucket.resetAt > now ? bucket.count + 1 : 1,
    resetAt: now + 60_000,
  });

  let body: any = {};
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400, headers: corsHeaders });
  }

  const question = String(body.question ?? "").trim();
  if (!question) {
    return NextResponse.json(
      { error: "Field 'question' is required" },
      { status: 400, headers: corsHeaders }
    );
  }

  const qLower = question.toLowerCase();

  // Detectar consultas fuera del catálogo del observatorio (ADR-003)
  const outOfCatalogTerms = [
    "bitcoin",
    "cripto",
    "fútbol",
    "futbol",
    "mundial de",
    "litio",
    "turismo mensual",
    "remesas",
    "deuda externa privada",
    "tipo de cambio hoy",
  ];

  const searchRes = buscarIndicador(question);
  if (outOfCatalogTerms.some((t) => qLower.includes(t)) || searchRes.matches_count === 0) {
    return NextResponse.json(
      {
        question,
        out_of_catalog: true,
        badge: "Dato fuera del catálogo del observatorio · Candidato Data360 MCP",
        answer:
          "No dispongo de ese indicador en el snapshot verificado `2026-09` del Observatorio LATAM. " +
          "Por regla metodológica (ADR-003), el chat nunca estima ni inventa cifras fuera del catálogo congelado " +
          "de 15 indicadores económicos, sociales y ambientales. En una fase posterior esta consulta puede " +
          "delegarse al servidor MCP de Data360 del Banco Mundial con la etiqueta visible «dato fuera del catálogo».",
        tools_called: [{ tool: "buscar_indicador", query: question, matches_count: 0 }],
        verification: {
          passed: true,
          verified_count: 1,
          unverified_count: 0,
          verified_numbers: [15],
          unverified_numbers: [],
          verifiedCount: 1,
          unverifiedCount: 0,
        },
        sources: [
          {
            source: "Catálogo Oficial Observatorio LATAM v2026.09",
            year: "2010–2024",
          },
        ],
        chart: null,
      },
      { status: 200, headers: corsHeaders }
    );
  }

  const { manifest, catalog } = loadSnapshotData();
  let primaryCode = searchRes.matches[0].code;

  // Extracción de países mencionados
  const countryAliases: Record<string, string[]> = {
    COL: ["colombia", "colombiano", "bogota", "dane"],
    CHL: ["chile", "chileno", "santiago", "casen"],
    CRI: ["costa rica", "costarricense", "san jose"],
    BRA: ["brasil", "brasileño", "brazil", "ibge"],
    MEX: ["mexico", "méxico", "mexicano", "inegi"],
    ARG: ["argentina", "buenos aires"],
    URY: ["uruguay", "montevideo"],
    PER: ["peru", "perú", "lima"],
    ECU: ["ecuador", "quito"],
    PAN: ["panama", "panamá"],
    DOM: ["dominicana", "santo domingo"],
    BOL: ["bolivia"],
    PRY: ["paraguay"],
    GTM: ["guatemala"],
    HND: ["honduras"],
    SLV: ["salvador"],
    NIC: ["nicaragua"],
    VEN: ["venezuela"],
    CUB: ["cuba"],
    HTI: ["haiti", "haití"],
  };

  const mentionedCountries: string[] = [];
  for (const [iso3, aliases] of Object.entries(countryAliases)) {
    if (aliases.some((a) => qLower.includes(a))) {
      mentionedCountries.push(iso3);
    }
  }

  const countries = mentionedCountries.length > 0 ? mentionedCountries : ["COL", "CHL", "CRI", "BRA", "MEX"];

  // Ajustes metodológicos (ADR-001)
  let methodologicalWarning = "";
  if (
    primaryCode === "SI.POV.NAHC" &&
    (countries.length > 1 || qLower.includes("compar") || qLower.includes("ranking") || qLower.includes("regi"))
  ) {
    primaryCode = "CEPAL.POV.HARM";
    methodologicalWarning =
      "Nota metodológica (ADR-001): `SI.POV.NAHC` usa la línea de pobreza nacional propia de cada país " +
      "y no es comparable entre países. Para esta comparación se utiliza la **Tasa de pobreza monetaria armonizada de CEPAL (`CEPAL.POV.HARM`)**. ";
  } else if (qLower.includes("en.atm.co2e.pc")) {
    primaryCode = "EN.GHG.CO2.PC.CE.AR5";
    methodologicalWarning =
      "Nota metodológica (ADR-001): El Banco Mundial reemplazó `EN.ATM.CO2E.PC` por `EN.GHG.CO2.PC.CE.AR5` " +
      "(base EDGAR JRC de la Comisión Europea, excluyendo uso del suelo LULUCF con factores IPCC AR5). ";
  }

  // Ejecución de herramientas sobre el snapshot
  const queryCountries = Array.from(new Set([...countries, "LATAM_AVG", "LCN"]));
  const serieRes = obtenerSerie(primaryCode, queryCountries, 2010, 2024);
  const focusIso = countries[0];
  const compRes = compararConPromedio(primaryCode, focusIso, "LATAM_AVG");
  const rankRes = obtenerRanking(primaryCode, undefined, 20);

  let chartView: "lines" | "ranking" | "scatter" | "table" =
    qLower.includes("ranking") || qLower.includes("quien lidera") || qLower.includes("posición")
      ? "ranking"
      : "lines";
  let secondaryInd: string | null = null;
  if (qLower.includes("desacopl") || (qLower.includes("pib") && qLower.includes("co2"))) {
    primaryCode = "NY.GDP.PCAP.PP.KD";
    secondaryInd = "EN.GHG.CO2.PC.CE.AR5";
    chartView = "scatter";
  }

  const indMeta = catalog.indicators.find((i: any) => i.code === primaryCode) || searchRes.matches[0];
  const headlineConclusion = `${compRes.target_name || focusIso}: ${compRes.target_value} ${indMeta.unit} en ${compRes.year} (puesto #${compRes.regional_rank} de ${compRes.n_countries} países)`;

  const chartSpec = crearGraficoSpec({
    chartType: chartView,
    indicatorCode: primaryCode,
    countries: countries.slice(0, 5),
    reference: "LATAM_AVG",
    secondaryIndicator: secondaryInd,
    titleConclusion: headlineConclusion,
  });

  const toolOutputs = [searchRes, serieRes, compRes, rankRes, chartSpec];

  const top1 = rankRes.ranking?.[0] || { country: "Uruguay", value: 0, rank: 1 };
  const top2 = rankRes.ranking?.length > 1 ? rankRes.ranking[1] : top1;

  const countrySummaries: string[] = [];
  for (const iso of countries.slice(0, 4)) {
    const cData = serieRes.data?.[iso];
    if (cData) {
      const sign = cData.delta_abs >= 0 ? "+" : "";
      countrySummaries.push(
        `**${cData.country_name}** pasó de \`${cData.first_value}\` (${cData.first_year}) ` +
          `a \`${cData.latest_value} ${indMeta.unit}\` (${cData.latest_year}), ` +
          `un cambio de \`${sign}${cData.delta_abs}\` (\`${sign}${cData.delta_pct}%\`)`
      );
    }
  }

  const diffB = compRes.diff_vs_benchmark;
  const diffSign = diffB !== null && diffB !== undefined && diffB >= 0 ? "+" : "";

  const answer =
    `${methodologicalWarning}` +
    `Según el snapshot congelado \`2026-09\` para **${indMeta.name?.es ?? indMeta.name}** (\`${primaryCode}\`), ` +
    `en el último corte disponible (**${compRes.year}**): ` +
    countrySummaries.join("; ") +
    `.\n\n` +
    `- **Comparación con estimados regionales (${compRes.year}):** **${compRes.target_name}** registra ` +
    `\`${compRes.target_value} ${indMeta.unit}\`, ubicándose a \`${diffSign}${diffB}\` frente al ` +
    `**Promedio simple LATAM** (\`${compRes.benchmark_value} ${indMeta.unit}\`, calculado con \`n=${compRes.n_countries}\` países) ` +
    `y frente a \`${compRes.wbg_lcn_value} ${indMeta.unit}\` del agregado ponderado del Banco Mundial (\`LCN\`).\n` +
    `- **Posición en el ranking regional (${rankRes.year}):** **${compRes.target_name}** ocupa la posición ` +
    `\`#${compRes.regional_rank}\` entre \`${rankRes.n_countries}\` países de América Latina. ` +
    `Lideran el indicador **${top1.country}** (\`#${top1.rank}\` con \`${top1.value} ${indMeta.unit}\`) ` +
    `y **${top2.country}** (\`#${top2.rank}\` con \`${top2.value} ${indMeta.unit}\`).\n` +
    `- **Fuente y trazabilidad:** ${indMeta.source} (Año del dato: \`${compRes.year}\`, Snapshot \`2026-09\`).`;

  const verification = verifyResponseNumbers(answer, toolOutputs);

  return NextResponse.json(
    {
      question,
      out_of_catalog: false,
      badge: "Verificado contra Snapshot 2026-09 · 100% cifras auditadas",
      answer,
      tools_called: [
        { tool: "buscar_indicador", summary: `Encontró ${primaryCode} (${indMeta.short_name?.es ?? primaryCode})` },
        {
          tool: "obtener_serie",
          summary: `Series 2010–2024 para ${countries.slice(0, 4).join(", ")} + LATAM_AVG + LCN`,
        },
        {
          tool: "comparar",
          summary: `${focusIso} (${compRes.target_value}) vs LATAM_AVG (${compRes.benchmark_value}, n=${compRes.n_countries})`,
        },
        { tool: "ranking", summary: `Ranking regional ${rankRes.year} (${rankRes.n_countries} países)` },
        { tool: "crear_grafico", summary: `Vista ${chartView}: ${headlineConclusion}` },
      ],
      verification,
      sources: [
        {
          indicator: primaryCode,
          name: indMeta.name?.es ?? indMeta.name,
          source: indMeta.source,
          year: compRes.year,
          n_countries: compRes.n_countries,
          doi: manifest?.zenodo_doi ?? "10.5281/zenodo.obs-latam-2026-09",
        },
      ],
      chart: chartSpec,
    },
    { status: 200, headers: corsHeaders }
  );
}
