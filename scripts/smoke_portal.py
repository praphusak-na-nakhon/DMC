"""Minimal synthetic Graduation portal, bound only to loopback for smoke checks."""
from __future__ import annotations

import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator
from urllib.parse import urlparse


class PortalState:
    def __init__(self) -> None:
        self.post_saves = 0


def _table() -> str:
    rows = []
    for index, first, last in [(1, "สมชาย", "ใจดี"), (2, "สมหญิง", "ดีใจ")]:
        cells = ["", str(index), "", "1", str(1000 + index), "ด.ช.", first, last, "", "", ""]
        rows.append(f'<tr id="tr-{index}">' + "".join(f"<td>{cell}</td>" for cell in cells)
                    + f'<td><select name="students[{index}].studyTypeCode"><option value="">--</option>'
                    + '<option value="317">317</option></select></td></tr>')
    return ('<!doctype html><html><body><form class="form-horizontal form-condensed" method="post" action="/save">'
            + '<table><tbody>' + "".join(rows) + '</tbody></table>'
            + '<button name="action" value="confirm" type="submit">save</button></form></body></html>')


@contextmanager
def synthetic_portal() -> Iterator[tuple[str, PortalState]]:
    state = PortalState()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format: str, *_args: object) -> None:
            pass

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/obec68/auth/login":
                body = "<html><body>Synthetic login ready</body></html>"
            elif path == "/obec68/studentpendingupl/add":
                body = _table()
            else:
                self.send_error(404)
                return
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self) -> None:
            state.post_saves += 1
            self.send_error(405, "Synthetic smoke forbids saving")

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
