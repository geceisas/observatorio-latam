"""
Conectores para Fuentes Estadísticas Nacionales (Fase 4 del Observatorio LATAM):
- DANE (Colombia): Gran Encuesta Integrada de Hogares (GEIH) y Pobreza Monetaria
- BCCh / INE (Chile): Base de Datos Estadísticos del Banco Central de Chile y CASEN
- BCCR / INEC (Costa Rica): Indicadores Económicos BCCR y ENAHO
- IBGE (Brasil): SIDRA / PNAD Contínua
- INEGI (México): Banco de Información Económica (BIE) / ENIGH
"""

from typing import Dict, Any

NATIONAL_SOURCES_REGISTRY: Dict[str, Dict[str, Any]] = {
    "COL": {
        "agency": "DANE (Departamento Administrativo Nacional de Estadística)",
        "portal": "https://www.dane.gov.co",
        "survey": "GEIH / Pobreza Monetaria Nacional",
    },
    "CHL": {
        "agency": "BCCh / Ministerio de Desarrollo Social (CASEN)",
        "portal": "https://si3.bcentral.cl",
        "survey": "Encuesta CASEN / Cuentas Nacionales BCCh",
    },
    "CRI": {
        "agency": "BCCR / INEC Costa Rica",
        "portal": "https://gee.bccr.fi.cr",
        "survey": "ENAHO / Indicadores Macroeconómicos BCCR",
    },
    "BRA": {
        "agency": "IBGE (Instituto Brasileiro de Geografia e Estatística)",
        "portal": "https://sidra.ibge.gov.br",
        "survey": "PNAD Contínua",
    },
    "MEX": {
        "agency": "INEGI / CONEVAL",
        "portal": "https://www.inegi.org.mx",
        "survey": "ENIGH / Medición Multidimensional de la Pobreza",
    },
}
