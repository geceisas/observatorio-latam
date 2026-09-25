"""
Test Server Manager for Observatorio LATAM E2E Test Suite.
Launches the unified local server (server.py) on an ephemeral port in a background
thread using the standard library, verifying real HTTP 200/400/404/405/CORS responses.
"""

from __future__ import annotations
import json
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from server import create_server


def find_free_port() -> int:
    """Find an available port assigned by the OS."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestServer:
    """Manages an in-process HTTP server instance for E2E integration testing."""

    def __init__(self, host: str = "127.0.0.1", port: Optional[int] = None):
        self.host = host
        self.port = port or find_free_port()
        self.base_url = f"http://{self.host}:{self.port}"
        self._server = None
        self._thread = None
        self._is_running = False

    def start(self, timeout: float = 5.0) -> TestServer:
        """Starts the server in a daemon thread and waits until it is ready."""
        if self._is_running:
            return self

        self._server = create_server(self.host, self.port)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        # Poll readiness
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                req = urllib.request.Request(f"{self.base_url}/")
                with urllib.request.urlopen(req, timeout=1.0) as resp:
                    if resp.status == 200:
                        self._is_running = True
                        return self
            except Exception:
                time.sleep(0.05)

        raise TimeoutError(f"Server at {self.base_url} did not become ready within {timeout}s")

    def stop(self) -> None:
        """Shuts down the server cleanly."""
        if self._server and self._is_running:
            try:
                self._server.shutdown()
                self._server.server_close()
            except Exception:
                pass
            finally:
                self._is_running = False
                if self._thread:
                    self._thread.join(timeout=2.0)

    def __enter__(self) -> TestServer:
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def get(self, path: str, timeout: float = 5.0) -> Tuple[int, Dict[str, str], bytes]:
        """Performs a GET request returning (status_code, headers, body_bytes)."""
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                headers = dict(resp.headers.items())
                body = resp.read()
                return resp.status, headers, body
        except urllib.error.HTTPError as e:
            headers = dict(e.headers.items()) if e.headers else {}
            body = e.read()
            return e.code, headers, body

    def post_json(self, path: str, payload: Any, raw_body: Optional[bytes] = None, timeout: float = 10.0) -> Tuple[int, Dict[str, str], bytes]:
        """Performs a POST request with JSON payload or raw bytes."""
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        if raw_body is not None:
            data = raw_body
        elif payload is not None:
            data = json.dumps(payload).encode("utf-8")
        else:
            data = b""

        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"} if payload is not None else {},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                headers = dict(resp.headers.items())
                body = resp.read()
                return resp.status, headers, body
        except urllib.error.HTTPError as e:
            headers = dict(e.headers.items()) if e.headers else {}
            body = e.read()
            return e.code, headers, body

    def options(self, path: str, timeout: float = 5.0) -> Tuple[int, Dict[str, str], bytes]:
        """Performs an OPTIONS request (CORS preflight)."""
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        req = urllib.request.Request(url, method="OPTIONS")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                headers = dict(resp.headers.items())
                body = resp.read()
                return resp.status, headers, body
        except urllib.error.HTTPError as e:
            headers = dict(e.headers.items()) if e.headers else {}
            body = e.read()
            return e.code, headers, body


_SHARED_SERVER: Optional[TestServer] = None
_SHARED_LOCK = threading.Lock()


def get_shared_server() -> TestServer:
    """Returns a lazily-initialized shared TestServer instance for test suites."""
    global _SHARED_SERVER
    if _SHARED_SERVER is None or not _SHARED_SERVER._is_running:
        with _SHARED_LOCK:
            if _SHARED_SERVER is None or not _SHARED_SERVER._is_running:
                _SHARED_SERVER = TestServer()
                _SHARED_SERVER.start()
    return _SHARED_SERVER


def shutdown_shared_server() -> None:
    """Shuts down the shared server if running."""
    global _SHARED_SERVER
    with _SHARED_LOCK:
        if _SHARED_SERVER is not None:
            _SHARED_SERVER.stop()
            _SHARED_SERVER = None
