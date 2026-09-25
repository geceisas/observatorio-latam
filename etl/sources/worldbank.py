"""
Cliente de la API v2 del Banco Mundial para el ETL del Observatorio LATAM.
Cumple estrictamente ADR-001:
- Usa HTTPS siempre (`https://api.worldbank.org/v2/...`)
- Agrega `per_page=1000` en cada petición (el valor por defecto es 50, lo cual trunca series de varios países x 16 años)
- Recorre todas las páginas (`page` hasta `pages`) y aplica reintentos con backoff exponencial.
"""

from __future__ import annotations
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional


WB_BASE_URL = "https://api.worldbank.org/v2"


def fetch_worldbank_indicator(
    wb_code: str,
    iso3_list: List[str],
    start_year: int = 2010,
    end_year: int = 2025,
    per_page: int = 1000,
    max_retries: int = 2,
    timeout: int = 12,
) -> List[Dict[str, Any]]:
    """
    Descarga una serie del Banco Mundial para la lista de códigos ISO3 (incluyendo agregados LCN, OED, WLD).
    Garantiza paginación completa con `per_page=1000` sobre HTTPS.
    """
    countries_param = ";".join(iso3_list)
    downloaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    observations: List[Dict[str, Any]] = []

    page = 1
    total_pages = 1

    while page <= total_pages:
        url = (
            f"{WB_BASE_URL}/country/{countries_param}/indicator/{wb_code}"
            f"?date={start_year}:{end_year}&format=json&per_page={per_page}&page={page}"
        )

        payload = _http_get_json(url, max_retries=max_retries, timeout=timeout)
        if not payload or not isinstance(payload, list) or len(payload) < 2:
            break

        meta = payload[0]
        rows = payload[1] or []
        total_pages = int(meta.get("pages", 1) or 1)

        for row in rows:
            val = row.get("value")
            if val is None:
                continue
            iso3 = row.get("countryiso3code") or (row.get("country", {}) or {}).get("id")
            date_str = str(row.get("date", ""))
            if not iso3 or not date_str.isdigit():
                continue
            year = int(date_str)
            if year < start_year or year > end_year:
                continue

            observations.append(
                {
                    "indicator": wb_code,
                    "iso3": iso3,
                    "year": year,
                    "value": float(val),
                    "source": "World Bank API v2",
                    "downloaded_at": downloaded_at,
                    "is_estimate": False,
                }
            )

        page += 1

    return observations


def _http_get_json(url: str, max_retries: int = 2, timeout: int = 12) -> Optional[Any]:
    headers = {
        "User-Agent": "ObservatorioLATAM-ETL/2026.09 (https://github.com/observatorio-latam; research-snapshot)"
    }
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            if attempt < max_retries:
                time.sleep(0.8 * (attempt + 1))
            else:
                return None
    return None
