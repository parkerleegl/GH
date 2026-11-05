"""Loopback-only test server; deliberately not a deployment server."""
import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .core import Problem

WEB = Path(__file__).resolve().parent.parent / "web"
STATIC = {"/": ("index.html", "text/html; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8")}


def strict_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Duplicate key")
        out[key] = value
    return out


def make_server(store, port=8765):
    class Handler(BaseHTTPRequestHandler):
        server_version = "GLRoomLocal"
        sys_version = ""

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, *args):
            pass  # No tokens, message bodies, or raw URLs in access logs.

        def send(self, status, payload, content_type="application/json; charset=utf-8"):
            raw = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(raw)

        def boundary(self):
            allowed = {"127.0.0.1:" + str(self.server.server_port), "localhost:" + str(self.server.server_port)}
            host = self.headers.get("Host")
            if host not in allowed or self.headers.get("Origin") not in (None, "http://" + host):
                raise Problem(403, "origin_forbidden", "Origen no permitido.")
            # Local-wide cap, 240 requests per minute. Not an Internet-grade rate limiter.
            now = time.monotonic()
            with self.server.rate_lock:
                while self.server.requests_at and now - self.server.requests_at[0] > 60:
                    self.server.requests_at.popleft()
                if len(self.server.requests_at) >= 240:
                    raise Problem(429, "rate_limit", "Demasiadas solicitudes. Esperá un minuto.")
                self.server.requests_at.append(now)
            auth = self.headers.get("Authorization", "")
            return auth[7:] if auth.startswith("Bearer ") else ""

        def handle_request(self, method):
            try:
                token = self.boundary()
                parsed = urlsplit(self.path)
                route = parsed.path
                if method == "GET" and route in STATIC and not parsed.query:
                    filename, content_type = STATIC[route]
                    return self.send(200, (WEB / filename).read_bytes(), content_type)
                if not route.startswith("/api/"):
                    raise Problem(404, "not_found", "Recurso inexistente.")
                if method == "GET":
                    query = parse_qs(parsed.query, strict_parsing=True) if parsed.query else {}
                    if set(query) - {"after"} or any(len(v) != 1 for v in query.values()):
                        raise Problem(400, "invalid_query", "Consulta inválida.")
                    after = int(query.get("after", ["0"])[0])
                    if after < 0 or after > 9223372036854775807:
                        raise ValueError("Invalid cursor")
                    return self.send(200, store.read(token, route, after))
                if parsed.query or self.headers.get_content_type() != "application/json" or self.headers.get("Transfer-Encoding"):
                    raise Problem(400, "invalid_body", "Usá JSON con Content-Length y sin query string.")
                length = int(self.headers.get("Content-Length", "-1"))
                if not 0 < length <= 32768:
                    raise Problem(413, "body_limit", "El cuerpo debe tener entre 1 y 32768 bytes.")
                data = json.loads(self.rfile.read(length).decode("utf-8"), object_pairs_hook=strict_object,
                                  parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite number")))
                if not isinstance(data, dict):
                    raise ValueError("Expected object")
                return self.send(200, store.mutate(token, route, self.headers.get("Idempotency-Key"), data))
            except Problem as exc:
                self.send(exc.status, {"error": exc.code, "message": exc.message})
            except (ValueError, UnicodeError, OverflowError):
                self.send(400, {"error": "invalid_input", "message": "Datos inválidos."})
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
                pass
            except Exception:
                self.send(500, {"error": "internal_error", "message": "No se pudo completar. Consultá el estado antes de reintentar."})

        def do_GET(self):
            self.handle_request("GET")

        def do_POST(self):
            self.handle_request("POST")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.requests_at = deque()
    server.rate_lock = threading.Lock()
    return server
