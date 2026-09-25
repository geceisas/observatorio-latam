"""
Vercel Serverless Function para `/api/chat` (Observatorio LATAM · ADR-003).
Ejecuta las 5 herramientas oficiales sobre el snapshot congelado (`data/public/`)
y aplica el verificador numérico (`verify_response_numbers`) sin requerir API keys externas.
"""

from __future__ import annotations
import json
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from etl.chat_engine import SnapshotStore, answer_question

_STORE = None


def get_store() -> SnapshotStore:
    global _STORE
    if _STORE is None:
        _STORE = SnapshotStore()
    return _STORE


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status_code: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"ok": True})

    def do_GET(self) -> None:
        store = get_store()
        self._send_json(
            200,
            {
                "status": "ok",
                "service": "Observatorio LATAM Chat API (ADR-003)",
                "snapshot_id": store.manifest.get("snapshot_id", "2026-09"),
                "tools": [
                    "buscar_indicador",
                    "obtener_serie",
                    "comparar",
                    "ranking",
                    "crear_grafico",
                ],
            },
        )

    def do_POST(self) -> None:
        try:
            content_length = int(self.headers.get("Content-Length", 0) or 0)
            raw_body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            data = json.loads(raw_body) if raw_body.strip() else {}
            question = str(data.get("question") or data.get("prompt") or data.get("message") or "").strip()
            if not question:
                self._send_json(400, {"error": "Debe enviar el campo 'question'."})
                return
            result = answer_question(question, store=get_store())
            self._send_json(200, result)
        except Exception as exc:
            self._send_json(500, {"error": str(exc)})
