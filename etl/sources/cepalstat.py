"""
Cliente de CEPALSTAT API para el ETL del Observatorio LATAM.
Resuelve el problema específico documentado en ADR-001:
"En CEPALSTAT, la respuesta trae los valores con identificadores de dimensión (dim_XXXX)
que hay que cruzar con la lista de miembros para saber a qué año y país corresponde cada dato."
"""

from __future__ import annotations
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional


CEPAL_BASE_URL = "https://api-cepalstat.cepal.org/cepalstat/api/v1/indicator"


def parse_cepalstat_payload(
    indicator_code: str,
    data_payload: Dict[str, Any],
    dimensions_payload: Dict[str, Any],
    cepal_id_to_iso3: Dict[str, str],
    start_year: int = 2010,
    end_year: int = 2025,
) -> List[Dict[str, Any]]:
    """
    Cruza la tabla `data` de CEPALSTAT (que usa IDs internos de miembros como `dim_208`: 216)
    con el árbol de `dimensions` para traducir cada miembro a código ISO3 de país y año calendario.
    """
    downloaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # 1. Construir diccionarios member_id -> iso3 y member_id -> year
    member_to_iso3: Dict[str, str] = {}
    member_to_year: Dict[str, int] = {}

    dims = (dimensions_payload.get("body", {}) or {}).get("dimensions", [])
    for dim in dims:
        dim_name = str(dim.get("name", "")).lower()
        members = dim.get("members", []) or []
        for m in members:
            m_id = str(m.get("id", ""))
            m_name = str(m.get("name", "")).strip()
            # Si coincide con nuestro mapeo cepal_id -> iso3
            if m_id in cepal_id_to_iso3:
                member_to_iso3[m_id] = cepal_id_to_iso3[m_id]
            # Si el nombre del miembro es un año de 4 dígitos
            if m_name.isdigit() and len(m_name) == 4:
                yr = int(m_name)
                if start_year <= yr <= end_year:
                    member_to_year[m_id] = yr
            elif "país" in dim_name or "country" in dim_name:
                # Búsqueda por nombre de país de respaldo
                for cid, iso3 in cepal_id_to_iso3.items():
                    if m_id == cid:
                        member_to_iso3[m_id] = iso3

    # 2. Recorrer los registros de valores y cruzar con los diccionarios de miembros
    records = (data_payload.get("body", {}) or {}).get("data", [])
    observations: List[Dict[str, Any]] = []

    for row in records:
        raw_val = row.get("value")
        if raw_val is None or raw_val == "":
            continue
        try:
            val = float(raw_val)
        except ValueError:
            continue

        found_iso3: Optional[str] = row.get("iso3")
        found_year: Optional[int] = None

        for key, attr_val in row.items():
            if key.startswith("dim_"):
                str_id = str(attr_val)
                if str_id in member_to_iso3:
                    found_iso3 = member_to_iso3[str_id]
                if str_id in member_to_year:
                    found_year = member_to_year[str_id]

        if found_iso3 and found_year is not None:
            observations.append(
                {
                    "indicator": indicator_code,
                    "iso3": found_iso3,
                    "year": found_year,
                    "value": round(val, 2),
                    "source": "CEPALSTAT (Serie armonizada)",
                    "downloaded_at": downloaded_at,
                    "is_estimate": False,
                }
            )

    return observations


def fetch_cepalstat_indicator(
    indicator_code: str,
    cepal_indicator_id: str,
    cepal_id_to_iso3: Dict[str, str],
    start_year: int = 2010,
    end_year: int = 2025,
    timeout: int = 10,
) -> List[Dict[str, Any]]:
    """
    Consulta los endpoints `/dimensions` y `/data` de CEPALSTAT y devuelve observaciones cruzadas.
    """
    dim_url = f"{CEPAL_BASE_URL}/{cepal_indicator_id}/dimensions?lang=es&format=json"
    data_url = f"{CEPAL_BASE_URL}/{cepal_indicator_id}/data?lang=es&format=json"

    try:
        req_dim = urllib.request.Request(dim_url, headers={"Accept": "application/json"})
        req_data = urllib.request.Request(data_url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req_dim, timeout=timeout) as r_dim:
            dim_json = json.loads(r_dim.read().decode("utf-8"))
        with urllib.request.urlopen(req_data, timeout=timeout) as r_data:
            data_json = json.loads(r_data.read().decode("utf-8"))

        return parse_cepalstat_payload(
            indicator_code=indicator_code,
            data_payload=data_json,
            dimensions_payload=dim_json,
            cepal_id_to_iso3=cepal_id_to_iso3,
            start_year=start_year,
            end_year=end_year,
        )
    except Exception:
        return []
