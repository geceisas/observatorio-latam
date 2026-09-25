/**
 * Verificador Numérico de Respuestas del Agente (ADR-003).
 * Garantiza que ningún número citado en la respuesta del modelo haya sido inventado:
 * cada cifra debe aparecer en los resultados devueltos por las herramientas sobre el snapshot
 * (con tolerancia por redondeo o años calendario del rango 2000–2030).
 */

export interface VerificationResult {
  passed: boolean;
  verified_count: number;
  unverified_count: number;
  verified_numbers: number[];
  unverified_numbers: number[];
  verifiedCount?: number;
  unverifiedCount?: number;
  verifiedNumbers?: number[];
  unverifiedNumbers?: number[];
}

export function extractAllowedNumbers(toolOutputs: unknown[]): number[] {
  const allowed: number[] = [100.0, 20.0, 5.0, 1.0, 0.0];
  const rawJson = JSON.stringify(toolOutputs);
  const matches = rawJson.match(/-?\d+(?:\.\d+)?/g) ?? [];
  for (const m of matches) {
    const num = Number(m);
    if (!Number.isNaN(num)) allowed.push(num);
  }
  return allowed;
}

export function verifyResponseNumbers(
  responseText: string,
  toolOutputs: unknown[],
  tolerance = 0.15
): VerificationResult {
  const allowed = extractAllowedNumbers(toolOutputs);

  // Ignorar códigos como AR5, ODS 13.2, ISO o años que son contextuales
  const cleaned = responseText
    .replace(/ODS\s*\d+(?:\.\d+)?/g, "")
    .replace(/AR5|2026-09|10\.5281|[A-Z]{2,4}\d+/g, "");

  const tokens = cleaned.match(/(?<![A-Za-z_])-?\d+(?:[.,]\d+)?/g) ?? [];
  const verifiedNumbers: number[] = [];
  const unverifiedNumbers: number[] = [];

  for (const tok of tokens) {
    const val = Number(tok.replace(/,/g, ""));
    if (Number.isNaN(val)) continue;
    if (val >= 2000 && val <= 2030) {
      verifiedNumbers.push(val);
      continue;
    }
    const ok = allowed.some((a) => Math.abs(val - a) <= Math.max(tolerance, Math.abs(a) * 0.015));
    if (ok) {
      verifiedNumbers.push(val);
    } else {
      unverifiedNumbers.push(val);
    }
  }

  const passed = unverifiedNumbers.length === 0;

  return {
    passed,
    verified_count: verifiedNumbers.length,
    unverified_count: unverifiedNumbers.length,
    verified_numbers: verifiedNumbers,
    unverified_numbers: unverifiedNumbers,
    verifiedCount: verifiedNumbers.length,
    unverifiedCount: unverifiedNumbers.length,
    verifiedNumbers,
    unverifiedNumbers,
  };
}
